"""回測引擎 — 微台指無限加倉 + 週選 PUT 保護策略。

每日流程：
1. 每月定期投入
2. 偵測期貨轉倉（扣除轉倉成本）
3. 若為結算日 → 結算到期 PUT，換倉新 PUT
4. 判斷加倉條件：漲幅門檻 + 趨勢過濾 + 冷卻期 + 回撤暫停
5. Margin Call 檢查
6. Mark-to-market & 記錄每日快照
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import date

from src.config import (
    ADD_COOLDOWN_DAYS,
    ADD_MA_PERIOD,
    ADD_MIN_PRICE_CHANGE_PCT,
    ALLOW_AUTO_INJECTION,
    FUTURES_CODE,
    FUTURES_COMMISSION,
    OPTIONS_CODE,
    FUTURES_MAINTENANCE_RATIO,
    FUTURES_MARGIN_RATIO,
    FUTURES_MULTIPLIER,
    FUTURES_PER_PUT,
    FUTURES_ROLLOVER_COST_POINTS,
    FUTURES_SLIPPAGE_POINTS,
    FUTURES_TAX_RATE,
    INITIAL_CAPITAL,
    OPTIONS_COMMISSION,
    OPTIONS_SPREAD_RATIO,
    OPTIONS_TAX_RATE,
    PAUSE_ADD_DRAWDOWN_PCT,
    POSITION_SIZING_TIERS,
    TARGET_RISK_RATIO,
    TXO_MULTIPLIER,
)
from src.calendar.settlement import (
    current_or_next_settlement,
    get_settlement_dates,
    is_settlement_day,
    next_settlement_date,
)
from src.models import (
    CashFlow,
    FuturesBar,
    FuturesPosition,
    OptionBar,
    PortfolioSnapshot,
    PutPosition,
    Trade,
)
from src.strategy.put_selector import select_put_by_premium
from src.strategy.slippage import apply_futures_slippage, apply_options_spread

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────
# 保證金計算
# ────────────────────────────────────────────


def _dynamic_margin(futures_price: float) -> float:
    """依當前期貨價格動態計算一口原始保證金。"""
    return futures_price * FUTURES_MULTIPLIER * FUTURES_MARGIN_RATIO


def _maintenance_margin_per_lot(futures_price: float) -> float:
    """依當前期貨價格動態計算一口維持保證金。"""
    return futures_price * FUTURES_MULTIPLIER * FUTURES_MAINTENANCE_RATIO


def _margin_required(positions: list[FuturesPosition], current_price: float) -> float:
    """計算當前所有持倉所需原始保證金（動態）。"""
    total_contracts = sum(pos.contracts for pos in positions)
    return total_contracts * _dynamic_margin(current_price)


def _total_maintenance_margin(positions: list[FuturesPosition], current_price: float) -> float:
    """計算當前所有持倉所需維持保證金。"""
    total_contracts = sum(pos.contracts for pos in positions)
    return total_contracts * _maintenance_margin_per_lot(current_price)


# ────────────────────────────────────────────
# 資金控管
# ────────────────────────────────────────────


def _position_sizing_ratio(equity: float) -> float:
    """依權益水位決定可動用保證金比例。"""
    for threshold, ratio in POSITION_SIZING_TIERS:
        if equity >= threshold:
            return ratio
    return 1.0


# ────────────────────────────────────────────
# 回測狀態
# ────────────────────────────────────────────


@dataclass
class BacktestState:
    """回測狀態（mutable，僅限引擎內部使用）。"""

    cash: float
    futures_positions: list[FuturesPosition]
    put_positions: list[PutPosition]
    trades: list[Trade]
    snapshots: list[PortfolioSnapshot]
    total_put_cost: float = 0.0
    total_injected: float = 0.0
    total_monthly: float = 0.0
    prev_close: float | None = None
    futures_per_put: int = FUTURES_PER_PUT
    last_contribution_month: tuple[int, int] | None = None
    allow_auto_injection: bool = ALLOW_AUTO_INJECTION

    # 加倉過濾
    price_history: deque = field(default_factory=lambda: deque(maxlen=50))
    last_add_day_idx: int = -999  # 上次加倉的交易日序號
    trading_day_idx: int = 0  # 當前交易日序號

    # 風控
    peak_equity: float = 0.0

    # XIRR 現金流
    cash_flows: list[CashFlow] = field(default_factory=list)

    # 轉倉偵測
    prev_contract_month: str = ""
    total_rollover_cost: float = 0.0


# ────────────────────────────────────────────
# 加倉條件判斷
# ────────────────────────────────────────────


def _can_add_position(state: BacktestState, current_price: float) -> bool:
    """綜合判斷是否滿足加倉條件。"""
    if state.prev_close is None:
        return False

    # 條件 1：最低漲幅門檻
    pct_change = (current_price - state.prev_close) / state.prev_close
    if pct_change < ADD_MIN_PRICE_CHANGE_PCT:
        return False

    # 條件 2：趨勢過濾（收盤 > N 日均線）
    if len(state.price_history) >= ADD_MA_PERIOD:
        ma = sum(state.price_history) / len(state.price_history)
        if current_price <= ma:
            return False

    # 條件 3：冷卻期
    days_since_last_add = state.trading_day_idx - state.last_add_day_idx
    if days_since_last_add < ADD_COOLDOWN_DAYS:
        return False

    return True


def _is_drawdown_paused(state: BacktestState, equity: float) -> bool:
    """回撤超過門檻時暫停加倉。"""
    if state.peak_equity <= 0:
        return False
    dd = (state.peak_equity - equity) / state.peak_equity
    return dd > PAUSE_ADD_DRAWDOWN_PCT


# ────────────────────────────────────────────
# 損益計算
# ────────────────────────────────────────────


def _futures_unrealized_pnl(positions: list[FuturesPosition], current_price: float) -> float:
    """計算期貨未實現損益。"""
    return sum(
        (current_price - pos.entry_price) * FUTURES_MULTIPLIER * pos.contracts for pos in positions
    )


def _build_put_price_index(
    options_today: list[OptionBar],
) -> dict[tuple[int, date], float]:
    """建立 PUT 行情的快速查詢索引：(strike, expiry) -> 最佳市價。"""
    index: dict[tuple[int, date], float] = {}
    for o in options_today:
        if o.cp != "P":
            continue
        key = (o.strike, o.expiry_date)
        price = o.close if o.close > 0 else o.settle
        existing = index.get(key)
        if existing is None or o.volume > 0:
            index[key] = price
    return index


def _puts_market_value(
    positions: list[PutPosition],
    options_today: list[OptionBar],
    _price_index: dict[tuple[int, date], float] | None = None,
) -> float:
    """計算 PUT 持倉市值。"""
    if _price_index is None:
        _price_index = _build_put_price_index(options_today)

    value = 0.0
    for put in positions:
        price = _price_index.get((put.strike, put.expiry_date), 0.0)
        value += price * TXO_MULTIPLIER * put.contracts
    return value


# ────────────────────────────────────────────
# 主回測迴圈
# ────────────────────────────────────────────


def run_backtest(
    futures_data: dict[date, FuturesBar],
    options_data: dict[date, list[OptionBar]],
    trading_days: list[date],
    start: date,
    end: date,
    initial_capital: float = INITIAL_CAPITAL,
    futures_per_put: int = FUTURES_PER_PUT,
    monthly_contribution: float = 0.0,
    allow_auto_injection: bool = ALLOW_AUTO_INJECTION,
) -> BacktestState:
    """執行回測。

    Args:
        futures_per_put: 幾口期貨配 1 口 PUT（例如 5 = 等值保護）
        monthly_contribution: 每月定期投入金額（0 = 不投入）
        allow_auto_injection: 資金不足時是否自動補入（預設 False）
    """
    state = BacktestState(
        cash=initial_capital,
        futures_positions=[],
        put_positions=[],
        trades=[],
        snapshots=[],
        futures_per_put=futures_per_put,
        peak_equity=initial_capital,
        allow_auto_injection=allow_auto_injection,
    )

    # 記錄初始資金投入
    state.cash_flows.append(CashFlow(date=start, amount=-initial_capital))

    settlement_dates = get_settlement_dates(start, end)

    for day in trading_days:
        if day < start or day > end:
            continue

        futures_bar = futures_data.get(day)
        if futures_bar is None:
            logger.debug("無期貨資料: %s，跳過", day)
            continue

        options_today = options_data.get(day, [])
        current_price = futures_bar.close
        put_index = _build_put_price_index(options_today)

        state.trading_day_idx += 1

        # ── Step 0: 每月定期投入 ──
        if monthly_contribution > 0:
            ym = (day.year, day.month)
            if state.last_contribution_month != ym:
                state.cash += monthly_contribution
                state.total_monthly += monthly_contribution
                state.last_contribution_month = ym
                state.cash_flows.append(CashFlow(date=day, amount=-monthly_contribution))
                logger.info(
                    "每月定期投入: date=%s, amount=%.0f, 累計=%.0f",
                    day,
                    monthly_contribution,
                    state.total_monthly,
                )

        # ── Step 0.5: 偵測期貨轉倉 ──
        _handle_rollover(state, day, futures_bar)

        # ── Step 1: 結算日處理 ──
        if is_settlement_day(day, settlement_dates):
            _handle_settlement(state, day, futures_bar, options_today, settlement_dates)

        # ── Step 2: 判斷加倉（加入漲幅門檻 + 趨勢 + 冷卻期 + 回撤暫停）──
        futures_pnl = _futures_unrealized_pnl(state.futures_positions, current_price)
        puts_value = _puts_market_value(state.put_positions, options_today, put_index)
        equity = state.cash + futures_pnl + puts_value
        state.peak_equity = max(state.peak_equity, equity)

        if _can_add_position(state, current_price):
            if not _is_drawdown_paused(state, equity):
                _try_add_position(
                    state, day, futures_bar, options_today, settlement_dates, put_index
                )
            else:
                logger.debug(
                    "回撤暫停加倉: date=%s, dd=%.1f%%",
                    day,
                    (state.peak_equity - equity) / state.peak_equity * 100,
                )

        # ── Step 3: Margin Call 檢查 ──
        _check_margin_call(state, day, current_price, options_today, put_index)

        # ── Step 4: Mark-to-market & 快照 ──
        futures_pnl = _futures_unrealized_pnl(state.futures_positions, current_price)
        puts_value = _puts_market_value(state.put_positions, options_today, put_index)
        margin_used = _margin_required(state.futures_positions, current_price)
        equity = state.cash + futures_pnl + puts_value
        state.peak_equity = max(state.peak_equity, equity)

        prev_equity = state.snapshots[-1].equity if state.snapshots else initial_capital
        daily_pnl = equity - prev_equity

        snapshot = PortfolioSnapshot(
            trade_date=day,
            equity=equity,
            cash=state.cash,
            margin_used=margin_used,
            futures_unrealized_pnl=futures_pnl,
            puts_market_value=puts_value,
            total_put_cost=state.total_put_cost,
            futures_count=sum(p.contracts for p in state.futures_positions),
            puts_count=sum(p.contracts for p in state.put_positions),
            daily_pnl=daily_pnl,
        )
        state.snapshots.append(snapshot)

        state.prev_close = current_price
        state.price_history.append(current_price)

    # 記錄最終權益作為現金流出（用於 XIRR）
    if state.snapshots:
        state.cash_flows.append(
            CashFlow(date=state.snapshots[-1].trade_date, amount=state.snapshots[-1].equity)
        )

    return state


# ────────────────────────────────────────────
# 轉倉偵測
# ────────────────────────────────────────────


def _handle_rollover(state: BacktestState, day: date, futures_bar: FuturesBar) -> None:
    """偵測期貨合約月份變更，扣除轉倉成本。"""
    cm = futures_bar.contract_month
    if not cm or not state.prev_contract_month:
        state.prev_contract_month = cm
        return

    if cm != state.prev_contract_month:
        total_contracts = sum(p.contracts for p in state.futures_positions)
        if total_contracts > 0:
            cost = FUTURES_ROLLOVER_COST_POINTS * FUTURES_MULTIPLIER * total_contracts
            state.cash -= cost
            state.total_rollover_cost += cost
            logger.info(
                "期貨轉倉: date=%s, %s→%s, contracts=%d, cost=%.0f",
                day,
                state.prev_contract_month,
                cm,
                total_contracts,
                cost,
            )
        state.prev_contract_month = cm


# ────────────────────────────────────────────
# 平倉輔助函式
# ────────────────────────────────────────────


def _close_excess_futures(
    state: BacktestState,
    day: date,
    current_price: float,
    contracts_to_close: int,
    options_today: list[OptionBar] | None = None,
    reason: str = "維持 PUT 保護",
) -> None:
    """平倉多餘的期貨部位（FIFO），同時賣出對應的 PUT。"""
    remaining = contracts_to_close
    closed_positions: list[int] = []

    sell_price = apply_futures_slippage(
        current_price, is_buy=False, slippage_points=FUTURES_SLIPPAGE_POINTS
    )

    for i, pos in enumerate(state.futures_positions):
        if remaining <= 0:
            break

        close_qty = min(pos.contracts, remaining)
        pnl = (sell_price - pos.entry_price) * FUTURES_MULTIPLIER * close_qty
        tax = sell_price * FUTURES_MULTIPLIER * close_qty * FUTURES_TAX_RATE
        commission = FUTURES_COMMISSION * close_qty

        state.cash += pnl - tax - commission

        state.trades.append(
            Trade(
                trade_date=day,
                instrument=FUTURES_CODE,
                action="SELL",
                price=sell_price,
                contracts=close_qty,
                pnl=pnl,
                commission=commission,
                tax=tax,
            )
        )

        logger.info(
            "平倉期貨 (%s): entry=%.0f, exit=%.0f, pnl=%.0f, contracts=%d",
            reason,
            pos.entry_price,
            sell_price,
            pnl,
            close_qty,
        )

        if close_qty >= pos.contracts:
            closed_positions.append(i)
        remaining -= close_qty

    for i in sorted(closed_positions, reverse=True):
        state.futures_positions.pop(i)

    # 同步平倉對應的 PUT（FIFO）
    fpp = state.futures_per_put
    puts_to_close = contracts_to_close // fpp if fpp > 0 else 0
    if puts_to_close > 0 and state.put_positions:
        _close_puts_fifo(state, day, puts_to_close, options_today or [], reason=reason)


def _close_puts_fifo(
    state: BacktestState,
    day: date,
    contracts_to_close: int,
    options_today: list[OptionBar],
    reason: str = "減倉",
    put_index: dict[tuple[int, date], float] | None = None,
) -> None:
    """FIFO 賣出 PUT 部位，實現損益回到 cash。"""
    if put_index is None:
        put_index = _build_put_price_index(options_today)

    remaining = contracts_to_close
    closed_positions: list[int] = []

    for i, put in enumerate(state.put_positions):
        if remaining <= 0:
            break

        close_qty = min(put.contracts, remaining)

        mid_price = put_index.get((put.strike, put.expiry_date), 0.0)
        sell_price = apply_options_spread(
            mid_price, is_buy=False, spread_ratio=OPTIONS_SPREAD_RATIO
        )

        pnl = (sell_price - put.entry_premium) * TXO_MULTIPLIER * close_qty
        tax = sell_price * TXO_MULTIPLIER * close_qty * OPTIONS_TAX_RATE if sell_price > 0 else 0
        commission = OPTIONS_COMMISSION * close_qty

        state.cash += sell_price * TXO_MULTIPLIER * close_qty - tax - commission

        state.trades.append(
            Trade(
                trade_date=day,
                instrument=OPTIONS_CODE,
                action="SELL",
                price=sell_price,
                contracts=close_qty,
                pnl=pnl,
                commission=commission,
                tax=tax,
                strike=put.strike,
                expiry=put.expiry_date,
            )
        )

        logger.info(
            "平倉 PUT (%s): strike=%d, sell=%.1f, pnl=%.0f, contracts=%d",
            reason,
            put.strike,
            sell_price,
            pnl,
            close_qty,
        )

        if close_qty >= put.contracts:
            closed_positions.append(i)
        remaining -= close_qty

    for i in sorted(closed_positions, reverse=True):
        state.put_positions.pop(i)


# ────────────────────────────────────────────
# Margin Call 檢查
# ────────────────────────────────────────────


def _check_margin_call(
    state: BacktestState,
    day: date,
    current_price: float,
    options_today: list[OptionBar],
    put_index: dict[tuple[int, date], float] | None = None,
) -> None:
    """檢查維持保證金，不足時批量平倉。"""
    total_contracts = sum(p.contracts for p in state.futures_positions)
    if total_contracts <= 0:
        return

    futures_pnl = _futures_unrealized_pnl(state.futures_positions, current_price)
    puts_value = _puts_market_value(state.put_positions, options_today, put_index)
    equity = state.cash + futures_pnl + puts_value

    maintenance = _total_maintenance_margin(state.futures_positions, current_price)

    if equity >= maintenance:
        return

    logger.warning(
        "Margin Call! equity=%.0f < maintenance=%.0f, date=%s, contracts=%d",
        equity,
        maintenance,
        day,
        total_contracts,
    )

    margin_per_lot = _dynamic_margin(current_price)

    if margin_per_lot > 0:
        max_affordable = int(equity / margin_per_lot)
        contracts_to_close = max(total_contracts - max_affordable, 1)
        contracts_to_close = min(contracts_to_close, total_contracts)
    else:
        contracts_to_close = total_contracts

    _close_excess_futures(
        state,
        day,
        current_price,
        contracts_to_close,
        options_today=options_today,
        reason="margin call",
    )

    # 驗證：如果仍不夠，全部平倉
    remaining_contracts = sum(p.contracts for p in state.futures_positions)
    if remaining_contracts > 0:
        futures_pnl = _futures_unrealized_pnl(state.futures_positions, current_price)
        puts_value = _puts_market_value(state.put_positions, options_today, put_index)
        equity = state.cash + futures_pnl + puts_value
        initial_margin = _margin_required(state.futures_positions, current_price)

        if equity < initial_margin:
            _close_excess_futures(
                state,
                day,
                current_price,
                remaining_contracts,
                options_today=options_today,
                reason="margin call (二次)",
            )

    remaining = sum(p.contracts for p in state.futures_positions)
    logger.info("Margin call 完成: date=%s, 剩餘期貨=%d口", day, remaining)

    # 全部平倉後重置 peak_equity，避免回撤暫停死鎖
    if remaining == 0:
        puts_value = _puts_market_value(state.put_positions, options_today, put_index)
        new_equity = state.cash + puts_value  # 無期貨 → 未實現損益為 0
        logger.info(
            "追繳清倉完畢，重置 peak_equity: %.0f → %.0f",
            state.peak_equity,
            new_equity,
        )
        state.peak_equity = new_equity


# ────────────────────────────────────────────
# 結算日處理
# ────────────────────────────────────────────


def _handle_settlement(
    state: BacktestState,
    day: date,
    futures_bar: FuturesBar,
    options_today: list[OptionBar],
    settlement_dates: list[date],
) -> None:
    """處理結算日：結算到期 PUT，換倉到下一期。"""
    settled_puts: list[PutPosition] = []
    remaining_puts: list[PutPosition] = []

    for put in state.put_positions:
        if put.expiry_date <= day:
            settled_puts.append(put)
        else:
            remaining_puts.append(put)

    for put in settled_puts:
        settle_price = 0.0
        matching = [
            o
            for o in options_today
            if o.strike == put.strike and o.expiry_date == put.expiry_date and o.cp == "P"
        ]
        if matching:
            settle_price = max(m.settle for m in matching)

        pnl = (settle_price - put.entry_premium) * TXO_MULTIPLIER * put.contracts
        tax = (
            settle_price * TXO_MULTIPLIER * put.contracts * OPTIONS_TAX_RATE
            if settle_price > 0
            else 0
        )

        state.cash += settle_price * TXO_MULTIPLIER * put.contracts
        state.cash -= tax

        state.trades.append(
            Trade(
                trade_date=day,
                instrument=OPTIONS_CODE,
                action="SETTLE",
                price=settle_price,
                contracts=put.contracts,
                pnl=pnl,
                tax=tax,
                strike=put.strike,
                expiry=put.expiry_date,
            )
        )

    state.put_positions = remaining_puts

    # 為現有期貨部位換倉新 PUT
    fpp = state.futures_per_put
    total_futures = sum(p.contracts for p in state.futures_positions)
    existing_puts = sum(p.contracts for p in state.put_positions)
    puts_needed = _puts_needed(total_futures, fpp) - existing_puts

    if puts_needed <= 0:
        return

    # 嘗試多個結算日
    put_bar = None
    next_expiry = None
    candidate_date = day
    for _attempt in range(3):
        candidate_date = next_settlement_date(candidate_date, settlement_dates)
        if candidate_date is None:
            break
        put_bar = select_put_by_premium(futures_bar.close, options_today, candidate_date)
        if put_bar is not None:
            next_expiry = candidate_date
            break
        logger.warning(
            "結算換倉找不到合適 PUT: date=%s, expiry=%s，嘗試下一個結算日",
            day,
            candidate_date,
        )

    if put_bar is None or next_expiry is None:
        logger.warning(
            "結算換倉: 嘗試多個結算日仍找不到 PUT，平倉無保護期貨: date=%s",
            day,
        )
        unprotected = total_futures - existing_puts * fpp
        if unprotected > 0 and state.futures_positions:
            _close_excess_futures(
                state,
                day,
                futures_bar.close,
                unprotected,
                options_today=options_today,
                reason="無 PUT 可換倉",
            )
        return

    premium = put_bar.close if put_bar.close > 0 else put_bar.settle
    if premium <= 0:
        premium = 1.0

    # 套用選擇權買賣價差（買入時付 ask）
    premium_with_spread = apply_options_spread(
        premium, is_buy=True, spread_ratio=OPTIONS_SPREAD_RATIO
    )

    cost_per_put = premium_with_spread * TXO_MULTIPLIER + OPTIONS_COMMISSION

    # 強制保護：若現金不足以買齊所有 PUT，逐口平倉期貨直到能負擔
    while puts_needed > 0 and state.cash < cost_per_put * puts_needed:
        total_futures = sum(p.contracts for p in state.futures_positions)
        if total_futures <= 0:
            break

        logger.info(
            "現金不足換倉 PUT，平倉期貨維持全保護: date=%s, cash=%.0f, need=%.0f",
            day,
            state.cash,
            cost_per_put * puts_needed,
        )
        close_count = min(fpp, total_futures)
        _close_excess_futures(
            state,
            day,
            futures_bar.close,
            close_count,
            options_today=options_today,
            reason="現金不足買 PUT",
        )

        total_futures = sum(p.contracts for p in state.futures_positions)
        existing_puts = sum(p.contracts for p in state.put_positions)
        puts_needed = _puts_needed(total_futures, fpp) - existing_puts

    if puts_needed <= 0:
        return

    total_cost = premium_with_spread * TXO_MULTIPLIER * puts_needed
    commission = OPTIONS_COMMISSION * puts_needed

    state.cash -= total_cost + commission
    state.total_put_cost += total_cost + commission

    new_put = PutPosition(
        entry_date=day,
        strike=put_bar.strike,
        expiry_date=next_expiry,
        entry_premium=premium_with_spread,
        contracts=puts_needed,
    )
    state.put_positions.append(new_put)

    state.trades.append(
        Trade(
            trade_date=day,
            instrument=OPTIONS_CODE,
            action="ROLL",
            price=premium_with_spread,
            contracts=puts_needed,
            commission=commission,
            strike=put_bar.strike,
            expiry=next_expiry,
        )
    )


# ────────────────────────────────────────────
# 加倉邏輯
# ────────────────────────────────────────────


def _puts_needed(total_futures: int, futures_per_put: int) -> int:
    """計算 N 口期貨需要幾口 PUT（無條件進位）。"""
    if futures_per_put <= 0 or total_futures <= 0:
        return 0
    return (total_futures + futures_per_put - 1) // futures_per_put


def _try_add_position(
    state: BacktestState,
    day: date,
    futures_bar: FuturesBar,
    options_today: list[OptionBar],
    settlement_dates: list[date],
    put_index: dict[tuple[int, date], float] | None = None,
) -> None:
    """嘗試連續加倉直到風險指標接近 TARGET_RISK_RATIO。

    每組 = N 口微台指 + 1 口 PUT。
    雙重限制：POSITION_SIZING_TIERS 資金比例 + 風險指標目標。
    若 allow_auto_injection=False 且資金不足，停止加倉。
    """
    fpp = state.futures_per_put
    current_price = futures_bar.close

    # 套用滑價
    entry_price = apply_futures_slippage(
        current_price, is_buy=True, slippage_points=FUTURES_SLIPPAGE_POINTS
    )
    margin_per_lot = _dynamic_margin(current_price)
    margin_per_group = margin_per_lot * fpp

    # 找 PUT（只做一次）
    target_expiry = current_or_next_settlement(day, settlement_dates)
    if target_expiry is None:
        return

    if target_expiry == day:
        target_expiry = next_settlement_date(day, settlement_dates)
        if target_expiry is None:
            return

    put_bar = select_put_by_premium(current_price, options_today, target_expiry)
    if put_bar is None:
        candidate_date = target_expiry
        for _attempt in range(2):
            candidate_date = next_settlement_date(candidate_date, settlement_dates)
            if candidate_date is None:
                break
            put_bar = select_put_by_premium(current_price, options_today, candidate_date)
            if put_bar is not None:
                target_expiry = candidate_date
                break

    if put_bar is None:
        logger.debug("無法找到合適 PUT，放棄加倉: date=%s", day)
        return

    put_premium = put_bar.close if put_bar.close > 0 else put_bar.settle
    if put_premium <= 0:
        put_premium = 1.0

    # 套用選擇權買賣價差
    put_premium_with_spread = apply_options_spread(
        put_premium, is_buy=True, spread_ratio=OPTIONS_SPREAD_RATIO
    )
    put_cost = put_premium_with_spread * TXO_MULTIPLIER + OPTIONS_COMMISSION

    # 每組交易成本（手續費 + PUT 權利金，不含保證金）
    tx_cost = FUTURES_COMMISSION * fpp + put_cost

    # ── 連續加倉迴圈 ──
    if put_index is None:
        put_index = _build_put_price_index(options_today)
    max_groups = 500  # 安全上限，防止配置錯誤導致無限迴圈
    groups_added = 0
    while groups_added < max_groups:
        # 計算當前風險狀態
        margin = _margin_required(state.futures_positions, current_price)
        futures_pnl = _futures_unrealized_pnl(state.futures_positions, current_price)
        puts_value = _puts_market_value(state.put_positions, options_today, put_index)
        equity = state.cash + futures_pnl + puts_value

        # 資金控管：依水位限制可用資金
        sizing_ratio = _position_sizing_ratio(equity)
        available = state.cash * sizing_ratio

        # 檢查 1: 可用資金夠付交易成本
        if available < tx_cost:
            if state.allow_auto_injection:
                shortfall = tx_cost - available
                if shortfall > 0:
                    state.cash += shortfall
                    state.total_injected += shortfall
                    state.cash_flows.append(CashFlow(date=day, amount=-shortfall))
                    logger.info(
                        "補入資金: date=%s, amount=%.0f, 累計補入=%.0f",
                        day,
                        shortfall,
                        state.total_injected,
                    )
            else:
                break

        # 檢查 2: 預估加一組後的風險指標
        new_margin = margin + margin_per_group
        new_equity = equity - tx_cost
        projected_ratio = new_equity / new_margin if new_margin > 0 else float("inf")

        if projected_ratio < TARGET_RISK_RATIO:
            break

        # ── 加一組：N 口期貨 ──
        state.cash -= FUTURES_COMMISSION * fpp
        new_futures = FuturesPosition(
            entry_date=day,
            entry_price=entry_price,
            contracts=fpp,
        )
        state.futures_positions.append(new_futures)

        state.trades.append(
            Trade(
                trade_date=day,
                instrument=FUTURES_CODE,
                action="BUY",
                price=entry_price,
                contracts=fpp,
                commission=FUTURES_COMMISSION * fpp,
            )
        )

        # ── 加一組：1 口 PUT ──
        state.cash -= put_cost
        state.total_put_cost += put_cost

        new_put = PutPosition(
            entry_date=day,
            strike=put_bar.strike,
            expiry_date=target_expiry,
            entry_premium=put_premium_with_spread,
            contracts=1,
        )
        state.put_positions.append(new_put)

        state.trades.append(
            Trade(
                trade_date=day,
                instrument=OPTIONS_CODE,
                action="BUY",
                price=put_premium_with_spread,
                contracts=1,
                commission=OPTIONS_COMMISSION,
                strike=put_bar.strike,
                expiry=target_expiry,
            )
        )

        groups_added += 1

        logger.debug(
            "加倉 #%d: %s@%.0f x%d + PUT strike=%d@%.1f, expiry=%s (risk=%.1f%%, sizing=%.0f%%)",
            groups_added,
            FUTURES_CODE,
            entry_price,
            fpp,
            put_bar.strike,
            put_premium_with_spread,
            target_expiry,
            projected_ratio * 100,
            sizing_ratio * 100,
        )

    # 記錄加倉時間（冷卻期用）
    if groups_added > 0:
        state.last_add_day_idx = state.trading_day_idx
        logger.info(
            "加倉完成: date=%s, groups=%d, 新增期貨=%d口",
            day,
            groups_added,
            groups_added * fpp,
        )

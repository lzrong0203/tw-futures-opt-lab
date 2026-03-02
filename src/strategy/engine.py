"""回測引擎 — 微台指無限加倉 + 週選 PUT 保護策略。

每日流程：
1. 載入當日行情
2. Mark-to-market 所有持倉
3. 若為結算日 → 結算到期 PUT，換倉新 PUT
4. 判斷加倉條件：上漲 + 保證金足夠（含動態資金控管）
5. Margin Call 檢查
6. 記錄每日快照
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from src.config import (
    FUTURES_CODE,
    FUTURES_COMMISSION,
    FUTURES_MAINTENANCE_RATIO,
    FUTURES_MARGIN_RATIO,
    FUTURES_MULTIPLIER,
    FUTURES_PER_PUT,
    FUTURES_TAX_RATE,
    INITIAL_CAPITAL,
    OPTIONS_COMMISSION,
    OPTIONS_TAX_RATE,
    POSITION_SIZING_TIERS,
    TXO_MULTIPLIER,
)
from src.calendar.settlement import (
    current_or_next_settlement,
    get_settlement_dates,
    is_settlement_day,
    next_settlement_date,
)
from src.models import (
    FuturesBar,
    FuturesPosition,
    OptionBar,
    PortfolioSnapshot,
    PutPosition,
    Trade,
)
from src.strategy.put_selector import select_put_by_premium

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────
# 保證金計算
# ────────────────────────────────────────────

def _dynamic_margin(futures_price: float) -> float:
    """依當前期貨價格動態計算一口原始保證金。

    保證金 ≈ 指數 × 合約乘數 × 保證金比例
    例: 22000 × 10 × 8.5% ≈ 18,700
    """
    return futures_price * FUTURES_MULTIPLIER * FUTURES_MARGIN_RATIO


def _maintenance_margin_per_lot(futures_price: float) -> float:
    """依當前期貨價格動態計算一口維持保證金。

    維持保證金 ≈ 指數 × 合約乘數 × 維持保證金比例
    例: 22000 × 10 × 6.5% ≈ 14,300
    """
    return futures_price * FUTURES_MULTIPLIER * FUTURES_MAINTENANCE_RATIO


def _margin_required(positions: list[FuturesPosition], current_price: float) -> float:
    """計算當前所有持倉所需原始保證金（動態）。"""
    total_contracts = sum(pos.contracts for pos in positions)
    return total_contracts * _dynamic_margin(current_price)


def _total_maintenance_margin(
    positions: list[FuturesPosition], current_price: float
) -> float:
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
    total_injected: float = 0.0  # 累計補入資金（資金不足時自動補入）
    total_monthly: float = 0.0  # 累計每月定期投入
    prev_close: float | None = None
    futures_per_put: int = FUTURES_PER_PUT  # N 口期貨對 1 口 PUT
    last_contribution_month: tuple[int, int] | None = None  # (year, month) 避免同月重複


# ────────────────────────────────────────────
# 損益計算
# ────────────────────────────────────────────

def _futures_unrealized_pnl(
    positions: list[FuturesPosition], current_price: float
) -> float:
    """計算期貨未實現損益。"""
    return sum(
        (current_price - pos.entry_price) * FUTURES_MULTIPLIER * pos.contracts
        for pos in positions
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
) -> BacktestState:
    """執行回測。

    Args:
        futures_per_put: 幾口期貨配 1 口 PUT（例如 3 = 每 3 口微台配 1 口 PUT）
        monthly_contribution: 每月定期投入金額（0 = 不投入）
    """
    state = BacktestState(
        cash=initial_capital,
        futures_positions=[],
        put_positions=[],
        trades=[],
        snapshots=[],
        futures_per_put=futures_per_put,
    )

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

        # ── Step 0: 每月定期投入 ──
        if monthly_contribution > 0:
            ym = (day.year, day.month)
            if state.last_contribution_month != ym:
                state.cash += monthly_contribution
                state.total_monthly += monthly_contribution
                state.last_contribution_month = ym
                logger.info(
                    "每月定期投入: date=%s, amount=%.0f, 累計=%.0f",
                    day, monthly_contribution, state.total_monthly,
                )

        # ── Step 1: 結算日處理 ──
        if is_settlement_day(day, settlement_dates):
            _handle_settlement(state, day, futures_bar, options_today, settlement_dates)

        # ── Step 2: 判斷加倉 ──
        if state.prev_close is not None and current_price > state.prev_close:
            _try_add_position(state, day, futures_bar, options_today, settlement_dates)

        # ── Step 3: Margin Call 檢查 ──
        _check_margin_call(state, day, current_price, options_today, put_index)

        # ── Step 4: Mark-to-market & 快照 ──
        futures_pnl = _futures_unrealized_pnl(state.futures_positions, current_price)
        puts_value = _puts_market_value(state.put_positions, options_today, put_index)
        margin_used = _margin_required(state.futures_positions, current_price)

        equity = state.cash + futures_pnl + puts_value

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

    return state


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

    for i, pos in enumerate(state.futures_positions):
        if remaining <= 0:
            break

        close_qty = min(pos.contracts, remaining)
        pnl = (current_price - pos.entry_price) * FUTURES_MULTIPLIER * close_qty
        tax = current_price * FUTURES_MULTIPLIER * close_qty * FUTURES_TAX_RATE
        commission = FUTURES_COMMISSION * close_qty

        state.cash += pnl - tax - commission

        state.trades.append(
            Trade(
                trade_date=day,
                instrument=FUTURES_CODE,
                action="SELL",
                price=current_price,
                contracts=close_qty,
                pnl=pnl,
                commission=commission,
                tax=tax,
            )
        )

        logger.info(
            "平倉期貨 (%s): entry=%.0f, exit=%.0f, pnl=%.0f, contracts=%d",
            reason, pos.entry_price, current_price, pnl, close_qty,
        )

        if close_qty >= pos.contracts:
            closed_positions.append(i)
        remaining -= close_qty

    for i in sorted(closed_positions, reverse=True):
        state.futures_positions.pop(i)

    # 同步平倉對應的 PUT（FIFO）
    # 每 futures_per_put 口期貨對應 1 口 PUT
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

        sell_price = put_index.get((put.strike, put.expiry_date), 0.0)

        pnl = (sell_price - put.entry_premium) * TXO_MULTIPLIER * close_qty
        tax = (
            sell_price * TXO_MULTIPLIER * close_qty * OPTIONS_TAX_RATE
            if sell_price > 0
            else 0
        )
        commission = OPTIONS_COMMISSION * close_qty

        state.cash += sell_price * TXO_MULTIPLIER * close_qty - tax - commission

        state.trades.append(
            Trade(
                trade_date=day,
                instrument="TXO_PUT",
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
            reason, put.strike, sell_price, pnl, close_qty,
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
    """檢查維持保證金，不足時批量平倉（模擬券商追繳機制）。

    權益 < 維持保證金 → 計算需平倉口數，一次批量平倉
    平倉直到剩餘持倉的「原始保證金」<= 權益
    """
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
        equity, maintenance, day, total_contracts,
    )

    # 估算需平倉口數：二分搜尋找到最少需平倉口數使得 equity >= initial_margin
    # 每平 1 口：釋放保證金（已在 cash 中），實現 PnL = (current - entry) * multiplier
    # 簡化估算：每口釋放的保證金 ≈ initial_margin_per_lot
    margin_per_lot = _dynamic_margin(current_price)
    initial_margin = _margin_required(state.futures_positions, current_price)

    # 需要滿足：equity >= (total_contracts - close_n) * margin_per_lot
    # 由於平倉會改變 equity（實現 PnL + 交易成本），先估算需關閉口數
    # 保守估計：假設平倉不增加 equity（虧損情況），只減少 margin 需求
    # close_n >= total_contracts - equity / margin_per_lot
    if margin_per_lot > 0:
        max_affordable = int(equity / margin_per_lot)
        contracts_to_close = max(total_contracts - max_affordable, 1)
        # 上限不超過全部
        contracts_to_close = min(contracts_to_close, total_contracts)
    else:
        contracts_to_close = total_contracts

    _close_excess_futures(
        state, day, current_price, contracts_to_close,
        options_today=options_today,
        reason="margin call",
    )

    # 驗證：如果仍不夠，繼續平倉（通常一次就足夠）
    remaining_contracts = sum(p.contracts for p in state.futures_positions)
    if remaining_contracts > 0:
        futures_pnl = _futures_unrealized_pnl(state.futures_positions, current_price)
        puts_value = _puts_market_value(state.put_positions, options_today, put_index)
        equity = state.cash + futures_pnl + puts_value
        initial_margin = _margin_required(state.futures_positions, current_price)

        if equity < initial_margin:
            extra_close = remaining_contracts  # 全部平倉
            _close_excess_futures(
                state, day, current_price, extra_close,
                options_today=options_today,
                reason="margin call (二次)",
            )

    remaining = sum(p.contracts for p in state.futures_positions)
    logger.info(
        "Margin call 完成: date=%s, 剩餘期貨=%d口", day, remaining,
    )


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
            if o.strike == put.strike
            and o.expiry_date == put.expiry_date
            and o.cp == "P"
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
                instrument="TXO_PUT",
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
    # 需要的 PUT 口數 = 期貨總口數 / N（無條件進位）
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
            day, candidate_date,
        )

    if put_bar is None or next_expiry is None:
        logger.warning(
            "結算換倉: 嘗試多個結算日仍找不到 PUT，平倉無保護期貨: date=%s", day,
        )
        unprotected = total_futures - existing_puts * fpp
        if unprotected > 0 and state.futures_positions:
            _close_excess_futures(
                state, day, futures_bar.close, unprotected,
                options_today=options_today, reason="無 PUT 可換倉",
            )
        return

    premium = put_bar.close if put_bar.close > 0 else put_bar.settle
    if premium <= 0:
        premium = 1.0

    cost_per_put = premium * TXO_MULTIPLIER + OPTIONS_COMMISSION

    # 強制保護：若現金不足以買齊所有 PUT，逐口平倉期貨直到能負擔
    while puts_needed > 0 and state.cash < cost_per_put * puts_needed:
        total_futures = sum(p.contracts for p in state.futures_positions)
        if total_futures <= 0:
            break

        logger.info(
            "現金不足換倉 PUT，平倉期貨維持全保護: "
            "date=%s, cash=%.0f, need=%.0f",
            day, state.cash, cost_per_put * puts_needed,
        )
        # 平 fpp 口期貨 = 減少 1 口 PUT 需求
        close_count = min(fpp, total_futures)
        _close_excess_futures(
            state, day, futures_bar.close, close_count,
            options_today=options_today, reason="現金不足買 PUT",
        )

        total_futures = sum(p.contracts for p in state.futures_positions)
        existing_puts = sum(p.contracts for p in state.put_positions)
        puts_needed = _puts_needed(total_futures, fpp) - existing_puts

    if puts_needed <= 0:
        return

    total_cost = premium * TXO_MULTIPLIER * puts_needed
    commission = OPTIONS_COMMISSION * puts_needed

    state.cash -= total_cost + commission
    state.total_put_cost += total_cost + commission

    new_put = PutPosition(
        entry_date=day,
        strike=put_bar.strike,
        expiry_date=next_expiry,
        entry_premium=premium,
        contracts=puts_needed,
    )
    state.put_positions.append(new_put)

    state.trades.append(
        Trade(
            trade_date=day,
            instrument="TXO_PUT",
            action="ROLL",
            price=premium,
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
) -> None:
    """嘗試加倉：買 N 口微台指 + 1 口 PUT。

    每次加倉 = futures_per_put 口期貨 + 1 口 PUT
    例如 futures_per_put=3 → 一次買 3 口微台 + 1 口 PUT

    若資金不足，補到剛好夠買一組的金額。
    """
    fpp = state.futures_per_put
    current_price = futures_bar.close
    margin_per_lot = _dynamic_margin(current_price)

    # 找 PUT
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
    put_cost = put_premium * TXO_MULTIPLIER + OPTIONS_COMMISSION  # 1 口 PUT 的成本

    # 一組所需：N 口期貨保證金 + N 口期貨手續費 + 1 口 PUT 成本
    cost_per_group = margin_per_lot * fpp + FUTURES_COMMISSION * fpp + put_cost

    # 計算當前權益
    futures_pnl = _futures_unrealized_pnl(state.futures_positions, current_price)
    puts_value = _puts_market_value(state.put_positions, options_today)
    equity = state.cash + futures_pnl + puts_value

    # 動態資金控管
    sizing_ratio = _position_sizing_ratio(equity)
    available_for_new = state.cash * sizing_ratio

    if available_for_new < cost_per_group:
        # 資金不足 → 補入至剛好能買一組
        shortfall = cost_per_group - state.cash
        if shortfall > 0:
            state.cash += shortfall
            state.total_injected += shortfall
            logger.info(
                "補入資金: date=%s, amount=%.0f, 累計補入=%.0f",
                day, shortfall, state.total_injected,
            )

    # 加倉 N 口期貨
    state.cash -= FUTURES_COMMISSION * fpp
    new_futures = FuturesPosition(
        entry_date=day,
        entry_price=current_price,
        contracts=fpp,
    )
    state.futures_positions.append(new_futures)

    state.trades.append(
        Trade(
            trade_date=day,
            instrument=FUTURES_CODE,
            action="BUY",
            price=current_price,
            contracts=fpp,
            commission=FUTURES_COMMISSION * fpp,
        )
    )

    # 加倉 1 口 PUT
    state.cash -= put_cost
    state.total_put_cost += put_cost

    new_put = PutPosition(
        entry_date=day,
        strike=put_bar.strike,
        expiry_date=target_expiry,
        entry_premium=put_premium,
        contracts=1,
    )
    state.put_positions.append(new_put)

    state.trades.append(
        Trade(
            trade_date=day,
            instrument="TXO_PUT",
            action="BUY",
            price=put_premium,
            contracts=1,
            commission=OPTIONS_COMMISSION,
            strike=put_bar.strike,
            expiry=target_expiry,
        )
    )

    logger.debug(
        "加倉: %s@%.0f x%d + PUT strike=%d@%.1f, expiry=%s (sizing=%.0f%%)",
        FUTURES_CODE,
        current_price,
        fpp,
        put_bar.strike,
        put_premium,
        target_expiry,
        sizing_ratio * 100,
    )

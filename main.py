"""微台指無限加倉 + 週選 PUT 保護 回測系統入口。

比較不同期貨:PUT 保護比例（含每月定期投入）。

使用方式:
    python main.py
    python main.py --start 2023-01-01 --end 2026-02-28 --ratios 3 5
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from src.config import (
    BACKTEST_END,
    BACKTEST_START,
    FUTURES_CODE,
    FUTURES_NAME,
    INITIAL_CAPITAL,
)
from src.calendar.settlement import get_settlement_dates, get_trading_days
from src.data.taifex_loader import load_futures_range, load_options_range
from src.models import FuturesBar, OptionBar
from src.report.metrics import (
    annualized_return,
    max_drawdown,
    plot_results,
    print_position_details,
    print_summary,
    sharpe_ratio,
    total_return,
    xirr,
)
from src.strategy.engine import run_backtest

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# 只讓 main 顯示 INFO
logging.getLogger(__name__).setLevel(logging.INFO)
logger = logging.getLogger(__name__)

MONTHLY_CONTRIBUTION: float = 30_000  # 每月定期投入 NT$30,000


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="微台指加倉 + 週選 PUT 保護回測")
    parser.add_argument(
        "--start", type=date.fromisoformat, default=BACKTEST_START,
        help="回測起始日 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end", type=date.fromisoformat, default=BACKTEST_END,
        help="回測結束日 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--ratios", type=int, nargs="+", default=[3, 5],
        help="期貨:PUT 比例（例如 3 5 表示 3:1 和 5:1）",
    )
    parser.add_argument(
        "--monthly", type=float, default=MONTHLY_CONTRIBUTION,
        help="每月定期投入金額",
    )
    parser.add_argument(
        "--auto-inject", action="store_true", default=False,
        help="啟用自動補入資金（預設關閉）",
    )
    return parser.parse_args()


def main() -> None:
    """執行回測。"""
    args = _parse_args()
    start = args.start
    end = args.end
    ratios: list[int] = args.ratios
    monthly = args.monthly

    logger.info("=" * 50)
    logger.info("%s加倉 + 週選 PUT 保護 回測系統", FUTURES_NAME)
    logger.info("回測期間: %s ~ %s", start, end)
    logger.info("初始資金: NT$%s", f"{INITIAL_CAPITAL:,}")
    logger.info("每月定期投入: NT$%s", f"{monthly:,.0f}")
    logger.info("比較比例: %s", ", ".join(f"{r}:1" for r in ratios))
    logger.info("自動補入: %s", "開啟" if args.auto_inject else "關閉")
    logger.info("=" * 50)

    # Step 1: 取得交易日
    logger.info("Step 1: 建立交易日曆...")
    trading_days = get_trading_days(start, end)
    settlement_dates = get_settlement_dates(start, end)
    logger.info("  交易日: %d 天", len(trading_days))
    logger.info("  結算日: %d 天", len(settlement_dates))

    # Step 2: 下載期貨資料（沿用 MTX 行情，乘數在 engine 中換算）
    logger.info("Step 2: 下載期貨資料...")
    futures_bars = load_futures_range(start, end)
    logger.info("  期貨資料: %d 筆", len(futures_bars))

    logger.info("Step 3: 下載選擇權資料...")
    options_bars = load_options_range(start, end)
    logger.info("  選擇權 PUT 資料: %d 筆", len(options_bars))

    if not futures_bars:
        logger.error("無期貨資料，無法回測。請檢查網路連線或日期範圍。")
        sys.exit(1)

    # 整理資料
    futures_data: dict[date, FuturesBar] = {}
    for bar in futures_bars:
        futures_data[bar.trade_date] = bar

    options_data: dict[date, list[OptionBar]] = {}
    for bar in options_bars:
        options_data.setdefault(bar.trade_date, []).append(bar)

    # Step 4: 執行回測
    results: list[dict] = []

    for fpp in ratios:
        logger.info("=" * 50)
        logger.info(
            "執行回測: %d 口%s : 1 口 PUT (每月投入 NT$%s)",
            fpp, FUTURES_NAME, f"{monthly:,.0f}",
        )
        logger.info("=" * 50)

        state = run_backtest(
            futures_data=futures_data,
            options_data=options_data,
            trading_days=trading_days,
            start=start,
            end=end,
            initial_capital=INITIAL_CAPITAL,
            futures_per_put=fpp,
            monthly_contribution=monthly,
            allow_auto_injection=args.auto_inject,
        )

        # 輸出個別結果
        print()
        print_summary(
            state.snapshots, state.trades,
            total_injected=state.total_injected,
            total_monthly=state.total_monthly,
            futures_per_put=fpp,
        )
        print_position_details(state.snapshots, state.trades, futures_per_put=fpp)

        # 繪製個別圖表
        chart_path = f"backtest_{fpp}to1.png"
        plot_results(
            state.snapshots,
            trades=state.trades,
            output_path=chart_path,
            total_injected=state.total_injected,
            total_monthly=state.total_monthly,
            futures_per_put=fpp,
        )

        # 收集比較數據
        total_capital = INITIAL_CAPITAL + state.total_injected + state.total_monthly
        mdd, mdd_amount, _, _, _ = max_drawdown(state.snapshots)
        min_eq = min(s.equity for s in state.snapshots) if state.snapshots else 0
        last = state.snapshots[-1] if state.snapshots else None

        xirr_ret = xirr(state.cash_flows) if state.cash_flows else 0.0

        results.append({
            "ratio": fpp,
            "total_capital": total_capital,
            "injected": state.total_injected,
            "monthly": state.total_monthly,
            "final_equity": last.equity if last else 0,
            "min_equity": min_eq,
            "total_return": total_return(state.snapshots, total_capital),
            "annual_return": annualized_return(state.snapshots, total_capital),
            "xirr": xirr_ret,
            "max_drawdown": mdd,
            "mdd_amount": mdd_amount,
            "sharpe": sharpe_ratio(state.snapshots),
            "total_trades": len([
                t for t in state.trades
                if t.action == "BUY" and t.instrument == FUTURES_CODE
            ]),
            "final_futures": last.futures_count if last else 0,
            "final_puts": last.puts_count if last else 0,
            "put_cost": last.total_put_cost if last else 0,
        })

    # Step 5: 輸出比較表
    print()
    print()
    print("=" * 140)
    print(f"  {FUTURES_NAME} vs PUT 比例比較表（每月定期投入 NT${monthly:,.0f}）")
    print("=" * 140)
    print(
        f"  {'比例':>6} {'總投入':>12} {'月投入':>10} {'補入':>10} {'最終權益':>12} "
        f"{'最低權益':>12} {'總報酬':>8} {'XIRR':>8} "
        f"{'MDD':>8} {'Sharpe':>8} {'加倉次':>6} {'持倉':>6} {'PUT成本':>10}"
    )
    print("-" * 140)
    for r in results:
        print(
            f"  {r['ratio']:>2}:1  "
            f"{r['total_capital']:>12,.0f} {r['monthly']:>10,.0f} "
            f"{r['injected']:>10,.0f} "
            f"{r['final_equity']:>12,.0f} {r['min_equity']:>12,.0f} "
            f"{r['total_return']:>+7.1%} {r['xirr']:>+7.1%} "
            f"{r['max_drawdown']:>7.1%} {r['sharpe']:>8.2f} "
            f"{r['total_trades']:>6} {r['final_futures']:>6} "
            f"{r['put_cost']:>10,.0f}"
        )
    print("=" * 140)


if __name__ == "__main__":
    main()

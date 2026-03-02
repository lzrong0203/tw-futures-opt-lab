"""Backtest execution service — wraps run_backtest() for the API."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from datetime import date

from src.calendar.settlement import get_trading_days
from src.config import INITIAL_CAPITAL
from src.data.taifex_loader import load_futures_range, load_options_range
from src.models import OptionBar, PortfolioSnapshot
from src.report.metrics import max_drawdown, sharpe_ratio, total_return, xirr
from src.strategy.engine import run_backtest

MONTHLY_CONTRIBUTION: float = 30_000

logger = logging.getLogger(__name__)


def _serialise_date(obj: object) -> str:
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _run_single(
    ratio: int,
    start: date,
    end: date,
    initial_capital: float,
    monthly_contribution: float,
    allow_auto_injection: bool,
) -> dict:
    """Run one backtest scenario (blocking)."""
    trading_days = get_trading_days(start, end)

    futures_bars = load_futures_range(start, end)
    options_bars = load_options_range(start, end)

    futures_data = {b.trade_date: b for b in futures_bars}

    options_data: dict[date, list[OptionBar]] = {}
    for b in options_bars:
        options_data.setdefault(b.trade_date, []).append(b)

    state = run_backtest(
        futures_data=futures_data,
        options_data=options_data,
        trading_days=trading_days,
        start=start,
        end=end,
        initial_capital=initial_capital,
        futures_per_put=ratio,
        monthly_contribution=monthly_contribution,
        allow_auto_injection=allow_auto_injection,
    )

    snaps: list[dict] = [asdict(s) for s in state.snapshots]
    trades: list[dict] = [asdict(t) for t in state.trades]
    cash_flows: list[dict] = [asdict(cf) for cf in state.cash_flows]

    mdd, mdd_amount, _, _, _ = max_drawdown(state.snapshots)
    tr = total_return(state.snapshots, initial_capital + state.total_monthly)
    sr = sharpe_ratio(state.snapshots)
    xirr_val = xirr(state.cash_flows)

    final_snap: PortfolioSnapshot | None = state.snapshots[-1] if state.snapshots else None

    metrics = {
        "final_equity": final_snap.equity if final_snap else initial_capital,
        "total_return": tr,
        "xirr": xirr_val,
        "sharpe": sr,
        "max_drawdown": mdd,
        "max_drawdown_amount": mdd_amount,
        "total_put_cost": final_snap.total_put_cost if final_snap else 0.0,
        "total_rollover_cost": state.total_rollover_cost,
        "total_injected": state.total_injected,
        "total_monthly": state.total_monthly,
        "futures_per_put": ratio,
    }

    return {
        "snapshots": snaps,
        "trades": trades,
        "cash_flows": cash_flows,
        "metrics": metrics,
    }


def run_all_ratios(
    ratios: list[int],
    start: date,
    end: date,
    initial_capital: float = INITIAL_CAPITAL,
    monthly_contribution: float = MONTHLY_CONTRIBUTION,
    allow_auto_injection: bool = False,
) -> dict:
    """Run backtests for all ratios and return combined results."""
    results: dict[str, dict] = {}
    for ratio in ratios:
        key = f"ratio_{ratio}"
        results[key] = _run_single(
            ratio=ratio,
            start=start,
            end=end,
            initial_capital=initial_capital,
            monthly_contribution=monthly_contribution,
            allow_auto_injection=allow_auto_injection,
        )
    return results


async def execute_backtest(
    ratios: list[int],
    start: date,
    end: date,
    initial_capital: float = INITIAL_CAPITAL,
    monthly_contribution: float = MONTHLY_CONTRIBUTION,
    allow_auto_injection: bool = False,
) -> tuple[str, str]:
    """Run backtests in a thread pool and return (results_json, summary_json)."""
    results = await asyncio.to_thread(
        run_all_ratios,
        ratios=ratios,
        start=start,
        end=end,
        initial_capital=initial_capital,
        monthly_contribution=monthly_contribution,
        allow_auto_injection=allow_auto_injection,
    )

    summary: dict[str, dict] = {}
    for key, data in results.items():
        summary[key] = data["metrics"]

    results_json = json.dumps(results, default=_serialise_date)
    summary_json = json.dumps(summary, default=_serialise_date)
    return results_json, summary_json

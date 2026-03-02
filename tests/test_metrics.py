"""績效指標測試。"""

from __future__ import annotations

from datetime import date

import pytest

from src.models import CashFlow, PortfolioSnapshot
from src.report.metrics import max_drawdown, sharpe_ratio, total_return, xirr


def _snap(d: date, equity: float) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        trade_date=d,
        equity=equity,
        cash=equity,
        margin_used=0,
        futures_unrealized_pnl=0,
        puts_market_value=0,
        total_put_cost=0,
        futures_count=0,
        puts_count=0,
    )


class TestTotalReturn:
    def test_basic(self) -> None:
        snaps = [_snap(date(2025, 1, 2), 100_000), _snap(date(2025, 12, 31), 120_000)]
        assert total_return(snaps, 100_000) == pytest.approx(0.20)

    def test_loss(self) -> None:
        snaps = [_snap(date(2025, 1, 2), 100_000), _snap(date(2025, 6, 30), 80_000)]
        assert total_return(snaps, 100_000) == pytest.approx(-0.20)

    def test_empty(self) -> None:
        assert total_return([], 100_000) == 0.0


class TestMaxDrawdown:
    def test_simple_drawdown(self) -> None:
        snaps = [
            _snap(date(2025, 1, 2), 100_000),
            _snap(date(2025, 2, 1), 120_000),  # peak
            _snap(date(2025, 3, 1), 90_000),  # trough
            _snap(date(2025, 4, 1), 110_000),
        ]
        mdd, mdd_amount, _, _, _ = max_drawdown(snaps)
        assert mdd == pytest.approx(0.25)  # (120k - 90k) / 120k
        assert mdd_amount == pytest.approx(30_000)

    def test_no_drawdown(self) -> None:
        snaps = [
            _snap(date(2025, 1, 2), 100_000),
            _snap(date(2025, 2, 1), 110_000),
            _snap(date(2025, 3, 1), 120_000),
        ]
        mdd, _, _, _, _ = max_drawdown(snaps)
        assert mdd == 0.0


class TestXirr:
    def test_simple_10_pct(self) -> None:
        """投入 100,000，一年後取回 110,000 → XIRR ≈ 10%。"""
        flows = [
            CashFlow(date=date(2025, 1, 1), amount=-100_000),
            CashFlow(date=date(2026, 1, 1), amount=110_000),
        ]
        result = xirr(flows)
        assert result == pytest.approx(0.10, abs=0.001)

    def test_dca(self) -> None:
        """每月投入 10,000 共 12 次，年底取回 130,000。"""
        flows = []
        for m in range(1, 13):
            flows.append(CashFlow(date=date(2025, m, 1), amount=-10_000))
        flows.append(CashFlow(date=date(2025, 12, 31), amount=130_000))
        result = xirr(flows)
        # 總投入 120k，取回 130k，年化應 > 0
        assert result > 0

    def test_loss(self) -> None:
        """投入 100,000，取回 80,000 → XIRR 為負。"""
        flows = [
            CashFlow(date=date(2025, 1, 1), amount=-100_000),
            CashFlow(date=date(2026, 1, 1), amount=80_000),
        ]
        result = xirr(flows)
        assert result < 0

    def test_empty(self) -> None:
        assert xirr([]) == 0.0


class TestSharpeRatio:
    def test_constant_equity_zero_sharpe(self) -> None:
        snaps = [_snap(date(2025, 1, d), 100_000) for d in range(2, 10)]
        assert sharpe_ratio(snaps) == 0.0

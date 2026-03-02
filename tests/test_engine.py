"""回測引擎核心邏輯測試。"""

from __future__ import annotations

from collections import deque

from src.strategy.engine import (
    BacktestState,
    _can_add_position,
    _is_drawdown_paused,
    _puts_needed,
)


class TestPutsNeeded:
    def test_dollar_neutral(self) -> None:
        assert _puts_needed(5, 5) == 1

    def test_round_up(self) -> None:
        assert _puts_needed(6, 5) == 2

    def test_exact_multiple(self) -> None:
        assert _puts_needed(10, 5) == 2

    def test_zero_futures(self) -> None:
        assert _puts_needed(0, 5) == 0

    def test_one_to_one(self) -> None:
        assert _puts_needed(3, 1) == 3


class TestCanAddPosition:
    def _make_state(
        self,
        prev_close: float = 22000,
        prices: list[float] | None = None,
        last_add_idx: int = -999,
        current_idx: int = 100,
    ) -> BacktestState:
        state = BacktestState(
            cash=200_000,
            futures_positions=[],
            put_positions=[],
            trades=[],
            snapshots=[],
            prev_close=prev_close,
            trading_day_idx=current_idx,
            last_add_day_idx=last_add_idx,
        )
        if prices:
            state.price_history = deque(prices, maxlen=50)
        return state

    def test_sufficient_price_change(self) -> None:
        state = self._make_state(prev_close=22000, prices=[22000] * 20)
        # 22000 * 1.005 = 22110 — above threshold
        assert _can_add_position(state, 22200) is True

    def test_insufficient_price_change(self) -> None:
        state = self._make_state(prev_close=22000, prices=[22000] * 20)
        # 22000 * 1.005 = 22110 — 22050 is below threshold
        assert _can_add_position(state, 22050) is False

    def test_below_ma_rejected(self) -> None:
        # MA = 22000, current = 21900 → below MA
        state = self._make_state(prev_close=21500, prices=[22000] * 20)
        assert _can_add_position(state, 21900) is False

    def test_cooldown_period(self) -> None:
        # Last add was 1 day ago, cooldown is 3
        state = self._make_state(
            prev_close=22000,
            prices=[22000] * 20,
            last_add_idx=99,
            current_idx=100,
        )
        assert _can_add_position(state, 22200) is False

    def test_cooldown_expired(self) -> None:
        # Last add was 4 days ago, cooldown is 3
        state = self._make_state(
            prev_close=22000,
            prices=[22000] * 20,
            last_add_idx=96,
            current_idx=100,
        )
        assert _can_add_position(state, 22200) is True

    def test_no_prev_close(self) -> None:
        state = self._make_state(prev_close=None)
        assert _can_add_position(state, 22000) is False


class TestIsDrawdownPaused:
    def test_below_threshold(self) -> None:
        state = BacktestState(
            cash=200_000,
            futures_positions=[],
            put_positions=[],
            trades=[],
            snapshots=[],
            peak_equity=300_000,
        )
        # dd = (300k - 270k) / 300k = 10% < 15%
        assert _is_drawdown_paused(state, 270_000) is False

    def test_above_threshold(self) -> None:
        state = BacktestState(
            cash=200_000,
            futures_positions=[],
            put_positions=[],
            trades=[],
            snapshots=[],
            peak_equity=300_000,
        )
        # dd = (300k - 240k) / 300k = 20% > 15%
        assert _is_drawdown_paused(state, 240_000) is True

    def test_zero_peak(self) -> None:
        state = BacktestState(
            cash=200_000,
            futures_positions=[],
            put_positions=[],
            trades=[],
            snapshots=[],
            peak_equity=0,
        )
        assert _is_drawdown_paused(state, 100_000) is False

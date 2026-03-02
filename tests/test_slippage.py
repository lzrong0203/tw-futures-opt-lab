"""滑價模型測試。"""

from src.strategy.slippage import apply_futures_slippage, apply_options_spread


class TestFuturesSlippage:
    def test_buy_adds_slippage(self) -> None:
        assert apply_futures_slippage(22000, is_buy=True, slippage_points=2.0) == 22002

    def test_sell_subtracts_slippage(self) -> None:
        assert apply_futures_slippage(22000, is_buy=False, slippage_points=2.0) == 21998

    def test_zero_slippage(self) -> None:
        assert apply_futures_slippage(22000, is_buy=True, slippage_points=0.0) == 22000


class TestOptionsSpread:
    def test_buy_pays_ask(self) -> None:
        # premium=20, spread_ratio=0.30, half_spread=3.0
        result = apply_options_spread(20.0, is_buy=True, spread_ratio=0.30)
        assert result == 23.0

    def test_sell_receives_bid(self) -> None:
        # premium=20, spread_ratio=0.30, half_spread=3.0
        result = apply_options_spread(20.0, is_buy=False, spread_ratio=0.30)
        assert result == 17.0

    def test_sell_floor_at_zero(self) -> None:
        # premium=1.0, spread_ratio=3.0, half_spread=1.5 → max(1.0 - 1.5, 0) = 0
        result = apply_options_spread(1.0, is_buy=False, spread_ratio=3.0)
        assert result == 0.0

    def test_zero_spread(self) -> None:
        result = apply_options_spread(20.0, is_buy=True, spread_ratio=0.0)
        assert result == 20.0

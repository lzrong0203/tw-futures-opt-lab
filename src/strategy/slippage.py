"""滑價與買賣價差模型。"""

from __future__ import annotations


def apply_futures_slippage(price: float, *, is_buy: bool, slippage_points: float) -> float:
    """期貨滑價：買高、賣低。"""
    return price + slippage_points if is_buy else price - slippage_points


def apply_options_spread(premium: float, *, is_buy: bool, spread_ratio: float) -> float:
    """選擇權買賣價差：買在 ask（加半個 spread），賣在 bid（減半個 spread）。"""
    half_spread = premium * spread_ratio / 2
    if is_buy:
        return premium + half_spread
    return max(premium - half_spread, 0.0)

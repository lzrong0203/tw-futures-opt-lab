"""PUT 選擇邏輯 regression 測試。"""

from __future__ import annotations

from datetime import date

from src.strategy.put_selector import select_put_by_premium


class TestSelectPutByPremium:
    def test_selects_deepest_otm_in_range(self, make_option_bar) -> None:
        """區間內選最深度價外（最低 strike）。"""
        expiry = date(2025, 3, 5)
        puts = [
            make_option_bar(strike=21600, premium=25.0, expiry=expiry),
            make_option_bar(strike=21500, premium=20.0, expiry=expiry),
            make_option_bar(strike=21400, premium=15.0, expiry=expiry),
            make_option_bar(strike=21300, premium=12.0, expiry=expiry),
        ]
        result = select_put_by_premium(22000, puts, expiry, min_premium=10, max_premium=30)
        assert result is not None
        assert result.strike == 21300  # 最深 OTM，在 [10, 30] 區間內

    def test_fallback_above_min(self, make_option_bar) -> None:
        """區間內無候選人，找 >= min_premium 中最便宜的。"""
        expiry = date(2025, 3, 5)
        puts = [
            make_option_bar(strike=21500, premium=35.0, expiry=expiry),
            make_option_bar(strike=21400, premium=40.0, expiry=expiry),
        ]
        result = select_put_by_premium(22000, puts, expiry, min_premium=10, max_premium=30)
        assert result is not None
        assert result.strike == 21500  # premium=35 最接近 min

    def test_fallback_all_below_min(self, make_option_bar) -> None:
        """所有 PUT < min_premium，選最貴的。"""
        expiry = date(2025, 3, 5)
        puts = [
            make_option_bar(strike=21500, premium=5.0, expiry=expiry),
            make_option_bar(strike=21400, premium=8.0, expiry=expiry),
        ]
        result = select_put_by_premium(22000, puts, expiry, min_premium=10, max_premium=30)
        assert result is not None
        assert result.strike == 21400  # premium=8 最貴

    def test_returns_none_no_candidates(self) -> None:
        """無 OTM PUT 時回傳 None。"""
        result = select_put_by_premium(22000, [], date(2025, 3, 5))
        assert result is None

    def test_prefers_volume(self, make_option_bar) -> None:
        """區間內有成交量的優先。"""
        expiry = date(2025, 3, 5)
        puts = [
            make_option_bar(strike=21400, premium=15.0, expiry=expiry, volume=0),
            make_option_bar(strike=21500, premium=20.0, expiry=expiry, volume=100),
        ]
        result = select_put_by_premium(22000, puts, expiry, min_premium=10, max_premium=30)
        assert result is not None
        # 有成交量的池中，21500 是唯一有 volume 的，但 21400 的 strike 更低
        # 邏輯：with_volume = [21500]，pool 只有一個，所以選 21500
        assert result.strike == 21500

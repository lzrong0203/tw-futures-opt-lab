"""交易日曆與結算日測試。"""

from __future__ import annotations

from datetime import date

from src.calendar.settlement import (
    get_settlement_dates,
    get_trading_days,
    is_trading_day,
)


class TestIsTradingDay:
    def test_weekday_is_trading(self) -> None:
        # 2025-03-03 is Monday
        assert is_trading_day(date(2025, 3, 3)) is True

    def test_saturday_not_trading(self) -> None:
        assert is_trading_day(date(2025, 3, 1)) is False

    def test_sunday_not_trading(self) -> None:
        assert is_trading_day(date(2025, 3, 2)) is False

    def test_holiday_not_trading(self) -> None:
        # 2025-01-01 元旦
        assert is_trading_day(date(2025, 1, 1)) is False

    def test_spring_festival(self) -> None:
        # 2025-01-28 春節
        assert is_trading_day(date(2025, 1, 28)) is False


class TestGetTradingDays:
    def test_count_2025_jan(self) -> None:
        days = get_trading_days(date(2025, 1, 1), date(2025, 1, 31))
        # Jan 2025: 23 weekdays - 6 holidays = 17 trading days
        assert len(days) > 10
        assert all(is_trading_day(d) for d in days)

    def test_sorted(self) -> None:
        days = get_trading_days(date(2025, 3, 1), date(2025, 3, 31))
        assert days == sorted(days)


class TestGetSettlementDates:
    def test_has_wednesdays(self) -> None:
        dates = get_settlement_dates(date(2025, 3, 1), date(2025, 3, 31))
        assert len(dates) >= 4  # At least 4 Wednesdays in March

    def test_all_are_trading_days(self) -> None:
        dates = get_settlement_dates(date(2025, 3, 1), date(2025, 6, 30))
        for d in dates:
            assert is_trading_day(d), f"{d} is not a trading day"

    def test_includes_fridays_after_june_27(self) -> None:
        dates = get_settlement_dates(date(2025, 7, 1), date(2025, 7, 31))
        weekdays = [d.weekday() for d in dates]
        # Should have both Wednesdays (2) and Fridays (4)
        assert 2 in weekdays  # Wednesday
        assert 4 in weekdays  # Friday

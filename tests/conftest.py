"""共用 test fixtures。"""

from __future__ import annotations

from datetime import date

import pytest

from src.models import FuturesBar, OptionBar


@pytest.fixture
def sample_futures_bar() -> FuturesBar:
    return FuturesBar(
        trade_date=date(2025, 3, 3),
        open=22000,
        high=22100,
        low=21900,
        close=22050,
        settle=22050,
        volume=10000,
        contract_month="202503",
    )


@pytest.fixture
def sample_option_bar() -> OptionBar:
    return OptionBar(
        trade_date=date(2025, 3, 3),
        contract_code="TXO",
        strike=21500,
        cp="P",
        expiry_date=date(2025, 3, 5),
        open=18.0,
        high=20.0,
        low=16.0,
        close=17.0,
        settle=17.0,
        volume=100,
    )


@pytest.fixture
def make_option_bar():
    """Factory fixture for creating OptionBar with custom fields."""

    def _make(
        strike: int = 21500,
        premium: float = 20.0,
        expiry: date = date(2025, 3, 5),
        volume: int = 50,
    ) -> OptionBar:
        return OptionBar(
            trade_date=date(2025, 3, 3),
            contract_code="TXO",
            strike=strike,
            cp="P",
            expiry_date=expiry,
            open=premium,
            high=premium + 2,
            low=premium - 2,
            close=premium,
            settle=premium,
            volume=volume,
        )

    return _make

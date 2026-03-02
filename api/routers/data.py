"""Data API endpoints (calendar, etc.)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from api.schemas import CalendarResponse
from src.calendar.settlement import get_settlement_dates, get_trading_days

router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/calendar", response_model=CalendarResponse)
async def get_calendar(
    start: date = Query(default=date(2025, 1, 1)),
    end: date = Query(default=date(2026, 12, 31)),
) -> CalendarResponse:
    """Return trading days and settlement dates for a given period."""
    trading_days = get_trading_days(start, end)
    settlement_dates = get_settlement_dates(start, end)
    return CalendarResponse(
        trading_days=trading_days,
        settlement_dates=settlement_dates,
    )

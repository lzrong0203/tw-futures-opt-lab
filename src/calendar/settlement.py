"""結算日曆 — 台指週選結算日與交易日管理。

台指週選結算日為每週三（若遇假日則提前至前一個交易日）。
月選結算日為每月第三個週三。
"""

from __future__ import annotations

import bisect
from datetime import date, timedelta
from typing import Sequence

# 2025~2026 台灣國定假日（排除週末）
# 來源：行政院人事行政總處
TW_HOLIDAYS: frozenset[date] = frozenset(
    [
        # 2025
        date(2025, 1, 1),  # 元旦
        date(2025, 1, 27),  # 除夕（調整）
        date(2025, 1, 28),  # 春節
        date(2025, 1, 29),  # 春節
        date(2025, 1, 30),  # 春節
        date(2025, 1, 31),  # 春節（彈性放假）
        date(2025, 2, 28),  # 和平紀念日
        date(2025, 4, 3),  # 兒童節（補假）
        date(2025, 4, 4),  # 清明節
        date(2025, 5, 1),  # 勞動節
        date(2025, 5, 30),  # 端午節（調整）
        date(2025, 5, 31),  # 端午節
        date(2025, 6, 2),  # 端午節（彈性放假） - 注意：這是週一
        date(2025, 10, 6),  # 中秋節
        date(2025, 10, 10),  # 國慶日
        # 2026
        date(2026, 1, 1),  # 元旦
        date(2026, 2, 16),  # 除夕（調整）
        date(2026, 2, 17),  # 春節
        date(2026, 2, 18),  # 春節
        date(2026, 2, 19),  # 春節
        date(2026, 2, 20),  # 春節（彈性放假）
        date(2026, 2, 28),  # 和平紀念日（週六，不影響）
    ]
)


def is_trading_day(d: date) -> bool:
    """判斷是否為交易日（非週末、非國定假日）。"""
    if d.weekday() >= 5:  # 週六=5, 週日=6
        return False
    return d not in TW_HOLIDAYS


def get_trading_days(start: date, end: date) -> list[date]:
    """取得期間內所有交易日。"""
    days: list[date] = []
    current = start
    while current <= end:
        if is_trading_day(current):
            days.append(current)
        current += timedelta(days=1)
    return days


def _get_weekdays(start: date, end: date, weekday: int) -> list[date]:
    """取得期間內所有指定星期幾的日期。weekday: 0=Mon, 2=Wed, 4=Fri。"""
    current = start
    while current.weekday() != weekday:
        current += timedelta(days=1)

    result: list[date] = []
    while current <= end:
        result.append(current)
        current += timedelta(days=7)
    return result


def get_wednesdays(start: date, end: date) -> list[date]:
    """取得期間內所有週三。"""
    return _get_weekdays(start, end, 2)


# 週五到期台指選擇權上市日（2025/06/27）
_FRIDAY_SETTLEMENT_START = date(2025, 6, 27)


def get_settlement_dates(start: date, end: date) -> list[date]:
    """取得期間內所有週選結算日。

    - 每週三為結算日（若遇假日則提前至前一個交易日）。
    - 2025/06/27 起，每週五也是結算日。
    """
    wednesdays = get_wednesdays(start, end)
    settlements: set[date] = set()

    for wed in wednesdays:
        settle_date = wed
        while not is_trading_day(settle_date):
            settle_date -= timedelta(days=1)
        settlements.add(settle_date)

    # 2025/06/27 之後加入週五結算
    # 注意：週五遇假日時直接跳過（不退到週四），因為台指週選只有週三/週五到期合約
    fri_start = max(start, _FRIDAY_SETTLEMENT_START)
    if fri_start <= end:
        fridays = _get_weekdays(fri_start, end, 4)
        for fri in fridays:
            if is_trading_day(fri):
                settlements.add(fri)

    return sorted(settlements)


def get_monthly_settlement_dates(start: date, end: date) -> list[date]:
    """取得期間內所有月選結算日（每月第三個週三）。"""
    monthly: list[date] = []
    current = date(start.year, start.month, 1)

    while current <= end:
        # 找該月第三個週三
        d = date(current.year, current.month, 1)
        wed_count = 0
        while wed_count < 3:
            if d.weekday() == 2:
                wed_count += 1
                if wed_count == 3:
                    break
            d += timedelta(days=1)

        # 若非交易日則提前
        settle = d
        while not is_trading_day(settle):
            settle -= timedelta(days=1)

        if start <= settle <= end:
            monthly.append(settle)

        # 下個月
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    return monthly


def next_settlement_date(from_date: date, settlement_dates: Sequence[date]) -> date | None:
    """找到 from_date 之後（不含當天）的最近結算日。"""
    idx = bisect.bisect_right(settlement_dates, from_date)
    return settlement_dates[idx] if idx < len(settlement_dates) else None


def current_or_next_settlement(from_date: date, settlement_dates: Sequence[date]) -> date | None:
    """找到 from_date 當天或之後的最近結算日。"""
    idx = bisect.bisect_left(settlement_dates, from_date)
    return settlement_dates[idx] if idx < len(settlement_dates) else None


def is_settlement_day(d: date, settlement_dates: Sequence[date]) -> bool:
    """判斷是否為結算日。"""
    return d in settlement_dates

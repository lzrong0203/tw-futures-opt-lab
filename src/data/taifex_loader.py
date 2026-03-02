"""TAIFEX 期交所資料下載與解析。

從臺灣期貨交易所官網下載每日期貨與選擇權行情資料，
並快取至本地 CSV 檔案以避免重複下載。
"""

from __future__ import annotations

import csv
import io
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from src.config import CACHE_DIR
from src.models import FuturesBar, OptionBar

logger = logging.getLogger(__name__)

# TAIFEX 每日行情查詢 URL
_FUTURES_URL = "https://www.taifex.com.tw/cht/3/futDataDown"
_OPTIONS_URL = "https://www.taifex.com.tw/cht/3/optDataDown"

_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.taifex.com.tw/cht/3/dlFutDailyMarketView",
    }
)


def _cache_path(prefix: str, start: date, end: date) -> Path:
    """產生快取檔案路徑。"""
    base = Path(CACHE_DIR)
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{prefix}_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.csv"


def _date_str(d: date) -> str:
    """格式化日期為 TAIFEX 格式 YYYY/MM/DD。"""
    return d.strftime("%Y/%m/%d")


def _download_futures_csv(start: date, end: date) -> str:
    """下載期貨每日行情 CSV 原始文字。"""
    payload = {
        "down_type": "1",
        "commodity_id": "MTX",
        "commodity_id2": "",
        "queryStartDate": _date_str(start),
        "queryEndDate": _date_str(end),
    }
    resp = _SESSION.post(_FUTURES_URL, data=payload, timeout=30)
    resp.encoding = "big5"
    return resp.text


def _download_options_csv(start: date, end: date) -> str:
    """下載選擇權每日行情 CSV 原始文字。"""
    payload = {
        "down_type": "1",
        "commodity_id": "TXO",
        "commodity_id2": "",
        "queryStartDate": _date_str(start),
        "queryEndDate": _date_str(end),
    }
    resp = _SESSION.post(_OPTIONS_URL, data=payload, timeout=30)
    resp.encoding = "big5"
    return resp.text


def _parse_date(s: str) -> date:
    """解析日期字串，支援 YYYY/MM/DD 格式。"""
    s = s.strip()
    for fmt in ("%Y/%m/%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"無法解析日期: {s!r}")


def _safe_float(s: str) -> float:
    """安全轉換浮點數，處理空值和特殊值。"""
    s = s.strip().replace(",", "")
    if not s or s == "-" or s == "--":
        return 0.0
    return float(s)


def _safe_int(s: str) -> int:
    """安全轉換整數。"""
    s = s.strip().replace(",", "")
    if not s or s == "-" or s == "--":
        return 0
    return int(s)


def _parse_expiry_month(contract_month: str, trade_date: date) -> date:
    """從合約月份字串推算到期日。

    合約月份格式：YYYYMM（月合約）或 YYYYMMW1/W2/W4/W5（週合約）
    """
    cm = contract_month.strip()

    # 週合約 (週三到期): 202501W1, 202501W2, etc.
    if "W" in cm:
        year = int(cm[:4])
        month = int(cm[4:6])
        week_num = int(cm[7])  # W 後面的數字

        # 找該月第 N 個週三
        d = date(year, month, 1)
        wed_count = 0
        while True:
            if d.weekday() == 2:  # Wednesday
                wed_count += 1
                if wed_count == week_num:
                    return d
            d += timedelta(days=1)
            if d.month != month:
                # 如果超出當月，返回最後一個找到的週三
                return d - timedelta(days=1)

    # 週五到期合約: 202507F2, 202507F3, etc.
    if "F" in cm:
        year = int(cm[:4])
        month = int(cm[4:6])
        fri_num = int(cm[7])  # F 後面的數字

        # 找該月第 N 個週五
        d = date(year, month, 1)
        fri_count = 0
        while True:
            if d.weekday() == 4:  # Friday
                fri_count += 1
                if fri_count == fri_num:
                    return d
            d += timedelta(days=1)
            if d.month != month:
                return d - timedelta(days=1)

    # 月合約: 202501
    if len(cm) == 6:
        year = int(cm[:4])
        month = int(cm[4:6])
        # 月選結算日 = 第三個週三
        d = date(year, month, 1)
        wed_count = 0
        while wed_count < 3:
            if d.weekday() == 2:
                wed_count += 1
                if wed_count == 3:
                    return d
            d += timedelta(days=1)

    raise ValueError(f"無法解析合約月份: {cm!r}")


def parse_futures_csv(raw_csv: str) -> list[FuturesBar]:
    """解析期貨行情 CSV。

    TAIFEX CSV 欄位（期貨）:
    交易日期(0), 契約(1), 到期月份(週別)(2), 開盤價(3), 最高價(4), 最低價(5),
    收盤價(6), 漲跌價(7), 漲跌%(8), 成交量(9), 結算價(10), 未沖銷契約數(11),
    最後最佳買價(12), 最後最佳賣價(13), 歷史最高價(14), 歷史最低價(15),
    是否因訊息面暫停交易(16), 交易時段(17), 價差對單式委託成交量(18)
    """
    bars: list[FuturesBar] = []
    reader = csv.reader(io.StringIO(raw_csv))

    header_found = False
    for row in reader:
        if not row or len(row) < 12:
            continue

        # 跳過標題列
        first_col = row[0].strip()
        if "交易日期" in first_col or "Date" in first_col:
            header_found = True
            continue
        if not header_found:
            continue

        # 只取 MTX（微台指）
        contract = row[1].strip()
        if contract != "MTX":
            continue

        try:
            trade_date = _parse_date(row[0])
            contract_month = row[2].strip() if len(row) > 2 else ""
            open_price = _safe_float(row[3])
            high = _safe_float(row[4])
            low = _safe_float(row[5])
            close = _safe_float(row[6])
            volume = _safe_int(row[9])
            settle = _safe_float(row[10])

            # 跳過盤後交易時段（只取一般交易時段）
            session = row[17].strip() if len(row) > 17 else ""
            if session == "盤後":
                continue

            # 跳過無效資料
            if close <= 0:
                continue

            bars.append(
                FuturesBar(
                    trade_date=trade_date,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    settle=settle if settle > 0 else close,
                    volume=volume,
                    contract_month=contract_month,
                )
            )
        except (ValueError, IndexError) as e:
            logger.debug("跳過無效期貨資料列: %s, 錯誤: %s", row, e)
            continue

    return bars


def parse_options_csv(raw_csv: str) -> list[OptionBar]:
    """解析選擇權行情 CSV。

    TAIFEX CSV 欄位（選擇權）:
    交易日期, 契約, 到期月份(週別), 履約價, 買賣權, 開盤價, 最高價, 最低價,
    收盤價, 成交量, 結算價, 未沖銷契約數, 最後最佳買價, 最後最佳賣價,
    歷史最高價, 歷史最低價, 是否因其他契約到期而新掛牌, 交易時段
    """
    bars: list[OptionBar] = []
    reader = csv.reader(io.StringIO(raw_csv))

    header_found = False
    for row in reader:
        if not row or len(row) < 12:
            continue

        first_col = row[0].strip()
        if "交易日期" in first_col or "Date" in first_col:
            header_found = True
            continue
        if not header_found:
            continue

        contract = row[1].strip()
        # 接受 TXO 及所有週選合約代碼
        valid_codes = {"TXO", "TX1", "TX2", "TX4", "TX5"}
        if contract not in valid_codes:
            continue

        try:
            trade_date = _parse_date(row[0])
            contract_month = row[2].strip()
            strike = int(_safe_float(row[3]))
            cp = row[4].strip()  # "買權" or "賣權" or "P" or "C"

            # 統一為 P/C
            if "賣" in cp or cp.upper() == "P":
                cp_normalized = "P"
            elif "買" in cp or cp.upper() == "C":
                cp_normalized = "C"
            else:
                continue

            # 只取 PUT
            if cp_normalized != "P":
                continue

            open_price = _safe_float(row[5])
            high = _safe_float(row[6])
            low = _safe_float(row[7])
            close = _safe_float(row[8])
            volume = _safe_int(row[9])
            settle = _safe_float(row[10])

            # 跳過盤後
            session = row[17].strip() if len(row) > 17 else ""
            if session == "盤後":
                continue

            expiry = _parse_expiry_month(contract_month, trade_date)

            bars.append(
                OptionBar(
                    trade_date=trade_date,
                    contract_code=contract,
                    strike=strike,
                    cp=cp_normalized,
                    expiry_date=expiry,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    settle=settle if settle > 0 else close,
                    volume=volume,
                )
            )
        except (ValueError, IndexError) as e:
            logger.debug("跳過無效選擇權資料列: %s, 錯誤: %s", row, e)
            continue

    return bars


def load_futures_range(start: date, end: date) -> list[FuturesBar]:
    """載入指定期間的微台指期貨資料。自動分月下載並快取。"""
    all_bars: list[FuturesBar] = []

    # 分月下載（TAIFEX 限制一次最多一個月）
    current_start = start
    while current_start <= end:
        # 本月結束日
        if current_start.month == 12:
            month_end = date(current_start.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(current_start.year, current_start.month + 1, 1) - timedelta(days=1)
        chunk_end = min(month_end, end)

        cache_file = _cache_path("fut_mtx", current_start, chunk_end)

        if cache_file.exists():
            logger.info("從快取載入期貨資料: %s", cache_file)
            raw_csv = cache_file.read_text(encoding="utf-8")
        else:
            logger.info("下載期貨資料: %s ~ %s", current_start, chunk_end)
            raw_csv = _download_futures_csv(current_start, chunk_end)
            cache_file.write_text(raw_csv, encoding="utf-8")
            time.sleep(1)  # 避免請求過於頻繁

        bars = parse_futures_csv(raw_csv)
        all_bars.extend(bars)

        current_start = chunk_end + timedelta(days=1)

    # 去重（同一天可能有多筆不同到期月份的合約，取近月合約）
    by_date: dict[date, list[FuturesBar]] = {}
    for bar in all_bars:
        by_date.setdefault(bar.trade_date, []).append(bar)

    result: list[FuturesBar] = []
    for trade_date in sorted(by_date.keys()):
        bars_on_day = by_date[trade_date]
        # 取成交量最大的合約（通常是近月）
        best = max(bars_on_day, key=lambda b: b.volume)
        result.append(best)

    return result


def load_options_range(start: date, end: date) -> list[OptionBar]:
    """載入指定期間的台指選擇權 PUT 資料。自動分月下載並快取。"""
    all_bars: list[OptionBar] = []

    current_start = start
    while current_start <= end:
        if current_start.month == 12:
            month_end = date(current_start.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(current_start.year, current_start.month + 1, 1) - timedelta(days=1)
        chunk_end = min(month_end, end)

        cache_file = _cache_path("opt_txo_put", current_start, chunk_end)

        if cache_file.exists():
            logger.info("從快取載入選擇權資料: %s", cache_file)
            raw_csv = cache_file.read_text(encoding="utf-8")
        else:
            logger.info("下載選擇權資料: %s ~ %s", current_start, chunk_end)
            raw_csv = _download_options_csv(current_start, chunk_end)
            cache_file.write_text(raw_csv, encoding="utf-8")
            time.sleep(1)

        bars = parse_options_csv(raw_csv)
        all_bars.extend(bars)

        current_start = chunk_end + timedelta(days=1)

    return all_bars

"""PUT 選擇邏輯 — 依權利金區間選擇最適合的價外 PUT 作為保護。

選擇策略：
1. 篩選到期日匹配且為價外 (strike < futures_price) 的 PUT
2. 取權利金在 [min_premium, max_premium] 區間內的候選人
3. 在區間內選最深度價外（最低 strike）→ 成本最低的有效保護
4. Fallback：若區間內無候選人，找最接近 min_premium 的 PUT
"""

from __future__ import annotations

import logging
from datetime import date

from src.config import PUT_PREMIUM_MAX, PUT_PREMIUM_MIN
from src.models import OptionBar

logger = logging.getLogger(__name__)


def _get_premium(bar: OptionBar) -> float:
    """取得 PUT 的有效權利金（優先用 close，其次 settle）。"""
    if bar.close > 0:
        return bar.close
    if bar.settle > 0:
        return bar.settle
    return 0.0


def select_put_by_premium(
    futures_price: float,
    available_puts: list[OptionBar],
    target_expiry: date,
    min_premium: float = PUT_PREMIUM_MIN,
    max_premium: float = PUT_PREMIUM_MAX,
) -> OptionBar | None:
    """依權利金區間選擇最適合的價外 PUT。

    選擇邏輯：
    1. 篩選到期日 = target_expiry、cp = "P"、strike < futures_price（OTM）
    2. 計算每個候選人的權利金
    3. 篩選權利金在 [min_premium, max_premium] 範圍內的
    4. 在範圍內選最深度價外（最低 strike）→ 最便宜的有效保護
    5. Fallback：若無候選人 → 找權利金最接近 min_premium 且 > 0 的

    Returns:
        OptionBar | None: 最適合的 PUT，或 None（無合適候選人）
    """
    # Step 1: 篩選正確到期日的 OTM PUT
    candidates = [
        p
        for p in available_puts
        if p.expiry_date == target_expiry and p.cp == "P" and p.strike < futures_price
    ]

    if not candidates:
        return None

    # Step 2: 計算權利金，排除無報價的
    priced = [(c, _get_premium(c)) for c in candidates]
    priced = [(c, prem) for c, prem in priced if prem > 0]

    if not priced:
        return None

    # Step 3: 篩選權利金在 [min, max] 區間內的（優先有成交量的）
    in_range = [(c, prem) for c, prem in priced if min_premium <= prem <= max_premium]

    if in_range:
        # 優先有成交量的
        with_volume = [(c, prem) for c, prem in in_range if c.volume > 0]
        pool = with_volume if with_volume else in_range
        # 選最深度價外（最低 strike）→ 最便宜的保護
        best = min(pool, key=lambda x: x[0].strike)
        return best[0]

    # Step 4: Fallback — 區間內沒有候選人
    # 找權利金最接近 min_premium 的（盡量便宜但有效）
    # 優先找 >= min_premium 的（保護力足夠）
    above_min = [(c, prem) for c, prem in priced if prem >= min_premium]
    if above_min:
        # 取最接近 min_premium 的（最便宜的有效保護）
        best = min(above_min, key=lambda x: x[1])
        logger.debug(
            "PUT fallback: 無 [%.0f, %.0f] 區間候選人，選最接近 min 的: strike=%d, premium=%.1f",
            min_premium,
            max_premium,
            best[0].strike,
            best[1],
        )
        return best[0]

    # 最後手段：所有 PUT 都 < min_premium，選最貴的（保護力最接近需求的）
    best = max(priced, key=lambda x: x[1])
    logger.debug(
        "PUT fallback: 所有 PUT 權利金 < %.0f，選最貴的: strike=%d, premium=%.1f",
        min_premium,
        best[0].strike,
        best[1],
    )
    return best[0]

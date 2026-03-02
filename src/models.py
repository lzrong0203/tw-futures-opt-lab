"""資料模型 — 所有核心資料結構使用 frozen dataclass。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class FuturesBar:
    """期貨日 K 線。"""

    trade_date: date
    open: float
    high: float
    low: float
    close: float
    settle: float  # 結算價
    volume: int


@dataclass(frozen=True)
class OptionBar:
    """選擇權日 K 線。"""

    trade_date: date
    contract_code: str  # e.g. "TXO", "TX1", "TX2", ...
    strike: int  # 履約價
    cp: str  # "P" or "C"
    expiry_date: date  # 到期日
    open: float
    high: float
    low: float
    close: float
    settle: float  # 結算價
    volume: int


@dataclass(frozen=True)
class FuturesPosition:
    """期貨多單部位。"""

    entry_date: date
    entry_price: float
    contracts: int = 1


@dataclass(frozen=True)
class PutPosition:
    """PUT 保護部位。"""

    entry_date: date
    strike: int
    expiry_date: date
    entry_premium: float  # 買入權利金（點數）
    contracts: int = 1


@dataclass(frozen=True)
class Trade:
    """交易記錄。"""

    trade_date: date
    instrument: str  # "MTX" or "TXO_PUT"
    action: str  # "BUY", "SELL", "SETTLE", "ROLL"
    price: float
    contracts: int
    pnl: float = 0.0  # 已實現損益
    commission: float = 0.0
    tax: float = 0.0
    strike: int | None = None  # PUT 履約價
    expiry: date | None = None  # PUT 到期日


@dataclass(frozen=True)
class PortfolioSnapshot:
    """每日投資組合快照。"""

    trade_date: date
    equity: float  # 總權益
    cash: float  # 現金餘額
    margin_used: float  # 已用保證金
    futures_unrealized_pnl: float  # 期貨未實現損益
    puts_market_value: float  # PUT 市值
    total_put_cost: float  # 累計 PUT 成本
    futures_count: int  # 期貨持倉口數
    puts_count: int  # PUT 持倉口數
    daily_pnl: float = 0.0  # 當日損益

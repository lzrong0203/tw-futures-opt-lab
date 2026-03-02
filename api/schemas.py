"""API Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


# ── Request ──────────────────────────────────


class BacktestRequest(BaseModel):
    """回測請求參數。"""

    ratios: list[int] = Field(default=[3, 5], description="期貨:PUT 保護比例清單")
    initial_capital: float = Field(default=200_000, gt=0)
    backtest_start: date = Field(default=date(2025, 1, 1))
    backtest_end: date = Field(default=date(2026, 2, 28))
    monthly_contribution: float = Field(default=30_000, ge=0)
    allow_auto_injection: bool = False


# ── Domain mirrors ───────────────────────────


class TradeSchema(BaseModel):
    trade_date: date
    instrument: str
    action: str
    price: float
    contracts: int
    pnl: float = 0.0
    commission: float = 0.0
    tax: float = 0.0
    strike: int | None = None
    expiry: date | None = None


class SnapshotSchema(BaseModel):
    trade_date: date
    equity: float
    cash: float
    margin_used: float
    futures_unrealized_pnl: float
    puts_market_value: float
    total_put_cost: float
    futures_count: int
    puts_count: int
    daily_pnl: float = 0.0


class CashFlowSchema(BaseModel):
    date: date
    amount: float


class MetricsSummary(BaseModel):
    final_equity: float
    total_return: float
    xirr: float
    sharpe: float
    max_drawdown: float
    max_drawdown_amount: float
    total_put_cost: float
    total_rollover_cost: float
    total_injected: float
    total_monthly: float
    futures_per_put: int


# ── Response ─────────────────────────────────


class BacktestCreated(BaseModel):
    """POST /api/backtest 回應。"""

    id: str
    status: str = "running"
    created_at: datetime


class BacktestStatus(BaseModel):
    """GET /api/backtest/{id}/status 回應。"""

    id: str
    status: str
    error_message: str | None = None


class BacktestResult(BaseModel):
    """GET /api/backtest/{id} 完整結果。"""

    id: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    parameters: BacktestRequest | None = None
    snapshots: list[SnapshotSchema] = []
    trades: list[TradeSchema] = []
    cash_flows: list[CashFlowSchema] = []
    metrics: MetricsSummary | None = None


class BacktestListItem(BaseModel):
    """GET /api/backtest 清單項目（摘要）。"""

    id: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    parameters: BacktestRequest | None = None
    metrics: MetricsSummary | None = None


class BacktestListResponse(BaseModel):
    items: list[BacktestListItem]
    total: int


# ── Data ─────────────────────────────────────


class CalendarResponse(BaseModel):
    trading_days: list[date]
    settlement_dates: list[date]


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    database: str

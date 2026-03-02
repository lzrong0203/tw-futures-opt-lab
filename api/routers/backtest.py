"""Backtest API endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, HTTPException

from api.db import (
    create_backtest,
    get_backtest,
    list_backtests,
    update_backtest_completed,
    update_backtest_failed,
)
from api.schemas import (
    BacktestCreated,
    BacktestListItem,
    BacktestListResponse,
    BacktestRequest,
    BacktestResult,
    BacktestStatus,
    CashFlowSchema,
    MetricsSummary,
    SnapshotSchema,
    TradeSchema,
)
from api.services.runner import execute_backtest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


async def _run_background(backtest_id: str, req: BacktestRequest) -> None:
    """Background coroutine: execute backtest then persist results."""
    try:
        results_json, summary_json = await execute_backtest(
            ratios=req.ratios,
            start=req.backtest_start,
            end=req.backtest_end,
            initial_capital=req.initial_capital,
            monthly_contribution=req.monthly_contribution,
            allow_auto_injection=req.allow_auto_injection,
        )
        await update_backtest_completed(backtest_id, results_json, summary_json)
        logger.info("Backtest %s completed", backtest_id)
    except Exception:
        logger.exception("Backtest %s failed", backtest_id)
        await update_backtest_failed(backtest_id, "Internal backtest error")


@router.post("", response_model=BacktestCreated, status_code=202)
async def create_backtest_run(req: BacktestRequest) -> BacktestCreated:
    """Submit a new backtest run (returns immediately)."""
    backtest_id = str(uuid.uuid4())
    await create_backtest(backtest_id, req.model_dump(mode="json"))
    asyncio.create_task(_run_background(backtest_id, req))

    row = await get_backtest(backtest_id)
    return BacktestCreated(
        id=backtest_id,
        status="running",
        created_at=row["created_at"],
    )


@router.get("/{backtest_id}", response_model=BacktestResult)
async def get_backtest_detail(backtest_id: str) -> BacktestResult:
    """Get full backtest result."""
    row = await get_backtest(backtest_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Backtest not found")

    result = BacktestResult(
        id=row["id"],
        status=row["status"],
        created_at=row["created_at"],
        completed_at=row.get("completed_at"),
        error_message=row.get("error_message"),
    )

    if row.get("parameters"):
        result.parameters = BacktestRequest.model_validate_json(row["parameters"])

    if row["status"] == "completed" and row.get("results_json"):
        data = json.loads(row["results_json"])
        # Take the first ratio's results for the detail view
        first_key = next(iter(data), None)
        if first_key:
            scenario = data[first_key]
            result.snapshots = [SnapshotSchema.model_validate(s) for s in scenario["snapshots"]]
            result.trades = [TradeSchema.model_validate(t) for t in scenario["trades"]]
            result.cash_flows = [CashFlowSchema.model_validate(cf) for cf in scenario["cash_flows"]]
            result.metrics = MetricsSummary.model_validate(scenario["metrics"])

    return result


@router.get("/{backtest_id}/status", response_model=BacktestStatus)
async def get_backtest_status(backtest_id: str) -> BacktestStatus:
    """Poll backtest execution status."""
    row = await get_backtest(backtest_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Backtest not found")

    return BacktestStatus(
        id=row["id"],
        status=row["status"],
        error_message=row.get("error_message"),
    )


@router.get("", response_model=BacktestListResponse)
async def list_backtest_runs(limit: int = 50, offset: int = 0) -> BacktestListResponse:
    """List historical backtest runs (summary only)."""
    rows, total = await list_backtests(limit=limit, offset=offset)

    items: list[BacktestListItem] = []
    for row in rows:
        item = BacktestListItem(
            id=row["id"],
            status=row["status"],
            created_at=row["created_at"],
            completed_at=row.get("completed_at"),
        )
        if row.get("parameters"):
            item.parameters = BacktestRequest.model_validate_json(row["parameters"])
        if row.get("summary"):
            summary_data = json.loads(row["summary"])
            first_key = next(iter(summary_data), None)
            if first_key:
                item.metrics = MetricsSummary.model_validate(summary_data[first_key])
        items.append(item)

    return BacktestListResponse(items=items, total=total)

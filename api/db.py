"""SQLite async persistence for backtest results."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

_DB_PATH = Path("backtest_results.db")

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS backtests (
    id             TEXT PRIMARY KEY,
    status         TEXT NOT NULL DEFAULT 'running',
    error_message  TEXT,
    created_at     TEXT NOT NULL,
    completed_at   TEXT,
    parameters     TEXT,
    results_json   TEXT,
    summary        TEXT
);
"""


async def get_db() -> aiosqlite.Connection:
    """Open (or reuse) an async SQLite connection."""
    db = await aiosqlite.connect(str(_DB_PATH))
    db.row_factory = aiosqlite.Row
    return db


async def init_db() -> None:
    """Create tables if they don't exist."""
    db = await get_db()
    try:
        await db.execute(_CREATE_TABLE)
        await db.commit()
        logger.info("Database initialised: %s", _DB_PATH)
    finally:
        await db.close()


async def create_backtest(
    backtest_id: str,
    parameters: dict,
) -> None:
    """Insert a new backtest record with status='running'."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO backtests (id, status, created_at, parameters) VALUES (?, ?, ?, ?)",
            (
                backtest_id,
                "running",
                datetime.utcnow().isoformat(),
                json.dumps(parameters, default=str),
            ),
        )
        await db.commit()
    finally:
        await db.close()


async def update_backtest_completed(
    backtest_id: str,
    results_json: str,
    summary: str,
) -> None:
    """Mark backtest as completed and store results."""
    db = await get_db()
    try:
        await db.execute(
            """UPDATE backtests
               SET status = 'completed',
                   completed_at = ?,
                   results_json = ?,
                   summary = ?
             WHERE id = ?""",
            (datetime.utcnow().isoformat(), results_json, summary, backtest_id),
        )
        await db.commit()
    finally:
        await db.close()


async def update_backtest_failed(backtest_id: str, error_message: str) -> None:
    """Mark backtest as failed."""
    db = await get_db()
    try:
        await db.execute(
            """UPDATE backtests
               SET status = 'failed',
                   completed_at = ?,
                   error_message = ?
             WHERE id = ?""",
            (datetime.utcnow().isoformat(), error_message, backtest_id),
        )
        await db.commit()
    finally:
        await db.close()


async def get_backtest(backtest_id: str) -> dict | None:
    """Fetch a single backtest record by ID."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM backtests WHERE id = ?", (backtest_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)
    finally:
        await db.close()


async def list_backtests(limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    """List backtests ordered by created_at DESC with pagination."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) FROM backtests")
        total = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT * FROM backtests ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows], total
    finally:
        await db.close()

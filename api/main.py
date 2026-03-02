"""FastAPI application entry point."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.db import init_db
from api.routers import backtest, data
from api.schemas import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    await init_db()
    yield


app = FastAPI(
    title="TW Futures Options Lab",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
_allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
]
_extra = os.environ.get("FRONTEND_URL")
if _extra:
    _allowed_origins.append(_extra)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Routers
app.include_router(backtest.router)
app.include_router(data.router)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        database="connected",
    )

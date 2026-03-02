# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Backtesting system for Taiwan micro index futures (微台指 TMF) with unlimited position building + weekly options PUT protection. Compares different futures-to-PUT hedging ratios (1:1, 2:1, etc.) with monthly capital contributions. All UI and logging is in Traditional Chinese (繁體中文).

## Commands

```bash
# Install dependencies (uses uv package manager)
uv sync
uv sync --extra dev  # includes pytest, pytest-cov, ruff

# Run backtest
python main.py

# Lint
ruff check src/
ruff format --check src/

# Run tests
pytest
pytest --cov=src --cov-report=term-missing

# Run a single test
pytest tests/test_foo.py::test_bar -v
```

## Architecture

```
src/
├── config.py              # All constants: margins, commissions, tax rates, premium ranges
├── models.py              # Frozen dataclasses: FuturesBar, OptionBar, positions, trades, snapshots
├── calendar/settlement.py # Taiwan trading calendar, settlement dates (weekly Wed + Fri from 2025-06-27)
├── data/taifex_loader.py  # Downloads & caches TAIFEX market data as monthly CSV chunks
├── strategy/
│   ├── engine.py          # Main backtesting engine — daily simulation loop
│   └── put_selector.py    # Selects protective PUT by premium range (deepest OTM in range)
└── report/metrics.py      # Performance metrics (Sharpe, MDD, returns) + matplotlib charts
```

**Data flow:** `main.py` → loads config → builds calendar → downloads data via `taifex_loader` → runs `engine.run_backtest()` per ratio → outputs via `report/metrics`.

### Key Design Decisions

- **Models are immutable** — all domain types use `@dataclass(frozen=True)`. `BacktestState` (mutable engine state) is the sole exception.
- **Data is MTX-based** — downloads use small Taiwan futures (MTX/小台指) price data; the engine applies TMF multiplier (NT$10/point vs MTX's NT$50) for P&L calculation.
- **PUT selection fallback chain** — in-range deepest OTM → closest to min premium → most expensive below min. Prefers contracts with volume.
- **Caching** — TAIFEX data is split into monthly chunks and cached as CSV in `src/data/cache/`. Subsequent runs skip downloads.

### Engine Daily Loop (`strategy/engine.py`)

1. Monthly contribution injection (if new month)
2. Settlement handling — settle expired PUTs, roll protection to next expiry
3. Position adding — if price up and margin sufficient, buy N futures + 1 PUT
4. Margin call check — binary search to find contracts to close (FIFO), close futures + corresponding PUTs
5. Mark-to-market all positions
6. Record `PortfolioSnapshot`

### Settlement Calendar (`calendar/settlement.py`)

Embeds Taiwan holidays for 2025–2026 (29 dates). Weekly settlement is every Wednesday; from 2025-06-27 onward, also every Friday. If settlement falls on a holiday, it moves to the prior trading day.

## Configuration

All strategy parameters live in [config.py](src/config.py): backtest period, margin ratios (8.5% original / 6.5% maintenance), PUT premium range (10–30 points), position sizing tiers, and trading costs. The `futures_per_put` ratio and `monthly_contribution` are set in `main.py` and passed to the engine.

## Python Version

Requires Python >= 3.11. Uses `from __future__ import annotations` throughout for PEP 604 union syntax.

# Plan: Shioaji Integration — 即時行情 + 手動下單 + 自動交易

## Context

目前系統只使用 TAIFEX 每日收盤資料做歷史回測。使用者希望整合永豐期貨的 Shioaji API，實現：
1. 歷史 tick 資料做更細粒度回測
2. 即時行情串流到前端（WebSocket）
3. 手動下單（前端送委託單）
4. 自動交易（策略引擎訊號 → 自動執行）

**使用者目前尚無永豐帳戶**，因此系統必須在無 Shioaji 帳戶的情況下可完整開發與測試（Mock/Paper 模式）。

---

## Phase 1: Data Provider 抽象層

**目標**: 將現有 TAIFEX loader 抽成 Protocol 介面，讓 Shioaji 或 Mock 可無痛替換。

### 新建檔案

| 檔案 | 說明 |
|------|------|
| `src/data/provider.py` | `HistoricalDataProvider` Protocol + `get_data_provider()` factory |
| `src/data/taifex_provider.py` | 包裝現有 `taifex_loader.py` 函式的 class |
| `src/data/mock_provider.py` | 產生合成資料的 mock 實作 |
| `src/models.py` (append) | 新增 `FuturesTick`, `OptionTick` frozen dataclass |
| `tests/test_provider.py` | Provider protocol 一致性測試 |
| `tests/fixtures/` | 測試用 JSON 固定資料 |

### 修改檔案

| 檔案 | 變更 |
|------|------|
| `api/services/runner.py` | `load_futures_range()` → `provider.load_futures()` |
| `main.py` | 同上 |
| `src/config.py` | 新增 `DATA_PROVIDER: str = "taifex"` |

### 關鍵設計

```python
class HistoricalDataProvider(Protocol):
    def load_futures(self, start: date, end: date) -> list[FuturesBar]: ...
    def load_options(self, start: date, end: date) -> list[OptionBar]: ...
```

- 回傳型別不變（`FuturesBar`, `OptionBar`），engine.py 零修改
- Factory 依 config 選擇 provider（`"taifex"` / `"shioaji"` / `"mock"`）

---

## Phase 2: Shioaji Client 封裝 + 歷史 Tick

**目標**: 建立 Shioaji SDK wrapper，實作 tick 資料抓取與 tick → bar 聚合。

### 新建檔案

| 檔案 | 說明 |
|------|------|
| `src/data/shioaji_client.py` | Shioaji 登入/登出生命週期管理（支援 context manager） |
| `src/data/shioaji_provider.py` | 實作 `HistoricalDataProvider`，映射 Shioaji tick → domain model |
| `src/data/tick_aggregator.py` | `aggregate_ticks_to_bars()` 支援 1D / 1H / 5m / 1m |
| `src/data/shioaji_mock.py` | Mock Shioaji client（不需安裝 shioaji 套件） |
| `tests/test_tick_aggregator.py` | 聚合正確性測試 |
| `tests/test_shioaji_client.py` | Mock client 生命週期測試 |

### 修改檔案

| 檔案 | 變更 |
|------|------|
| `pyproject.toml` | 新增 `[project.optional-dependencies] shioaji = ["shioaji>=1.0.0"]` |
| `src/data/provider.py` | Factory 註冊 Shioaji provider |
| `src/config.py` | 新增 `SHIOAJI_SIMULATION: bool = True` |

### 關鍵設計

- `shioaji` 為 **optional dependency**，lazy import + `try/except ImportError`
- CI 不需安裝 shioaji 即可通過
- 環境變數：`SHIOAJI_API_KEY`, `SHIOAJI_SECRET_KEY`

---

## Phase 3: WebSocket 即時行情

**目標**: FastAPI WebSocket 端點 + Shioaji 即時串流橋接 + 前端即時行情頁。

### 新建檔案

| 檔案 | 說明 |
|------|------|
| `api/ws/__init__.py` | WebSocket package |
| `api/ws/manager.py` | `ConnectionManager` — 多頻道 WebSocket 連線管理 |
| `api/routers/ws.py` | `ws://host/ws/market` 端點 |
| `api/services/market_stream.py` | `MarketStreamService` — Shioaji callback → asyncio Queue → WS broadcast |
| `api/services/mock_market_stream.py` | Mock 串流（random walk，1 tick/sec） |
| `api/schemas.py` (append) | `MarketTickMessage`, `WsSubscribeMessage` |
| `frontend/src/lib/ws.ts` | `useMarketStream()` hook（auto-reconnect + exponential backoff） |
| `frontend/src/types/market.ts` | `MarketTick` interface |
| `frontend/src/app/market/page.tsx` | 即時行情頁：報價、漲跌幅、迷你走勢圖 |
| `tests/test_ws_manager.py` | WebSocket 連線管理測試 |
| `tests/test_market_stream.py` | Mock 串流測試 |

### 修改檔案

| 檔案 | 變更 |
|------|------|
| `api/main.py` | 註冊 WS router + lifespan 啟動/停止 stream |
| `frontend/src/app/page.tsx` | 新增「即時行情」卡片 |
| `frontend/src/app/layout.tsx` | 新增「行情」導航連結 |

### 關鍵設計：Thread → Async 橋接

```python
# Shioaji callback (thread context)
def _on_tick(self, exchange, tick):
    self._queue.put_nowait(FuturesTick(...))  # asyncio.Queue, thread-safe

# MarketStreamService (async context)
async def _relay_loop(self):
    while self._running:
        tick = await self._queue.get()
        await self._manager.broadcast("market:futures", tick_to_dict(tick))
```

- 預設 `MARKET_STREAM=mock`，開發時不需 Shioaji
- Server-side 200ms debounce 避免前端過載

---

## Phase 4: 手動下單系統

**目標**: Protocol-based broker 介面 + Paper trading + 前端下單表單。

### 新建檔案

| 檔案 | 說明 |
|------|------|
| `src/broker/__init__.py` | Broker package |
| `src/broker/protocol.py` | `BrokerProtocol` + `OrderRequest` / `OrderResult` 定義 |
| `src/broker/paper.py` | `PaperBroker` — 模擬成交、追蹤部位、計算手續費/稅 |
| `src/broker/shioaji_broker.py` | `ShioajiBroker` — 映射到 Shioaji `sj.Order` API |
| `api/routers/orders.py` | `POST/GET/DELETE /api/orders` + `GET /api/positions` |
| `api/schemas.py` (append) | `OrderRequestSchema`, `OrderResultSchema` |
| `frontend/src/app/trading/page.tsx` | 交易頁：下單表單 + 委託列表 + 部位摘要 |
| `frontend/src/components/forms/OrderForm.tsx` | 下單表單元件 |
| `frontend/src/components/tables/OrderTable.tsx` | 委託單表格 |
| `frontend/src/components/tables/PositionTable.tsx` | 持倉表格 |
| `frontend/src/types/trading.ts` | `OrderRequest`, `OrderResult`, `Position` types |
| `frontend/src/lib/api.ts` (append) | `placeOrder()`, `listOrders()`, `cancelOrder()` |
| `tests/test_paper_broker.py` | Paper broker 生命週期測試 |
| `tests/test_orders_api.py` | Order API 整合測試 |

### 修改檔案

| 檔案 | 變更 |
|------|------|
| `api/main.py` | 註冊 orders router + lifespan 初始化 broker |
| `src/config.py` | 新增 `BROKER_MODE: str = "paper"` |
| `frontend/src/app/page.tsx` | 新增「手動交易」卡片 |
| `frontend/src/app/layout.tsx` | 新增「交易」導航連結 |
| `api/routers/ws.py` | 新增 `"orders"` channel 推送成交回報 |

### 安全設計：三重門檻

切換到真實下單需要同時滿足：
1. `BROKER_MODE=shioaji`
2. 有效的 `SHIOAJI_API_KEY` + `SHIOAJI_SECRET_KEY`
3. `SHIOAJI_SIMULATION=false`（預設 `true`）

UI 顯示醒目的「模擬交易」/「實盤交易」badge。

---

## Phase 5: 自動交易（策略訊號 → 執行）

**目標**: 即時引擎消費 tick → 產生 StrategySignal → 可選自動執行。

### 新建檔案

| 檔案 | 說明 |
|------|------|
| `src/strategy/signal.py` | `StrategySignal` frozen dataclass（ADD_POSITION / MARGIN_CALL / ROLL_PUT 等） |
| `src/strategy/live_engine.py` | `LiveEngine` — 消費 tick，產生 signal（不直接下單） |
| `src/strategy/signal_executor.py` | `SignalExecutor` — signal → OrderRequest，含安全控制 |
| `src/strategy/live_config.py` | `LiveEngineConfig`（持倉上限、每分鐘下單上限、每日虧損上限） |
| `api/routers/auto_trade.py` | `POST /api/auto-trade/start\|stop\|kill-switch` + `GET status\|signals` |
| `api/services/auto_trade_service.py` | `AutoTradeService` — 協調 LiveEngine + SignalExecutor + Stream |
| `frontend/src/app/auto-trade/page.tsx` | 自動交易儀表板：啟停、訊號列表、緊急停止按鈕 |
| `frontend/src/components/AutoTradeStatus.tsx` | 狀態指示元件 |
| `tests/test_live_engine.py` | 各情境訊號產生測試 |
| `tests/test_signal_executor.py` | 安全控制測試 |
| `tests/test_auto_trade_service.py` | 全流程整合測試 |

### 修改檔案

| 檔案 | 變更 |
|------|------|
| `api/main.py` | 註冊 auto-trade router |
| `api/routers/ws.py` | 新增 `"signals"` channel |
| `frontend/src/app/page.tsx` | 新增「自動交易」卡片 |
| `frontend/src/app/layout.tsx` | 新增「自動交易」導航連結 |
| `src/config.py` | 新增 live trading 常數 |

### 關鍵設計：Signal-First 架構

```
LiveEngine.on_futures_tick(tick) → [StrategySignal, ...]
                                        │
                              ┌─────────┼──────────┐
                              ▼         ▼          ▼
                          Log to DB  Push to WS  Execute?
                                                (if auto_execute=True)
```

- LiveEngine 只產生訊號，不直接下單
- `auto_execute` 預設 `False`（訊號顯示但不執行）
- 安全控制：每分鐘下單上限、持倉上限、每日虧損上限、交易時間檢查
- Kill switch：1 秒內停止所有交易
- LiveEngine 重用 `engine.py` 的純函式（`_can_add_position`, `_dynamic_margin` 等）

---

## Phase 依賴關係

```
Phase 1 (Provider 抽象層)
    │
    ▼
Phase 2 (Shioaji Client + Tick)
    │
    ├──→ Phase 3 (WebSocket 即時行情) ──→ Phase 5 (自動交易)
    │                                         ▲
    └──→ Phase 4 (手動下單) ─────────────────┘
```

Phase 3 和 4 可在 Phase 2 完成後**並行開發**。Phase 5 依賴 3 + 4。

---

## Git Workflow

- 每個 Phase 一個 branch + PR
- Branch naming: `feat/shioaji-phase-N-description`
- 每個 PR 獨立可合併、可部署

## Verification

每個 Phase 完成時：
1. `pytest --cov=src --cov-report=term-missing` — 新程式碼覆蓋率 >= 80%
2. `ruff check src/ api/` + `ruff format --check src/ api/` — lint 通過
3. `cd frontend && pnpm build` — 前端建置成功
4. 手動測試對應功能（mock 模式下即可驗證）
5. 無 `shioaji` 套件安裝時全部測試仍通過

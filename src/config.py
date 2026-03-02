"""回測系統常數與設定。"""

from datetime import date

# ── 回測期間 ──
BACKTEST_START = date(2025, 1, 1)
BACKTEST_END = date(2026, 2, 28)

# ── 微型台指期貨 (TMF) ──
# 注意：微台指與小台指追蹤同一指數，僅乘數/保證金不同
# 回測沿用小台指 (MTX) 行情資料，透過乘數換算為微台損益
FUTURES_MULTIPLIER: int = 10  # 微台指每點 NT$10（小台 50、大台 200）
FUTURES_TICK_SIZE: float = 1  # 最小跳動點
FUTURES_CODE: str = "TMF"  # 商品代碼（報表顯示用）
OPTIONS_CODE: str = "TXO_PUT"  # 選擇權代碼（報表顯示用）
FUTURES_NAME: str = "微台指"  # 中文名稱（報表顯示用）
# 保證金比例（動態計算：指數 × 乘數 × 比例）
FUTURES_MARGIN_RATIO: float = 0.085  # 原始保證金約為合約價值的 8.5%
FUTURES_MAINTENANCE_RATIO: float = 0.065  # 維持保證金約為合約價值的 6.5%

# ── 台指週選擇權 (TXO) ──
TXO_MULTIPLIER: int = 50  # 每點 NT$50（選擇權乘數不變）
STRIKE_INTERVAL: int = 100  # 履約價間距（指數 > 10,000 時）

# ── 策略參數 ──
INITIAL_CAPITAL: int = 200_000  # 初始資金 NT$20 萬
RISK_FREE_RATE: float = 0.015  # 無風險利率 1.5%（年化）

# ── PUT 選擇（權利金區間） ──
# 選擇權利金在此區間內、最深度價外的 PUT（最便宜的有效保護）
PUT_PREMIUM_MIN: float = 10.0  # 最低權利金（點）→ NT$500/口
PUT_PREMIUM_MAX: float = 30.0  # 最高權利金（點）→ NT$1,500/口

# ── 動態資金控管 ──
# 權益達到門檻後，每次新倉只動用可用保證金的一定比例
POSITION_SIZING_TIERS: list[tuple[int, float]] = [
    (4_000_000, 0.30),  # 權益 >= 400 萬 → 動用 30%
    (2_000_000, 0.50),  # 權益 >= 200 萬 → 動用 50%
    (0, 1.00),  # 權益 < 200 萬 → 動用 100%（全額）
]

# ── 期貨對 PUT 比例 ──
# N 口微台指配 1 口 TXO PUT
# 1 口 TXO PUT (50元/點) = 5 口微台 (10元/點) 的曝險
DOLLAR_NEUTRAL_RATIO: int = TXO_MULTIPLIER // FUTURES_MULTIPLIER  # = 5
FUTURES_PER_PUT: int = DOLLAR_NEUTRAL_RATIO  # 預設等值保護（由 main.py 覆寫）

# ── 交易成本 ──
FUTURES_COMMISSION: int = 8  # 微台指手續費 NT$/口（單邊，比小台便宜）
OPTIONS_COMMISSION: int = 15  # 選擇權手續費 NT$/口（單邊）
FUTURES_TAX_RATE: float = 0.00002  # 期貨交易稅 十萬分之二
OPTIONS_TAX_RATE: float = 0.001  # 選擇權交易稅 千分之一

# ── 滑價模型 ──
FUTURES_SLIPPAGE_POINTS: float = 2.0  # 期貨滑價（點）
OPTIONS_SPREAD_RATIO: float = 0.30  # PUT 買賣價差佔權利金比例（30%）

# ── 期貨轉倉成本 ──
FUTURES_ROLLOVER_COST_POINTS: float = 5.0  # 轉倉價差（點）

# ── 加倉條件過濾 ──
ADD_MIN_PRICE_CHANGE_PCT: float = 0.005  # 最低漲幅 0.5%
ADD_MA_PERIOD: int = 10  # 趨勢過濾：收盤 > N 日均線
ADD_COOLDOWN_DAYS: int = 3  # 冷卻期：兩次加倉至少間隔 N 個交易日

# ── 自動補入資金 ──
ALLOW_AUTO_INJECTION: bool = False  # 預設關閉，僅靠月投

# ── 風控 ──
TARGET_RISK_RATIO: float = 1.10  # 目標風險指標（equity / margin），110% = 積極建倉
PAUSE_ADD_DRAWDOWN_PCT: float = 0.15  # 回撤 > 15% 時暫停加倉
TRAILING_STOP_ENABLED: bool = False  # 移動停損（預設關閉）
TRAILING_STOP_POINTS: float = 500.0  # 移動停損距離（點）

# ── 資料快取 ──
CACHE_DIR: str = "src/data/cache"

# ── TAIFEX 下載 URL ──
TAIFEX_FUTURES_URL: str = "https://www.taifex.com.tw/cht/3/futDataDown"
TAIFEX_OPTIONS_URL: str = "https://www.taifex.com.tw/cht/3/optDataDown"

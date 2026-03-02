"""績效指標計算與圖表輸出。"""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 無頭模式
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import numpy as np

from src.config import FUTURES_CODE, FUTURES_NAME, INITIAL_CAPITAL, OPTIONS_CODE, RISK_FREE_RATE
from src.models import CashFlow, PortfolioSnapshot, Trade

# 設定中文字體 — 支援環境變數 CJK_FONT_PATH 覆寫，再嘗試常見路徑
import os as _os

_CJK_FONT_PATHS = [p for p in [_os.environ.get("CJK_FONT_PATH", "")] if p]
_CJK_FONT_PATHS += [
    str(Path.home() / "Library/Fonts/NotoSansTC-VariableFont_wght.ttf"),
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]
for _font_path in _CJK_FONT_PATHS:
    if _font_path and Path(_font_path).exists():
        fm.fontManager.addfont(_font_path)

plt.rcParams["font.family"] = [
    "Noto Sans TC",
    "Heiti TC",
    "STHeiti",
    "Arial Unicode MS",
    "sans-serif",
]
plt.rcParams["axes.unicode_minus"] = False


def total_return(snapshots: list[PortfolioSnapshot], capital: float = INITIAL_CAPITAL) -> float:
    """總報酬率。"""
    if not snapshots:
        return 0.0
    return (snapshots[-1].equity - capital) / capital


def annualized_return(
    snapshots: list[PortfolioSnapshot], capital: float = INITIAL_CAPITAL
) -> float:
    """年化報酬率。"""
    if len(snapshots) < 2:
        return 0.0
    days = (snapshots[-1].trade_date - snapshots[0].trade_date).days
    if days <= 0:
        return 0.0
    tr = total_return(snapshots, capital)
    growth = 1 + tr
    if growth <= 0:
        return tr
    return growth ** (365 / days) - 1


def max_drawdown(
    snapshots: list[PortfolioSnapshot],
) -> tuple[float, float, float, date | None, date | None]:
    """最大回撤 (MDD)。回傳 (回撤比例, 回撤金額, 高點權益, 高點日期, 低點日期)。"""
    if not snapshots:
        return 0.0, 0.0, 0.0, None, None

    peak = snapshots[0].equity
    peak_date = snapshots[0].trade_date
    mdd = 0.0
    mdd_amount = 0.0
    mdd_peak_equity = 0.0
    mdd_peak_date: date | None = None
    mdd_trough_date: date | None = None

    for snap in snapshots:
        if snap.equity > peak:
            peak = snap.equity
            peak_date = snap.trade_date

        drawdown = (peak - snap.equity) / peak if peak > 0 else 0
        if drawdown > mdd:
            mdd = drawdown
            mdd_amount = peak - snap.equity
            mdd_peak_equity = peak
            mdd_peak_date = peak_date
            mdd_trough_date = snap.trade_date

    return mdd, mdd_amount, mdd_peak_equity, mdd_peak_date, mdd_trough_date


def sharpe_ratio(snapshots: list[PortfolioSnapshot]) -> float:
    """Sharpe Ratio（年化）。"""
    if len(snapshots) < 2:
        return 0.0

    daily_returns = []
    for i in range(1, len(snapshots)):
        prev_eq = snapshots[i - 1].equity
        if prev_eq > 0:
            daily_returns.append((snapshots[i].equity - prev_eq) / prev_eq)

    if not daily_returns:
        return 0.0

    arr = np.array(daily_returns)
    mean_daily = float(np.mean(arr))
    std_daily = float(np.std(arr, ddof=1))

    if std_daily == 0:
        return 0.0

    daily_rf = RISK_FREE_RATE / 252
    return (mean_daily - daily_rf) / std_daily * math.sqrt(252)


def xirr(cash_flows: list[CashFlow]) -> float:
    """計算 XIRR（年化內部報酬率），使用 Newton-Raphson 法。

    cash_flows: amount < 0 表示投入，amount > 0 表示取回。
    """
    if len(cash_flows) < 2:
        return 0.0

    base_date = cash_flows[0].date

    def npv(rate: float) -> float:
        return sum(
            cf.amount / (1 + rate) ** ((cf.date - base_date).days / 365.0) for cf in cash_flows
        )

    def npv_derivative(rate: float) -> float:
        return sum(
            -cf.amount
            * ((cf.date - base_date).days / 365.0)
            / (1 + rate) ** ((cf.date - base_date).days / 365.0 + 1)
            for cf in cash_flows
        )

    rate = 0.1  # 初始猜測
    for _ in range(200):
        f = npv(rate)
        f_prime = npv_derivative(rate)
        if abs(f_prime) < 1e-12:
            break
        new_rate = rate - f / f_prime
        # 限制範圍避免發散
        new_rate = max(new_rate, -0.99)
        if abs(new_rate - rate) < 1e-8:
            return new_rate
        rate = new_rate
    return rate


def win_rate(trades: list[Trade]) -> float:
    """勝率（已實現交易）。"""
    realized = [t for t in trades if t.action in ("SETTLE", "SELL") and t.pnl != 0]
    if not realized:
        return 0.0
    wins = sum(1 for t in realized if t.pnl > 0)
    return wins / len(realized)


def total_commission_and_tax(trades: list[Trade]) -> tuple[float, float]:
    """總手續費和稅金。"""
    comm = sum(t.commission for t in trades)
    tax = sum(t.tax for t in trades)
    return comm, tax


def print_summary(
    snapshots: list[PortfolioSnapshot],
    trades: list[Trade],
    total_injected: float = 0.0,
    total_monthly: float = 0.0,
    futures_per_put: int = 1,
) -> None:
    """印出回測摘要。"""
    if not snapshots:
        print("無回測資料。")
        return

    total_capital = INITIAL_CAPITAL + total_injected + total_monthly
    tr = total_return(snapshots, total_capital)
    ar = annualized_return(snapshots, total_capital)
    mdd, mdd_amount, mdd_peak_eq, mdd_peak, mdd_trough = max_drawdown(snapshots)
    sr = sharpe_ratio(snapshots)
    wr = win_rate(trades)
    comm, tax = total_commission_and_tax(trades)

    last = snapshots[-1]
    total_trades = len([t for t in trades if t.action == "BUY" and t.instrument == FUTURES_CODE])

    min_equity = min(s.equity for s in snapshots)

    ratio_str = f"{futures_per_put}口{FUTURES_NAME}:1口PUT"

    print("=" * 60)
    print(f"  {FUTURES_NAME}加倉 + 週選 PUT 保護 回測結果 ({ratio_str})")
    print("=" * 60)
    print(f"  回測期間:  {snapshots[0].trade_date} ~ {snapshots[-1].trade_date}")
    print(f"  交易天數:  {len(snapshots)} 天")
    print(f"  初始資金:  NT${INITIAL_CAPITAL:,.0f}")
    if total_monthly > 0:
        print(f"  每月定投:  NT${total_monthly:,.0f}")
    if total_injected > 0:
        print(f"  不足補入:  NT${total_injected:,.0f}")
    if total_monthly > 0 or total_injected > 0:
        print(f"  總投入:    NT${total_capital:,.0f}")
    print(f"  最終權益:  NT${last.equity:,.0f}")
    print(f"  最低權益:  NT${min_equity:,.0f}")
    print("-" * 60)
    print(f"  總報酬率:    {tr:+.2%}")
    print(f"  年化報酬率:  {ar:+.2%}")
    print(f"  最大回撤:    {mdd:.2%} (NT${mdd_amount:,.0f})")
    if mdd_peak and mdd_trough:
        print(f"    高點: {mdd_peak} (NT${mdd_peak_eq:,.0f})  低點: {mdd_trough}")
    print(f"  Sharpe Ratio: {sr:.2f}")
    print("-" * 60)
    print(f"  加倉次數:      {total_trades} 次")
    print(f"  最終持倉口數:  {last.futures_count} 口")
    print(f"  累計 PUT 成本: NT${last.total_put_cost:,.0f}")
    print(f"  總手續費:      NT${comm:,.0f}")
    print(f"  總稅金:        NT${tax:,.0f}")
    print(f"  PUT 結算勝率:  {wr:.1%}")
    print("=" * 60)


def print_position_details(
    snapshots: list[PortfolioSnapshot],
    trades: list[Trade],
    futures_per_put: int = 1,
) -> None:
    """印出每筆加倉的期貨與對應 PUT 合約明細。"""
    if not trades:
        print("無交易記錄。")
        return

    fut_buys = [t for t in trades if t.action == "BUY" and t.instrument == FUTURES_CODE]
    put_buys = [t for t in trades if t.action == "BUY" and t.instrument == OPTIONS_CODE]

    print()
    print("=" * 100)
    print(f"  加倉明細（每 {futures_per_put} 口{FUTURES_NAME} + 1 口 PUT）")
    print("=" * 100)
    print(
        f"  {'#':>3} {'日期':<12} {'期貨進場價':>10} {'期貨口數':>8}"
        f"{'PUT履約價':>10} {'PUT到期日':<12} {'PUT權利金':>10}"
    )
    print("-" * 100)

    put_idx = 0
    for i, ft in enumerate(fut_buys):
        strike_str = "-"
        expiry_str = "-"
        premium_str = "-"
        if put_idx < len(put_buys) and put_buys[put_idx].trade_date == ft.trade_date:
            pt = put_buys[put_idx]
            strike_str = f"{pt.strike:,}" if pt.strike else "-"
            expiry_str = str(pt.expiry) if pt.expiry else "-"
            premium_str = f"{pt.price:.1f}"
            put_idx += 1

        print(
            f"  {i + 1:>3} {ft.trade_date!s:<12} {ft.price:>10,.0f} {ft.contracts:>8}"
            f"{strike_str:>10} {expiry_str:<12} {premium_str:>10}"
        )
    print(f"  合計加倉: {len(fut_buys)} 次")

    # PUT 換倉明細
    rolls = [t for t in trades if t.action == "ROLL" and t.instrument == OPTIONS_CODE]
    if rolls:
        print()
        print("=" * 100)
        print("  PUT 換倉明細（結算日自動換到下一期）")
        print("=" * 100)
        print(
            f"  {'日期':<12} {'履約價':>8} {'到期日':<12} "
            f"{'權利金':>8} {'口數':>6} {'成本(NT$)':>12}"
        )
        print("-" * 100)
        for t in rolls:
            strike_str = f"{t.strike:,}" if t.strike else "-"
            expiry_str = str(t.expiry) if t.expiry else "-"
            cost = t.price * 50 * t.contracts + t.commission
            print(
                f"  {t.trade_date!s:<12} {strike_str:>8} {expiry_str:<12} "
                f"{t.price:>8.1f} {t.contracts:>6} {cost:>12,.0f}"
            )
        roll_total = sum(t.price * 50 * t.contracts + t.commission for t in rolls)
        print(f"  換倉總成本: NT${roll_total:,.0f}")

    # PUT 結算明細
    settles = [t for t in trades if t.action == "SETTLE" and t.instrument == OPTIONS_CODE]
    if settles:
        print()
        print("=" * 100)
        print("  PUT 結算明細")
        print("=" * 100)
        print(
            f"  {'日期':<12} {'履約價':>8} {'到期日':<12} "
            f"{'結算價':>8} {'口數':>6} {'損益(NT$)':>12}"
        )
        print("-" * 100)
        for t in settles:
            strike_str = f"{t.strike:,}" if t.strike else "-"
            expiry_str = str(t.expiry) if t.expiry else "-"
            print(
                f"  {t.trade_date!s:<12} {strike_str:>8} {expiry_str:<12} "
                f"{t.price:>8.1f} {t.contracts:>6} {t.pnl:>12,.0f}"
            )
        settle_pnl = sum(t.pnl for t in settles)
        print(f"  PUT 結算總損益: NT${settle_pnl:,.0f}")

    # 期貨平倉明細
    sells = [t for t in trades if t.action == "SELL" and t.instrument == FUTURES_CODE]
    if sells:
        print()
        print("=" * 100)
        print("  期貨平倉明細")
        print("=" * 100)
        print(f"  {'日期':<12} {'平倉價':>10} {'口數':>6} {'損益(NT$)':>12}")
        print("-" * 100)
        for t in sells:
            print(f"  {t.trade_date!s:<12} {t.price:>10,.0f} {t.contracts:>6} {t.pnl:>12,.0f}")
        sell_pnl = sum(t.pnl for t in sells)
        print(f"  期貨平倉總損益: NT${sell_pnl:,.0f}")


def plot_results(
    snapshots: list[PortfolioSnapshot],
    trades: list[Trade] | None = None,
    output_path: str = "backtest_result.png",
    total_injected: float = 0.0,
    total_monthly: float = 0.0,
    futures_per_put: int = 1,
) -> None:
    """繪製完整回測報告圖表（5 panel + 績效摘要）。"""
    if not snapshots:
        return

    dates = [s.trade_date for s in snapshots]
    equity = [s.equity for s in snapshots]
    cash = [s.cash for s in snapshots]
    futures_count = [s.futures_count for s in snapshots]
    puts_count = [s.puts_count for s in snapshots]
    daily_pnl = [s.daily_pnl for s in snapshots]
    put_cost = [s.total_put_cost for s in snapshots]

    # 回撤序列
    peak = snapshots[0].equity
    drawdown_pct: list[float] = []
    for s in snapshots:
        if s.equity > peak:
            peak = s.equity
        dd = (peak - s.equity) / peak * 100 if peak > 0 else 0
        drawdown_pct.append(-dd)

    # 績效指標
    total_capital = INITIAL_CAPITAL + total_injected + total_monthly
    tr = total_return(snapshots, total_capital)
    ar = annualized_return(snapshots, total_capital)
    mdd, mdd_amount, _, _, _ = max_drawdown(snapshots)
    sr = sharpe_ratio(snapshots)
    min_eq = min(s.equity for s in snapshots)
    last = snapshots[-1]

    trades_list = trades or []
    total_buys = len([t for t in trades_list if t.action == "BUY" and t.instrument == FUTURES_CODE])
    ratio_str = f"{futures_per_put}:{FUTURES_NAME}:1PUT"

    fig = plt.figure(figsize=(16, 22))
    gs = fig.add_gridspec(
        6,
        1,
        height_ratios=[0.6, 1.2, 0.8, 0.8, 0.8, 0.8],
        hspace=0.35,
    )

    # Panel 0: 摘要
    ax0 = fig.add_subplot(gs[0])
    ax0.axis("off")

    monthly_line = f"\n每月定投: NT${total_monthly:>12,.0f}" if total_monthly > 0 else ""
    inject_line = f"\n不足補入: NT${total_injected:>12,.0f}" if total_injected > 0 else ""
    capital_line = (
        f"\n總投入:   NT${total_capital:>12,.0f}"
        if (total_monthly > 0 or total_injected > 0)
        else ""
    )
    summary_left = (
        f"回測期間: {snapshots[0].trade_date} ~ {snapshots[-1].trade_date}\n"
        f"初始資金: NT${INITIAL_CAPITAL:>12,}\n"
        f"最終權益: NT${last.equity:>12,.0f}\n"
        f"最低權益: NT${min_eq:>12,.0f}"
        f"{monthly_line}{inject_line}{capital_line}\n"
        f"累計 PUT 成本: NT${last.total_put_cost:>12,.0f}"
    )
    summary_right = (
        f"總報酬率:   {tr:>+10.2%}\n"
        f"年化報酬:   {ar:>+10.2%}\n"
        f"最大回撤:   {mdd:>10.2%}\n"
        f"Sharpe:     {sr:>10.2f}\n"
        f"加倉次數:   {total_buys:>10} 次"
    )

    ax0.text(
        0.02,
        0.95,
        summary_left,
        transform=ax0.transAxes,
        fontsize=11,
        verticalalignment="top",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#e8f4fd", "alpha": 0.8},
    )
    ax0.text(
        0.52,
        0.95,
        summary_right,
        transform=ax0.transAxes,
        fontsize=11,
        verticalalignment="top",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#fdf2e8", "alpha": 0.8},
    )
    ax0.set_title(
        f"{FUTURES_NAME}加倉 + 週選 PUT 保護 回測報告 ({ratio_str})",
        fontsize=15,
        fontweight="bold",
        pad=12,
    )

    fmt_nt = plt.FuncFormatter(lambda x, _: f"{x:,.0f}")

    # Panel 1: 權益曲線
    ax1 = fig.add_subplot(gs[1])
    ax1.plot(dates, equity, color="#1a73e8", linewidth=1.8, label="總權益", zorder=3)
    ax1.fill_between(dates, equity, alpha=0.08, color="#1a73e8")
    ax1.plot(dates, cash, color="#34a853", linewidth=0.8, alpha=0.6, label="現金")
    ax1.axhline(y=INITIAL_CAPITAL, color="gray", linestyle="--", alpha=0.4, label="初始資金")
    ax1.axhline(y=0, color="red", linestyle="-", alpha=0.3, linewidth=0.5)
    max_eq_idx = max(range(len(equity)), key=lambda i: equity[i])
    min_eq_idx = min(range(len(equity)), key=lambda i: equity[i])
    ax1.annotate(
        f"最高 {equity[max_eq_idx]:,.0f}",
        xy=(dates[max_eq_idx], equity[max_eq_idx]),
        xytext=(0, 10),
        textcoords="offset points",
        fontsize=8,
        ha="center",
        color="#1a73e8",
        arrowprops={"arrowstyle": "->", "color": "#1a73e8", "lw": 0.8},
    )
    ax1.annotate(
        f"最低 {equity[min_eq_idx]:,.0f}",
        xy=(dates[min_eq_idx], equity[min_eq_idx]),
        xytext=(0, -18),
        textcoords="offset points",
        fontsize=8,
        ha="center",
        color="red",
        arrowprops={"arrowstyle": "->", "color": "red", "lw": 0.8},
    )
    ax1.set_ylabel("NT$")
    ax1.set_title("權益曲線", fontsize=11)
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(True, alpha=0.2)
    ax1.yaxis.set_major_formatter(fmt_nt)

    # Panel 2: 持倉口數
    ax2 = fig.add_subplot(gs[2], sharex=ax1)
    ax2.fill_between(dates, futures_count, alpha=0.5, color="#34a853", label="期貨口數")
    ax2.plot(dates, puts_count, color="#ea4335", linewidth=0.8, alpha=0.7, label="PUT 口數")
    ax2.set_ylabel("口數")
    ax2.set_title("持倉口數（期貨 vs PUT）", fontsize=11)
    ax2.legend(loc="upper left", fontsize=9)
    ax2.grid(True, alpha=0.2)

    # Panel 3: 回撤
    ax3 = fig.add_subplot(gs[3], sharex=ax1)
    ax3.fill_between(dates, drawdown_pct, 0, alpha=0.4, color="#ea4335")
    ax3.plot(dates, drawdown_pct, color="#ea4335", linewidth=0.8)
    ax3.set_ylabel("回撤 (%)")
    ax3.set_title("回撤幅度", fontsize=11)
    ax3.grid(True, alpha=0.2)
    ax3.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))

    # Panel 4: 每日損益
    ax4 = fig.add_subplot(gs[4], sharex=ax1)
    pos_pnl = [p if p >= 0 else 0 for p in daily_pnl]
    neg_pnl = [p if p < 0 else 0 for p in daily_pnl]
    ax4.bar(dates, pos_pnl, color="#34a853", alpha=0.6, width=1, label="獲利")
    ax4.bar(dates, neg_pnl, color="#ea4335", alpha=0.6, width=1, label="虧損")
    ax4.set_ylabel("NT$")
    ax4.set_title("每日損益", fontsize=11)
    ax4.legend(loc="upper left", fontsize=9)
    ax4.grid(True, alpha=0.2)
    ax4.yaxis.set_major_formatter(fmt_nt)

    # Panel 5: 累計 PUT 成本
    ax5 = fig.add_subplot(gs[5], sharex=ax1)
    ax5.plot(dates, put_cost, color="#ea4335", linewidth=1.5, label="累計 PUT 成本")
    ax5.fill_between(dates, put_cost, alpha=0.1, color="#ea4335")
    ax5.set_ylabel("NT$")
    ax5.set_title("累計 PUT 保護成本", fontsize=11)
    ax5.legend(loc="upper left", fontsize=9)
    ax5.grid(True, alpha=0.2)
    ax5.yaxis.set_major_formatter(fmt_nt)

    ax5.xaxis.set_major_locator(mdates.MonthLocator())
    ax5.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.setp(ax5.xaxis.get_majorticklabels(), rotation=45)

    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"\n圖表已儲存至: {output_path}")

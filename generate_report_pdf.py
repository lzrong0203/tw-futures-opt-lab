"""產生 1:1 微台指回測報告 PDF。"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── 中文字型註冊 ──
FONT_PATH = str(Path.home() / "Library/Fonts/NotoSansTC-VariableFont_wght.ttf")
pdfmetrics.registerFont(TTFont("NotoSansTC", FONT_PATH))

# ── 自定義樣式 ──
styles = getSampleStyleSheet()

FONT_NAME = "NotoSansTC"

style_title = ParagraphStyle(
    "CTitle",
    parent=styles["Title"],
    fontName=FONT_NAME,
    fontSize=22,
    leading=28,
    spaceAfter=12,
    alignment=TA_CENTER,
)

style_h1 = ParagraphStyle(
    "CH1",
    parent=styles["Heading1"],
    fontName=FONT_NAME,
    fontSize=16,
    leading=22,
    spaceBefore=18,
    spaceAfter=8,
    textColor=colors.HexColor("#1a5276"),
)

style_h2 = ParagraphStyle(
    "CH2",
    parent=styles["Heading2"],
    fontName=FONT_NAME,
    fontSize=13,
    leading=18,
    spaceBefore=12,
    spaceAfter=6,
    textColor=colors.HexColor("#2c3e50"),
)

style_body = ParagraphStyle(
    "CBody",
    parent=styles["Normal"],
    fontName=FONT_NAME,
    fontSize=10,
    leading=16,
    spaceAfter=4,
)

style_body_bold = ParagraphStyle(
    "CBodyBold",
    parent=style_body,
    fontName=FONT_NAME,
    fontSize=10,
    leading=16,
    spaceAfter=4,
)

style_small = ParagraphStyle(
    "CSmall",
    parent=styles["Normal"],
    fontName=FONT_NAME,
    fontSize=8,
    leading=12,
    textColor=colors.grey,
)

style_table_header = ParagraphStyle(
    "CTableHeader",
    fontName=FONT_NAME,
    fontSize=9,
    leading=12,
    alignment=TA_CENTER,
    textColor=colors.white,
)

style_table_cell = ParagraphStyle(
    "CTableCell",
    fontName=FONT_NAME,
    fontSize=9,
    leading=12,
    alignment=TA_RIGHT,
)

style_table_cell_left = ParagraphStyle(
    "CTableCellLeft",
    fontName=FONT_NAME,
    fontSize=9,
    leading=12,
    alignment=TA_LEFT,
)


def _p(text: str, style: ParagraphStyle = style_body) -> Paragraph:
    return Paragraph(text, style)


def _make_table(
    headers: list[str],
    rows: list[list[str]],
    col_widths: list[float] | None = None,
) -> Table:
    """建立帶樣式的表格。"""
    header_cells = [_p(h, style_table_header) for h in headers]
    data = [header_cells]
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            s = style_table_cell_left if i == 0 else style_table_cell
            cells.append(_p(cell, s))
        data.append(cells)

    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
                ("TOPPADDING", (0, 1), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return t


def build_report(output_path: str = "backtest_1to1_report.pdf") -> None:
    """建立 1:1 回測報告 PDF。"""
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    story: list = []

    # ── 標題 ──
    story.append(_p("微台指 1:1 PUT 保護策略回測報告", style_title))
    story.append(_p("回測期間: 2025/01/01 ~ 2026/02/28 | 每月定投 NT$30,000", style_small))
    story.append(Spacer(1, 12))

    # ── 1. 策略概述 ──
    story.append(_p("一、策略概述", style_h1))
    story.append(_p(
        "本策略以微型台指期貨 (TMF) 做多為核心，每口期貨搭配 1 口台指週選 PUT "
        "做為下檔保護（1:1 比例）。初始資金 NT$200,000，另設每月定期投入 "
        "NT$30,000 機制，模擬長期定期定額的投資情境。"
    ))

    # ── 2. 策略規則 ──
    story.append(_p("二、策略規則", style_h1))

    story.append(_p("2.1 進場與加倉", style_h2))
    story.append(_p("&bull; 每個交易日檢查是否有足夠資金開立新倉位（1 口期貨 + 1 口 PUT）"))
    story.append(_p("&bull; 保證金 = 台指期貨指數 x 10 x 8.5%（約 NT$18,700 @ 22,000）"))
    story.append(_p("&bull; PUT 成本 = 權利金（點）x NT$50/點（約 NT$500 ~ NT$1,500/口）"))
    story.append(_p("&bull; 資金充足時持續加倉，每日最多加一組"))
    story.append(_p("&bull; 動態資金控管：權益 >= 200 萬用 50%，>= 400 萬用 30%"))

    story.append(_p("2.2 PUT 選擇邏輯", style_h2))
    story.append(_p("&bull; 標的：台指週選擇權 (TXO)，僅選 PUT"))
    story.append(_p("&bull; 到期日：最近一個週三結算日"))
    story.append(_p("&bull; 篩選條件：價外（strike &lt; 期貨價格）且權利金在 10~30 點之間"))
    story.append(_p("&bull; 在符合條件中選最深度價外（最低 strike），即成本最低的有效保護"))
    story.append(_p("&bull; Fallback：若區間內無候選人，選最接近 10 點的 PUT"))

    story.append(_p("2.3 結算與換倉", style_h2))
    story.append(_p("&bull; 每週三 PUT 到期結算，價內自動行使、價外歸零"))
    story.append(_p("&bull; 結算後立即買入新一週的 PUT，確保 100% 保護率"))
    story.append(_p("&bull; 現金不足買齊 PUT 時，逐口平倉期貨直到全部有保護"))

    story.append(_p("2.4 風控機制", style_h2))
    story.append(_p("&bull; 維持保證金 = 指數 x 10 x 6.5%"))
    story.append(_p("&bull; 權益低於維持保證金時觸發追繳，批次平倉至安全水位"))
    story.append(_p("&bull; 資金不足開新倉時，自動補入差額（模擬追加資金）"))

    story.append(_p("2.5 每月定投", style_h2))
    story.append(_p("&bull; 每月第一個交易日注入 NT$30,000 至現金帳戶"))
    story.append(_p("&bull; 14 個月共投入 NT$420,000"))

    # ── 3. 回測結果 ──
    story.append(_p("三、回測結果總覽", style_h1))

    results_table = _make_table(
        headers=["項目", "數值"],
        rows=[
            ["初始資金", "NT$200,000"],
            ["每月定投（14 個月）", "NT$420,000"],
            ["不足補入", "NT$201,818"],
            ["總投入資金", "NT$821,818"],
            ["最終權益", "NT$8,003,158"],
            ["總報酬率", "+873.8%"],
            ["年化報酬率", "+633.2%"],
            ["最大回撤 (MDD)", "67.9%"],
            ["Sharpe Ratio", "1.73"],
            ["最低權益", "NT$536,252"],
        ],
        col_widths=[8 * cm, 6 * cm],
    )
    story.append(results_table)
    story.append(Spacer(1, 12))

    # ── 4. 交易統計 ──
    story.append(_p("四、交易統計", style_h1))

    trade_table = _make_table(
        headers=["項目", "數值"],
        rows=[
            ["加倉次數", "155 次"],
            ["最終持有期貨", "106 口"],
            ["最終持有 PUT", "106 口"],
            ["保護覆蓋率", "100%（期貨 = PUT）"],
            ["PUT 總成本", "NT$3,069,435"],
            ["PUT 結算獲利次數", "約 1.7%（多數歸零）"],
            ["交易手續費（期貨）", "NT$8/口（單邊）"],
            ["交易手續費（選擇權）", "NT$15/口（單邊）"],
        ],
        col_widths=[8 * cm, 6 * cm],
    )
    story.append(trade_table)
    story.append(Spacer(1, 12))

    # ── 5. 損益拆解 ──
    story.append(_p("五、損益拆解", style_h1))
    story.append(_p(
        "期貨做多的獲利來自台指從 ~22,000 上漲至 ~24,000 的趨勢行情，"
        "加上持續加倉的複利效應。PUT 保護雖然大多數週歸零（價外到期），"
        "但在 2025/04 急跌時發揮了保護作用，有效限制了下檔虧損。"
    ))

    pnl_table = _make_table(
        headers=["損益項目", "金額", "說明"],
        rows=[
            ["期貨浮動損益", "正值（主要獲利來源）", "多頭持倉 x 指數漲幅 x NT$10"],
            ["PUT 保護成本", "-NT$3,069,435", "每週買入 PUT 的權利金支出"],
            ["PUT 結算收入", "少量", "僅約 1.7% 到期時為價內"],
            ["交易稅與手續費", "小額", "期貨稅率十萬分之二，選擇權千分之一"],
            ["淨損益", "+NT$7,181,340", "最終權益 - 總投入"],
        ],
        col_widths=[4 * cm, 4.5 * cm, 7.5 * cm],
    )
    story.append(pnl_table)
    story.append(Spacer(1, 12))

    # ── 6. PUT 合約特性 ──
    story.append(_p("六、PUT 合約特性", style_h1))

    put_table = _make_table(
        headers=["項目", "內容"],
        rows=[
            ["選擇權類型", "台指週選 PUT (TXO)"],
            ["到期頻率", "每週三"],
            ["選擇條件", "價外、權利金 10~30 點"],
            ["乘數", "NT$50/點"],
            ["每口成本範圍", "NT$500 ~ NT$1,500"],
            ["典型 strike", "低於期貨價格 300~800 點"],
            ["保護效果", "大跌時 PUT 增值，抵消期貨虧損"],
            ["持有至到期", "是，不提前平倉"],
        ],
        col_widths=[5 * cm, 11 * cm],
    )
    story.append(put_table)

    # ── 7. 權益曲線圖 ──
    story.append(PageBreak())
    story.append(_p("七、權益曲線圖", style_h1))

    chart_path = str(Path(__file__).parent / "backtest_1to1.png")
    if os.path.exists(chart_path):
        img_width = 16 * cm
        img = Image(chart_path, width=img_width, height=img_width * 0.75)
        story.append(img)
    else:
        story.append(_p("（圖表檔案不存在，請先執行 python main.py 產生）"))

    story.append(Spacer(1, 8))

    # ── 8. 重大風險事件 ──
    story.append(_p("八、重大風險事件", style_h1))

    risk_table = _make_table(
        headers=["日期", "事件", "影響"],
        rows=[
            ["2025/04/02~04/09", "台指急跌約 3,000 點", "觸發多次追繳，被迫平倉期貨"],
            ["2025/04/09", "權益降至最低點", "MDD 達 67.9%，PUT 有效限制虧損"],
            ["2025/04 下旬", "指數反彈", "剩餘部位開始回血，權益回升"],
            ["2025 下半年~2026", "指數穩步上升", "持續加倉，權益大幅成長"],
        ],
        col_widths=[3.5 * cm, 5 * cm, 7.5 * cm],
    )
    story.append(risk_table)
    story.append(Spacer(1, 12))

    # ── 9. 策略特點與注意事項 ──
    story.append(_p("九、策略特點與注意事項", style_h1))

    story.append(_p("9.1 優勢", style_h2))
    story.append(_p("&bull; 100% PUT 保護覆蓋率，有效控制尾端風險"))
    story.append(_p("&bull; 每週換倉，保護時效性高"))
    story.append(_p("&bull; 微台指門檻低，適合小資金長期累積"))
    story.append(_p("&bull; 每月定投機制，平滑進場成本"))

    story.append(_p("9.2 風險與注意事項", style_h2))
    story.append(_p("&bull; PUT 成本高：NT$3,069,435 佔總成本比重大，長期侵蝕獲利"))
    story.append(_p("&bull; 回測期間為多頭行情，空頭市場表現未知"))
    story.append(_p("&bull; MDD 67.9% 仍然偏高，實際操作心理壓力大"))
    story.append(_p("&bull; 資金補入假設可能不符實際情況（隨時有錢補）"))
    story.append(_p("&bull; 週選流動性有時不足，實際成交價可能不理想"))
    story.append(_p("&bull; 未考慮滑價與盤後結算差異"))

    story.append(Spacer(1, 20))
    story.append(_p(
        f"報告產生日期: {date.today().strftime('%Y/%m/%d')} | 資料來源: 台灣期貨交易所 (TAIFEX)",
        style_small,
    ))

    # ── Build PDF ──
    doc.build(story)
    print(f"PDF 報告已產生: {output_path}")


if __name__ == "__main__":
    build_report()

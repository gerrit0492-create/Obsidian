"""Build a polished, multi-section PDF report for the charging dashboard.

Pure reportlab (text, tables and native vector charts) so it has no image-export
dependency — reliable on hosted Streamlit. ``build_pdf`` takes a plain context
dict assembled by the app and returns the PDF as bytes.
"""

from __future__ import annotations

import io

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#1f2a44")
ACCENT = colors.HexColor("#2a9d8f")
LINE = colors.HexColor("#e6eaf0")
SOFT = colors.HexColor("#f5f7fa")


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("Hero", parent=ss["Title"], textColor=colors.white, fontSize=20, leading=24))
    ss.add(ParagraphStyle("HeroSub", parent=ss["Normal"], textColor=colors.white, fontSize=10, leading=13))
    ss.add(ParagraphStyle("H2", parent=ss["Heading2"], textColor=INK, fontSize=13, spaceBefore=10, spaceAfter=4))
    ss.add(ParagraphStyle("CarH", parent=ss["Heading2"], textColor=colors.white, fontSize=12, leading=15))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], textColor=INK, fontSize=9, leading=12))
    return ss


def _banner(title: str, subtitle: str, ss) -> Table:
    inner = [[Paragraph(title, ss["Hero"])], [Paragraph(subtitle, ss["HeroSub"])]]
    t = Table(inner, colWidths=[170 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (0, 0), 12),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
            ]
        )
    )
    return t


def _kpi_grid(kpis, ss, cols: int = 3) -> Table:
    def cell(label, value):
        inner = Table(
            [
                [Paragraph(f'<font size=8 color="#6b7280">{label}</font>', ss["Body"])],
                [Paragraph(f"<b>{value}</b>", ss["Body"])],
            ],
            colWidths=[52 * mm],
        )
        inner.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            )
        )
        return inner

    cells = [cell(label, value) for label, value in kpis]
    while len(cells) % cols:
        cells.append(Paragraph("", ss["Body"]))
    rows = [cells[i : i + cols] for i in range(0, len(cells), cols)]
    t = Table(rows, colWidths=[56 * mm] * cols)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def _table(rows, ss, col_widths=None) -> Table:
    data = [
        [
            Paragraph(f'<b><font color="white">{c}</font></b>', ss["Body"]) if r == 0
            else Paragraph(str(c), ss["Body"])
            for c in row
        ]
        for r, row in enumerate(rows)
    ]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _pie(share) -> Drawing:
    # Wide canvas so the side labels have room and don't clip at the page edge.
    d = Drawing(320, 150)
    d.hAlign = "CENTER"
    pie = Pie()
    pie.x, pie.y = 100, 12
    pie.width = pie.height = 124
    total = sum(max(float(c), 0.0) for _, c, _ in share) or 1.0
    pie.data = [max(float(c), 0.0001) for _, c, _ in share]
    pie.labels = [f"{name}  {float(c) / total * 100:.0f}%" for name, c, _ in share]
    pie.sideLabels = True
    pie.slices.fontSize = 8
    pie.slices.strokeColor = colors.white
    for i, (_, _, hexc) in enumerate(share):
        pie.slices[i].fillColor = colors.HexColor(hexc)
    d.add(pie)
    return d


def _bars(months, hexc, width=180, height=95) -> Drawing:
    d = Drawing(width, height)
    bc = VerticalBarChart()
    bc.x, bc.y = 28, 18
    bc.width, bc.height = width - 40, height - 30
    bc.data = [[float(c) for _, c in months]]
    bc.categoryAxis.categoryNames = [str(m) for m, _ in months]
    bc.categoryAxis.labels.fontSize = 7
    bc.valueAxis.labels.fontSize = 7
    bc.valueAxis.valueMin = 0
    bc.bars[0].fillColor = colors.HexColor(hexc)
    bc.barWidth = 8
    d.add(bc)
    return d


def build_pdf(ctx: dict) -> bytes:
    """Render the report. See the app for the exact context shape."""
    ss = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title="Car Charging Costs report",
    )
    story = [
        _banner(ctx["title"], ctx["subtitle"], ss),
        Spacer(1, 10),
        _kpi_grid(ctx["kpis"], ss),
        Spacer(1, 12),
    ]

    story.append(Paragraph("Cost share &amp; totals by car", ss["H2"]))
    story.append(_table(ctx["overview"], ss, col_widths=[44 * mm, 26 * mm, 26 * mm, 30 * mm, 24 * mm]))
    if ctx.get("share"):
        story.append(Spacer(1, 6))
        story.append(_pie(ctx["share"]))
    story.append(Spacer(1, 10))

    if ctx.get("tou"):
        story.append(Paragraph("Peak vs off-peak (your home tariff)", ss["H2"]))
        story.append(_table(ctx["tou"], ss, col_widths=[45 * mm, 30 * mm, 40 * mm, 40 * mm]))
        story.append(Spacer(1, 6))

    for car in ctx["per_car"]:
        block = [
            Table(
                [[Paragraph(car["name"], ss["CarH"])]],
                colWidths=[170 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(car["color"])),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                ),
            ),
            Spacer(1, 6),
        ]
        metric_tbl = _table(
            [["Metric", "Value"]] + [[m, v] for m, v in car["metrics"]],
            ss, col_widths=[45 * mm, 40 * mm],
        )
        if car.get("months"):
            block.append(Table([[metric_tbl, _bars(car["months"], car["color"])]],
                               colWidths=[90 * mm, 80 * mm]))
        else:
            block.append(metric_tbl)
        story.append(KeepTogether(block))
        story.append(Spacer(1, 10))

    doc.build(story)
    return buf.getvalue()

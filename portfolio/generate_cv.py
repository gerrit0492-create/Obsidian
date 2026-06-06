"""Generate a clean one-page CV PDF (assets/cv.pdf) from your data.

A privacy-safe web CV: no home address, phone or birth date. Run:

    python generate_cv.py

Edit the data below to change the CV; re-run to regenerate.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer,
)

INK = HexColor("#1f2a44")
ACCENT = HexColor("#2a9d8f")
GREY = HexColor("#475569")

NAME = "Gerrit Düthler"
ROLE = "Cost Engineer · Calculator · Werkvoorbereider"
CONTACT = "gerrit@duthler.info · Eindhoven, NL · linkedin.com/in/… · github.com/gerrit0492-create"

PROFILE = (
    "Cost engineer met 35+ jaar ervaring in de maakindustrie (DAF, VDL ETG, Andritz, "
    "Wilting, Wärtsilä). Vertaalt techniek naar kosten en bouwt eigen tools (Power BI, "
    "Excel/SAP, Python) die handwerk wegnemen en betere kostenbeslissingen mogelijk maken. "
    "Lean Six Sigma Green Belt."
)

HIGHLIGHTS = [
    "Spoorde via een zelfgebouwd pre/post-calculatiemodel (Power BI) een quantity-fout op: "
    "een korting van <b>€195k</b> die niet was meegenomen.",
    "Zette nacalculatie- en kostenopvolgingsmodellen op samen met business control.",
    "Realiseerde proces- en kostenverbeteringen via Lean/DMAIC, Kaizen, 5S en FMEA.",
]

EXPERIENCE = [
    ("2021 – 2026", "Wärtsilä", "Cost Engineer", [
        "Kostendata in de offerte-software; kostenanalyses en calculaties voor ontwikkel-, "
        "klant- en niet-standaard projecten.",
        "Ondersteuning van engineering, verkoop, project management, inkoop en product management.",
        "Mede bepalen van kostenstrategieën en kostenreductie-initiatieven over disciplines heen.",
    ]),
    ("2019 – 2021", "Wilting", "Manufacturing Engineer", [
        "Inkoop NPG/gereedschappen, inrichting werkplaats en gereedschapsbeheer.",
        "Verbeterprojecten op veiligheid, kwaliteit, leverbetrouwbaarheid en kosten (Lean RCA).",
    ]),
    ("2017 – 2019", "VDL ETG", "Factory Engineer", [
        "Maakstrategie en routing van complexe producten; productdocumentatie.",
        "Verbeteren en begeleiden van lopende productie; producteigenaar.",
    ]),
    ("2011 – 2017", "Andritz Feed & Biofuel", "Supervisor productie", [
        "KPI-gedreven aansturing van de harderij en 3 productieafdelingen; coaching en HR.",
        "Procesverbeteringen via DMAIC; schakel tussen werkvloer en management.",
    ]),
    ("1987 – 2011", "DAF Trucks", "Production / Technical Engineer & Teamleider", [
        "Proces- en productverbeteringen, machine-afnames, implementatie nieuwe productielijnen.",
        "FMEA, 5S, DMAIC, Kaizen, CNC-programmeren; aansturen en instrueren van medewerkers.",
    ]),
]

SKILLS = (
    "Kostencalculatie · Should-cost · Nacalculatie · Lean Six Sigma (Green Belt) · "
    "DMAIC/Kaizen/5S/FMEA · Werkvoorbereiding & routing · Maakstrategie · SAP · Power BI · "
    "Excel & VBA · Python · CNC-programmeren · Procesverbetering · Leidinggeven"
)
EDUCATION = "KMBO Metaaltechniek C, Eindhoven (1985) · LTS Metaaltechniek C, Eindhoven (1981–1985)"
LANGUAGES = "Nederlands (moedertaal) · Engels · Duits — in woord en geschrift"


def build(path: Path) -> None:
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9.5, leading=13,
                          textColor=INK, alignment=TA_LEFT)
    name = ParagraphStyle("name", parent=body, fontSize=20, leading=22, textColor=INK, spaceAfter=1)
    role = ParagraphStyle("role", parent=body, fontSize=11, leading=14, textColor=ACCENT, spaceAfter=2)
    contact = ParagraphStyle("contact", parent=body, fontSize=8.5, textColor=GREY, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=body, fontSize=11, leading=14, textColor=INK,
                        spaceBefore=9, spaceAfter=3, fontName="Helvetica-Bold")
    job = ParagraphStyle("job", parent=body, fontName="Helvetica-Bold", spaceBefore=4)
    meta = ParagraphStyle("meta", parent=body, fontSize=8.5, textColor=GREY)

    def bullets(items):
        return ListFlowable(
            [ListItem(Paragraph(t, body), leftIndent=10, value="•") for t in items],
            bulletType="bullet", start="•", leftIndent=8, spaceBefore=1,
        )

    flow = [
        Paragraph(NAME, name),
        Paragraph(ROLE, role),
        Paragraph(CONTACT, contact),
        HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=6),
        Paragraph("Profiel", h2), Paragraph(PROFILE, body),
        Paragraph("Belangrijkste resultaten", h2), bullets(HIGHLIGHTS),
        Paragraph("Werkervaring", h2),
    ]
    for period, org, title, items in EXPERIENCE:
        flow.append(Paragraph(f"{title} — {org}", job))
        flow.append(Paragraph(period, meta))
        flow.append(bullets(items))
    flow += [
        Paragraph("Vaardigheden", h2), Paragraph(SKILLS, body),
        Paragraph("Opleiding", h2), Paragraph(EDUCATION, body),
        Paragraph("Talen", h2), Paragraph(LANGUAGES, body),
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=12 * mm,
        title=f"CV {NAME}", author=NAME,
    )
    doc.build(flow)


if __name__ == "__main__":
    out = Path(__file__).parent / "assets" / "cv.pdf"
    build(out)
    print(f"Wrote {out}")

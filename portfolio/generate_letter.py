"""Generate a motivation letter (cover letter) in PDF and Word (.docx).

A strong, ATS-friendly letter built automatically from Gerrit's profile and how
it relates to the vacancy — no manual "why this company" text needed. Available
in Dutch and English. Run:

    python generate_letter.py        # NL + EN templates with [placeholders]

Or import and call build_pdf/build_docx with company/role/contact/highlights
filled in (``highlights`` = the keywords the vacancy and CV share).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

INK = HexColor("#1f2a44")
SENDER = "Gerrit Düthler"
SENDER_CONTACT = "gerrit@duthler.info · Eindhoven · linkedin.com/in/gerrit-d-90a50234"

DEFAULTS = {
    "nl": {"company": "[Bedrijf]", "role": "[Functie]", "contact": "heer/mevrouw"},
    "en": {"company": "[Company]", "role": "[Role]", "contact": "Sir or Madam"},
}


def _highlight_phrase(highlights, lang: str) -> str:
    """Turn the shared CV/vacancy keywords into a readable phrase."""
    items = [h for h in (highlights or []) if h][:5]
    if not items:
        return ("kostencalculatie, should-cost en procesverbetering" if lang == "nl"
                else "cost estimating, should-cost and process improvement")
    if len(items) == 1:
        return items[0]
    joiner = " en " if lang == "nl" else " and "
    return ", ".join(items[:-1]) + joiner + items[-1]


def paragraphs(company: str, role: str, contact: str, highlights=None, lang: str = "nl") -> list[str]:
    """The full letter body, built automatically — no fill-in text fields."""
    today = date.today().strftime("%d-%m-%Y")
    hl = _highlight_phrase(highlights, lang)
    if lang == "en":
        return [
            f"Eindhoven, {today}",
            f"{company}",
            f"Attn: {contact}",
            f"Subject: application for {role}",
            f"Dear {contact},",
            (f"With more than 35 years in manufacturing — from DAF Trucks and VDL ETG to "
             f"Andritz and Wärtsilä — I am applying with enthusiasm for the role of {role} at "
             f"{company}. As a cost engineer I turn engineering into reliable cost prices and "
             f"keep cost under control."),
            (f"Your vacancy asks for exactly my strengths: {hl}. What I bring to {company} is "
             f"defensible calculations, faster quotes and margins you can defend — working "
             f"closely with engineering, purchasing, sales and business control."),
            ("As a Lean Six Sigma Green Belt I improve processes structurally (DMAIC, Kaizen, "
             "5S, FMEA) and make estimating faster and more transparent with data — Power BI, "
             "SAP and Excel/VBA."),
            (f"I would gladly explain in a personal conversation how I can add measurable value "
             f"to {company} as well. You can reach me at gerrit@duthler.info."),
            "Kind regards,",
            SENDER,
            SENDER_CONTACT,
        ]
    return [
        f"Eindhoven, {today}",
        f"{company}",
        f"T.a.v. {contact}",
        f"Betreft: sollicitatie {role}",
        f"Geachte {contact},",
        (f"Met ruim 35 jaar ervaring in de maakindustrie — van DAF Trucks en VDL ETG tot "
         f"Andritz en Wärtsilä — solliciteer ik met enthousiasme naar de functie van {role} "
         f"bij {company}. Als cost engineer vertaal ik techniek naar betrouwbare kostprijzen "
         f"en houd ik kosten beheersbaar."),
        (f"In uw vacature herken ik direct mijn kracht: {hl}. Wat ik bij {company} kom brengen: "
         f"onderbouwde calculaties, snellere offertes en marges die kloppen — in nauwe "
         f"samenwerking met engineering, inkoop, verkoop en business control."),
        ("Als Lean Six Sigma Green Belt verbeter ik processen structureel (DMAIC, Kaizen, 5S, "
         "FMEA) en maak ik calculeren sneller en transparanter met data — Power BI, SAP en "
         "Excel/VBA."),
        (f"Graag licht ik in een persoonlijk gesprek toe hoe ik ook voor {company} aantoonbaar "
         "waarde toevoeg. U kunt mij bereiken via gerrit@duthler.info."),
        "Met vriendelijke groet,",
        SENDER,
        SENDER_CONTACT,
    ]


def _resolve(company, role, contact, lang):
    d = DEFAULTS["en" if lang == "en" else "nl"]
    return (company or d["company"], role or d["role"], contact or d["contact"])


def build_pdf(path: Path, company="", role="", contact="", highlights=None, lang="nl") -> None:
    company, role, contact = _resolve(company, role, contact, lang)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10.5, leading=15,
                          textColor=INK, alignment=TA_LEFT, spaceAfter=8)
    paras = paragraphs(company, role, contact, highlights, lang)
    flow = []
    for i, p in enumerate(paras):
        flow.append(Paragraph(p, body))
        if i in (0, 2, 3):           # extra space after date block, address, subject
            flow.append(Spacer(1, 6))
    path.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                      topMargin=20 * mm, bottomMargin=18 * mm,
                      title=f"Motivatiebrief {SENDER}", author=SENDER).build(flow)


def build_docx(path: Path, company="", role="", contact="", highlights=None, lang="nl") -> None:
    from docx import Document
    from docx.shared import Pt

    company, role, contact = _resolve(company, role, contact, lang)
    doc = Document()
    f = doc.styles["Normal"].font
    f.name, f.size = "Calibri", Pt(11)
    for p in paragraphs(company, role, contact, highlights, lang):
        doc.add_paragraph(p)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))


if __name__ == "__main__":
    assets = Path(__file__).parent / "assets"
    build_pdf(assets / "motivation.pdf", lang="nl")
    build_docx(assets / "motivation.docx", lang="nl")
    build_pdf(assets / "motivation_en.pdf", lang="en")
    build_docx(assets / "motivation_en.docx", lang="en")
    print(f"Wrote NL + EN motivation letters in {assets}")

"""Generate a motivation letter (cover letter) in PDF and Word (.docx).

A strong, ATS-friendly Dutch letter built from Gerrit's profile, with fill-in
fields per vacancy. Run:

    python generate_letter.py                       # template with [placeholders]

Or import and call build_pdf/build_docx with company/role/contact/reason filled in.
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


def paragraphs(company: str, role: str, contact: str, reason: str) -> list[str]:
    """The letter body. Anything in [brackets] is a fill-in field."""
    return [
        f"Eindhoven, {date.today().strftime('%d-%m-%Y')}",
        f"{company}",
        f"T.a.v. {contact}",
        f"Betreft: sollicitatie {role}",
        f"Geachte {contact},",
        (f"Met ruim 35 jaar ervaring in de maakindustrie — van DAF Trucks en VDL ETG tot "
         f"Andritz en Wärtsilä — solliciteer ik met enthousiasme naar de functie van {role} "
         f"bij {company}. Als cost engineer vertaal ik techniek naar betrouwbare kostprijzen "
         f"en houd ik kosten beheersbaar."),
        ("Wat mij onderscheidt: ik stop niet bij de calculatie, maar bouw de tools die "
         "calculaties sneller en scherper maken. Zo ontwikkelde ik een pre/post-calculatiemodel "
         "in Power BI dat een gemiste korting van €195.000 opspoorde — geld dat anders was "
         "misgelopen. Als Lean Six Sigma Green Belt verbeter ik processen structureel (DMAIC, "
         "Kaizen, 5S, FMEA), in nauwe samenwerking met engineering, inkoop, verkoop en business "
         "control."),
        (f"{company} spreekt mij aan omdat {reason}. Mijn combinatie van werkvloer-ervaring, "
         "calculatie-expertise en data-vaardigheid sluit daar naadloos op aan."),
        (f"Graag licht ik in een persoonlijk gesprek toe hoe ik ook voor {company} aantoonbaar "
         "waarde toevoeg. U kunt mij bereiken via gerrit@duthler.info."),
        "Met vriendelijke groet,",
        SENDER,
        SENDER_CONTACT,
    ]


def build_pdf(path: Path, company="[Bedrijf]", role="[Functie]",
              contact="[Contactpersoon]", reason="[reden: bv. jullie focus op complexe high-tech producten]") -> None:
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10.5, leading=15,
                          textColor=INK, alignment=TA_LEFT, spaceAfter=8)
    paras = paragraphs(company, role, contact, reason)
    flow = []
    for i, p in enumerate(paras):
        flow.append(Paragraph(p, body))
        if i in (0, 2, 3):           # extra space after date block, address, subject
            flow.append(Spacer(1, 6))
    path.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                      topMargin=20 * mm, bottomMargin=18 * mm,
                      title=f"Motivatiebrief {SENDER}", author=SENDER).build(flow)


def build_docx(path: Path, company="[Bedrijf]", role="[Functie]",
               contact="[Contactpersoon]", reason="[reden: bv. jullie focus op complexe high-tech producten]") -> None:
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    f = doc.styles["Normal"].font
    f.name, f.size = "Calibri", Pt(11)
    for p in paragraphs(company, role, contact, reason):
        doc.add_paragraph(p)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))


if __name__ == "__main__":
    assets = Path(__file__).parent / "assets"
    build_pdf(assets / "motivation.pdf")
    build_docx(assets / "motivation.docx")
    print(f"Wrote {assets/'motivation.pdf'} and {assets/'motivation.docx'}")

"""Genereer een complete start-gids (PDF + Excel) uit de planner-data.

Vat alles samen: kerninzicht, marge-portfolio, businesscase, markt & strategie,
Nederlandse regels, de installateur-route en de zes diep uitgewerkte niches.
Wordt in de app als download aangeboden zodat PDF/Excel altijd in sync zijn.
"""

from __future__ import annotations

import io

import pandas as pd
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (HRFlowable, ListFlowable, ListItem, PageBreak,
                                Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

import model as m

INK = HexColor("#1f2a44")
ACCENT = HexColor("#2a9d8f")
GREY = HexColor("#5b6675")
RULE = HexColor("#d7dee6")


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _default_prognose():
    inst = next((p for p in m.STANDAARD_PRODUCTEN if p.get("Dienst")), m.STANDAARD_PRODUCTEN[0])
    e = m.stuk_economie(inst["Prijs"], inst["Inkoop"], dienst=bool(inst.get("Dienst")))
    prog, be = m.prognose(15, 0.10, 12, 150, 750, e["winst"], e["omzet_excl"])
    return inst["Product"], prog, be


# --- Excel -----------------------------------------------------------------
def build_excel_bytes() -> bytes:
    portfolio = m.portfolio_tabel(m.STANDAARD_PRODUCTEN)
    lead, prog, _ = _default_prognose()
    markt = pd.DataFrame([{"Cijfer": a, "Waarde": b, "Toelichting": c} for a, b, c in m.MARKT["stats"]])
    regels = pd.DataFrame([{"Categorie": cat, "Punt": p.replace("**", "")}
                           for cat, punten in m.REGELS.items() for p in punten])
    route = pd.DataFrame(
        [{"Onderdeel": f["fase"], "Punt": p} for f in m.INSTALLATEUR_ROUTE["fases"] for p in f["punten"]]
        + [{"Onderdeel": "Tarief", "Punt": f"{d}: {t}"} for d, t in m.INSTALLATEUR_ROUTE["tarieven"]])
    niches = pd.DataFrame([{
        "Niche": n["naam"], "Fit": n["fit"], "Marge": n["marge"], "Drempel": n["drempel"],
        "Wat": n["wat"], "Klant": n["klant"],
        "Verdienmodel": " | ".join(n["verdienmodel"]),
        "Starten": " | ".join(n["start"]),
        "Eisen": " | ".join(n["eisen"]),
        "Klanten werven": " | ".join(n["klanten_werven"]),
        "Cijfers": n["cijfers"], "Risico's": " | ".join(n["risicos"]),
    } for n in m.NICHES])
    return m.df_to_excel_bytes({
        "Portfolio": portfolio, f"Businesscase ({lead[:18]})": prog,
        "Markt": markt, "Regels": regels, "Installateur-route": route, "Niches": niches,
    })


# --- PDF -------------------------------------------------------------------
def build_pdf_bytes() -> bytes:
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9.5, leading=13,
                          textColor=INK, alignment=TA_LEFT)
    h1 = ParagraphStyle("h1", parent=body, fontSize=18, leading=21, fontName="Helvetica-Bold", spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=body, fontSize=12.5, leading=15, textColor=INK,
                        fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=3)
    h3 = ParagraphStyle("h3", parent=body, fontName="Helvetica-Bold", fontSize=10, spaceBefore=6, spaceAfter=1)
    small = ParagraphStyle("small", parent=body, fontSize=8.4, textColor=GREY)
    italic = ParagraphStyle("italic", parent=body, fontName="Helvetica-Oblique", textColor=GREY)

    def bullets(items):
        return ListFlowable([ListItem(Paragraph(_esc(t), body), leftIndent=8, value="•") for t in items],
                            bulletType="bullet", start="•", leftIndent=8, spaceBefore=1, spaceAfter=2)

    def section(title):
        return [Paragraph(_esc(title), h2),
                HRFlowable(width="100%", thickness=0.6, color=RULE, spaceAfter=4)]

    flow = [Paragraph("Start-gids — stekkerbatterij + installatie/advies", h1),
            Paragraph("Een laag-budget startdossier voor Gerrit Düthler — marge, businesscase, "
                      "Nederlandse regels, de installateur-route en zes high-value niches.", small),
            HRFlowable(width="100%", thickness=1.1, color=INK, spaceBefore=4, spaceAfter=2)]

    # Kerninzicht
    flow += section("Kerninzicht")
    flow.append(bullets([
        "De batterij verliest geld op een marktplaats (Bol-commissie + prijsvergelijking) — verkoop direct of bij installatie.",
        "De winst zit in accessoires (~15–25%) en vooral installatie/advies (≈€216/klus, ~88%; advies ~95%).",
        "Laag budget: begin met advies + plug-in setup (geen certificering) en accessoires; bouw richting gecertificeerde installatie.",
    ]))

    # Portfolio-tabel
    flow += section("Marge per product/dienst (voorbeeld)")
    pt = m.portfolio_tabel(m.STANDAARD_PRODUCTEN)
    data = [["Product/dienst", "Soort", "Inkoop", "Prijs", "Winst", "Marge%"]]
    for _, r in pt.iterrows():
        data.append([r["Product"][:34], r["Soort"], f"€{r['Inkoop (geland)']:.0f}",
                     f"€{r['Prijs (incl. btw)']:.0f}", f"€{r['Winst/stuk']:.0f}", f"{r['Marge %']:.0f}%"])
    tbl = Table(data, colWidths=[58 * mm, 18 * mm, 18 * mm, 18 * mm, 18 * mm, 16 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f5f7fa"), HexColor("#ffffff")]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE), ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    flow += [tbl]

    # Markt & strategie
    flow += section("Markt & strategie")
    flow += [Paragraph("  ·  ".join(f"{_esc(a)}: <b>{_esc(b)}</b>" for a, b, _ in m.MARKT["stats"]), body),
             Paragraph("Beachhead", h3)] + [bullets(m.MARKT["beachhead"]),
             Paragraph("Moat", h3), bullets(m.MARKT["moat"]),
             Paragraph("Niet hier concurreren", h3), bullets(m.MARKT["vermijden"]),
             Paragraph("Risico's", h3), bullets(m.MARKT["risicos"])]

    # Regels
    flow += [PageBreak()] + section("Nederlandse regels & belasting (algemeen — geen advies)")
    for cat, punten in m.REGELS.items():
        flow += [Paragraph(_esc(cat), h3), bullets([p.replace("**", "") for p in punten])]

    # Installateur-route
    flow += section("Installateur-/advies-route")
    for f in m.INSTALLATEUR_ROUTE["fases"]:
        flow += [Paragraph(_esc(f["fase"]), h3), bullets(f["punten"])]
    flow += [Paragraph("Tarieven", h3),
             bullets([f"{d}: {t}" for d, t in m.INSTALLATEUR_ROUTE["tarieven"]]),
             Paragraph("Klanten werven", h3), bullets(m.INSTALLATEUR_ROUTE["leads"]),
             Paragraph("Verzekering & risico", h3), bullets(m.INSTALLATEUR_ROUTE["verzekering"])]

    # Niches
    flow += [PageBreak()] + section("Zes high-value niches — diep uitgewerkt")
    for n in m.NICHES:
        flow += [Paragraph(f"{_esc(n['naam'])} — fit {_esc(n['fit'])} · marge {_esc(n['marge'])} · "
                           f"drempel {_esc(n['drempel'])}", h3),
                 Paragraph(_esc(n["waarom"]), italic),
                 Paragraph(f"<b>Wat &amp; klant:</b> {_esc(n['wat'])} — {_esc(n['klant'])}", body),
                 Paragraph("<b>Verdienmodel</b>", body), bullets(n["verdienmodel"]),
                 Paragraph("<b>Starten</b>", body), bullets(n["start"]),
                 Paragraph("<b>Eisen</b>", body), bullets(n["eisen"]),
                 Paragraph("<b>Klanten werven</b>", body), bullets(n["klanten_werven"]),
                 Paragraph(f"<b>Indicatie:</b> {_esc(n['cijfers'])}", body),
                 Spacer(1, 6)]

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                      topMargin=14 * mm, bottomMargin=13 * mm,
                      title="Start-gids e-commerce", author="Gerrit Düthler").build(flow)
    return buf.getvalue()


if __name__ == "__main__":
    from pathlib import Path
    out = Path(__file__).parent
    (out / "Startgids.pdf").write_bytes(build_pdf_bytes())
    (out / "Startgids.xlsx").write_bytes(build_excel_bytes())
    print("Wrote Startgids.pdf + Startgids.xlsx")

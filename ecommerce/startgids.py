"""Genereer een niche-afhankelijke start-gids (PDF + Excel) uit de planner-data.

Vat de ACTIEVE niche samen: kerninzicht (uit de portfolio-marges), marge-tabel,
markt & strategie (niche-playbook of de batterijmarkt), de relevante Nederlandse
regels en — alleen waar van toepassing — de installateur-route. Wordt in de app
als download aangeboden zodat PDF/Excel altijd matchen met de gekozen niche.
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

VRIJ = "(eigen / vrij)"


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _label(niche) -> str:
    return niche if niche and niche != VRIJ else "stekkerbatterij + installatie"


def _niche_dict(niche):
    return next((n for n in m.NICHES if n["naam"] == niche), None)


def _route_relevant(niche) -> bool:
    return niche == VRIJ or niche in m.INSTALLATIE_NICHES


def _regels_items(niche):
    if _niche_dict(niche):  # dienst-niche → algemene + ZZP-secties
        return [(t, p) for t, p in m.REGELS.items() if t in m.REGELS_ALGEMEEN]
    return list(m.REGELS.items())  # batterij/eigen → alles


def _prognose(producten):
    lead = next((p for p in producten if p.get("Dienst")), producten[0] if producten else None)
    if not lead:
        return None, None, None
    e = m.stuk_economie(lead["Prijs"], lead["Inkoop"], dienst=bool(lead.get("Dienst")))
    prog, be = m.prognose(15, 0.10, 12, 150, 750, e["winst"], e["omzet_excl"])
    return lead["Product"], prog, be


# --- Excel -----------------------------------------------------------------
def build_excel_bytes(niche=VRIJ, producten=None) -> bytes:
    producten = producten or m.STANDAARD_PRODUCTEN
    portfolio = m.portfolio_tabel(producten)
    lead, prog, _ = _prognose(producten)
    sheets = {"Portfolio": portfolio}
    if prog is not None:
        sheets[f"Businesscase ({(lead or '')[:14]})"] = prog

    _n = _niche_dict(niche)
    if _n:
        markt = pd.DataFrame(
            [{"Onderdeel": "Wat", "Inhoud": _n["wat"]}, {"Onderdeel": "Klant", "Inhoud": _n["klant"]}]
            + [{"Onderdeel": "Verdienmodel", "Inhoud": x} for x in _n["verdienmodel"]]
            + [{"Onderdeel": "Starten", "Inhoud": x} for x in _n["start"]]
            + [{"Onderdeel": "Klanten werven", "Inhoud": x} for x in _n["klanten_werven"]]
            + [{"Onderdeel": "Cijfers", "Inhoud": _n["cijfers"]}]
            + [{"Onderdeel": "Risico", "Inhoud": x} for x in _n["risicos"]])
    else:
        markt = pd.DataFrame([{"Cijfer": a, "Waarde": b, "Toelichting": c} for a, b, c in m.MARKT["stats"]])
    regels = pd.DataFrame([{"Categorie": cat, "Punt": p.replace("**", "")}
                           for cat, punten in _regels_items(niche) for p in punten])
    sheets["Markt & strategie"] = markt
    sheets["Regels"] = regels
    return m.df_to_excel_bytes(sheets)


# --- PDF -------------------------------------------------------------------
def build_pdf_bytes(niche=VRIJ, producten=None) -> bytes:
    producten = producten or m.STANDAARD_PRODUCTEN
    label = _label(niche)
    _n = _niche_dict(niche)

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9.5, leading=13,
                          textColor=INK, alignment=TA_LEFT)
    h1 = ParagraphStyle("h1", parent=body, fontSize=18, leading=21, fontName="Helvetica-Bold", spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=body, fontSize=12.5, leading=15, fontName="Helvetica-Bold",
                        spaceBefore=12, spaceAfter=3)
    h3 = ParagraphStyle("h3", parent=body, fontName="Helvetica-Bold", fontSize=10, spaceBefore=6, spaceAfter=1)
    small = ParagraphStyle("small", parent=body, fontSize=8.4, textColor=GREY)
    italic = ParagraphStyle("italic", parent=body, fontName="Helvetica-Oblique", textColor=GREY)

    def bul(items):
        return ListFlowable([ListItem(Paragraph(_esc(t), body), leftIndent=8, value="•") for t in items],
                            bulletType="bullet", start="•", leftIndent=8, spaceBefore=1, spaceAfter=2)

    def section(title):
        return [Paragraph(_esc(title), h2),
                HRFlowable(width="100%", thickness=0.6, color=RULE, spaceAfter=4)]

    flow = [Paragraph(f"Start-gids — {_esc(label)}", h1),
            Paragraph("Een onderbouwd startdossier voor deze niche — marge, businesscase, "
                      "markt, Nederlandse regels en (waar nodig) de installateur-route.", small),
            HRFlowable(width="100%", thickness=1.1, color=INK, spaceBefore=4, spaceAfter=2)]

    # Kerninzicht uit de portfolio-marges
    pt = m.portfolio_tabel(producten)
    flow += section("Kerninzicht")
    inzicht = []
    if not pt.empty:
        best, worst = pt.iloc[0], pt.iloc[-1]
        inzicht.append(f"Beste marge: {best['Product']} — €{best['Winst/stuk']:.0f}/stuk ({best['Marge %']:.0f}%).")
        if worst["Marge %"] < 10:
            inzicht.append(f"Let op: {worst['Product']} heeft een dunne/negatieve marge "
                           f"({worst['Marge %']:.0f}%) — heroverweeg prijs of kanaal (direct i.p.v. marktplaats).")
    inzicht.append("Diensten dragen geen marktplaats-fees of retouren; producten wel.")
    flow.append(bul(inzicht))

    # Marge-tabel
    flow += section("Marge per product/dienst")
    data = [["Product/dienst", "Soort", "Inkoop", "Prijs", "Winst", "Marge%"]]
    for _, r in pt.iterrows():
        data.append([r["Product"][:34], r["Soort"], f"€{r['Inkoop (geland)']:.0f}",
                     f"€{r['Prijs (incl. btw)']:.0f}", f"€{r['Winst/stuk']:.0f}", f"{r['Marge %']:.0f}%"])
    if len(data) > 1:
        tbl = Table(data, colWidths=[58 * mm, 18 * mm, 18 * mm, 18 * mm, 18 * mm, 16 * mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.2),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#f5f7fa"), HexColor("#ffffff")]),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE), ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        flow += [tbl]
    else:
        flow += [Paragraph("Nog geen producten/diensten ingevuld voor deze niche.", italic)]

    # Markt & strategie — niche-playbook of batterijmarkt
    flow += section("Markt & strategie")
    if _n:
        flow += [Paragraph(_esc(_n["waarom"]), italic),
                 Paragraph(f"<b>Wat &amp; klant:</b> {_esc(_n['wat'])} — {_esc(_n['klant'])}", body),
                 Paragraph("<b>Verdienmodel</b>", body), bul(_n["verdienmodel"]),
                 Paragraph("<b>Starten</b>", body), bul(_n["start"]),
                 Paragraph("<b>Klanten werven</b>", body), bul(_n["klanten_werven"]),
                 Paragraph(f"<b>Indicatie:</b> {_esc(_n['cijfers'])}", body),
                 Paragraph("<b>Risico's</b>", body), bul(_n["risicos"])]
    else:
        flow += [Paragraph("  ·  ".join(f"{_esc(a)}: <b>{_esc(b)}</b>" for a, b, _ in m.MARKT["stats"]), body),
                 Paragraph("Beachhead", h3), bul(m.MARKT["beachhead"]),
                 Paragraph("Moat", h3), bul(m.MARKT["moat"]),
                 Paragraph("Niet hier concurreren", h3), bul(m.MARKT["vermijden"]),
                 Paragraph("Risico's", h3), bul(m.MARKT["risicos"])]

    # Regels — gefilterd per niche
    flow += [PageBreak()] + section("Nederlandse regels & belasting (algemeen — geen advies)")
    for cat, punten in _regels_items(niche):
        flow += [Paragraph(_esc(cat), h3), bul([p.replace("**", "") for p in punten])]

    # Installateur-route — alleen indien relevant
    if _route_relevant(niche):
        flow += section("Installateur-/advies-route")
        for f in m.INSTALLATEUR_ROUTE["fases"]:
            flow += [Paragraph(_esc(f["fase"]), h3), bul(f["punten"])]
        flow += [Paragraph("Tarieven", h3), bul([f"{d}: {t}" for d, t in m.INSTALLATEUR_ROUTE["tarieven"]]),
                 Paragraph("Klanten werven", h3), bul(m.INSTALLATEUR_ROUTE["leads"])]

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                      topMargin=14 * mm, bottomMargin=13 * mm,
                      title=f"Start-gids {label}", author="Gerrit Düthler").build(flow)
    return buf.getvalue()


if __name__ == "__main__":
    from pathlib import Path
    out = Path(__file__).parent
    (out / "Startgids.pdf").write_bytes(build_pdf_bytes())
    (out / "Startgids.xlsx").write_bytes(build_excel_bytes())
    print("Wrote Startgids.pdf + Startgids.xlsx")

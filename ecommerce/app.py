"""E-commerce planner — marge, portfolio, businesscase, markt en NL-regels.

Een planningstool voor het starten van een home-energy / domotica-webshop in
Nederland. Gemaakt voor een cost engineer: de stuk-economie is expliciet en de
hele analyse exporteert naar Excel. Alle getallen zijn aanpasbare schattingen om
te valideren — geen beloftes. De Regels-sectie is algemene info, geen advies.

Starten:  streamlit run app.py
"""

from __future__ import annotations

import json
import math
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import model as m
import ai
import store

st.set_page_config(page_title="E-commerce planner", page_icon="🛒", layout="wide")


def _app_password():
    import os
    try:
        if "APP_PASSWORD" in st.secrets:
            return str(st.secrets["APP_PASSWORD"])
    except Exception:  # noqa: BLE001
        pass
    return os.environ.get("APP_PASSWORD", "")


def _require_login():
    """Optioneel wachtwoord: actief zodra het secret APP_PASSWORD is gezet; anders blijft de app open."""
    _pw = _app_password()
    if not _pw or st.session_state.get("_authed"):
        return
    st.title("🔒 Beveiligd")
    st.caption("Voer het wachtwoord in om verder te gaan.")
    _in = st.text_input("Wachtwoord", type="password", key="_app_pw")
    if st.button("Inloggen", type="primary"):
        if _in == _pw:
            st.session_state["_authed"] = True
            st.rerun()
        else:
            st.error("Onjuist wachtwoord.")
    st.stop()


_require_login()
_header = st.container()  # titel + caption worden gevuld zodra de actieve niche bekend is


def eur(x: float) -> str:
    return f"€{x:,.2f}"


# Dakrenovatie offerte-tracker — startdata (vooringevuld met de Westermeer-offerte).
DAK_DEFAULT = [
    {"Bedrijf": "Dakbedrijf Westermeer", "Offertenr.": "OFF-2026-0189", "Datum": "2026-06-11",
     "Geldig t/m": "2026-06-25", "Excl. btw": 16680.0, "Incl. btw": 20182.80, "Status": "Ontvangen",
     "Garantie": "15 jaar werkgarantie", "Isolatie": "Rd 3,8",
     "Notities": "60 m² × €250/m² + lood €900 + vogelwering €780; isolatie Rd 3,8; betaling 50/50"},
    {"Bedrijf": "B. Albers Dakwerken", "Offertenr.": "2026060231", "Datum": "2026-06-01",
     "Geldig t/m": "2026-07-01", "Excl. btw": 13540.0, "Incl. btw": 16191.40, "Status": "Ontvangen",
     "Garantie": "10 jaar", "Isolatie": "Rc 3,89–4,11 (SF40BB, ISDE KA28563)",
     "Notities": "Compleet dakrenovatie + isoleren; 9% btw op isolatie-arbeid; 10 jr garantie; PDF 2026060231"},
    {"Bedrijf": "", "Offertenr.": "", "Datum": "", "Geldig t/m": "", "Excl. btw": 0.0,
     "Incl. btw": 0.0, "Status": "Aangevraagd", "Garantie": "", "Isolatie": "", "Notities": ""},
]
def _dak_offerte_key(row):
    """Sleutel om dezelfde offerte te herkennen: offertenummer, anders bedrijfsnaam."""
    nr = str(row.get("Offertenr.") or "").strip().lower()
    return ("nr", nr) if nr else ("bedrijf", str(row.get("Bedrijf") or "").strip().lower())


def _dak_dedup(offertes):
    """Houd per offerte (zelfde offertenummer, anders bedrijf) alleen de laatste regel."""
    out, idx = [], {}
    for row in offertes:
        k = _dak_offerte_key(row)
        if k in idx:
            out[idx[k]] = row
        else:
            idx[k] = len(out)
            out.append(row)
    return out


def _dak_shouldcost_posten(opp):
    """Should-cost baseline per scope-onderdeel met **LCL/UCL** (excl. btw), geschaald naar het dakoppervlak.

    Complete bottom-up raming (NL, 60 m² referentie) die álle scope-onderdelen dekt die in de ontvangen
    offertes voorkomen. Per post een ondergrens (LCL, efficiënt) en bovengrens (UCL); het midpunt voedt de
    puntvergelijking, de band toont wat een offerte 'zou moeten' kosten.
    """
    r = max(float(opp or 60), 1.0) / 60.0
    items = [  # (Onderdeel, LCL @60 m², UCL @60 m², btw %, schaalt mee, optie-key of None)
        ("Steiger + materieel + pannenlift", 900, 1400, 21, False, None),
        ("Sloop + afvoer + container", 700, 1100, 21, True, None),
        ("Isolatie materiaal (Rd ≥ 3,5)", 900, 1400, 21, True, None),
        ("Isolatie aanbrengen (arbeid)", 500, 800, 9, True, None),
        ("Tengels + panlatten", 600, 1000, 21, True, None),
        ("Dakpannen (beton, midmarkt)", 1000, 1600, 21, True, None),
        ("Dakpannen leggen / montage", 1000, 1600, 21, True, None),
        ("Nokvorsten + ruiters", 400, 800, 21, False, None),
        ("Kant-/gevelpannen", 300, 600, 21, False, None),
        ("Zinken bakgoot + gootbeugels", 900, 1500, 21, False, "goot"),
        ("Loodaansluiting dakkapel (10 m)", 500, 900, 21, False, "dakkapel"),
        ("Vogelwering + dakvoet (12 m)", 250, 450, 21, False, "vogelwering"),
        ("Panhaken / stormklemmen", 150, 350, 21, False, None),
    ]
    out = []
    for _n, _lo, _hi, _b, _s, _opt in items:
        # Huis-specifieke extra's (goot/dakkapel-lood/vogelwering) tellen alleen mee als dit dak ze
        # heeft — anders staat de should-cost kunstmatig hoog voor een 60 m²-referentie mét dakkapel.
        if _opt is not None and not st.session_state.get(f"dak_sc_extra_{_opt}", True):
            continue
        _sc = r if _s else 1.0
        _l, _u = round(_lo * _sc), round(_hi * _sc)
        out.append({"Bedrijf": "Should-cost (baseline)", "Onderdeel": _n,
                    "Prijs excl. btw": float(round((_l + _u) / 2)), "Btw %": _b,
                    "LCL": float(_l), "UCL": float(_u)})
    return out


def _dak_attachments_dir():
    """Map waar de originele offerte-PDF's staan (Westermeer-regel: altijd terugvindbaar)."""
    from pathlib import Path
    for d in (Path(__file__).parent.parent / "vault" / "attachments",
              Path.cwd() / "vault" / "attachments"):
        if d.exists():
            return d
    return None


def _offerte_pdf_path(orow):
    """Zoek de originele PDF van een offerte op offertenummer, anders op bedrijfsnaam."""
    d = _dak_attachments_dir()
    if d is None:
        return None
    nr = str(orow.get("Offertenr.") or "").strip().lower()
    woorden = [w for w in str(orow.get("Bedrijf") or "").lower().replace(".", " ").split() if len(w) > 3]
    pdfs = sorted(d.glob("*.pdf"))
    for p in pdfs:                                   # 1) match op offertenummer
        if nr and nr in p.name.lower():
            return p
    for p in pdfs:                                   # 2) anders op een woord uit de bedrijfsnaam
        if any(w in p.name.lower() for w in woorden):
            return p
    return None


DAK_MARKT_LO, DAK_MARKT_HI = 180.0, 260.0  # €/m² incl. btw, NL-indicatie

# Posten per offerte (lang formaat) — voor de onderlinge vergelijking met scope-verschillen.
DAK_POSTEN_DEFAULT = [
    # Westermeer — alle regels uit offerte OFF-2026-0189 (bundelprijs + specificatie 'incl.' + lood + vogelwering).
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "Complete dakrenovatie (60 m²) — keramische betonpannen [bundelprijs]", "Prijs excl. btw": 15000.0, "Btw %": 21},
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "• Verwijderen oude dakpannen, tengels en panlatten — 60 m² (incl.)", "Prijs excl. btw": 0.0, "Btw %": 21},
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "• Container 3,5 m³ + afvoer naar erkend recyclingbedrijf — 1 st (incl.)", "Prijs excl. btw": 0.0, "Btw %": 21},
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "• Isolatiedeken aanbrengen — Rd 3,8 — 60 m² (incl.)", "Prijs excl. btw": 0.0, "Btw %": 21},
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "• Nieuwe tengels + panlatten monteren — 60 m² (incl.)", "Prijs excl. btw": 0.0, "Btw %": 21},
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "• Keramische betonpannen hoofddak — 368 st (incl.)", "Prijs excl. btw": 0.0, "Btw %": 21},
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "• Keramische betonpannen erker voorzijde — 35 st (incl.)", "Prijs excl. btw": 0.0, "Btw %": 21},
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "• Keramische betonpannen dakkapel — 66 st (incl.)", "Prijs excl. btw": 0.0, "Btw %": 21},
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "• Nokvorsten — 17 st (incl.)", "Prijs excl. btw": 0.0, "Btw %": 21},
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "• Linkse kantpannen (hoofddak + erker) — 21 st (incl.)", "Prijs excl. btw": 0.0, "Btw %": 21},
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "• Rechtse kantpannen (hoofddak + erker) — 21 st (incl.)", "Prijs excl. btw": 0.0, "Btw %": 21},
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "• Pannenlift + paslodespijkers (2.000 st) + slijp-/zaagmateriaal (incl.)", "Prijs excl. btw": 0.0, "Btw %": 21},
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "• Volledige montage + arbeid, max. 3 werkdagen (incl.)", "Prijs excl. btw": 0.0, "Btw %": 21},
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "Loodaansluiting dakkapel voorzijde — 10 m (lood code 18)", "Prijs excl. btw": 900.0, "Btw %": 21},
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "Vogelwering & dakvoetprofielen — 12 m", "Prijs excl. btw": 780.0, "Btw %": 21},
    # Albers — alle 20 regels uit offerte 2026060231 (incl. de €0-regels en de 3 stelposten).
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Bouwkundige voorzieningen: steiger Layher (€1.840) + pannenlift/kraan (€100) + puincontainer/afvoer (€450)", "Prijs excl. btw": 2390.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Afvoeren en opruimen van overgebleven bouwafval (incl.)", "Prijs excl. btw": 0.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Opruimen en schoonmaken van de dakgoten (incl.)", "Prijs excl. btw": 0.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "SF40BB isolatiefolie aanbrengen — arbeid (Rc 3,89–4,11, 60 m²)", "Prijs excl. btw": 1600.0, "Btw %": 9},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "SF40BB isolatiefolie leveren (60 m²)", "Prijs excl. btw": 2000.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Panlatten als tengels t.b.v. folie (200 m¹)", "Prijs excl. btw": 800.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Panlatten (200 m¹)", "Prijs excl. btw": 1100.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Ruitersteunen (10 st)", "Prijs excl. btw": 200.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Ruiterbalk voor de nok (m¹)", "Prijs excl. btw": 200.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Ondervorst over de nokbalk (7 m¹)", "Prijs excl. btw": 250.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Sneldek betonpannen Antraciet (60 m²)", "Prijs excl. btw": 1800.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Linkse gevelpannen", "Prijs excl. btw": 300.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Rechtse gevelpannen", "Prijs excl. btw": 300.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Nelskamp halfronde vorst Antraciet (21 st, keramisch)", "Prijs excl. btw": 700.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Gootbeugels", "Prijs excl. btw": 400.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Zinken bakgoot b37 (14 m¹)", "Prijs excl. btw": 1200.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Panhaken (RVS, NEN 6707)", "Prijs excl. btw": 300.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Stelpost: dakdoorvoer (rookgas, CV) — optie €400 extern", "Prijs excl. btw": 0.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Stelpost: kunstlood dakkapel vernieuwen (optie €700/dakkapel)", "Prijs excl. btw": 0.0, "Btw %": 21},
    {"Bedrijf": "B. Albers Dakwerken", "Onderdeel": "Stelpost: regenpijpen zink vervangen (optie €1.400)", "Prijs excl. btw": 0.0, "Btw %": 21},
]

# Should-cost (bottom-up) voor een hellend pannendak vervangen INCL. isolatie — NL 2025/2026,
# €/m² EXCL. btw. Directe kosten (materiaal + arbeid); de opslagen (AK + winst/risico) worden
# eronder berekend. Loodwerk en vogelwering zijn aparte posten (zie de offerte-uitsplitsing).
DAK_RENO_SHOULDCOST = [
    {"Onderdeel": "Oude pannen/tengels/panlatten verwijderen (sloop, arbeid)", "Laag": 6.0, "Hoog": 11.0},
    {"Onderdeel": "Afvoer afval — container(s) + stortkosten (pannen/hout/folie)", "Laag": 5.0, "Hoog": 10.0},
    {"Onderdeel": "Onderdak — waterkerende, dampopen folie (materiaal + aanbrengen)", "Laag": 3.0, "Hoog": 6.0},
    {"Onderdeel": "Isolatie Rd 3,8 — materiaal + aanbrengen", "Laag": 20.0, "Hoog": 30.0},
    {"Onderdeel": "Nieuwe tengels + panlatten — materiaal + arbeid", "Laag": 8.0, "Hoog": 13.0},
    {"Onderdeel": "Pannen leggen — arbeid", "Laag": 16.0, "Hoog": 24.0},
    {"Onderdeel": "Nok-/kantpannen (droge nok/vorst), hulpstukken, bevestiging", "Laag": 6.0, "Hoog": 10.0},
    {"Onderdeel": "Dakrandafwerking — boeiboord/windveer, daktrim", "Laag": 3.0, "Hoog": 6.0},
    {"Onderdeel": "Steiger (toegerekend per m²)", "Laag": 7.0, "Hoog": 12.0},
    {"Onderdeel": "Materiaaltransport, kraan/hijswerk, klein materieel", "Laag": 3.0, "Hoog": 6.0},
]
DAK_RENO_AK = 0.10   # algemene kosten / overhead (werkvoorbereiding, projectleiding, CAR, administratie)
DAK_RENO_WR = 0.07   # winst & risico
DAK_RENO_BTW = 0.21  # offerte rekent vlak 21%; isolatie-arbeid (woning > 2 jr) kan 9% zijn
# Pannen-materiaal €/m² EXCL. btw per type (bron: prijsoverzicht, omgerekend van incl.) — kies per
# offerte, want er komen offertes met zowel keramische als betonnen pannen.
DAK_RENO_PANTYPE = {
    "Betonpan / Sneldek (antraciet)": (20.0, 30.0),  # standaard hier; bron ≈ €26–36/m² incl.
    "Keramisch (antraciet)": (26.0, 45.0),           # bron ≈ €35–75/m² incl.
}

# Directe arbeid (cao-dakdekker incl. directe werkgeverslasten, excl. AK/W&R/btw).
DAK_RENO_UURTARIEF = 45.0  # €/uur
# Gedetailleerde cost-price-opbouw per scope-onderdeel (indicatief, €/m²) — "zo bouwt de dakdekker de
# kostprijs op". Per regel: (component, hoeveelheid, eenheid, prijs per eenheid, bron). Arbeidsregels
# rekenen uren × DAK_RENO_UURTARIEF; de som per scope sluit aan op de LCL–UCL-band hierboven.
# Bronnen: Kosten-Dakdekker, Oranje Dakbeheer, Homedeal, Werkspot, containerverhuur NL (2025/26).
DAK_RENO_DETAIL = {
    "Oude pannen/tengels/panlatten verwijderen (sloop, arbeid)": [
        ("Demontage pannen + tengels/panlatten (arbeid)", 0.16, "u/m²", DAK_RENO_UURTARIEF, "Kosten-Dakdekker (sloop ≈ 0,15 u/m²)"),
        ("Klein materieel, dekzeilen, zakgoed", 1.3, "post/m²", 1.0, "Werkspot"),
    ],
    "Afvoer afval — container(s) + stortkosten (pannen/hout/folie)": [
        ("Afvalcontainer — huur + plaatsen", 3.6, "post/m²", 1.0, "containerverhuur NL"),
        ("Stortkosten dakpannen/bouwafval", 3.0, "post/m²", 1.0, "verwerkingstarief"),
        ("Laden container (arbeid)", 0.02, "u/m²", DAK_RENO_UURTARIEF, "—"),
    ],
    "Onderdak — waterkerende, dampopen folie (materiaal + aanbrengen)": [
        ("Dampopen onderdakfolie (materiaal)", 2.6, "m²/m²", 1.0, "fabrikantprijs"),
        ("Aanbrengen folie (arbeid)", 0.042, "u/m²", DAK_RENO_UURTARIEF, "—"),
    ],
    "Isolatie Rd 3,8 — materiaal + aanbrengen": [
        ("Isolatieplaat Rd 3,8 — PIR/steenwol (materiaal)", 18.0, "m²/m²", 1.0, "Homedeal/Oranje Dakbeheer"),
        ("Aanbrengen isolatie (arbeid — kan 9% btw)", 0.156, "u/m²", DAK_RENO_UURTARIEF, "—"),
    ],
    "Nieuwe tengels + panlatten — materiaal + arbeid": [
        ("Tengels + panlatten — hout (materiaal)", 5.6, "m/m²", 1.0, "houthandel"),
        ("Aanbrengen tengels/panlatten (arbeid)", 0.109, "u/m²", DAK_RENO_UURTARIEF, "—"),
    ],
    "Pannen leggen — arbeid": [
        ("Pannen leggen (arbeid)", 0.40, "u/m²", DAK_RENO_UURTARIEF, "Kosten-Dakdekker (leggen 30–35%)"),
        ("Pashulp, snijwerk, bevestiging (arbeid)", 0.044, "u/m²", DAK_RENO_UURTARIEF, "—"),
    ],
    "Nok-/kantpannen (droge nok/vorst), hulpstukken, bevestiging": [
        ("Nok-/kant-/vorstpannen + droge-noksysteem (materiaal)", 4.6, "m/m²", 1.0, "fabrikantprijs"),
        ("Aanbrengen nok/vorst (arbeid)", 0.076, "u/m²", DAK_RENO_UURTARIEF, "—"),
    ],
    "Dakrandafwerking — boeiboord/windveer, daktrim": [
        ("Boeiboord/windveer + daktrim (materiaal)", 2.7, "m/m²", 1.0, "—"),
        ("Aanbrengen dakrand (arbeid)", 0.04, "u/m²", DAK_RENO_UURTARIEF, "—"),
    ],
    "Steiger (toegerekend per m²)": [
        ("Steigerhuur — toegerekend over de looptijd", 6.8, "post/m²", 1.0, "steigerverhuur NL"),
        ("Op- en afbouw steiger (arbeid)", 0.06, "u/m²", DAK_RENO_UURTARIEF, "—"),
    ],
    "Materiaaltransport, kraan/hijswerk, klein materieel": [
        ("Kraan/pannenlift — toegerekend", 2.5, "post/m²", 1.0, "—"),
        ("Transport materiaal + klein materieel", 2.0, "post/m²", 1.0, "—"),
    ],
}

# Dekkend aantal pannen per m² (LCL–UCL) per type — om een geoffreerd pannenaantal te toetsen aan het
# dakoppervlak (bron: Sleiderink / dakpanrichtlijnen). Holle keramisch & OVH liggen hoger dan vlakke/beton.
DAK_RENO_PANNEN_PER_M2 = {
    "Sneldek (grootformaat beton)": (8.5, 10.5),
    "Betonpan / vlak keramisch": (10.0, 12.0),
    "Keramisch hol / OVH": (14.0, 16.0),
}

# Contacten & afspraken per dakbedrijf (datum/tijd/type/status) — gesynchroniseerd met de DePoorter-agenda.
# Geen geseede afspraken: de afsprakenlijst komt volledig uit je eigen agenda (iCal-import) en
# handmatige invoer. (Een verse start toont dus een lege lijst tot je importeert of toevoegt.)
DAK_AFSPRAKEN_DEFAULT = []
DAK_AFSPR_TYPES = ["Contact", "Bellen", "Mailen", "Bezoek/inspectie", "Offerte-overleg", "Oplevering", "Overig"]
DAK_AFSPR_STATUS = ["Bezoek gepland", "Bezoek uitgevoerd", "Wachten op offerte", "Offerte ontvangen", "Geannuleerd"]
DAK_AFSPR_GAP_MIN = 60  # minimaal aantal minuten tussen twee afspraken op dezelfde dag


def _afspraak_conflicten(rows, min_gap_min=DAK_AFSPR_GAP_MIN):
    """Afspraken op dezelfde dag die overlappen of < min_gap_min uit elkaar liggen."""
    from datetime import datetime
    per_dag = {}
    for r in rows:
        d, t = str(r.get("Datum") or "").strip(), str(r.get("Tijd") or "").strip()
        if str(r.get("Status") or "") == "Geannuleerd" or not d or not t:
            continue
        try:
            tt = datetime.strptime(t, "%H:%M")
        except ValueError:
            continue
        per_dag.setdefault(d, []).append((tt.hour * 60 + tt.minute, t, str(r.get("Bedrijf") or "")))
    waarschuwingen = []
    for d in sorted(per_dag):
        items = sorted(per_dag[d])
        for (m1, t1, b1), (m2, t2, b2) in zip(items, items[1:]):
            gap = m2 - m1
            if gap < min_gap_min:
                hoe = "overlap" if gap <= 0 else f"maar {gap} min ertussen"
                waarschuwingen.append(f"{d}: {t1} {b1} ↔ {t2} {b2} ({hoe})")
    return waarschuwingen


def _maand_kalender_cel(jaar, maand, daynum, weekdagidx, per_dag, conf_dat):
    """HTML voor één kalendercel (dagnummer + gekleurde afspraak-chips per status)."""
    from datetime import date
    kleur = {"Bezoek gepland": ("#e1ecff", "#2d6cdf"),
             "Bezoek uitgevoerd": ("#e3f5e9", "#1e8449"),
             "Offerte ontvangen": ("#fdf2dc", "#d68910"),
             "Wachten op offerte": ("#fdf2dc", "#d68910"),
             "Geannuleerd": ("#eeeeee", "#999999")}

    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if daynum == 0:
        return "<div style='min-height:58px;'></div>"
    iso = date(jaar, maand, daynum).isoformat()
    appts = per_dag.get(iso, [])
    statuses = [a[2] for a in appts]
    if iso in conf_dat:
        bg = "#fdecec"
    elif "Bezoek gepland" in statuses:
        bg = "#eef4fd"
    elif weekdagidx >= 5:
        bg = "#f6f7f8"
    else:
        bg = "#ffffff"
    parts = [f"<div style='text-align:right;font-size:10px;color:#8a9099;'>{daynum}</div>"]
    for t, b, sstat in appts:
        bgc, brc = kleur.get(sstat, ("#eef2f5", "#8a9099"))
        mark = "⚠️ " if iso in conf_dat else ""
        strike = "text-decoration:line-through;" if sstat == "Geannuleerd" else ""
        label = (f"{t} " if t else "") + esc(b)
        parts.append(f"<div style='background:{bgc};border-left:3px solid {brc};border-radius:3px;"
                     f"margin-top:2px;padding:0 3px;font-size:10px;line-height:1.3;{strike}"
                     f"overflow:hidden;' title='{esc(sstat)}: {label}'>{mark}{label}</div>")
    return (f"<div style='min-height:58px;background:{bg};border:1px solid #e2e6ea;"
            f"border-radius:4px;padding:2px 3px;'>" + "".join(parts) + "</div>")


def _render_maand_kalender(jaar, maand, per_dag, conf_dat):
    """Teken een maandkalender (ma–zo) met st.columns — elke week is een aparte rij."""
    import calendar
    dagen = ["ma", "di", "wo", "do", "vr", "za", "zo"]
    mnd = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
           "september", "oktober", "november", "december"]
    st.markdown(f"**📅 {mnd[maand - 1]} {jaar}**")
    _hc = st.columns(7)
    for _i, _d in enumerate(dagen):
        _hc[_i].markdown(f"<div style='text-align:center;font-size:11px;font-weight:600;"
                         f"color:#8a9099;'>{_d}</div>", unsafe_allow_html=True)
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(jaar, maand):
        _wc = st.columns(7)
        for _i, _daynum in enumerate(week):
            _wc[_i].markdown(_maand_kalender_cel(jaar, maand, _daynum, _i, per_dag, conf_dat),
                             unsafe_allow_html=True)


def _dak_roof_3d_fig(L, B, pitch_deg, wall_h=3.0, dk_br=0.0, dk_di=0.0, dkf_br=0.0, dkf_di=0.0,
                     dk_right_b=0.3, dk_right_f=0.5):
    """Schematisch 3D-model van een gezadeld pannendak (muren + twee dakschilden + dakkapellen).

    L = nokrichting (m), B = breedte gevel-tot-gevel (m), pitch_deg = dakhelling. Dakkapel op het
    achterschild (dk_br × dk_di, rechterrand dk_right_b m van de rechterwand) en op het voorschild
    (dkf_br × dkf_di, dk_right_f m). Visueel/indicatief.
    """
    pitch = math.radians(max(0.0, min(pitch_deg, 75.0)))
    apex = wall_h + (B / 2.0) * math.tan(pitch)
    V = [(0, 0, 0), (L, 0, 0), (L, B, 0), (0, B, 0),                  # 0-3 grondvlak
         (0, 0, wall_h), (L, 0, wall_h), (L, B, wall_h), (0, B, wall_h),  # 4-7 dakvoet
         (0, B / 2, apex), (L, B / 2, apex)]                          # 8-9 nok
    xs, ys, zs = [v[0] for v in V], [v[1] for v in V], [v[2] for v in V]
    roof = [(4, 5, 9), (4, 9, 8), (7, 6, 9), (7, 9, 8)]
    walls = [(0, 1, 5), (0, 5, 4), (3, 2, 6), (3, 6, 7), (0, 3, 7), (0, 7, 4),
             (1, 2, 6), (1, 6, 5), (4, 7, 8), (5, 6, 9)]
    fig = go.Figure()
    fig.add_trace(go.Mesh3d(x=xs, y=ys, z=zs, i=[t[0] for t in walls], j=[t[1] for t in walls],
                            k=[t[2] for t in walls], color="#d9c7a3", flatshading=True, name="muren"))
    fig.add_trace(go.Mesh3d(x=xs, y=ys, z=zs, i=[t[0] for t in roof], j=[t[1] for t in roof],
                            k=[t[2] for t in roof], color="#3a3f44", flatshading=True, name="dakvlak"))

    def _dormer(br, di, toward_back, naam, right):
        if br <= 0 or di <= 0:
            return
        if right and right > 0:              # rechterrand op `right` meter van de rechterwand
            x1 = min(L, L - right)
            x0 = max(0.0, x1 - br)
        else:                                # 0 = gecentreerd
            xc = L / 2.0
            x0, x1 = max(0.0, xc - br / 2), min(L, xc + br / 2)
        if toward_back:
            yi, yo = B * 0.58, min(B * 0.96, B * 0.58 + di)
        else:
            yi, yo = B * 0.42, max(B * 0.04, B * 0.42 - di)
        z_top = max(wall_h + 0.3, min(apex - abs(yi - B / 2) * math.tan(pitch), apex - 0.2))
        DV = [(x0, yi, wall_h), (x1, yi, wall_h), (x1, yo, wall_h), (x0, yo, wall_h),
              (x0, yi, z_top), (x1, yi, z_top), (x1, yo, z_top), (x0, yo, z_top)]
        cub = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
               (3, 2, 6), (3, 6, 7), (0, 3, 7), (0, 7, 4), (1, 2, 6), (1, 6, 5)]
        fig.add_trace(go.Mesh3d(x=[v[0] for v in DV], y=[v[1] for v in DV], z=[v[2] for v in DV],
                                i=[t[0] for t in cub], j=[t[1] for t in cub], k=[t[2] for t in cub],
                                color="#9fb0bb", flatshading=True, name=naam))

    _dormer(dk_br, dk_di, True, "dakkapel achter", dk_right_b)
    _dormer(dkf_br, dkf_di, False, "dakkapel voor", dk_right_f)
    fig.update_layout(scene=dict(aspectmode="data", xaxis_title="lengte (m)", yaxis_title="breedte (m)",
                                 zaxis_title="hoogte (m)",
                                 camera=dict(projection=dict(type="orthographic"),
                                             eye=dict(x=1.4, y=1.4, z=0.9))),
                      margin=dict(l=0, r=0, t=10, b=0), height=440)
    return fig


def _dak_vergelijking_chart_png(hl, dak_opp, lo, hi, sc_lo=None, sc_hi=None, sc_mid=None):
    """Twee staafdiagrammen: totaal incl. btw per offerte + €/m² t.o.v. de markt- en should-cost band."""
    import io
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    namen = [h["Offerte"] for h in hl]
    incl = [h["Incl. btw"] for h in hl]
    m2 = [h["€/m² incl."] for h in hl]
    kleur = ["#2d6cdf", "#1e8449", "#d68910", "#8e44ad", "#16a085"][:len(namen)] or ["#2d6cdf"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.2, 3.2))
    b1 = ax1.bar(namen, incl, color=kleur)
    ax1.set_title("Totaal incl. btw (€)", fontsize=10)
    ax1.bar_label(b1, fmt="€%.0f", fontsize=8)
    ax1.tick_params(axis="x", labelrotation=12, labelsize=7)
    if hi and hi > 0:
        ax2.axhspan(lo, hi, color="#e7f1fb", alpha=0.6, label=f"markt €{lo:.0f}–{hi:.0f}/m²")
    if sc_lo and sc_hi:
        ax2.axhspan(sc_lo, sc_hi, color="#e3f5e9", alpha=0.7,
                    label=f"should-cost €{sc_lo:.0f}–{sc_hi:.0f}/m²")
        if sc_mid:
            ax2.axhline(sc_mid, color="#1e8449", linestyle="--", linewidth=1)
    b2 = ax2.bar(namen, m2, color=kleur)
    ax2.set_title("€/m² incl. btw — t.o.v. should-cost band", fontsize=10)
    ax2.bar_label(b2, fmt="€%.0f", fontsize=8)
    ax2.tick_params(axis="x", labelrotation=12, labelsize=7)
    ax2.legend(fontsize=6.5)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130)
    plt.close(fig)
    return buf.getvalue()


def _dak_vergelijking_pdf_bytes(hl, cmpdf, posten_df, dak_opp, isde1, isde2, bullets, lo, hi, normdf=None,
                                sc_lo=None, sc_hi=None, sc_mid=None):
    """Printbaar A4-rapport van de offertevergelijking met grafieken, scope en advies."""
    import io
    from datetime import date
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=14 * mm, bottomMargin=14 * mm,
                            leftMargin=13 * mm, rightMargin=13 * mm)
    ss = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=ss["Title"], fontSize=16)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=11, spaceBefore=8, spaceAfter=3)
    sub = ParagraphStyle("sub", parent=ss["Normal"], fontSize=8, textColor=colors.HexColor("#555555"))
    head = ParagraphStyle("hd", parent=ss["Normal"], fontSize=7.5, textColor=colors.white, fontName="Helvetica-Bold")
    cell = ParagraphStyle("cl", parent=ss["Normal"], fontSize=7.5)
    small = ParagraphStyle("sm", parent=ss["Normal"], fontSize=8, leading=11)

    def esc(t):
        return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _tbl(cols, rows, widths):
        data = [[Paragraph(esc(c), head) for c in cols]]
        for r in rows:
            data.append([Paragraph(esc(v), cell) for v in r])
        t = Table(data, repeatRows=1, colWidths=widths)
        style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                 ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8bcc0")),
                 ("VALIGN", (0, 0), (-1, -1), "TOP"),
                 ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f5f7")])]
        t.setStyle(TableStyle(style))
        return t

    el = [Paragraph("Offertevergelijking — dakrenovatie", title),
          Paragraph(f"Gegenereerd op {date.today().isoformat()} · dakoppervlak {dak_opp:.0f} m²", sub),
          Spacer(1, 6)]
    el.append(Paragraph("Kerncijfers", h2))
    _kcols = ["Offerte", "Excl. btw", "Incl. btw", "€/m²", "Btw", "Isolatie", "Garantie"]
    _krows = [[h.get("Offerte", ""), f"€{h.get('Excl. btw', 0):.0f}", f"€{h.get('Incl. btw', 0):.0f}",
               f"€{h.get('€/m² incl.', 0):.0f}", h.get("Effectief btw", ""), h.get("Isolatie", ""),
               h.get("Garantie", "")] for h in hl]
    el.append(_tbl(_kcols, _krows, [30 * mm, 20 * mm, 20 * mm, 14 * mm, 12 * mm, 36 * mm, 30 * mm]))
    try:
        el.append(Spacer(1, 6))
        el.append(Image(io.BytesIO(_dak_vergelijking_chart_png(hl, dak_opp, lo, hi, sc_lo, sc_hi, sc_mid)),
                        width=172 * mm, height=67 * mm))
    except Exception:  # noqa: BLE001
        pass
    el.append(Paragraph("Scope-vergelijking", h2))
    _scols = list(cmpdf.columns)
    _srows = [[r[c] for c in _scols] for _, r in cmpdf.iterrows()]
    el.append(_tbl(_scols, _srows, None))
    el.append(Paragraph("ISDE-subsidie & advies", h2))
    el.append(Paragraph(f"Dakisolatie met Rd ≥ 3,5 m²K/W komt in aanmerking. Indicatie voor {dak_opp:.0f} m²: "
                        f"± €{isde1:.0f} (één maatregel) tot € {isde2:.0f} (twee maatregelen). Geldt voor beide "
                        "offertes en verlaagt de netto kosten.", small))
    el.append(Spacer(1, 3))
    for b in bullets:
        el.append(Paragraph("• " + esc(b.replace("**", "")), small))
    if normdf is not None and len(normdf):
        el.append(Paragraph("Eerlijke vergelijking — zelfde scope, netto (incl. btw)", h2))
        _ncols = [c for c in normdf.columns if c != "Toegevoegd"]
        _nrows = [[(str(r[c]) if c == "Offerte" else f"€{r[c]:.0f}") for c in _ncols] for _, r in normdf.iterrows()]
        el.append(_tbl(_ncols, _nrows, None))
    el.append(Spacer(1, 8))
    el.append(Paragraph("Posten per offerte", h2))
    _prows2 = [[str(r["Bedrijf"]), str(r["Onderdeel"]), f"€{float(r['Prijs excl. btw']):.0f}", f"{int(r['Btw %'])}%"]
               for _, r in posten_df.iterrows()]
    el.append(_tbl(["Offerte", "Post", "Excl. btw", "Btw"], _prows2, [32 * mm, 96 * mm, 22 * mm, 12 * mm]))
    doc.build(el)
    return buf.getvalue()


def _afspraken_pdf_bytes(rows, conflicten=None):
    """Printbare A4-PDF (liggend) van de contacten & afspraken."""
    import io
    from datetime import date
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=12 * mm, bottomMargin=12 * mm,
                            leftMargin=12 * mm, rightMargin=12 * mm,
                            title="Dakrenovatie — contacten & afspraken")
    base = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=base["Title"], fontSize=16, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=base["Normal"], fontSize=9, textColor=colors.grey)
    cell = ParagraphStyle("cell", parent=base["Normal"], fontSize=8, leading=10)
    head = ParagraphStyle("head", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")

    def _p(txt, style):
        return Paragraph(str(txt or "").replace("&", "&amp;").replace("<", "&lt;"), style)

    elems = [_p("Dakrenovatie — contacten & afspraken", h),
             _p("Gegenereerd op " + date.today().isoformat(), sub), Spacer(1, 6)]
    cols = ["Bedrijf", "Type", "Datum", "Tijd", "Contactpersoon", "Telefoon", "E-mail", "Status", "Notitie"]
    widths = [34, 22, 20, 13, 30, 28, 44, 28, 54]  # mm, som ≈ 273 (liggend A4 minus marges)
    data = [[_p(c, head) for c in cols]]
    for r in sorted(rows, key=lambda x: (str(x.get("Datum") or ""), str(x.get("Tijd") or ""))):
        data.append([_p(r.get(c, ""), cell) for c in cols])
    tbl = Table(data, repeatRows=1, colWidths=[w * mm for w in widths])
    style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
             ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b0b0b0")),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f2f4f6")))
    tbl.setStyle(TableStyle(style))
    elems.append(tbl)
    elems.append(Spacer(1, 8))
    if conflicten:
        red = ParagraphStyle("red", parent=cell, textColor=colors.HexColor("#c0392b"))
        elems.append(_p("Planning-check — te krap (overlap of < 1 uur ertussen):", red))
        for c in conflicten:
            elems.append(_p("• " + c, red))
    else:
        green = ParagraphStyle("green", parent=cell, textColor=colors.HexColor("#1e8449"))
        elems.append(_p("Planning-check: geen overlap — minstens 1 uur tussen afspraken op dezelfde dag.", green))
    doc.build(elems)
    return buf.getvalue()


def _fetch_url(url, timeout=15):
    """Download tekst van een URL (stdlib, geen extra dependency)."""
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read().decode("utf-8", "replace")


@st.cache_data(show_spinner=False, ttl=86400)
def _bag_geocode(address):
    """Adres → lijst van {naam, x, y} (RD-coördinaten) via de PDOK-adressenservice (Locatieserver)."""
    import urllib.parse
    # Normaliseer: komma's weg, dubbele spaties weg, en een aan-elkaar-geplakt huisnummer losmaken
    # ("Compiegnehof11" → "Compiegnehof 11"). PDOK is ongevoelig voor accenten/hoofdletters.
    _adr = re.sub(r"([^\W\d_])(\d)", r"\1 \2", re.sub(r"\s+", " ", address.replace(",", " ")).strip())
    url = ("https://api.pdok.nl/bzk/locatieserver/search/v3_1/free?q=" + urllib.parse.quote(_adr)
           + "&fq=type:adres&fl=weergavenaam,centroide_rd&rows=5")
    out = []
    for d in json.loads(_fetch_url(url, timeout=20)).get("response", {}).get("docs", []):
        m_ = re.search(r"POINT\(([-\d.]+)\s+([-\d.]+)\)", str(d.get("centroide_rd") or ""))
        if m_:
            out.append({"naam": d.get("weergavenaam", ""), "x": float(m_.group(1)), "y": float(m_.group(2))})
    return out


@st.cache_data(show_spinner=False, ttl=86400)
def _bag3d_fc_text(x, y, d=6.0):
    """Ruwe 3D BAG-respons (CityJSONFeatures) voor de panden rond een RD-coördinaat (bbox in EPSG:28992)."""
    url = ("https://api.3dbag.nl/collections/pand/items?"
           f"bbox={x - d:.1f},{y - d:.1f},{x + d:.1f},{y + d:.1f}&limit=20")
    return _fetch_url(url, timeout=30)


def _earclip(ring_pts):
    """Trianguleer een (mogelijk niet-convexe) 3D-polygoon via ear-clipping. Geeft lokale index-triples.

    Voorkomt de 'rare lijnen' die een simpele waaier-triangulatie op niet-convexe dakvlakken oplevert.
    """
    n = len(ring_pts)
    if n < 3:
        return []
    # vlaknormaal (Newell) → projecteer naar 2D op de dominante as
    nx = ny = nz = 0.0
    for i in range(n):
        a, b = ring_pts[i], ring_pts[(i + 1) % n]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    ax = max(range(3), key=lambda k: abs((nx, ny, nz)[k]))
    drop = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[ax]
    p = [(pt[drop[0]], pt[drop[1]]) for pt in ring_pts]
    idx = list(range(n))
    if sum(p[i][0] * p[(i + 1) % n][1] - p[(i + 1) % n][0] * p[i][1] for i in range(n)) < 0:
        idx.reverse()

    def _in_tri(q, a, b, c):
        d1 = (q[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (q[1] - b[1])
        d2 = (q[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (q[1] - c[1])
        d3 = (q[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (q[1] - a[1])
        return not (((d1 < 0) or (d2 < 0) or (d3 < 0)) and ((d1 > 0) or (d2 > 0) or (d3 > 0)))

    tris, guard = [], 0
    while len(idx) > 3 and guard < n * n + 5:
        guard += 1
        m = len(idx)
        for ii in range(m):
            i0, i1, i2 = idx[(ii - 1) % m], idx[ii], idx[(ii + 1) % m]
            a, b, c = p[i0], p[i1], p[i2]
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) <= 0:
                continue  # reflex/straight → geen oor
            if any(j not in (i0, i1, i2) and _in_tri(p[j], a, b, c) for j in idx):
                continue
            tris.append((i0, i1, i2))
            idx.pop(ii)
            break
        else:
            break
    if len(idx) == 3:
        tris.append((idx[0], idx[1], idx[2]))
    return tris


def _bag3d_fig(text, x=None, y=None):
    """Bouw een Plotly-3D-figuur uit een 3D BAG-respons (FeatureCollection van CityJSONFeatures).

    Met een RD-coördinaat (x, y) wordt alleen het pand getoond waarvan het zwaartepunt het dichtst
    bij die coördinaat ligt — zo blijven bij rijtjeswoningen de buurpanden buiten beeld.
    """
    resp = json.loads(text)
    feats = resp.get("features")
    if feats is None:  # losse CityJSONFeature i.p.v. een collectie
        feats = [resp.get("feature", resp)]
    tf0 = resp.get("transform") or (resp.get("metadata") or {}).get("transform")

    def _realverts(feat):
        verts = feat.get("vertices", []) or []
        tf = feat.get("transform") or tf0
        if tf:
            sc, tr = tf.get("scale", [1, 1, 1]), tf.get("translate", [0, 0, 0])
            return [(v[0] * sc[0] + tr[0], v[1] * sc[1] + tr[1], v[2] * sc[2] + tr[2]) for v in verts]
        return [(v[0], v[1], v[2]) for v in verts]

    rverts = [_realverts(f) for f in feats]

    def _lod(obj):
        geoms = obj.get("geometry") or []
        if not geoms:
            return None
        return next((c for c in geoms if str(c.get("lod")) in ("2.2", "2")), None) \
            or max(geoms, key=lambda c: float(str(c.get("lod", "0")) or 0))

    def _flat_idx(o, acc):
        if isinstance(o, int):
            acc.append(o)
        elif isinstance(o, list):
            for e in o:
                _flat_idx(e, acc)

    # Verzamel per geometrie-object (BuildingPart) het pand-id en het zwaartepunt, zodat we één
    # pand kunnen kiezen — ook als alle buurpanden in één feature met gedeelde vertices zitten.
    units = []
    for _fi, feat in enumerate(feats):
        rv = rverts[_fi]
        for oid, obj in (feat.get("CityObjects", {}) or {}).items():
            g = _lod(obj)
            if not g:
                continue
            _ix = []
            _flat_idx(g.get("boundaries", []) or [], _ix)
            _ix = [i for i in _ix if 0 <= i < len(rv)]
            if not _ix:
                continue
            cx = sum(rv[i][0] for i in _ix) / len(_ix)
            cy = sum(rv[i][1] for i in _ix) / len(_ix)
            units.append({"pid": oid.split("-")[0], "fi": _fi, "g": g, "cx": cx, "cy": cy})

    _allpids = {u["pid"] for u in units if "Pand." in u["pid"]}
    sel_pid = None
    if x is not None and y is not None and len(_allpids) > 1 and units:
        sel_pid = min(units, key=lambda u: (u["cx"] - x) ** 2 + (u["cy"] - y) ** 2)["pid"]
    sel_units = [u for u in units if (sel_pid is None or u["pid"] == sel_pid)]
    pids = sorted({u["pid"] for u in sel_units})

    X, Y, Z, roof, other = [], [], [], [], []
    roof_tot = roof_sl = roof_fl = foot = 0.0
    foot_rings, flat_patches = [], []

    def _tri(ring, rv, off, bucket):
        if ring and len(ring) >= 3:
            for a, b, c in _earclip([rv[i] for i in ring]):
                bucket.append((ring[a] + off, ring[b] + off, ring[c] + off))

    def _area_tilt(pts):
        """Oppervlak (m²) en helling (° t.o.v. horizontaal) van een 3D-polygoon (Newell)."""
        nx = ny = nz = 0.0
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            nx += (a[1] - b[1]) * (a[2] + b[2])
            ny += (a[2] - b[2]) * (a[0] + b[0])
            nz += (a[0] - b[0]) * (a[1] + b[1])
        mag = math.sqrt(nx * nx + ny * ny + nz * nz)
        if mag == 0:
            return 0.0, 0.0
        return mag / 2.0, math.degrees(math.acos(min(1.0, abs(nz) / mag)))

    for u in sel_units:
        rv = rverts[u["fi"]]
        g = u["g"]
        off = len(X)
        X += [p[0] for p in rv]
        Y += [p[1] for p in rv]
        Z += [p[2] for p in rv]
        gtype, bnd = g.get("type"), g.get("boundaries", []) or []
        sem = g.get("semantics") or {}
        surfaces, values = sem.get("surfaces") or [], sem.get("values")

        def _stype(idx):
            try:
                return surfaces[idx].get("type") if idx is not None else None
            except (IndexError, TypeError):
                return None
        if gtype == "Solid":
            shells, vshells = bnd, (values or [])
        elif gtype in ("MultiSurface", "CompositeSurface"):
            shells, vshells = [bnd], [values]
        else:
            shells, vshells = [], []
        for si, shell in enumerate(shells):
            svals = vshells[si] if (vshells and si < len(vshells)) else None
            for fi, face in enumerate(shell):
                stype = _stype(svals[fi] if (svals and fi < len(svals)) else None)
                ring = face[0] if face else []
                _tri(ring, rv, off, roof if stype == "RoofSurface" else other)
                if len(ring) >= 3 and stype == "RoofSurface":
                    _a, _tilt = _area_tilt([rv[_i] for _i in ring])
                    roof_tot += _a
                    if _tilt <= 20.0:        # bijna plat → dakkapeltop / plat dak
                        roof_fl += _a
                        _rx = [rv[_i][0] for _i in ring]
                        _ry = [rv[_i][1] for _i in ring]
                        _dx, _dy = max(_rx) - min(_rx), max(_ry) - min(_ry)
                        flat_patches.append({"w": max(_dx, _dy), "d": min(_dx, _dy), "m2": _a})
                    elif _tilt < 80.0:       # hellend dakvlak → krijgt pannen
                        roof_sl += _a
                elif len(ring) >= 3 and stype == "GroundSurface":
                    foot += _area_tilt([rv[_i] for _i in ring])[0]
                    foot_rings.append([(rv[_i][0], rv[_i][1]) for _i in ring])
    if X:
        cx, cy, mz = sum(X) / len(X), sum(Y) / len(Y), min(Z)
        X = [v - cx for v in X]
        Y = [v - cy for v in Y]
        Z = [v - mz for v in Z]
    fig = go.Figure()
    if other:
        fig.add_trace(go.Mesh3d(x=X, y=Y, z=Z, i=[t[0] for t in other], j=[t[1] for t in other],
                                k=[t[2] for t in other], color="#cdb892", flatshading=True, name="gevels/grond"))
    if roof:
        fig.add_trace(go.Mesh3d(x=X, y=Y, z=Z, i=[t[0] for t in roof], j=[t[1] for t in roof],
                                k=[t[2] for t in roof], color="#7a2f2f", flatshading=True, name="dak"))
    fig.update_layout(scene=dict(aspectmode="data", xaxis_title="x (m)", yaxis_title="y (m)",
                                 zaxis_title="hoogte (m)",
                                 camera=dict(projection=dict(type="orthographic"),
                                             eye=dict(x=1.4, y=1.4, z=0.9))),
                      margin=dict(l=0, r=0, t=10, b=0), height=460)
    return fig, {"faces": len(roof) + len(other), "roof": len(roof), "panden": sorted(set(pids)),
                 "roof_m2": roof_tot, "roof_sloped_m2": roof_sl, "roof_flat_m2": roof_fl, "footprint_m2": foot,
                 "footprint_rings": foot_rings,
                 "flat_patches": sorted([p for p in flat_patches if p["m2"] >= 1.0], key=lambda p: -p["m2"])}


@st.cache_data(show_spinner=False, ttl=86400)
def _perceel_rings(x, y, d=40.0):
    """Perceelpolygonen (RD) rond een coördinaat via de PDOK Kadastralekaart-WFS. Lijst van buitenringen."""
    url = ("https://service.pdok.nl/kadaster/kadastralekaart/wfs/v5_0?service=WFS&version=2.0.0"
           "&request=GetFeature&typeNames=Perceel&srsName=EPSG:28992&count=50&outputFormat=application/json"
           f"&bbox={x - d:.1f},{y - d:.1f},{x + d:.1f},{y + d:.1f},EPSG:28992")
    data = json.loads(_fetch_url(url, timeout=25))
    rings = []
    for ft in data.get("features", []):
        geom = ft.get("geometry") or {}
        gtype, coords = geom.get("type"), geom.get("coordinates") or []
        polys = [coords] if gtype == "Polygon" else (coords if gtype == "MultiPolygon" else [])
        for poly in polys:
            if poly and poly[0]:
                rings.append([(float(p[0]), float(p[1])) for p in poly[0]])
    return rings


def _ring_contains(ring, px, py):
    """Punt-in-polygoon (ray casting)."""
    inside, n, j = False, len(ring), len(ring) - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _perceel_plan_fig(perceel_rings, house_rings, x=None, y=None, extras=None):
    """2D-plattegrond: perceel(en) + huis-footprint (+ bijgebouwen), op schaal (gelijke assen, RD-meters)."""
    fig = go.Figure()
    own = None
    if x is not None and y is not None:
        own = next((i for i, r in enumerate(perceel_rings) if len(r) >= 3 and _ring_contains(r, x, y)), None)
    for i, r in enumerate(perceel_rings):
        if len(r) < 3:
            continue
        xs = [p[0] for p in r] + [r[0][0]]
        ys = [p[1] for p in r] + [r[0][1]]
        if i == own or (own is None and len(perceel_rings) == 1):
            fig.add_trace(go.Scatter(x=xs, y=ys, fill="toself", fillcolor="rgba(120,170,90,0.30)",
                                     line=dict(color="#4d7a2a", width=2), name="ons perceel", hoverinfo="skip"))
        else:
            fig.add_trace(go.Scatter(x=xs, y=ys, fill="toself", fillcolor="rgba(0,0,0,0.03)", showlegend=False,
                                     line=dict(color="#c2c2c2", width=1), name="buurperceel", hoverinfo="skip"))
    for k, r in enumerate(house_rings):
        if len(r) < 3:
            continue
        xs = [p[0] for p in r] + [r[0][0]]
        ys = [p[1] for p in r] + [r[0][1]]
        fig.add_trace(go.Scatter(x=xs, y=ys, fill="toself", fillcolor="rgba(150,40,40,0.55)",
                                 line=dict(color="#7a2f2f", width=2), name="huis", showlegend=(k == 0),
                                 hoverinfo="skip"))
    for ex in (extras or []):
        r = ex.get("ring") or []
        if len(r) < 3:
            continue
        xs = [p[0] for p in r] + [r[0][0]]
        ys = [p[1] for p in r] + [r[0][1]]
        fig.add_trace(go.Scatter(x=xs, y=ys, fill="toself", fillcolor=ex.get("fill", "rgba(90,130,160,0.45)"),
                                 line=dict(color=ex.get("line", "#3f6781"), width=2), name=ex.get("naam"),
                                 hoverinfo="skip"))
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=440, legend=dict(orientation="h"),
                      xaxis_title="RD-x (m)", yaxis_title="RD-y (m)")
    return fig


def _ics_unfold(text):
    """Splits een iCal-bestand in regels en plak gevouwen vervolgregels weer aan elkaar."""
    out = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line[:1] in (" ", "\t") and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def _ics_dt(val, key):
    """DTSTART-waarde -> ('YYYY-MM-DD', 'HH:MM'); zet UTC om naar Europe/Amsterdam."""
    from datetime import datetime, timezone
    try:
        from zoneinfo import ZoneInfo
        ams = ZoneInfo("Europe/Amsterdam")
    except Exception:  # noqa: BLE001
        ams = None
    v = val.strip()
    if "VALUE=DATE" in key.upper() or ("T" not in v and len(v) == 8):
        return f"{v[0:4]}-{v[4:6]}-{v[6:8]}", ""
    try:
        if v.endswith("Z"):
            dt = datetime.strptime(v[:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
            if ams:
                dt = dt.astimezone(ams)
        else:
            dt = datetime.strptime(v[:15], "%Y%m%dT%H%M%S")
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    except ValueError:
        return "", ""


def _afspr_key(r):
    """Sleutel om afspraken te ontdubbelen: bedrijf (genormaliseerd) + datum + tijd."""
    return (str(r.get("Bedrijf") or "").strip().lower(),
            str(r.get("Datum") or "").strip(), str(r.get("Tijd") or "").strip())


def _afspr_slotkey(r):
    """Dedup op tijdslot: zelfde datum + tijd = dezelfde afspraak, ook bij een andere schrijfwijze
    van de naam (bv. seed 'Dakbedrijf Westermeer' vs agenda 'Dak offerte westerman'). Afspraken
    zonder datum én tijd vallen terug op de exacte bedrijf+datum+tijd-sleutel."""
    _d, _t = str(r.get("Datum") or "").strip(), str(r.get("Tijd") or "").strip()
    return ("slot", _d, _t) if (_d and _t) else ("exact",) + _afspr_key(r)


def _ics_dak_afspraken(text, keyword="dak", today=None, min_datum=None):
    """Afspraken uit iCal waarvan de titel het trefwoord bevat en datum >= min_datum."""
    from datetime import date
    today = today or date.today().isoformat()
    rows, cur = [], None
    for line in _ics_unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            s = (cur or {}).get("summary", "") if cur is not None else ""
            d = (cur or {}).get("datum", "") if cur is not None else ""
            if cur is not None and keyword in s.lower() and not (min_datum and d and d < min_datum):
                typ = "Offerte-overleg" if "offerte" in s.lower() else "Bezoek/inspectie"
                status = "Bezoek uitgevoerd" if (d or "9999") < today else "Bezoek gepland"
                rows.append({"Bedrijf": s.strip()[:60], "Type": typ,
                             "Datum": d, "Tijd": cur.get("tijd", ""),
                             "Contactpersoon": "", "Telefoon": "", "E-mail": "",
                             "Status": status, "Notitie": "Uit Google Agenda"})
            cur = None
        elif cur is not None and ":" in line:
            key, val = line.split(":", 1)
            name = key.split(";", 1)[0].upper()
            if name == "SUMMARY":
                cur["summary"] = val
            elif name == "DTSTART":
                cur["datum"], cur["tijd"] = _ics_dt(val, key)
    rows.sort(key=lambda r: (r["Datum"], r["Tijd"]))
    return rows


@st.cache_data
def _startgids_bytes(niche, producten_json):
    import json
    import startgids
    prod = json.loads(producten_json)
    return startgids.build_pdf_bytes(niche, prod), startgids.build_excel_bytes(niche, prod)


# --- Permanente state laden (Gist) — per-niche keuzes overleven een reboot ---
if "niche_state" not in st.session_state:
    try:
        _data = store.load()
    except Exception:  # noqa: BLE001
        _data = {}
    _data = _data if isinstance(_data, dict) else {}
    st.session_state["niche_state"] = _data.get("niches", {})
    if "scans" not in st.session_state:
        st.session_state["scans"] = _data.get("scans", [])
    if "dakofferte" not in st.session_state:
        st.session_state["dakofferte"] = _data.get("dakofferte", DAK_DEFAULT)
    if "dak_posten" not in st.session_state:
        st.session_state["dak_posten"] = _data.get("dak_posten", DAK_POSTEN_DEFAULT)
    if "dak_afspraken" not in st.session_state:
        st.session_state["dak_afspraken"] = _data.get("dak_afspraken", DAK_AFSPRAKEN_DEFAULT)
    if "dak_shouldcost" not in st.session_state:
        st.session_state["dak_shouldcost"] = _data.get("dak_shouldcost", [])  # [] = automatisch
    if "dak_opp" not in st.session_state:
        st.session_state["dak_opp"] = float(_data.get("dak_opp", 60.0) or 60.0)
    if "dak_migr" not in st.session_state:
        st.session_state["dak_migr"] = _data.get("dak_migr", 0)
NS = st.session_state["niche_state"]  # {niche: {"producten":[...], "bc":{...}}}


def _persist():
    return store.save({"niches": NS, "scans": st.session_state.get("scans", []),
                       "dakofferte": st.session_state.get("dakofferte", []),
                       "dak_posten": st.session_state.get("dak_posten", []),
                       "dak_afspraken": st.session_state.get("dak_afspraken", []),
                       "dak_shouldcost": st.session_state.get("dak_shouldcost", []),
                       "dak_opp": st.session_state.get("dak_opp", 60.0),
                       "dak_migr": st.session_state.get("dak_migr", 0)})


def _persist_safe():
    """Opslaan zonder te crashen (bv. voor widget on_change-callbacks)."""
    try:
        _persist()
    except Exception:  # noqa: BLE001
        pass


_DAK_SEED_KW = ("westermeer", "albers")  # trefwoorden van de geseedde offertes


def _dak_fix_albers(offertes, posten):
    """One-time data fix: correct the Albers quote and (re)seat the seeded posten (Westermeer + Albers).

    Matcht op trefwoord, zodat ook naam-varianten en dubbele regels (bv. 'Westermeer' naast
    'Dakbedrijf Westermeer') worden opgeschoond. Posten van andere bedrijven blijven staan.
    """
    def _kw(r):
        b = str(r.get("Bedrijf") or "").lower()
        return any(k in b for k in _DAK_SEED_KW)
    offertes[:] = [o for o in offertes if not (_kw(o) or str(o.get("Offertenr.") or "") == "2026060231")]
    offertes.extend(dict(o) for o in DAK_DEFAULT if _kw(o))
    posten[:] = [p for p in posten if not _kw(p)]
    posten.extend(dict(p) for p in DAK_POSTEN_DEFAULT)


# Eenmalige correctie: Albers-mis-parse + dubbele/variant-posten van Westermeer opschonen.
if st.session_state.get("dak_migr", 0) < 7:
    _dak_fix_albers(st.session_state["dakofferte"], st.session_state["dak_posten"])
    st.session_state["dak_migr"] = 7
    try:
        _persist()
    except Exception:  # noqa: BLE001
        pass


# --- Actieve niche (bovenaan de zijbalk) — stuurt het hele dashboard --------
st.sidebar.header("🎯 Actieve niche")
_predef = ["(eigen / vrij)"] + [n["naam"] for n in m.NICHES]
_custom = [k for k in NS.keys() if k not in _predef]
_scan_namen = [s["Niche"] for s in st.session_state.get("scans", [])]
_niche_opties, _seen = [], set()
for _n in _predef + _custom + _scan_namen:
    if _n not in _seen:
        _seen.add(_n)
        _niche_opties.append(_n)
if st.session_state.get("_force_niche") in _niche_opties:
    st.session_state["actieve_niche"] = st.session_state.pop("_force_niche")
actieve_niche = st.sidebar.selectbox(
    "Kies niche", _niche_opties, key="actieve_niche", label_visibility="collapsed",
    help="Stuurt titel, portfolio, businesscase, markt, regels en de Niche-scan/Founder-check.")
if actieve_niche != "(eigen / vrij)" and st.session_state.get("_last_niche") != actieve_niche:
    _nd = next((n for n in m.NICHES if n["naam"] == actieve_niche), None)
    st.session_state["founder_idea"] = actieve_niche
    st.session_state["founder_ctx"] = ((f"Doelgroep: {_nd['klant']} " if _nd else "")
                                       + "Nederlandse starter met laag budget.")
st.session_state["_last_niche"] = actieve_niche

with st.sidebar.expander("➕ Nieuwe niche maken"):
    _nn = st.text_input("Naam van de niche", key="nieuw_naam")
    _nc = st.text_input("Korte context (optioneel)", key="nieuw_ctx")
    if st.button("Maak niche", key="nieuw_make", use_container_width=True):
        if not _nn.strip():
            st.warning("Geef de niche een naam.")
        else:
            _prods = ai.suggest_products(_nn.strip(), _nc) if ai.available() else None
            NS[_nn.strip()] = {"producten": _prods or []}
            st.session_state["_force_niche"] = _nn.strip()
            try:
                _persist()
            except Exception:  # noqa: BLE001
                pass
            st.rerun()
    st.caption("Met een LLM-key vult de AI meteen producten/diensten voor; anders start je leeg.")

if store.enabled():
    if st.sidebar.button("💾 Bewaar alles in Gist", use_container_width=True):
        try:
            _persist()
            st.sidebar.success("Opgeslagen.")
        except Exception as exc:  # noqa: BLE001
            st.sidebar.error(f"Opslaan mislukt: {exc}")
    st.sidebar.caption("☁️ Permanente opslag aan — keuzes overleven een reboot.")
else:
    st.sidebar.caption("💾 Per sessie. Zet GIST_TOKEN + ECOM_GIST_ID in Secrets voor permanente opslag.")

# --- Platform-aannames — bewegen mee met de niche --------------------------
_portf = m.NICHE_PORTFOLIOS.get(actieve_niche, m.STANDAARD_PRODUCTEN)
_heeft_producten = any(not p.get("Dienst") for p in _portf)
st.sidebar.divider()
if _heeft_producten:
    st.sidebar.header("⚙️ Platform-aannames")
    st.sidebar.caption("Standaard: verkopen via Bol.nl (B2C, prijzen incl. 21% btw).")
    _box = st.sidebar
else:
    st.sidebar.markdown("### ⚙️ Platform-aannames")
    _box = st.sidebar.expander("Marktplaats-fees (alleen nodig bij producten)")
    _box.caption("Deze niche is dienst-gericht — fees gelden alleen als je producten toevoegt.")
fees = {
    "commissie_pct": _box.slider("Commissie %", 0.0, 25.0, m.BOL["commissie_pct"] * 100, 0.5) / 100,
    "vaste_fee": _box.number_input("Vaste fee/artikel (€)", 0.0, 5.0, m.BOL["vaste_fee"], 0.05),
    "betaal_pct": _box.slider("Betaalkosten %", 0.0, 5.0, m.BOL["betaal_pct"] * 100, 0.1) / 100,
    "verzending": _box.number_input("Verzending naar klant (€)", 0.0, 15.0, m.BOL["verzending"], 0.25),
    "retour_pct": _box.slider("Retouren %", 0.0, 30.0, m.BOL["retour_pct"] * 100, 1.0) / 100,
    "advertentie": _box.number_input("Advertentie/verkoop — CAC (€)", 0.0, 30.0, m.BOL["advertentie"], 0.25),
    "verwijderingsbijdrage": _box.number_input(
        "Verwijderingsbijdrage WEEE/batterij (€)", 0.0, 2.0, m.BOL["verwijderingsbijdrage"], 0.05,
        help="Verplichte recyclingbijdrage voor elektronica/batterijen in NL."),
}
if _heeft_producten:
    st.sidebar.caption("Bol-commissie varieert ~8–17% per categorie. Pas aan naar jouw situatie.")

# --- Startgids -------------------------------------------------------------
st.sidebar.divider()
st.sidebar.markdown("#### 📘 Startgids (voor deze niche)")
_gp = (NS.get(actieve_niche) or {}).get("producten") or m.NICHE_PORTFOLIOS.get(actieve_niche, m.STANDAARD_PRODUCTEN)
try:
    _pdf, _xl = _startgids_bytes(actieve_niche, json.dumps(_gp))
    st.sidebar.download_button("📄 Startgids (PDF)", _pdf, file_name="Startgids_ecommerce.pdf",
                               mime="application/pdf", use_container_width=True)
    st.sidebar.download_button("📊 Startgids (Excel)", _xl, file_name="Startgids_ecommerce.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
except Exception as exc:  # noqa: BLE001
    st.sidebar.caption(f"Startgids niet beschikbaar: {exc}")

_niche_label = actieve_niche if actieve_niche != "(eigen / vrij)" else "stekkerbatterij + installatie"
_niche_key = re.sub(r"\W+", "_", actieve_niche).strip("_") or "vrij"
_niche = next((n for n in m.NICHES if n["naam"] == actieve_niche), None)  # None = batterij/eigen
_is_battery = actieve_niche == "(eigen / vrij)"
_is_custom = (not _is_battery) and (_niche is None)  # zelf-gemaakte/gescande niche
# Installateur-route tonen bij batterij (eigen/vrij) of een installatie-niche.
show_route = _is_battery or (actieve_niche in m.INSTALLATIE_NICHES)
with _header:
    st.title("🛒 E-commerce planner")
    st.caption("Plan marge, productmix, de businesscase, de markt én de Nederlandse regels op één plek. "
               "Alle getallen zijn aanpasbare schattingen om te valideren — geen beloftes.")

_labels = ["🏠 Dakofferte-tracker", "🧮 Marge-calculator", "📦 Productportfolio", "📈 Businesscase",
           "🌍 Markt & strategie", "📋 Regels & belasting"]
if show_route:
    _labels.append("🧰 Installateur-route")
_labels += ["💡 Niches (overzicht)", "🔎 Niche-scan", "📑 Onderzoek & groei", "🚀 Founder-check"]
_it = iter(st.tabs(_labels))
tab_dak = next(_it)
tab_calc = next(_it); tab_port = next(_it); tab_case = next(_it); tab_markt = next(_it); tab_regels = next(_it)
tab_route = next(_it) if show_route else None
tab_niches = next(_it); tab_scan = next(_it); tab_onderzoek = next(_it); tab_founder = next(_it)


# --- 1. Marge-calculator ---------------------------------------------------
with tab_calc:
    st.subheader("Stuk-economie")
    if actieve_niche != "(eigen / vrij)":
        st.caption(f"🎯 Niche-context: **{_niche_label}** — kies een product/dienst of vul zelf in.")

    _calc_prod = (NS.get(actieve_niche) or {}).get("producten") or m.NICHE_PORTFOLIOS.get(actieve_niche, m.STANDAARD_PRODUCTEN)
    _opts = [p["Product"] for p in _calc_prod if p.get("Product")] + ["— eigen invoer —"]
    pick = st.selectbox("Reken door voor", _opts, key=f"calc_pick_{_niche_key}")
    _picked = next((p for p in _calc_prod if p["Product"] == pick), None)

    _pk, _ik, _dk = f"calc_prijs_{_niche_key}", f"calc_inkoop_{_niche_key}", f"calc_dienst_{_niche_key}"
    if _pk not in st.session_state:
        _f = _calc_prod[0] if _calc_prod else {}
        st.session_state[_pk] = float(_f.get("Prijs", 100.0))
        st.session_state[_ik] = float(_f.get("Inkoop", 0.0))
        st.session_state[_dk] = bool(_f.get("Dienst"))
    if _picked and st.session_state.get(f"_calc_last_{_niche_key}") != pick:
        st.session_state[_pk] = float(_picked["Prijs"])
        st.session_state[_ik] = float(_picked["Inkoop"])
        st.session_state[_dk] = bool(_picked.get("Dienst"))
    st.session_state[f"_calc_last_{_niche_key}"] = pick

    _is_uur = bool(_picked and _picked.get("Dienst") and "uur" in pick.lower())
    _is_dienst = bool(_picked.get("Dienst")) if _picked else st.session_state.get(_dk, False)
    if _is_uur:
        _pl, _il, _unit = "Uurtarief (incl. btw) €", "Kosten per uur (excl. btw) €", "uur"
    elif _is_dienst:
        _pl, _il, _unit = "Tarief (incl. btw) €", "Kosten per klus (excl. btw) €", "klus"
    else:
        _pl, _il, _unit = "Verkoopprijs (incl. btw) €", "Geland inkoopbedrag/stuk (excl. btw) €", "stuk"

    c1, c2 = st.columns(2)
    prijs = c1.number_input(_pl, 0.0, 5000.0, step=1.0, key=_pk)
    inkoop = c2.number_input(_il, 0.0, 4000.0, step=1.0, key=_ik,
                             help="Inkoop + vracht (product) of materiaal-/uurkosten (dienst).")
    dienst = st.toggle("Dit is een dienst — geen marktplaats-fees of retouren", key=_dk)
    e = m.stuk_economie(prijs, inkoop, dienst=dienst, **fees)
    _unit = "uur" if (dienst and "uur" in pick.lower()) else ("klus" if dienst else "stuk")

    k = st.columns(4)
    k[0].metric(f"Winst / {_unit}", eur(e["winst"]))
    k[1].metric("Marge %", f"{e['marge_pct'] * 100:.1f}%")
    k[2].metric("Opslag", f"{e['opslag_x']:.2f}×")
    k[3].metric("Omzet excl. btw", eur(e["omzet_excl"]))

    if e["marge_pct"] < 0.10:
        if dienst:
            st.error("⚠️ Marge onder 10% — je tarief is te laag voor je materiaal-/reiskosten. "
                     "Verhoog het uur- of projecttarief.")
        else:
            st.error("⚠️ Marge onder 10% — fees + advertentiekosten eten dit op. Bundel het, "
                     "verhoog de prijs, of verlaag de CAC.")
    elif e["marge_pct"] < 0.20:
        if dienst:
            st.warning("Dunne marge (10–20%) voor een dienst — verhoog je tarief. "
                       "Je hebt hier geen marktplaats-fees of retouren, dus marge zou hoger moeten kunnen.")
        else:
            st.warning("Dunne marge (10–20%). Werkbaar, maar weinig ruimte voor advertenties en retouren.")
    else:
        st.success("Gezonde marge (20%+). Dit soort product/bundel is de basis om op te bouwen.")

    # Waterval: omzet → (alleen niet-nul kosten) → winst
    _posten = [("Inkoop", e["inkoop"]), ("Commissie", e["commissie"]), ("Vaste fee", e["vaste_fee"]),
               ("Betaalkosten", e["betaal"]), ("Verzending", e["verzending"]), ("Retouren", e["retour_kosten"]),
               ("Advertentie", e["advertentie"]), ("Verwijderingsbijdr.", e["verwijderingsbijdrage"])]
    labels, values, measure = ["Omzet excl. btw"], [e["omzet_excl"]], ["absolute"]
    for _lab, _val in _posten:
        if _val:  # 0-posten (bv. retouren bij een dienst) niet tonen
            labels.append(_lab)
            values.append(-_val)
            measure.append("relative")
    labels.append("Winst")
    values.append(e["winst"])
    measure.append("total")
    fig = go.Figure(go.Waterfall(
        orientation="v", measure=measure, x=labels, y=values,
        connector={"line": {"color": "#cdd5df"}},
        decreasing={"marker": {"color": "#e76f51"}},
        increasing={"marker": {"color": "#2a9d8f"}},
        totals={"marker": {"color": "#16223d"}}))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10), yaxis_title="€ per stuk")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("ℹ️ Hoe dit berekend wordt"):
        st.markdown(
            "- **Omzet excl. btw** = prijs ÷ 1,21 (je draagt de 21% btw af).\n"
            "- **Commissie / betaalkosten** worden gerekend over de consumentprijs (incl. btw).\n"
            "- **Retouren** gaan ervan uit dat de verzending verloren is en de helft van de "
            "geretourneerde goederen wordt afgeschreven.\n"
            "- **Verwijderingsbijdrage** = verplichte WEEE/batterij-recyclingbijdrage per stuk.\n"
            "- **Winst** = omzet excl. btw − alle bovenstaande. Marge % is op omzet excl. btw.")


# --- 2. Productportfolio ---------------------------------------------------
with tab_port:
    st.subheader("Vergelijk producten — beste marge bovenaan")
    st.caption(f"Producten/diensten voor **{_niche_label}**. Pas aan of voeg rijen toe — "
               "‘Inkoop’ is geland excl. btw; ‘Prijs’ is incl. btw.")
    if actieve_niche in NS and "producten" in NS[actieve_niche]:
        seed = NS[actieve_niche]["producten"] or [{"Product": "", "Inkoop": 0.0, "Prijs": 0.0, "Dienst": False}]
    else:
        seed = m.NICHE_PORTFOLIOS.get(actieve_niche, m.STANDAARD_PRODUCTEN)
    edited = st.data_editor(
        pd.DataFrame(seed), num_rows="dynamic", use_container_width=True, key=f"port_{_niche_key}",
        column_config={
            "Inkoop": st.column_config.NumberColumn("Inkoop (geland €)", format="%.2f"),
            "Prijs": st.column_config.NumberColumn("Prijs (incl. btw €)", format="%.2f"),
            "Dienst": st.column_config.CheckboxColumn("Dienst?", help="Installatie/advies: geen marktplaats-fees"),
        })
    producten = [r for r in edited.to_dict("records") if r.get("Product")]
    NS.setdefault(actieve_niche, {})["producten"] = producten
    st.session_state["producten"] = producten

    tabel = m.portfolio_tabel(producten, **fees)
    st.dataframe(
        tabel, use_container_width=True, hide_index=True,
        column_config={
            "Winst/stuk": st.column_config.NumberColumn(format="€%.2f"),
            "Marge %": st.column_config.NumberColumn(format="%.1f%%"),
            "Inkoop (geland)": st.column_config.NumberColumn(format="€%.2f"),
            "Prijs (incl. btw)": st.column_config.NumberColumn(format="€%.2f"),
            "Opslag": st.column_config.NumberColumn(format="%.2f×"),
        })

    if not tabel.empty:
        bar = go.Figure(go.Bar(
            x=tabel["Winst/stuk"], y=tabel["Product"], orientation="h",
            marker_color=["#2a9d8f" if v >= 20 else "#e9c46a" if v >= 10 else "#e76f51"
                          for v in tabel["Marge %"]],
            text=[f"{p:.2f}€ · {mg:.0f}%" for p, mg in zip(tabel["Winst/stuk"], tabel["Marge %"])]))
        bar.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                          xaxis_title="Winst / stuk (€)", yaxis={"autorange": "reversed"})
        st.plotly_chart(bar, use_container_width=True)
        st.info("💡 De **batterij verliest geld op een marktplaats** (Bol-commissie + prijsvergelijking). "
                "Verkoop die **direct of bij installatie** (zet de commissie in de zijbalk op 0). "
                "De echte winst zit in **accessoires + installatie/advies** — laag instapbudget, hoge marge.")
        st.download_button("⬇️ Download portfolio (Excel)",
                           m.df_to_excel_bytes({"Portfolio": tabel}),
                           file_name="ecommerce_portfolio.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# --- 3. Businesscase -------------------------------------------------------
with tab_case:
    st.subheader("12-maands businesscase")
    st.caption(f"Prognose voor **{_niche_label}** — kies hieronder het hoofdproduct/-dienst.")
    producten = st.session_state.get("producten", m.STANDAARD_PRODUCTEN)
    namen = [p["Product"] for p in producten] or ["—"]
    default_idx = next((i for i, p in enumerate(producten) if p.get("Dienst")), 0)
    keuze = st.selectbox("Hoofdproduct/-dienst (stuurt de prognose)", namen, index=default_idx)
    gekozen = next((p for p in producten if p["Product"] == keuze),
                   producten[0] if producten else {"Prijs": 295.0, "Inkoop": 25.0, "Dienst": True})
    e = m.stuk_economie(gekozen["Prijs"], gekozen["Inkoop"],
                        dienst=bool(gekozen.get("Dienst", False)), **fees)

    # Eenheid bepalen: een dienst-per-uur rekent in uren, andere diensten in klussen.
    if gekozen.get("Dienst") and "uur" in (keuze or "").lower():
        _eenheid, _qlabel = "uur", "Declarabele uren / maand"
    elif gekozen.get("Dienst"):
        _eenheid, _qlabel = "klus", "Klussen / maand"
    else:
        _eenheid, _qlabel = "stuk", "Stuks / maand"
    if _eenheid == "uur":
        st.caption(f"💼 Dienst per uur: **{eur(gekozen['Prijs'])}/uur** tarief, "
                   f"**{eur(gekozen['Inkoop'])}/uur** kosten → **{eur(e['winst'])}/uur** winst.")

    _bc = (NS.get(actieve_niche) or {}).get("bc", {})
    a = st.columns(4)
    stuks1 = a[0].number_input(_qlabel, 1, 5000, int(_bc.get("stuks", 15)), 1,
                               key=f"bc_stuks_{_niche_key}")
    groei = a[1].slider("Maandelijkse groei %", 0.0, 30.0, float(_bc.get("groei", 10.0)), 1.0,
                        key=f"bc_groei_{_niche_key}") / 100
    vast = a[2].number_input("Vaste kosten / maand €", 0.0, 5000.0, float(_bc.get("vast", 150.0)), 25.0,
                             key=f"bc_vast_{_niche_key}", help="Webshop/Bol, tools, verzekering, enz.")
    start = a[3].number_input("Startinvestering €", 0.0, 50000.0, float(_bc.get("start", 750.0)), 50.0,
                              key=f"bc_start_{_niche_key}", help="Laag starten: voorraad + gereedschap + opzet.")
    NS.setdefault(actieve_niche, {})["bc"] = {"stuks": stuks1, "groei": groei * 100, "vast": vast, "start": start}

    prog, be = m.prognose(stuks1, groei, 12, vast, start, e["winst"], e["omzet_excl"])
    s = st.columns(4)
    s[0].metric(f"Winst / {_eenheid}", eur(e["winst"]))
    s[1].metric("Jaar-1 omzet (excl. btw)", eur(prog["Omzet (excl. btw)"].sum()))
    s[2].metric("Jaar-1 netto", eur(prog["Netto/maand"].sum()))
    s[3].metric("Break-even", f"Maand {be}" if be else "niet in 12 mnd")

    if not be:
        st.warning("Dit hoofdproduct is niet break-even binnen een jaar bij deze aantallen — "
                   "kies een bundel met hogere marge, verhoog het volume, of verlaag vaste kosten/CAC.")

    line = go.Figure()
    line.add_bar(x=prog["Maand"], y=prog["Netto/maand"], name="Netto/maand", marker_color="#94a3b8")
    line.add_trace(go.Scatter(x=prog["Maand"], y=prog["Cumulatieve cash"], name="Cumulatieve cash",
                              mode="lines+markers", line=dict(color="#16223d", width=3)))
    line.add_hline(y=0, line_dash="dot", line_color="#e76f51")
    line.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10),
                       xaxis_title="Maand", yaxis_title="€", legend=dict(orientation="h"))
    st.plotly_chart(line, use_container_width=True)

    st.dataframe(prog, use_container_width=True, hide_index=True)
    volledig = m.df_to_excel_bytes({
        "Businesscase": prog,
        "Portfolio": m.portfolio_tabel(producten, **fees),
        "Aannames": pd.DataFrame([
            {"Item": "Hoofdproduct", "Waarde": keuze},
            {"Item": "Stuks maand 1", "Waarde": stuks1},
            {"Item": "Maandelijkse groei %", "Waarde": groei * 100},
            {"Item": "Vaste kosten / maand", "Waarde": vast},
            {"Item": "Startinvestering", "Waarde": start},
            {"Item": "Commissie %", "Waarde": fees["commissie_pct"] * 100},
            {"Item": "Advertentie/verkoop (CAC)", "Waarde": fees["advertentie"]},
            {"Item": "Retouren %", "Waarde": fees["retour_pct"] * 100},
        ]),
    })
    st.download_button("⬇️ Download volledige businesscase (Excel)", volledig,
                       file_name="ecommerce_businesscase.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# --- 4. Markt & strategie --------------------------------------------------
with tab_markt:
    if _niche:
        st.subheader(f"Markt & strategie — {_niche['naam']}")
        st.caption(_niche["waarom"])
        st.markdown(f"**Wat & voor wie** — {_niche['wat']}")
        st.markdown(f"_Klant:_ {_niche['klant']}")
        st.markdown("**Verdienmodel & tarieven**")
        for x in _niche["verdienmodel"]:
            st.markdown(f"- {x}")
        gg1, gg2 = st.columns(2)
        with gg1:
            st.markdown("#### 🎯 Hoe te starten")
            for x in _niche["start"]:
                st.markdown(f"- {x}")
            st.markdown("#### 🧠 Eisen / certificering")
            for x in _niche["eisen"]:
                st.markdown(f"- {x}")
        with gg2:
            st.markdown("#### 📣 Klanten werven")
            for x in _niche["klanten_werven"]:
                st.markdown(f"- {x}")
            st.markdown("#### ⚠️ Risico's")
            for x in _niche["risicos"]:
                st.markdown(f"- {x}")
        st.success(f"📈 Indicatie: {_niche['cijfers']}")
        if _niche.get("bronnen"):
            st.markdown("#### Bronnen")
            st.markdown("  ·  ".join(f"[{a}]({b})" for a, b in _niche["bronnen"]))
    elif _is_battery:
        st.subheader("Markt & strategie — stekkerbatterij + installatie (NL)")
        cols = st.columns(3)
        for i, (label, val, sub) in enumerate(m.MARKT["stats"]):
            cols[i % 3].metric(label, val, sub or None)
        seg = m.MARKT["segmenten"]
        pie = go.Figure(go.Pie(labels=list(seg), values=list(seg.values()), hole=0.5))
        pie.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                          title="Smart-home omzet per segment (EU, %)")
        st.plotly_chart(pie, use_container_width=True)
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("#### 🎯 Jouw beachhead")
            for x in m.MARKT["beachhead"]:
                st.markdown(f"- {x}")
            st.markdown("#### 🧠 Jouw moat")
            for x in m.MARKT["moat"]:
                st.markdown(f"- {x}")
        with g2:
            st.markdown("#### 🚫 Hier niet concurreren")
            for x in m.MARKT["vermijden"]:
                st.markdown(f"- {x}")
            st.markdown("#### ⚠️ Risico's om te beheersen")
            for x in m.MARKT["risicos"]:
                st.markdown(f"- {x}")
        st.markdown("#### Bronnen")
        st.markdown("  ·  ".join(f"[{naam}]({url})" for naam, url in m.MARKT["bronnen"]))
    else:  # zelf-gemaakte niche → geen vaste marktdata; AI-analyse op maat
        st.subheader(f"Markt & strategie — {actieve_niche}")
        _mk = f"markt_ai_{_niche_key}"
        if ai.available():
            if st.button("🤖 Genereer marktanalyse voor deze niche", key=f"btn_{_mk}"):
                with st.spinner("AI denkt na…"):
                    st.session_state[_mk] = ai.complete(
                        m.ONDERZOEK_GROEI["🔬 Grondig marktonderzoek"]["prompt"].format(niche=actieve_niche)
                        + " Voeg beachhead, moat en de 3 grootste risico's toe. Antwoord volledig en "
                        "beslissend in het Nederlands.", 1200)
            if st.session_state.get(_mk):
                st.markdown(st.session_state[_mk])
            else:
                st.info("Klik op de knop voor een AI-marktanalyse die specifiek op deze niche is toegespitst.")
        else:
            st.info("Voor een eigen niche is er nog geen vaste marktdata. Zet een LLM-key (Groq) voor een "
                    "AI-marktanalyse, of gebruik de tab **📑 Onderzoek & groei** voor het marktonderzoek.")


# --- 5. Regels & belasting -------------------------------------------------
with tab_regels:
    st.subheader("Nederlandse regels & regelgeving")
    st.caption(f"Specifiek voor **{_niche_label}** — algemene info, geen juridisch of fiscaal advies. "
               "Check je eigen situatie bij KvK en Belastingdienst.")

    if _niche and _niche["naam"] in m.NICHE_REGELS:
        st.markdown("#### 📌 Specifiek voor deze niche")
        for p in m.NICHE_REGELS[_niche["naam"]]:
            st.markdown(f"- {p}")
        st.divider()

    if _is_battery:  # alleen de batterij-niche krijgt de batterij/China-secties
        items = list(m.REGELS.items())
    else:            # vaste dienst-niche én eigen niche → algemene + ZZP-secties
        items = [(t, p) for t, p in m.REGELS.items() if t in m.REGELS_ALGEMEEN]
    cols = st.columns(2)
    for i, (titel, punten) in enumerate(items):
        with cols[i % 2]:
            st.markdown(f"#### {titel}")
            for p in punten:
                st.markdown(f"- {p}")

    if not _niche:
        st.info("💡 Twee dingen die je marge raken (al meegerekend): de **verwijderingsbijdrage** "
                "(WEEE/batterij) per stuk, en het **14-daagse retourrecht** dat retouren onvermijdelijk "
                "maakt — houd de retour-aanname realistisch.")
    st.markdown("#### Bronnen")
    st.markdown("  ·  ".join(f"[{naam}]({url})" for naam, url in m.REGELS_BRONNEN))


# --- 6. Installateur-route -------------------------------------------------
if tab_route is not None:  # alleen zichtbaar bij batterij / installatie-niches
    with tab_route:
        st.subheader("Installateur-/advies-route — van laag budget naar gecertificeerd")
        st.caption("Plug-in advies/setup mag zónder erkenning; vaste installaties vragen "
                   "NEN 1010/3140 + InstallQ. Gefaseerd opbouwen houdt het budget laag.")
        r = m.INSTALLATEUR_ROUTE
        for f in r["fases"]:
            st.markdown(f"#### {f['fase']}")
            for p in f["punten"]:
                st.markdown(f"- {p}")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 💶 Indicatieve tarieven")
            st.table(pd.DataFrame(r["tarieven"], columns=["Dienst", "Tarief"]))
        with c2:
            st.markdown("#### 🎯 Klanten werven")
            for x in r["leads"]:
                st.markdown(f"- {x}")
            st.markdown("#### 🛡️ Verzekering & risico")
            for x in r["verzekering"]:
                st.markdown(f"- {x}")

        st.markdown("#### Bronnen")
        st.markdown("  ·  ".join(f"[{n}]({u})" for n, u in r["bronnen"]))


# --- 7. Niche-overzicht (alle niches, gesorteerd op fit + marge) -----------
with tab_niches:
    st.subheader("🗂️ Niche-overzicht")
    st.caption("Alle niches — bekende én je eigen — gesorteerd op fit en marge. "
               "Klik ‘Activeer’ om het hele dashboard op die niche te zetten.")

    def _fitnum(f):
        try:
            return float(str(f).split("/")[0].replace(",", "."))
        except Exception:  # noqa: BLE001
            return 0.0

    def _margerank(mg):
        t = str(mg).lower()
        return 5 if "zeer hoog" in t else 4 if "hoog" in t else 3 if "goed" in t else 2

    _pre = [n["naam"] for n in m.NICHES]
    _entries = [{"naam": n["naam"], "fit": n["fit"], "marge": n["marge"],
                 "drempel": n["drempel"], "data": n, "custom": False, "icon": "⭐"} for n in m.NICHES]
    for k in [x for x in NS.keys() if x not in _pre]:
        _sc = next((s for s in st.session_state.get("scans", []) if s["Niche"] == k), None)
        _entries.append({"naam": k, "fit": (f"{int(_sc['Score']) // 10}/10" if _sc else "—"),
                         "marge": "eigen niche", "drempel": "—", "data": None, "custom": True,
                         "icon": "🆕", "score": _sc["Score"] if _sc else None})
    _entries.sort(key=lambda e: (-_fitnum(e["fit"]), -_margerank(e["marge"])))

    for e in _entries:
        with st.expander(f"{e['icon']} {e['naam']}  —  fit {e['fit']} · marge {e['marge']} · drempel {e['drempel']}"):
            if st.button("▶️ Activeer deze niche", key=f"act_{e['naam']}"):
                st.session_state["_force_niche"] = e["naam"]
                st.rerun()
            n = e["data"]
            if n:
                st.caption(n["waarom"])
                st.markdown(f"**Wat & voor wie** — {n['wat']}")
                st.markdown(f"_Klant:_ {n['klant']}")
                st.markdown("**Verdienmodel & tarieven**")
                for x in n["verdienmodel"]:
                    st.markdown(f"- {x}")
                cc1, cc2 = st.columns(2)
                with cc1:
                    st.markdown("**Hoe te starten**")
                    for x in n["start"]:
                        st.markdown(f"- {x}")
                    st.markdown("**Eisen / certificering / regels**")
                    for x in n["eisen"]:
                        st.markdown(f"- {x}")
                with cc2:
                    st.markdown("**Klanten werven**")
                    for x in n["klanten_werven"]:
                        st.markdown(f"- {x}")
                    st.markdown("**Risico's**")
                    for x in n["risicos"]:
                        st.markdown(f"- {x}")
                st.success(f"📈 Indicatie: {n['cijfers']}")
                if n.get("bronnen"):
                    st.markdown("Bronnen: " + "  ·  ".join(f"[{a}]({b})" for a, b in n["bronnen"]))
            else:
                _prods = (NS.get(e["naam"]) or {}).get("producten", [])
                _extra = f" · scan-score {e['score']}/100" if e.get("score") else ""
                st.caption(f"Zelf-gemaakte niche — {len(_prods)} product(en)/dienst(en){_extra}.")
                st.markdown("Werk 'm uit via **Markt & strategie** (AI), **Productportfolio** en "
                            "**📑 Onderzoek & groei**.")

    # Gescande ideeën die nog geen niche zijn → activeer maakt er een aan
    _created = set(NS.keys()) | set(_pre)
    _ideas = [s for s in st.session_state.get("scans", []) if s["Niche"] not in _created]
    if _ideas:
        st.markdown("#### 🔎 Gescande ideeën (nog niet aangemaakt)")
        for s in sorted(_ideas, key=lambda x: x.get("Score", 0), reverse=True):
            cc = st.columns([3, 1])
            cc[0].markdown(f"**{s['Niche']}** — score {s.get('Score', '?')}/100 · {s.get('Verdict', '')}")
            if cc[1].button("▶️ Activeer", key=f"acts_{s['Niche']}"):
                NS.setdefault(s["Niche"], {"producten": []})
                st.session_state["_force_niche"] = s["Niche"]
                try:
                    _persist()
                except Exception:  # noqa: BLE001
                    pass
                st.rerun()


# --- 8. Founder-check ------------------------------------------------------
with tab_founder:
    st.subheader("🚀 Founder-check — pressure-test elk idee")
    st.caption("Typ je idee in en draai de zes founder-rollen erop. Werkt met je gratis "
               "Groq-key (Secrets); zonder key krijg je de prompts om te kopiëren.")
    idea = st.text_area("Jouw idee / niche", key="founder_idea",
                        placeholder="Bijv. 3D-print STL-designs voor gereedschapshouders…")
    ctx = st.text_input("Context — doelgroep, budget, fase (optioneel)", key="founder_ctx")
    opties = [f"{p['nr']}. {p['titel']}" for p in m.FOUNDER_PROMPTS]
    keuze = st.multiselect("Welke analyses draaien?", opties, default=opties[:3])

    def _bouw_prompt(p):
        return (f"Je bent {p['role']}\n\nTaak: {p['task']}\n\nVolg deze stappen:\n{p['steps']}\n\n"
                f"IDEE: {idea}\nCONTEXT: {ctx or 'niet opgegeven — benoem je aanname'}\n\n"
                "Antwoord in het Nederlands, concreet en eerlijk; geen wollige taal. "
                "Vraag niets terug en geef een VOLLEDIG, beslissend antwoord — maak redelijke "
                "aannames en eindig met een duidelijke conclusie. Zeg NIET dat verdere analyse "
                "nodig is en laat je antwoord niet halverwege stoppen.")

    if ai.available():
        if st.button("Analyseer", type="primary"):
            if not idea.strip():
                st.warning("Vul eerst je idee in.")
            else:
                for p in m.FOUNDER_PROMPTS:
                    if f"{p['nr']}. {p['titel']}" not in keuze:
                        continue
                    with st.spinner(f"{p['nr']}. {p['titel']}…"):
                        out = ai.complete(_bouw_prompt(p), 1400)
                    st.markdown(f"#### {p['nr']}. {p['titel']}")
                    st.markdown(out or "_(geen antwoord — probeer opnieuw)_")
                    st.divider()
    else:
        st.info("Geen LLM-key gevonden. Zet **GROQ_API_KEY** (gratis, geen creditcard) in Secrets "
                "om dit automatisch te draaien. Of kopieer hieronder de prompts naar je eigen AI.")
        for p in m.FOUNDER_PROMPTS:
            with st.expander(f"{p['nr']}. {p['titel']}"):
                st.code(f"Je bent {p['role']}\n\nTaak: {p['task']}\n\nStappen:\n{p['steps']}")


# --- 9. Niche-scan ---------------------------------------------------------
with tab_scan:
    st.subheader("🔎 Niche-scan — kies flexibel, zie of het iets is")
    st.caption("Kies een bestaande niche of voeg er zelf één toe, scoor 'm op 6 criteria → "
               "score + verdict. Voeg toe om te vergelijken.")
    _scan_opts = [o for o in _niche_opties if o != "(eigen / vrij)"] + ["✏️ Eigen invoer…"]
    _sel_idx = _scan_opts.index(actieve_niche) if actieve_niche in _scan_opts else len(_scan_opts) - 1
    _sel = st.selectbox("Niche", _scan_opts, index=_sel_idx, key="scan_sel")
    if _sel == "✏️ Eigen invoer…":
        naam = st.text_input("Naam van de niche", key="scan_naam",
                             placeholder="Bijv. 3D-print STL functioneel, printables bruiloft, POD volleybal…")
    else:
        naam = _sel

    if ai.available():
        if st.button("🤖 AI-tweede mening", key="scan_ai"):
            if naam.strip():
                prompt = (f"Beoordeel kort en eerlijk de e-commerce niche '{naam}' voor een Nederlandse "
                          "starter met laag budget. Geef per criterium een cijfer 1-5: vraag&groei, "
                          "marge/ROI, concurrentie (1=veel..5=weinig), investering/risico (1=hoog..5=laag), "
                          "fit voor een technische cost-engineer, en moat/herhaalaankoop. Sluit af met "
                          "één zin advies. Antwoord volledig en beslissend in het Nederlands; "
                          "zeg niet dat verdere analyse nodig is.")
                with st.spinner("AI denkt na…"):
                    out = ai.complete(prompt, 900)
                st.info(out or "Geen antwoord — vul de scores zelf in.")
            else:
                st.warning("Vul eerst een niche in.")

    cols = st.columns(2)
    scores = {}
    for i, (key, label, help_, _omg, _w) in enumerate(m.SCAN_CRITERIA):
        scores[key] = cols[i % 2].slider(label, 1, 5, 3, help=help_, key=f"scan_{key}")
    pct, verdict = m.score_niche(scores)

    top = st.columns([1, 2])
    top[0].metric("Score", f"{pct}/100", verdict)
    eff = m.scan_effectief(scores)
    radar = go.Figure(go.Scatterpolar(
        r=list(eff.values()) + [list(eff.values())[0]],
        theta=list(eff.keys()) + [list(eff.keys())[0]],
        fill="toself", line_color="#2a9d8f"))
    radar.update_layout(height=320, margin=dict(l=30, r=30, t=20, b=20),
                        polar=dict(radialaxis=dict(range=[0, 5], visible=True)), showlegend=False)
    top[1].plotly_chart(radar, use_container_width=True)
    st.caption("Radar toont de effectieve score (hoger = beter; concurrentie/investering zijn al omgedraaid).")

    if st.button("➕ Voeg toe aan vergelijking", key="scan_add", type="primary"):
        if naam.strip():
            row = {"Niche": naam, "Score": pct, "Verdict": verdict, **eff}
            st.session_state.setdefault("scans", []).append(row)
        else:
            st.warning("Geef de niche eerst een naam.")

    scans = st.session_state.get("scans", [])
    if scans:
        df = pd.DataFrame(scans).sort_values("Score", ascending=False).reset_index(drop=True)
        st.markdown("#### Vergelijking (beste bovenaan)")
        st.dataframe(df, use_container_width=True, hide_index=True)
        cc = st.columns(2)
        cc[0].download_button("⬇️ Vergelijking (Excel)", m.df_to_excel_bytes({"Niche-scan": df}),
                              file_name="niche_scan.xlsx",
                              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              use_container_width=True)
        if cc[1].button("🗑️ Leeg de vergelijking", key="scan_clear", use_container_width=True):
            st.session_state["scans"] = []
            st.rerun()


# --- 10. Onderzoek & groei -------------------------------------------------
with tab_onderzoek:
    st.subheader(f"Onderzoek & groei — {_niche_label}")
    st.caption("Praktische checklists (werken altijd). Met een LLM-key krijg je per onderdeel "
               "een AI-versie toegespitst op deze niche.")
    _np = actieve_niche if actieve_niche != "(eigen / vrij)" else _niche_label
    for _titel, _blok in m.ONDERZOEK_GROEI.items():
        with st.expander(_titel, expanded=False):
            st.markdown(f"_{_blok['doel']}_")
            for _s in _blok["stappen"]:
                st.markdown(f"- {_s}")
            if ai.available():
                _ogk = f"og_{_niche_key}_{_titel}"
                if st.button(f"🤖 AI voor «{_niche_label}»", key=f"btn_{_ogk}"):
                    with st.spinner("AI denkt na…"):
                        st.session_state[_ogk] = ai.complete(
                            _blok["prompt"].format(niche=_np) + " Antwoord volledig en beslissend in "
                            "het Nederlands; maak aannames waar nodig en zeg niet dat verdere "
                            "analyse nodig is.", 1200)
                if st.session_state.get(_ogk):
                    st.markdown(st.session_state[_ogk])


# --- 11. Dakofferte-tracker ------------------------------------------------
with tab_dak:
    st.subheader("🏠 Dakrenovatie — offertes volgen & vergelijken")
    st.caption("Compiègnehof 11, Eindhoven · volledige dakrenovatie. Vergelijk op €/m² incl. btw.")
    dc = st.columns(3)
    st.session_state.setdefault("dak_opp", 60.0)
    # Automatisch: volg het berekende 3D-BAG-dakvlak (hellende vlakken − dakkapellen + carport-patch).
    # Eénmalig overnemen per nieuwe berekening; daarna kun je het veld nog handmatig bijstellen.
    _bag_area = st.session_state.get("_dak_bag_area")
    if _bag_area:
        _ba = float(min(max(round(_bag_area), 1), 1000))
        if st.session_state.get("_dak_bag_area_applied") != _ba:
            st.session_state["dak_opp"] = _ba
            st.session_state["_dak_bag_area_applied"] = _ba
            _persist_safe()
    dak_opp = dc[0].number_input("Dakoppervlak (m²)", min_value=1.0, max_value=1000.0, step=1.0, key="dak_opp",
                                 on_change=_persist_safe)
    dc[1].metric("Marktindicatie", f"€{DAK_MARKT_LO:.0f}–€{DAK_MARKT_HI:.0f}/m²", "incl. btw")
    dc[2].caption("Bron: Werkspot / Oranje Dakbeheer / Homedeal — indicatie, geen taxatie.")
    for _ek in ("dakkapel", "goot", "vogelwering"):
        st.session_state.setdefault(f"dak_sc_extra_{_ek}", True)
    st.caption("Welke extra's zitten in dít dak? (uitvinken = lagere should-cost; deze posten staan los "
               "van de kale €/m² dakrenovatie)")
    _ec = st.columns(3)
    _ec[0].checkbox("Dakkapel-loodwerk", key="dak_sc_extra_dakkapel")
    _ec[1].checkbox("Bakgoot / regenwater", key="dak_sc_extra_goot")
    _ec[2].checkbox("Vogelwering", key="dak_sc_extra_vogelwering")

    def _dak_apply_calc():
        _v = st.session_state.get("_dak_roof_calc")
        if _v:
            st.session_state["dak_opp"] = float(round(_v))
            _persist_safe()

    def _dak_apply_foot():
        st.session_state["dak_perc_huis"] = float(round(st.session_state.get("dak_bag_footprint", 0.0)))

    def _dak_apply_dakkapel():
        _fps = st.session_state.get("dak_bag_flat") or []
        if _fps:
            st.session_state["dak_calc_dkf_br"] = float(round(_fps[0]["w"], 1))
            st.session_state["dak_calc_dkf_di"] = float(round(_fps[0]["d"], 1))
        if len(_fps) > 1:
            st.session_state["dak_calc_dk_br"] = float(round(_fps[1]["w"], 1))
            st.session_state["dak_calc_dk_di"] = float(round(_fps[1]["d"], 1))

    # --- Samenvatting (KPI's) + vervaldatum-signalen ---
    from datetime import date as _kdate
    _ktoday = _kdate.today()
    _koffs = [o for o in st.session_state.get("dakofferte", [])
              if str(o.get("Bedrijf") or "").strip() and float(o.get("Incl. btw") or 0) > 0]
    _ksc = _dak_shouldcost_posten(dak_opp)
    _ksc_incl = sum(float(p["Prijs excl. btw"]) * (1 + p["Btw %"] / 100) for p in _ksc)
    _knext = None
    for _r in st.session_state.get("dak_afspraken", []):
        if str(_r.get("Status") or "") == "Bezoek gepland":
            try:
                _kd = _kdate.fromisoformat(str(_r.get("Datum")))
            except Exception:  # noqa: BLE001
                continue
            if _kd >= _ktoday and (_knext is None or _kd < _knext[0]):
                _knext = (_kd, str(_r.get("Bedrijf") or ""))
    _km = st.columns(4)
    _km[0].metric("Offertes", str(len(_koffs)),
                  help="Aantal offertes met een bedrag boven €0.")
    if _koffs:
        _klo = min(_koffs, key=lambda o: float(o["Incl. btw"]))
        _km[1].metric("Laagste (incl. btw)", f"€{float(_klo['Incl. btw']):,.0f}".replace(",", "."),
                      str(_klo.get("Bedrijf") or "")[:16], delta_color="off",
                      help="Laagste totaalprijs incl. btw; eronder staat de aannemer.")
    else:
        _km[1].metric("Laagste (incl. btw)", "—",
                      help="Laagste totaalprijs incl. btw; eronder staat de aannemer.")
    _km[2].metric("Should-cost (mean)", f"€{_ksc_incl:,.0f}".replace(",", "."),
                  f"≈ €{_ksc_incl / dak_opp:.0f}/m²" if _ksc_incl else "—", delta_color="off",
                  help="Onafhankelijke richtprijs (bottom-up), geschaald naar dit dakoppervlak; alleen "
                       "de hierboven aangevinkte extra's tellen mee. De band staat bij 'Vergelijking & advies'.")
    _kmnd = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
    _km[3].metric("Eerstvolgend bezoek", f"{_knext[0].day} {_kmnd[_knext[0].month - 1]}" if _knext else "—",
                  (_knext[1][:16] if _knext else None), delta_color="off",
                  help="Eerstvolgende geplande inspectie/bezoek uit de agenda.")
    _kexp = []
    for o in _koffs:
        _kg = str(o.get("Geldig t/m") or "").strip()
        try:
            _kdays = (_kdate.fromisoformat(_kg) - _ktoday).days
        except Exception:  # noqa: BLE001
            continue
        if _kdays < 0:
            _kexp.append(f"**{o.get('Bedrijf')}** verlopen (t/m {_kg})")
        elif _kdays <= 7:
            _kexp.append(f"**{o.get('Bedrijf')}** verloopt over {_kdays} dag(en)")
    if _kexp:
        st.warning("⏳ Let op vervaldatum: " + " · ".join(_kexp))
    if _koffs and _ksc_incl:
        _klo_incl = float(_klo["Incl. btw"])
        _kgap = _klo_incl - _ksc_incl
        _kpct = _kgap / _ksc_incl * 100
        _knm = str(_klo.get("Bedrijf") or "")
        _keur = f"€{abs(_kgap):,.0f}".replace(",", ".")
        if _kgap <= 0:
            st.success(f"💡 Laagste offerte (**{_knm}**) ligt {_keur} **onder** de should-cost ({_kpct:.0f}%) — scherp geprijsd.")
        elif _kpct <= 10:
            st.info(f"💡 Laagste offerte (**{_knm}**) ligt {_keur} **boven** de should-cost (+{_kpct:.0f}%) — binnen een normale marge.")
        else:
            st.warning(f"💡 Laagste offerte (**{_knm}**) ligt {_keur} **boven** de should-cost (+{_kpct:.0f}%) — de moeite waard om na te vragen.")

    st.markdown("#### 📐 Opmeten & model — dak, pannen, 3D & perceel")
    _meet = st.tabs(["📐 Dak m² (Maps)", "🧱 Pannen-check", "🏠 Schema 3D", "🛰️ 3D BAG", "🗺️ Perceel & plattegrond"])
    with _meet[0]:
        st.caption("Meet de **footprint** (het dakvlak van bovenaf) in Google Maps: rechtsklik op de kaart → "
                   "*Afstand meten* en klik de dakomtrek rond. Een hellend dak is gróter dan die platte footprint: "
                   "**dakvlak ≈ footprint ÷ cos(dakhelling)** (gezadeld dak, beide schilden even steil).")
        _mode = st.radio("Footprint invoeren als", ["Oppervlak (m²)", "Lengte × breedte"],
                         horizontal=True, key="dak_calc_mode")
        if _mode == "Lengte × breedte":
            _lb = st.columns(2)
            _l = _lb[0].number_input("Lengte (m)", 1.0, 200.0, 10.0, 0.1, key="dak_calc_l")
            _b = _lb[1].number_input("Breedte (m)", 1.0, 200.0, 6.0, 0.1, key="dak_calc_b")
            _fp = _l * _b
        else:
            _fp = st.number_input("Footprint uit Google Maps (m²)", 1.0, 3000.0, 50.0, 1.0, key="dak_calc_fp")
        _pitch = st.slider("Dakhelling (°)", 0, 70, 40, 1, key="dak_calc_pitch",
                           help="0° = plat dak (dakvlak = footprint). Hellend pannendak in NL: meestal 35–45°.")
        _factor = 1.0 / math.cos(math.radians(_pitch))
        _main = _fp * _factor
        st.markdown("**Dakkapellen** — tel de dakvlakken van de dakkapellen mee (uit 3D BAG of zelf gemeten).")
        for _k, _v in {"dak_calc_dk_br": 3.0, "dak_calc_dk_di": 1.2,
                       "dak_calc_dkf_br": 3.0, "dak_calc_dkf_di": 1.5}.items():
            st.session_state.setdefault(_k, _v)
        _dk = st.columns([1.3, 1, 1])
        _dk_on = _dk[0].checkbox("Achterzijde meetellen", value=True, key="dak_calc_dk_on")
        _dk_br = _dk[1].number_input("Breedte achter (m)", 0.0, 50.0, step=0.1, key="dak_calc_dk_br")
        _dk_di = _dk[2].number_input("Uitbouw achter (m)", 0.0, 20.0, step=0.1, key="dak_calc_dk_di")
        _dkf = st.columns([1.3, 1, 1])
        _dkf_on = _dkf[0].checkbox("Voorzijde meetellen", value=True, key="dak_calc_dkf_on")
        _dkf_br = _dkf[1].number_input("Breedte voor (m)", 0.0, 50.0, step=0.1, key="dak_calc_dkf_br")
        _dkf_di = _dkf[2].number_input("Diepte voor (m)", 0.0, 20.0, step=0.1, key="dak_calc_dkf_di")
        _dr = st.columns(2)
        _dr[0].number_input("Dakkapel vóór — afstand vanaf rechterwand (m)", 0.0, 50.0, 0.5, 0.1,
                            key="dak_calc_dk_right_f", help="Rechterrand van de voorste dakkapel t.o.v. de rechtergevel.")
        _dr[1].number_input("Dakkapel achter — afstand vanaf rechterwand (m)", 0.0, 50.0, 0.3, 0.1,
                            key="dak_calc_dk_right_b", help="Rechterrand van de achterste dakkapel t.o.v. de rechtergevel.")
        _dk_extra = (_dk_br * _dk_di if _dk_on else 0.0) + (_dkf_br * _dkf_di if _dkf_on else 0.0)
        _roof = _main + _dk_extra
        st.session_state["_dak_roof_calc"] = _roof
        _mc = st.columns(2)
        _mc[0].metric("Berekend dakoppervlak", f"{_roof:.0f} m²",
                      f"hoofddak {_main:.0f} m² (×{_factor:.2f}) + dakkapellen {_dk_extra:.0f} m²", delta_color="off")
        _mc[1].button("📥 Gebruik als dakoppervlak", key="dak_calc_apply", on_click=_dak_apply_calc,
                      help="Zet dit berekende dakvlak bovenaan als dakoppervlak (m²).")
        st.caption("Google Maps meet het **platte** grondvlak; de helling maakt er het echte schuine dakvlak van. "
                   "Tel bij de dakkapel alleen mee wat met pannen wordt bedekt (een platte dakkapelkap niet). "
                   "De achterzijde-dakkapel is hier 1,2 m uitgebouwd → breedte × 1,2 m extra dakvlak.")

    with _meet[1]:
        st.caption("Toets een geoffreerd aantal dakpannen aan het dakoppervlak. Dekkend aantal per m² (bron "
                   "dakpanrichtlijnen): **Sneldek (grootformaat) ~8–10**, betonpan / vlak keramisch **10–12**, "
                   "holle keramisch / OVH **14–16**.")
        _pc = st.columns(2)
        _pct = _pc[0].selectbox("Pantype", list(DAK_RENO_PANNEN_PER_M2), key="dak_pannen_type")
        _pp_lo, _pp_hi = DAK_RENO_PANNEN_PER_M2[_pct]
        _pp = _pc[1].slider("Pannen per m²", 6.0, 20.0, round((_pp_lo + _pp_hi) / 2, 1), 0.5,
                            key="dak_pannen_per_m2", help="Pas aan als de leverancier een ander dekkend aantal opgeeft.")
        _exp_lo, _exp_hi, _exp = dak_opp * _pp_lo, dak_opp * _pp_hi, dak_opp * _pp
        _stated = st.number_input("Aantal pannen volgens offerte", 0, 100000, 469, 1, key="dak_pannen_stated",
                                  help="Westermeer OFF-2026-0189: hoofddak 368 + erker 35 + dakkapel 66 = 469.")
        _pm = st.columns(3)
        _pm[0].metric("Verwacht (mean)", f"{_exp:.0f} pannen", f"band {_exp_lo:.0f}–{_exp_hi:.0f}", delta_color="off")
        _pm[1].metric("Volgens offerte", f"{_stated} pannen",
                      f"= {(_stated / dak_opp if dak_opp else 0):.1f}/m²", delta_color="off")
        _pm[2].metric("Impliceert dakvlak", f"{(_stated / _pp if _pp else 0):.0f} m²",
                      f"bij {_pp:.1f}/m²", delta_color="off")
        if _stated == 0:
            st.caption("Vul het aantal pannen uit de offerte in om te toetsen.")
        elif _exp_lo <= _stated <= _exp_hi:
            st.success(f"🟢 {_stated} pannen past binnen de verwachting ({_exp_lo:.0f}–{_exp_hi:.0f}) voor "
                       f"{dak_opp:.0f} m² {_pct.lower()}.")
        elif _stated < _exp_lo:
            st.warning(f"🟡 {_stated} pannen ligt **onder** de verwachting ({_exp_lo:.0f}–{_exp_hi:.0f}) — "
                       f"impliceert ~{_stated / _pp:.0f} m² i.p.v. {dak_opp:.0f} m². Grotere pannen, minder dakvlak "
                       f"of een te hoog ingesteld dakoppervlak.")
        else:
            st.warning(f"🟡 {_stated} pannen ligt **boven** de verwachting ({_exp_lo:.0f}–{_exp_hi:.0f}) — "
                       f"impliceert ~{_stated / _pp:.0f} m². Meer dakvlak (dakkapel/erker) of kleinere pannen; "
                       f"check de specificatie.")

    with _meet[2]:
        _3l = st.session_state.get("dak_calc_l")
        _3b = st.session_state.get("dak_calc_b")
        if not _3l or not _3b:
            # Geen lengte×breedte ingevuld → leid een vierkante footprint af uit het oppervlak.
            _area = st.session_state.get("dak_calc_fp") or dak_opp
            _3l = _3b = math.sqrt(max(float(_area), 1.0))
        _3pitch = st.session_state.get("dak_calc_pitch", 40)
        _3on = st.session_state.get("dak_calc_dk_on", True)
        _3dkbr = st.session_state.get("dak_calc_dk_br", 3.0) if _3on else 0.0
        _3dkdi = st.session_state.get("dak_calc_dk_di", 1.2) if _3on else 0.0
        _3fon = st.session_state.get("dak_calc_dkf_on", True)
        _3fbr = st.session_state.get("dak_calc_dkf_br", 3.0) if _3fon else 0.0
        _3fdi = st.session_state.get("dak_calc_dkf_di", 1.5) if _3fon else 0.0
        _3rf = float(st.session_state.get("dak_calc_dk_right_f", 0.5))
        _3rb = float(st.session_state.get("dak_calc_dk_right_b", 0.3))
        st.plotly_chart(_dak_roof_3d_fig(float(_3l), float(_3b), float(_3pitch), 3.0,
                                         float(_3dkbr), float(_3dkdi), float(_3fbr), float(_3fdi), _3rb, _3rf),
                        use_container_width=True)
        st.caption("Schematisch 3D-model op basis van de afmetingen uit de rekenhulp hierboven (lengte × breedte, "
                   "dakhelling en de dakkapellen voor + achter). Sleep om te draaien/zoomen. "
                   "Indicatief — geen bouwtekening.")

    with _meet[3]:
        st.caption("Haalt het werkelijke gebouwmodel (LoD 2.2) op uit het **3D BAG** (TU Delft) via de "
                   "PDOK-adressenservice. Vereist internettoegang naar `api.pdok.nl` en `api.3dbag.nl`.")
        _adr = st.text_input("Adres", value="Compiègnehof 11, Eindhoven", key="dak_bag_adres")
        if st.button("🛰️ Haal 3D BAG-model op", key="dak_bag_fetch"):
            try:
                _hits = _bag_geocode(_adr.strip())
                if not _hits:
                    st.session_state.pop("dak_bag_xy", None)
                    st.warning("Geen adres gevonden — schrijf het als 'Straat 11, Plaats'.")
                else:
                    st.session_state["dak_bag_xy"] = [_hits[0]["x"], _hits[0]["y"]]
                    st.session_state["dak_bag_naam"] = _hits[0]["naam"]
            except Exception as exc:  # noqa: BLE001
                st.session_state.pop("dak_bag_xy", None)
                st.error(f"Adres opzoeken mislukt: {exc}. Staat `api.pdok.nl` op de allowlist?")
        _xy = st.session_state.get("dak_bag_xy")
        if _xy:
            try:
                _fig3, _info3 = _bag3d_fig(_bag3d_fc_text(_xy[0], _xy[1]), _xy[0], _xy[1])
                if _info3["faces"]:
                    _pnd = ", ".join(p.split(".")[-1] for p in _info3["panden"]) or "—"
                    st.caption(f"{st.session_state.get('dak_bag_naam', '')} · pand {_pnd} · "
                               f"{_info3['faces']} vlakken ({_info3['roof']} dak). Officieel 3D BAG LoD 2.2-model "
                               "(blokkig); sleep om te draaien.")
                    st.plotly_chart(_fig3, use_container_width=True)
                    st.session_state["dak_bag_footprint"] = float(_info3.get("footprint_m2", 0.0))
                    st.session_state["dak_bag_foot_rings"] = _info3.get("footprint_rings", [])
                    _slope = float(_info3.get("roof_sloped_m2", 0.0))
                    st.markdown("**Dakvlak & pannen uit het 3D BAG-model (LoD 2.2)**")
                    _bm = st.columns(3)
                    _bm[0].metric("Totaal dakvlak", f"{_info3.get('roof_m2', 0):.0f} m²", delta_color="off")
                    _bm[1].metric("Hellend — pannen", f"{_slope:.0f} m²", "excl. platte dakkapellen", delta_color="off")
                    _bm[2].metric("Plat (dakkapel/plat dak)", f"{_info3.get('roof_flat_m2', 0):.0f} m²", delta_color="off")
                    st.markdown("Carport-patch (pannen, zelfde dakhelling) — niet in het BAG-model, dus handmatig:")
                    _bc = st.columns(3)
                    _cpw = _bc[0].number_input("Carport breedte (m)", 0.0, 50.0, 3.0, 0.1, key="dak_bag_cpw")
                    _cph = _bc[1].number_input("Carport langs helling (m)", 0.0, 50.0, 2.0, 0.1, key="dak_bag_cph")
                    _ppm = _bc[2].number_input("Pannen per m²", 4.0, 20.0, 10.0, 0.5, key="dak_bag_ppm",
                                               help="Beton/Sneldek & vlakke keramisch 10–12; holle keramisch / OVH 14–16.")
                    _extra = _cpw * _cph
                    _tarea = _slope + _extra
                    st.metric("Pannen-aantal (hellend dakvlak + carport-patch)", f"{round(_tarea * _ppm)} pannen",
                              f"{_tarea:.0f} m² ({_slope:.0f} dak + {_extra:.0f} carport) × {_ppm:.1f}/m²",
                              delta_color="off")
                    st.caption("Afgeleid uit het 3D BAG LoD 2.2-model: som van de **hellende** dakvlakken "
                               "(dakhelling 20–80°). Platte vlakken (dakkapeltoppen, plat dak) tellen niet mee — dat "
                               "is het 'echte dakvlak minus de dakkapellen'. De carport-patch (breedte × lengte langs "
                               "de helling) komt erbij. Indicatief, geen meetstaat.")
                    st.session_state["_dak_bag_area"] = _tarea
                    st.caption(f"➡️ Dit berekende dakvlak (**{_tarea:.0f} m²** = hellende vlakken − dakkapellen + "
                               "carport-patch) wordt **automatisch** als dakoppervlak gebruikt voor de should-cost en €/m².")
                    if round(_tarea) != st.session_state.get("_dak_bag_area_applied"):
                        st.rerun()
                    _flat = _info3.get("flat_patches", [])
                    st.session_state["dak_bag_flat"] = _flat
                    if _flat:
                        st.markdown("**Dakkapel-maten uit het model** (platte dakvlakken = dakkapeltoppen):")
                        st.dataframe(pd.DataFrame([{"Vlak": f"#{i + 1}", "Breedte ≈ (m)": round(p["w"], 1),
                                                    "Diepte ≈ (m)": round(p["d"], 1), "Oppervlak (m²)": round(p["m2"], 1)}
                                                   for i, p in enumerate(_flat)]),
                                     hide_index=True, use_container_width=True)
                        st.button("📥 Neem de 2 grootste over als dakkapel vóór/achter", key="dak_bag_dk_apply",
                                  on_click=_dak_apply_dakkapel,
                                  help="Zet breedte × diepte van de twee grootste platte vlakken in de dakkapel-velden "
                                       "in de Google Maps-rekenhulp. Hoogte staat niet in de meting.")
                        st.caption("Let op: een plat dak/aanbouw kan hier ook tussen staan — kies de juiste. "
                                   "Hoogte van de dakkapel staat niet in deze meting (van bovenaf niet zichtbaar).")
                else:
                    st.warning("Geen geometrie gevonden op deze locatie in het 3D BAG.")
            except Exception as exc:  # noqa: BLE001
                st.error(f"3D BAG-model laden mislukt: {exc}")

    with _meet[4]:
        st.caption("Verdeel je kavel. Het **huis-footprint** komt automatisch uit het 3D BAG-model hierboven "
                   "(haal dat eerst op). Schuur, carport en de voor/achter-verdeling staan niet in open data — die "
                   "vul je zelf in; de achtertuin/rest reken ik uit.")
        _fp = float(st.session_state.get("dak_bag_footprint", 0.0))
        st.session_state.setdefault("dak_perc_huis", float(round(_fp)))
        _pp = st.columns(2)
        _perc = _pp[0].number_input("Perceel totaal (m²)", min_value=0.0, max_value=10000.0, step=1.0,
                                    key="dak_perc_tot", help="Bron: Kadaster (kadastrale grootte) of je koopakte/WOZ.")
        _huis = _pp[1].number_input("Huis — footprint (m²)", min_value=0.0, max_value=5000.0, step=1.0,
                                    key="dak_perc_huis", help="Automatisch uit het 3D BAG-model; pas aan indien nodig.")
        if _fp > 0:
            _pp[1].button(f"📥 Neem BAG-footprint over ({_fp:.0f} m²)", key="dak_perc_huis_apply",
                          on_click=_dak_apply_foot)
        _p2 = st.columns(3)
        _schuur = _p2[0].number_input("Schuur/berging (m²)", min_value=0.0, max_value=2000.0, step=1.0, key="dak_perc_schuur")
        _carport = _p2[1].number_input("Carport (m²)", min_value=0.0, max_value=2000.0, step=1.0, key="dak_perc_carport")
        _voor = _p2[2].number_input("Voortuin (m²)", min_value=0.0, max_value=5000.0, step=1.0, key="dak_perc_voor")
        _bebouwd = _huis + _schuur + _carport
        _rest = _perc - _bebouwd - _voor
        _prows = [{"Onderdeel": "Huis (footprint)", "m²": round(_huis, 1)},
                  {"Onderdeel": "Schuur / berging", "m²": round(_schuur, 1)},
                  {"Onderdeel": "Carport", "m²": round(_carport, 1)},
                  {"Onderdeel": "Voortuin", "m²": round(_voor, 1)},
                  {"Onderdeel": "Achtertuin / resterend", "m²": round(_rest, 1)},
                  {"Onderdeel": "Perceel totaal", "m²": round(_perc, 1)}]
        _pdf = pd.DataFrame(_prows)
        st.dataframe(_pdf, hide_index=True, use_container_width=True,
                     column_config={"m²": st.column_config.NumberColumn(format="%.1f m²")})
        if _perc > 0:
            st.bar_chart(_pdf[~_pdf["Onderdeel"].eq("Perceel totaal")].set_index("Onderdeel"),
                         use_container_width=True)
            st.caption(f"Bebouwd (huis + schuur + carport): {_bebouwd:.0f} m² ({100 * _bebouwd / _perc:.0f}% van "
                       f"het perceel) · tuin (voor + achter): {_voor + max(_rest, 0.0):.0f} m².")
            if _rest < -0.5:
                st.warning("De onderdelen samen zijn groter dan het perceel — controleer de invoer.")
        st.download_button("⬇️ Download perceel-overzicht (Excel)", m.df_to_excel_bytes({"Perceel": _pdf}),
                           file_name="perceel_oppervlakten.xlsx", key="dak_perc_xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        st.markdown("**🗺️ Plattegrond — perceel met het huis erop**")
        _frings = st.session_state.get("dak_bag_foot_rings") or []
        _pxy = st.session_state.get("dak_bag_xy")
        if not _frings or not _pxy:
            st.caption("Haal eerst het **3D BAG-model** hierboven op — dan teken ik het echte huis-footprint, "
                       "en kun je het perceel uit het Kadaster halen of met maten tekenen.")
        else:
            _cp = st.columns(2)
            if _cp[0].button("🗺️ Perceel ophalen (Kadaster)", key="dak_perc_fetch"):
                try:
                    st.session_state["dak_perc_rings"] = _perceel_rings(_pxy[0], _pxy[1])
                    if not st.session_state["dak_perc_rings"]:
                        st.warning("Geen perceel gevonden — gebruik de handmatige maten.")
                except Exception as exc:  # noqa: BLE001
                    st.session_state["dak_perc_rings"] = []
                    st.warning(f"Perceel ophalen mislukt: {exc} — gebruik de handmatige maten hieronder.")
            _mb = _cp[1].number_input("Of perceel handmatig: breedte (m)", 0.0, 200.0, 0.0, 0.5, key="dak_perc_br")
            _md = st.number_input("Perceel diepte (m)", 0.0, 200.0, 0.0, 0.5, key="dak_perc_di")
            _perc_rings = list(st.session_state.get("dak_perc_rings") or [])
            if not _perc_rings and _mb > 0 and _md > 0:
                _all = [p for r in _frings for p in r]
                _cx = sum(p[0] for p in _all) / len(_all)
                _cy = sum(p[1] for p in _all) / len(_all)
                _perc_rings = [[(_cx - _mb / 2, _cy - _md / 2), (_cx + _mb / 2, _cy - _md / 2),
                                (_cx + _mb / 2, _cy + _md / 2), (_cx - _mb / 2, _cy + _md / 2)]]
            # Bijgebouwen tegen het huis tekenen (carport zit vast aan het huis, schuur evt. ook).
            _all = [p for r in _frings for p in r]
            _bb = (min(p[0] for p in _all), max(p[0] for p in _all),
                   min(p[1] for p in _all), max(p[1] for p in _all))

            _ix, _ax, _iy, _ay = _bb
            _hcx, _hcy = (_ix + _ax) / 2, (_iy + _ay) / 2
            _hw, _hd = (_ax - _ix), (_ay - _iy)

            def _box(offx, offy, breedte, diepte):
                cx, cy = _hcx + offx, _hcy + offy
                return [(cx - breedte / 2, cy - diepte / 2), (cx + breedte / 2, cy - diepte / 2),
                        (cx + breedte / 2, cy + diepte / 2), (cx - breedte / 2, cy + diepte / 2)]
            _extras = []
            with st.expander("🔧 Carport & schuur — maten/plaatsing (staat al goed voor dit huis)", expanded=False):
                st.caption("Vaste plaatsing voor deze woning; alleen openen als je wilt bijstellen. ← links / → "
                           "rechts en ↓ voor / ↑ achter, in meter t.o.v. het midden van het huis.")
                st.markdown("**Carport** (voorste-linkerhoek, vast aan het huis)")
                _cc1 = st.columns(2)
                _cp_br = _cc1[0].number_input("Breedte (m)", 0.0, 50.0, 3.0, 0.1, key="dak_plan_cp_br")
                _cp_di = _cc1[1].number_input("Diepte (m)", 0.0, 50.0, 5.0, 0.1, key="dak_plan_cp_di")
                _cc2 = st.columns(2)
                _cp_x = _cc2[0].number_input("← links / rechts → (m)", -60.0, 60.0, -round(_hw / 2 + 1.5, 1), 0.5, key="dak_plan_cp_x")
                _cp_y = _cc2[1].number_input("↓ voor / achter ↑ (m)", -60.0, 60.0, -round(_hd / 2, 1), 0.5, key="dak_plan_cp_y")
                st.markdown("**Schuur** (achter in de tuin, volle breedte)")
                _sc1 = st.columns(2)
                _sc_br = _sc1[0].number_input("Breedte (m)", 0.0, 50.0, round(_hw, 1), 0.1, key="dak_plan_sc_br")
                _sc_di = _sc1[1].number_input("Diepte (m)", 0.0, 50.0, 3.0, 0.1, key="dak_plan_sc_di")
                _sc2 = st.columns(2)
                _sc_x = _sc2[0].number_input("← links / rechts → (m)", -60.0, 60.0, 0.0, 0.5, key="dak_plan_sc_x")
                _sc_y = _sc2[1].number_input("↓ voor / achter ↑ (m)", -80.0, 80.0, round(_hd / 2 + 8.0, 1), 0.5, key="dak_plan_sc_y")
            if _cp_br > 0 and _cp_di > 0:
                _extras.append({"ring": _box(_cp_x, _cp_y, _cp_br, _cp_di), "naam": "carport",
                                "fill": "rgba(90,130,160,0.45)", "line": "#3f6781"})
            if _sc_br > 0 and _sc_di > 0:
                _extras.append({"ring": _box(_sc_x, _sc_y, _sc_br, _sc_di), "naam": "schuur",
                                "fill": "rgba(150,120,80,0.45)", "line": "#8a6d3b"})
            st.plotly_chart(_perceel_plan_fig(_perc_rings, _frings, _pxy[0], _pxy[1], _extras),
                            use_container_width=True)
            st.caption("Huis-footprint = echt uit het 3D BAG. Perceel = Kadaster (knop) of handmatige maten. "
                       "Carport/schuur plaats je vrij met de schuifjes. Op schaal in RD-meters.")

    st.markdown("**🧭 Werkwijze:**  1️⃣ Aannemers vinden  →  2️⃣ Uitnodigen / offerte aanvragen  →  "
                "3️⃣ Offerte ontvangen (⬆️ upload)  →  4️⃣ Vergelijken  →  5️⃣ Inzichten & advies  →  6️⃣ Kiezen")
    with st.expander("🧭 Werkwijze — wat doe je in elke stap?", expanded=False):
        st.markdown(
            "1. **Aannemers vinden** — zoek lokale dakdekkers (Werkspot, Trustoo, mond-tot-mond) en leg ze vast "
            "onder **📇 Contacten & afspraken**.\n"
            "2. **Uitnodigen / offerte aanvragen** — plan een inspectie/bezoek; zet de afspraak in de agenda "
            "(of importeer via iCal). Status: *Aangevraagd*.\n"
            "3. **Offerte ontvangen** — upload de PDF bij **⬆️ Offerte uploaden**: posten, bedragen en btw worden "
            "uitgelezen, de **PDF wordt bewaard** (altijd terugvindbaar) en de offerte verschijnt overal. "
            "*Elke nieuwe offerte krijgt automatisch exact dezelfde uitwerking* — uploaden, vergelijken, advies.\n"
            "4. **Vergelijken** — **🔍 Posten vergelijken**: per post wie wat rekent en waar de scope verschilt.\n"
            "5. **Inzichten & advies** — **📊 Vergelijking & advies**: €/m², markttoets, ontbrekende scope, "
            "ISDE-subsidie en een **eerlijke vergelijking** (gelijke scope) netto. Download het rapport (Excel/PDF met grafieken).\n"
            "6. **Kiezen** — kies onderaan je aannemer; die offerte krijgt status *Gekozen*.")

    _stage = st.tabs(["🔎 Aannemers & afspraken", "📥 Offertes", "⚖️ Vergelijken · advies · kiezen"])
    with _stage[1]:
        _off_tabs = st.tabs(["📋 Offertetabel", "📄 Offerte uitwerken", "⬆️ Uploaden (PDF)",
                             "➕ Handmatig toevoegen"])
        with _off_tabs[1]:
            _off = st.session_state.get("dakofferte", DAK_DEFAULT)
            _bedrijven = [str(o.get("Bedrijf") or "").strip() for o in _off if str(o.get("Bedrijf") or "").strip()]
            if not _bedrijven:
                st.info("Nog geen offertes — voeg er een toe via ⬆️ upload of ➕ handmatig.")
            else:
                _sel = st.selectbox("Kies een offerte om uit te werken", _bedrijven, key="dak_uitwerk_sel")
                _orow = next((o for o in _off if str(o.get("Bedrijf") or "").strip() == _sel), {})
                _posten = [p for p in st.session_state.get("dak_posten", DAK_POSTEN_DEFAULT)
                           if str(p.get("Bedrijf") or "").strip().lower() == _sel.lower()]
                if _posten:
                    _rows_u = []
                    for _p in _posten:
                        _pr = float(_p.get("Prijs excl. btw") or 0)
                        _pct = int(float(_p.get("Btw %") or 21))
                        _rows_u.append({"Onderdeel": str(_p.get("Onderdeel", "")), "Prijs excl. btw": _pr,
                                        "Btw %": _pct, "Btw €": round(_pr * _pct / 100, 2)})
                    _pdf = pd.DataFrame(_rows_u)
                    _sub = float(_pdf["Prijs excl. btw"].sum())
                    _btw = round(float(_pdf["Btw €"].sum()), 2)
                    _tot_incl = round(_sub + _btw, 2)
                    st.dataframe(_pdf, use_container_width=True, hide_index=True,
                                 column_config={"Prijs excl. btw": st.column_config.NumberColumn(format="€%.0f"),
                                                "Btw €": st.column_config.NumberColumn(format="€%.0f"),
                                                "Btw %": st.column_config.NumberColumn(format="%d%%"),
                                                "Onderdeel": st.column_config.TextColumn(width="large")})
                    _b21 = float(_pdf.loc[_pdf["Btw %"] == 21, "Btw €"].sum())
                    _b9 = float(_pdf.loc[_pdf["Btw %"] == 9, "Btw €"].sum())
                    if _b21 and _b9:
                        st.caption(f"Btw-opbouw: {eur(_b21)} @ 21% + {eur(_b9)} @ 9% = {eur(_btw)} totaal.")
                else:
                    _pdf = pd.DataFrame([{"Onderdeel": "(geen detailposten)", "Prijs excl. btw": 0.0,
                                          "Btw %": 21, "Btw €": 0.0}])
                    _sub = float(_orow.get("Excl. btw") or 0)
                    _incl_st = float(_orow.get("Incl. btw") or 0)
                    if _sub <= 0 and _incl_st > 0:        # alleen incl bekend → excl eruit afleiden
                        _sub = round(_incl_st / 1.21, 2)
                    _tot_incl = _incl_st if _incl_st > 0 else round(_sub * 1.21, 2)
                    _btw = round(_tot_incl - _sub, 2)
                    st.warning("Nog geen **detailposten** voor deze offerte. Voeg ze toe in **‘Posten vergelijken’** "
                               "(bv. *dakpannen type 1*, *dakpannen type 2*, *regenpijpen vervangen*, *loodwerk*, "
                               "*isolatie*) met hun **btw% (9 of 21)** — dan splitst de offerte zich hier vanzelf uit. "
                               f"Nu reken ik met het offertetotaal ({eur(_sub)} excl. btw).")
                _eff = (_btw / _sub * 100) if _sub > 0 else 0.0
                _m2 = _tot_incl / dak_opp if dak_opp else 0.0
                tt = st.columns(3)
                tt[0].metric("Subtotaal excl. btw", eur(_sub))
                tt[1].metric(f"Btw ({_eff:.0f}%)", eur(_btw))
                tt[2].metric("Totaal incl. btw", eur(_tot_incl), f"≈ €{_m2:.0f}/m² alles-in")
                if _sub > 0 and not (8.5 <= _eff <= 21.5):
                    st.warning(f"⚠️ Effectief btw-tarief is **{_eff:.0f}%** — buiten 9–21%. Waarschijnlijk staat een "
                               "excl- of incl-bedrag fout; corrigeer het in **‘Offertes vergelijken’**.")
                if _m2 <= 0:
                    st.caption("Vul bedragen in om de €/m²-toets te tonen.")
                elif _m2 <= DAK_MARKT_HI:
                    st.success(f"🟢 €{_m2:.0f}/m² incl. btw — **marktconform** "
                               f"(NL-indicatie €{DAK_MARKT_LO:.0f}–{DAK_MARKT_HI:.0f}/m²).")
                elif _m2 <= DAK_MARKT_HI * 1.25:
                    st.warning(f"🟡 €{_m2:.0f}/m² incl. btw — **aan de hoge kant** "
                               f"(markt €{DAK_MARKT_LO:.0f}–{DAK_MARKT_HI:.0f}/m²).")
                else:
                    st.error(f"🔴 €{_m2:.0f}/m² incl. btw — **fors boven markt** "
                             f"(€{DAK_MARKT_LO:.0f}–{DAK_MARKT_HI:.0f}/m²).")
                st.caption("Alles-in €/m² is incl. loodwerk + vogelwering e.d. De **dakrenovatie zelf** "
                           "vergelijk je het eerlijkst los — zie de should-cost hieronder.")

                if _posten:
                    st.caption(f"📋 **{len(_posten)} scope-regels** in deze offerte — consistent met de "
                               "posten-matrix en de vergelijking.")

                # Westermeer-regel voor élke offerte: originele PDF altijd terugvindbaar.
                _pdf_path = _offerte_pdf_path(_orow)
                if _pdf_path:
                    _bytes = _pdf_path.read_bytes()
                    st.download_button("📄 Originele offerte (PDF) downloaden", _bytes,
                                       file_name=_pdf_path.name, mime="application/pdf",
                                       key=f"dak_pdf_dl_{_sel}")
                    if st.checkbox("👁️ Offerte-tekst hier tonen", key=f"dak_show_pdf_{_sel}"):
                        _txt = ai.extract_pdf_text(_bytes, maxpages=12)
                        st.text_area("Offerte-tekst (uit de PDF)", _txt or "Tekst uitlezen lukte niet.",
                                     height=420, key=f"dak_pdf_txt_{_sel}")
                else:
                    st.caption("ℹ️ Geen originele PDF gevonden voor deze offerte. Upload 'm bij "
                               "**⬆️ Offerte uploaden** — dan wordt-ie bewaard en hier terugvindbaar.")

                _samen = pd.DataFrame({"Post": ["Subtotaal excl. btw", f"Btw ({_eff:.0f}%)", "Totaal incl. btw", "€/m² incl."],
                                       "Bedrag": [_sub, _btw, _tot_incl, round(_m2, 0)]})
                st.download_button("⬇️ Download uitwerking (Excel)",
                                   m.df_to_excel_bytes({"Posten": _pdf, "Samenvatting": _samen}),
                                   file_name=f"offerte_uitwerking_{_sel[:20].replace(' ', '_')}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   key="dak_uitwerk_xlsx")

    with _stage[2]:
        if st.session_state.get("dak_flash"):
            _lvl, _msg = st.session_state.pop("dak_flash")
            getattr(st, _lvl, st.info)(_msg)
        _cmp_tabs = st.tabs(["🧮 Should-cost", "🔍 Posten vergelijken", "⚖️ Vergelijking & advies"])
        with _cmp_tabs[0]:
            st.caption("Onafhankelijke bottom-up referentie (€/m² excl. btw) om de dakrenovatie te toetsen — "
                       "zoals een cost engineer een should-cost opbouwt. Hellend pannendak vervangen incl. "
                       "isolatie; schaalt mee met het dakoppervlak hierboven. Loodwerk + vogelwering zijn apart.")
            # Pannen-materiaal als band over de pankeuze: LCL = goedkoopste pan (Sneldek, grootformaat
            # beton), UCL = duurste (kleinere keramische pan). Data-gedreven uit DAK_RENO_PANTYPE.
            _plo = min(_lo for _lo, _hi in DAK_RENO_PANTYPE.values())   # goedkoopste pan = LCL
            _phi = max(_hi for _lo, _hi in DAK_RENO_PANTYPE.values())   # duurste pan = UCL
            st.caption("Pannen-materiaal als band: **LCL = Sneldek** (goedkoopste grootformaat beton) → "
                       "**UCL = keramische kleinere pan** (duurder, meer pannen/m²).")
            _rows = list(DAK_RENO_SHOULDCOST)
            _ix = next(i for i, r in enumerate(_rows) if "leggen" in r["Onderdeel"].lower())
            _rows.insert(_ix, {"Onderdeel": "Dakpannen — materiaal (Sneldek=LCL → keramisch klein=UCL)",
                               "Laag": _plo, "Hoog": _phi})
            _rb = pd.DataFrame(_rows)
            _rb["Gem."] = (_rb["Laag"] + _rb["Hoog"]) / 2.0
            _dlo, _dhi = float(_rb["Laag"].sum()), float(_rb["Hoog"].sum())  # directe kosten €/m²
            _dme = float(_rb["Gem."].sum())
            # Scope-lijnen + TOTAAL-rij, met LCL (laag) / Mean / UCL (hoog) per m².
            _rb_show = pd.concat([_rb, pd.DataFrame(
                [{"Onderdeel": "TOTAAL directe kosten", "Laag": _dlo, "Gem.": _dme, "Hoog": _dhi}])],
                ignore_index=True)[["Onderdeel", "Laag", "Gem.", "Hoog"]]
            st.dataframe(_rb_show, use_container_width=True, hide_index=True,
                         column_config={"Laag": st.column_config.NumberColumn("LCL (€/m²)", format="€%.0f"),
                                        "Gem.": st.column_config.NumberColumn("Mean (€/m²)", format="€%.0f"),
                                        "Hoog": st.column_config.NumberColumn("UCL (€/m²)", format="€%.0f")})
            # Gedetailleerde cost-price-opbouw per scope (manuren × uurtarief, materiaal, materieel + bron).
            _detail_rows = []  # platte lijst voor de Excel-export
            with st.expander("🔍 Gedetailleerde kostenopbouw per scope — zo bouw ik de kostprijs op", expanded=False):
                st.caption(f"Indicatieve bottom-up opbouw per m², directe kosten **excl. AK/W&R/btw** (arbeid à "
                           f"€{DAK_RENO_UURTARIEF:.0f}/u directe arbeid). AK, winst & risico en btw komen in de "
                           "opbouwtabel hieronder erbovenop. Bron per regel in de kolom 'Bron'.")
                for _, _scr in _rb.iterrows():
                    _onam = str(_scr["Onderdeel"])
                    _det = DAK_RENO_DETAIL.get(_onam)
                    if _det is None and "pannen — materiaal" in _onam:
                        _det = [(f"Dakpannen — materiaal (Sneldek €{_plo:.0f} → keramisch €{_phi:.0f}/m²)",
                                 1.0, "m²", round((_plo + _phi) / 2.0, 2),
                                 "prijsoverzicht pannen (beton/Sneldek → keramisch)")]
                    if not _det:
                        continue
                    _drows = [{"Component": _c, "Hoeveelheid": _h, "Eenheid": _e, "€/eenheid": round(_p, 2),
                               "Subtotaal €/m²": round(_h * _p, 2), "Bron": _bron} for _c, _h, _e, _p, _bron in _det]
                    _dsum = sum(_r["Subtotaal €/m²"] for _r in _drows)
                    st.markdown(f"**{_onam}** — opbouw ≈ €{_dsum:.0f}/m² (band €{float(_scr['Laag']):.0f}–"
                                f"€{float(_scr['Hoog']):.0f}/m²)")
                    st.dataframe(pd.DataFrame(_drows), use_container_width=True, hide_index=True,
                                 column_config={"€/eenheid": st.column_config.NumberColumn(format="€%.2f"),
                                                "Subtotaal €/m²": st.column_config.NumberColumn(format="€%.2f"),
                                                "Component": st.column_config.TextColumn(width="large")})
                    for _r in _drows:
                        _detail_rows.append({"Scope": _onam, **_r})
                st.caption("Indicatief, geen offerte. Arbeidsuren × uurtarief = directe arbeid; materiaal/materieel "
                           "is inkoop/huur. Schaalt met het dakoppervlak; loodwerk + vogelwering staan apart.")
            # Opbouw naar should-price: directe kosten + algemene kosten + winst & risico (LCL/Mean/UCL).
            _ak_lo, _ak_me, _ak_hi = _dlo * DAK_RENO_AK, _dme * DAK_RENO_AK, _dhi * DAK_RENO_AK
            _wr_lo, _wr_me, _wr_hi = ((_dlo + _ak_lo) * DAK_RENO_WR, (_dme + _ak_me) * DAK_RENO_WR,
                                      (_dhi + _ak_hi) * DAK_RENO_WR)
            _slo, _sme, _shi = _dlo + _ak_lo + _wr_lo, _dme + _ak_me + _wr_me, _dhi + _ak_hi + _wr_hi  # excl. btw €/m²
            _btw_lo, _btw_me, _btw_hi = _slo * DAK_RENO_BTW, _sme * DAK_RENO_BTW, _shi * DAK_RENO_BTW
            _silo, _sime, _sihi = _slo + _btw_lo, _sme + _btw_me, _shi + _btw_hi  # incl. btw €/m²
            _opb = pd.DataFrame([
                {"Opbouw": "Directe kosten (materiaal + arbeid)", "LCL (€/m²)": _dlo, "Mean (€/m²)": _dme, "UCL (€/m²)": _dhi},
                {"Opbouw": f"+ Algemene kosten ({DAK_RENO_AK * 100:.0f}%)", "LCL (€/m²)": _ak_lo, "Mean (€/m²)": _ak_me, "UCL (€/m²)": _ak_hi},
                {"Opbouw": f"+ Winst & risico ({DAK_RENO_WR * 100:.0f}%)", "LCL (€/m²)": _wr_lo, "Mean (€/m²)": _wr_me, "UCL (€/m²)": _wr_hi},
                {"Opbouw": "= Should-price excl. btw", "LCL (€/m²)": _slo, "Mean (€/m²)": _sme, "UCL (€/m²)": _shi},
                {"Opbouw": f"+ BTW ({DAK_RENO_BTW * 100:.0f}%)", "LCL (€/m²)": _btw_lo, "Mean (€/m²)": _btw_me, "UCL (€/m²)": _btw_hi},
                {"Opbouw": "= Should-price incl. btw", "LCL (€/m²)": _silo, "Mean (€/m²)": _sime, "UCL (€/m²)": _sihi},
            ])
            st.dataframe(_opb, use_container_width=True, hide_index=True,
                         column_config={"LCL (€/m²)": st.column_config.NumberColumn(format="€%.0f"),
                                        "Mean (€/m²)": st.column_config.NumberColumn(format="€%.0f"),
                                        "UCL (€/m²)": st.column_config.NumberColumn(format="€%.0f")})
            rc = st.columns(3)
            rc[0].metric("Should-price excl. btw (mean)", f"€{_sme:.0f}/m²",
                         f"LCL €{_slo:.0f} – UCL €{_shi:.0f}", delta_color="off")
            rc[1].metric("Should-price incl. btw (mean)", f"€{_sime:.0f}/m²",
                         f"LCL €{_silo:.0f} – UCL €{_sihi:.0f}", delta_color="off")
            rc[2].metric(f"Totaal incl. btw — {dak_opp:.0f} m² (mean)", eur(_sime * dak_opp),
                         f"{eur(_silo * dak_opp)} – {eur(_sihi * dak_opp)}", delta_color="off")
            st.caption(f"Voor {dak_opp:.0f} m²: {eur(_slo * dak_opp)} – {eur(_shi * dak_opp)} excl. btw "
                       f"(mean {eur(_sme * dak_opp)}) → **{eur(_silo * dak_opp)} – {eur(_sihi * dak_opp)} incl. btw "
                       f"(mean {eur(_sime * dak_opp)})**.")
            # Toets álle offertes (niet één hardcoded naam) aan de should-price — driven door de data.
            _toets = [o for o in st.session_state.get("dakofferte", [])
                      if str(o.get("Bedrijf") or "").strip() and str(o.get("Status") or "") != "Afgewezen"
                      and float(o.get("Excl. btw") or 0) > 0]
            if _toets:
                st.markdown("**Offertes getoetst aan de should-price** (€/m² excl. btw):")
                for _o in _toets:
                    _oex = float(_o.get("Excl. btw") or 0)
                    _om2 = _oex / dak_opp if dak_opp else 0.0
                    _ov = ("🟢 marktconform" if _om2 <= _shi
                           else "🟡 aan de hoge kant" if _om2 <= _shi * 1.25 else "🔴 fors boven should-price")
                    st.markdown(f"- **{_o.get('Bedrijf')}**: {eur(_oex)} excl. = **€{_om2:.0f}/m²** → {_ov} "
                                f"(should-price €{_slo:.0f}–€{_shi:.0f}/m²).")
                st.caption("De should-price is het **dakrenovatie-deel** (excl. lood/vogelwering/goot); "
                           "offertetotalen bevatten die vaak wél → die liggen hoger. Voor de zuivere, "
                           "scope-genormaliseerde vergelijking zie **⚖️ Vergelijking & advies**.")
            else:
                st.caption("Nog geen offertes om te toetsen — voeg ze toe bij **📥 Offertes**.")
            _q = st.number_input("Andere offerte toetsen (€ excl. btw voor de dakrenovatie · 0 = overslaan)",
                                 0.0, 1_000_000.0, 0.0, 250.0, key="dak_reno_quote")
            if _q > 0:
                _qm2 = _q / dak_opp
                if _qm2 < _slo:
                    st.success(f"🟢 €{_qm2:.0f}/m² ligt **onder** de should-price — scherp (check specs en garantie).")
                elif _qm2 <= _shi:
                    st.success(f"🟢 €{_qm2:.0f}/m² is **marktconform**.")
                elif _qm2 <= _shi * 1.25:
                    st.warning(f"🟡 €{_qm2:.0f}/m² ligt **aan de hoge kant** — onderhandel of vraag uitsplitsing.")
                else:
                    st.error(f"🔴 €{_qm2:.0f}/m² ligt **fors boven** de should-price (~€{_shi:.0f}/m²).")
            st.caption("Directe kosten = materiaal + arbeid. **AK** dekt werkvoorbereiding, projectleiding, "
                       "CAR-verzekering en administratie; **W&R** is winst + risico — samen maken ze er een "
                       "should-*price* van die je met een offerte mag vergelijken. Marktonderzoek 2025/26: een "
                       "pannendak volledig vernieuwen **incl. isolatie** kost ≈ €125–300/m² (consument; Oranje "
                       "Dakbeheer, Homedeal, Kosten-Dakdekker); puur **herdekken zonder isolatie** ligt lager "
                       "(60 m²: betonpan ≈ €50–58, keramisch ≈ €67–92/m²). Kostenverdeling herdekken: pannen "
                       "35–40%, leggen 30–35%, tengels/panlatten 10–15%, steiger 5–10% (Kosten-Dakdekker). "
                       "BTW-regel = 21% (gelijk aan de offerte); valt de **isolatie-arbeid** onder 9% (woning > 2 "
                       "jr) dan ligt incl. iets lager. Pannen-materiaal volgt het **pantype**. Loodwerk + "
                       "vogelwering apart. Indicatie, geen offerte.")
            _sc_sheets = {"Directe kosten": _rb_show, "Opbouw should-price": _opb}
            if _detail_rows:
                _sc_sheets["Kostenopbouw per scope"] = pd.DataFrame(_detail_rows)[
                    ["Scope", "Component", "Hoeveelheid", "Eenheid", "€/eenheid", "Subtotaal €/m²", "Bron"]]
            st.download_button("⬇️ Download should-cost dakrenovatie (Excel)",
                               m.df_to_excel_bytes(_sc_sheets),
                               file_name="dakrenovatie_shouldcost.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="dak_reno_xlsx")
    with _stage[1]:
        with _off_tabs[2]:
            _up = st.file_uploader("Offerte (PDF)", type=["pdf"], key="dak_up")
            if _up is not None and st.button("Verwerk upload (AI)", key="dak_up_btn", type="primary"):
                if not ai.available():
                    st.warning("Automatisch uitlezen vereist een LLM-key (Groq). Voeg anders handmatig toe.")
                else:
                    with st.spinner("PDF uitlezen + posten herkennen…"):
                        _pdf_bytes = _up.read()
                        _txt = ai.extract_pdf_text(_pdf_bytes)
                        _od = ai.parse_offerte(_txt) if _txt else None
                    _ok = bool(_od and str(_od.get("bedrijf") or "").strip())
                    _new_posten = []
                    if not _ok:
                        # uitlezen mislukt — tóch toevoegen (op bestandsnaam) zodat de offerte niet verdwijnt
                        _bn = (getattr(_up, "name", "") or "Onbekende offerte").rsplit(".", 1)[0].strip() \
                            or "Onbekende offerte"
                        _row = {"Bedrijf": _bn, "Offertenr.": "", "Datum": "", "Geldig t/m": "",
                                "Excl. btw": 0.0, "Incl. btw": 0.0, "Status": "Ontvangen",
                                "Notities": "automatisch uitlezen mislukt — vul bedragen handmatig aan"}
                    else:
                        _bn = str(_od["bedrijf"]).strip()
                        _row = {"Bedrijf": _bn, "Offertenr.": _od.get("offertenummer", ""),
                                "Datum": _od.get("datum", ""), "Geldig t/m": _od.get("geldig", ""),
                                "Excl. btw": float(_od.get("totaal_excl", 0) or 0),
                                "Incl. btw": float(_od.get("totaal_incl", 0) or 0),
                                "Status": "Ontvangen", "Notities": "automatisch uit PDF"}
                        for _p in _od.get("posten", []):
                            try:
                                _pr = float(_p.get("prijs_excl", 0) or 0)
                            except Exception:  # noqa: BLE001
                                _pr = 0.0
                            if str(_p.get("onderdeel") or "").strip():
                                _new_posten.append({"Bedrijf": _bn, "Onderdeel": str(_p["onderdeel"]).strip(),
                                                    "Prijs excl. btw": _pr})
                    # dezelfde offerte (zelfde offertenummer/bedrijf) bijwerken i.p.v. dubbel toevoegen
                    _lst = st.session_state["dakofferte"]
                    _key = _dak_offerte_key(_row)
                    _hit = next((i for i, r in enumerate(_lst) if _dak_offerte_key(r) == _key), None)
                    if _hit is None:
                        _lst.append(_row)
                    else:
                        _lst[_hit] = _row
                    # posten van dit bedrijf vervangen, zodat her-upload geen dubbele posten geeft
                    st.session_state["dak_posten"] = [
                        p for p in st.session_state.get("dak_posten", [])
                        if str(p.get("Bedrijf") or "").strip().lower() != _bn.lower()] + _new_posten
                    # Westermeer-regel: bewaar de geüploade PDF zodat de offerte altijd terugvindbaar is
                    try:
                        _adir = _dak_attachments_dir()
                        if _adir is not None:
                            _safe = "".join(c for c in _bn if c.isalnum() or c in " -_").strip().replace(" ", "-")
                            _nr2 = str(_row.get("Offertenr.") or "").strip() or "offerte"
                            (_adir / f"Offerte-{_safe}-{_nr2}.pdf").write_bytes(_pdf_bytes)
                    except Exception:  # noqa: BLE001
                        pass
                    _verb = "bijgewerkt" if _hit is not None else "toegevoegd"
                    if _ok:
                        st.session_state["dak_flash"] = (
                            "success", f"Offerte van {_bn} {_verb} met {len(_new_posten)} posten — "
                            "zie de tabel en posten-matrix.")
                    else:
                        st.session_state["dak_flash"] = (
                            "warning", f"Kon '{_bn}' niet automatisch uitlezen — als lege regel {_verb}, "
                            "vul de bedragen handmatig aan in de tabel.")
                    try:
                        _persist()
                    except Exception as _exc:  # noqa: BLE001
                        st.session_state["dak_flash"] = (
                            "warning", f"Toegevoegd, maar opslaan in Gist mislukte: {_exc}")
                    st.rerun()
            st.caption("De posten/totalen worden automatisch uit de PDF gehaald (met je Groq-key). "
                       "Op Streamlit Cloud wordt de PDF zelf niet bewaard; de uitgelezen gegevens wél (Gist).")

    with _stage[1]:
        with _off_tabs[3]:
            with st.form("dak_add", clear_on_submit=True):
                af = st.columns(2)
                _b = af[0].text_input("Bedrijf *")
                _nr = af[1].text_input("Offertenummer")
                af2 = st.columns(2)
                _datum = af2[0].text_input("Datum (jjjj-mm-dd)")
                _geldig = af2[1].text_input("Geldig t/m")
                af3 = st.columns(2)
                _excl = af3[0].number_input("Bedrag excl. btw (€)", 0.0, 1_000_000.0, 0.0, 100.0)
                _incl = af3[1].number_input("Bedrag incl. btw (€) — 0 = excl × 1,21", 0.0, 1_000_000.0, 0.0, 100.0)
                _status = st.selectbox("Status", ["Aangevraagd", "Ontvangen", "Vergeleken", "Gekozen", "Afgewezen"])
                _notes = st.text_input("Notities")
                if st.form_submit_button("Toevoegen", type="primary"):
                    if _b.strip():
                        st.session_state["dakofferte"].append({
                            "Bedrijf": _b.strip(), "Offertenr.": _nr, "Datum": _datum, "Geldig t/m": _geldig,
                            "Excl. btw": _excl, "Incl. btw": _incl or round(_excl * 1.21, 2),
                            "Status": _status, "Notities": _notes})
                        try:
                            _persist()
                        except Exception:  # noqa: BLE001
                            pass
                        st.rerun()
                    else:
                        st.warning("Vul minimaal het bedrijf in.")

    with _off_tabs[0]:
        st.markdown("#### Offertes vergelijken")
        st.caption("Of bewerk hieronder rechtstreeks in de tabel (rij toevoegen met +).")
        _dak_edit = st.data_editor(
            pd.DataFrame(st.session_state.get("dakofferte", DAK_DEFAULT)), num_rows="dynamic",
            use_container_width=True, key=f"dak_oe_{len(st.session_state.get('dakofferte', []))}",
            column_config={
                "Excl. btw": st.column_config.NumberColumn(format="€%.2f"),
                "Incl. btw": st.column_config.NumberColumn(format="€%.2f"),
                "Status": st.column_config.SelectboxColumn(
                    options=["Aangevraagd", "Ontvangen", "Vergeleken", "Gekozen", "Afgewezen"]),
            })
        _dak_rows = [r for r in _dak_edit.to_dict("records") if str(r.get("Bedrijf") or "").strip()]
        st.session_state["dakofferte"] = _dak_rows
        st.caption(f"📄 {len(_dak_rows)} offerte(s) in beheer"
                   + (": " + ", ".join(str(r["Bedrijf"]) for r in _dak_rows) if _dak_rows else "."))
        _dak_uniek = _dak_dedup(_dak_rows)
        if len(_dak_uniek) < len(_dak_rows):
            st.warning(f"⚠️ {len(_dak_rows) - len(_dak_uniek)} dubbele offerte(s) gevonden "
                       "(zelfde offertenummer/bedrijf).")
            if st.button("🧹 Dubbele offertes opruimen (laatste behouden)", key="dak_dedup_btn"):
                st.session_state["dakofferte"] = _dak_uniek
                _keep = {str(r.get("Bedrijf") or "").strip().lower() for r in _dak_uniek}
                _seen, _pd = set(), []
                for _p in st.session_state.get("dak_posten", []):
                    _pk = (str(_p.get("Bedrijf") or "").strip().lower(), str(_p.get("Onderdeel") or "").strip().lower())
                    if _pk not in _seen:
                        _seen.add(_pk)
                        _pd.append(_p)
                st.session_state["dak_posten"] = _pd
                try:
                    _persist()
                except Exception:  # noqa: BLE001
                    pass
                st.rerun()
        _btw_mis = []
        for r in _dak_rows:
            _e = float(r.get("Excl. btw") or 0)
            _i = float(r.get("Incl. btw") or 0)
            if _e > 0 and _i > 0 and not (8.5 <= (_i - _e) / _e * 100 <= 21.5):
                _btw_mis.append(str(r.get("Bedrijf") or ""))
        if _btw_mis:
            st.warning("⚠️ **Btw-controle** — effectief tarief buiten 9–21% bij: " + ", ".join(_btw_mis)
                       + ". Waarschijnlijk las de PDF-import excl of incl fout (een mix van 9% en 21% is prima). "
                       "Corrigeer het juiste bedrag in de tabel, of — als **alles 21%** is — herbereken incl:")
            if st.button("🔁 Incl. btw = excl × 1,21 herberekenen", key="dak_btw_fix"):
                for _r in st.session_state["dakofferte"]:
                    _e = float(_r.get("Excl. btw") or 0)
                    if _e > 0 and abs(float(_r.get("Incl. btw") or 0) - _e * 1.21) > 1.0:
                        _r["Incl. btw"] = round(_e * 1.21, 2)
                try:
                    _persist()
                except Exception:  # noqa: BLE001
                    pass
                st.rerun()
        if store.enabled() and st.button("💾 Offertes bewaren in Gist", key="dak_save"):
            try:
                _persist()
                st.success("Opgeslagen.")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Opslaan mislukt: {exc}")

        def _dak_oordeel(v):
            if v <= DAK_MARKT_HI:
                return "🟢 marktconform"
            return "🟡 aan de hoge kant" if v <= DAK_MARKT_HI * 1.25 else "🔴 fors boven markt"

        if _dak_rows:
            _dv = pd.DataFrame(_dak_rows)
            _dv["€/m² incl."] = (_dv["Incl. btw"] / dak_opp).round(0)
            _dv["Oordeel"] = _dv["€/m² incl."].apply(_dak_oordeel)

            from datetime import date as _vdate

            def _verval(g):
                try:
                    _d = (_vdate.fromisoformat(str(g).strip()) - _vdate.today()).days
                except Exception:  # noqa: BLE001
                    return ""
                return "⛔ verlopen" if _d < 0 else (f"⚠️ {_d} d" if _d <= 7 else f"{_d} d")
            _dv["Vervalt"] = _dv["Geldig t/m"].apply(_verval)
            _dv = _dv.sort_values("Incl. btw").reset_index(drop=True)
            st.dataframe(
                _dv[["Bedrijf", "Offertenr.", "Geldig t/m", "Vervalt", "Excl. btw", "Incl. btw", "€/m² incl.",
                     "Oordeel", "Status", "Notities"]],
                use_container_width=True, hide_index=True,
                column_config={
                    "Excl. btw": st.column_config.NumberColumn(format="€%.0f"),
                    "Incl. btw": st.column_config.NumberColumn(format="€%.0f"),
                    "€/m² incl.": st.column_config.NumberColumn(format="€%.0f"),
                })
            st.bar_chart(_dv[["Bedrijf", "€/m² incl."]].set_index("Bedrijf"), use_container_width=True)
            st.download_button("⬇️ Download vergelijking (Excel)",
                               m.df_to_excel_bytes({"Offertes": _dv}),
                               file_name="dakrenovatie_offertes.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with _stage[0]:
        st.markdown("#### 📇 Contacten & afspraken")
        st.caption("Leg per bedrijf de contactgegevens en afspraken vast — datum, tijd, type en status. "
                   "Rij toevoegen met +, of gebruik het formulier eronder.")
        from datetime import date as _date_af
        _af_tabs = st.tabs(["📇 Overzicht", "📅 Agenda & bezoeken", "➕ Toevoegen & importeren",
                            "🛠️ Acties & export"])

        with _af_tabs[0]:
            _vanaf = st.date_input("Toon afspraken vanaf", value=_date_af(2026, 6, 1), key="dak_afspr_vanaf",
                                   format="DD-MM-YYYY")
            _vanaf_s = _vanaf.isoformat() if hasattr(_vanaf, "isoformat") else str(_vanaf)
            _acols = ["Bedrijf", "Type", "Datum", "Tijd", "Contactpersoon", "Telefoon", "E-mail", "Status", "Notitie"]
            _alle_afspr = list(st.session_state.get("dak_afspraken", DAK_AFSPRAKEN_DEFAULT))
            # Automatisch ontdubbelen op tijdslot (datum+tijd): seed- en agenda-varianten van dezelfde
            # afspraak (bv. 'Dakbedrijf Westermeer' vs 'Dak offerte westerman', of 'Bonné Dakonderhoud'
            # vs 'Bonné dak onderhoud') vallen samen — de meest complete rij blijft staan, geannuleerde
            # afspraken blijven los (geannuleerd + nieuwe = twee aparte). Eénmalig opslaan zodat ook de
            # Gist schoon wordt; daarna komen de dubbelen niet meer terug.
            def _af_filled(r):
                return sum(1 for v in r.values() if str(v or "").strip())
            _seen_slot, _clean_afspr = {}, []
            for _r in _alle_afspr:
                if str(_r.get("Status") or "") == "Geannuleerd":
                    _clean_afspr.append(_r)
                    continue
                _k = _afspr_slotkey(_r)
                if _k not in _seen_slot:
                    _seen_slot[_k] = len(_clean_afspr)
                    _clean_afspr.append(_r)
                elif _af_filled(_r) > _af_filled(_clean_afspr[_seen_slot[_k]]):
                    _clean_afspr[_seen_slot[_k]] = _r  # houd de meest complete rij van dit tijdslot
            if len(_clean_afspr) != len(_alle_afspr):
                _alle_afspr = _clean_afspr
                st.session_state["dak_afspraken"] = _clean_afspr
                st.session_state["dak_afspr_nonce"] = st.session_state.get("dak_afspr_nonce", 0) + 1
                try:
                    _persist()
                except Exception:  # noqa: BLE001
                    pass
                st.rerun()
            _verborgen = [r for r in _alle_afspr if str(r.get("Datum") or "") and str(r.get("Datum")) < _vanaf_s]
            _zichtbaar = [r for r in _alle_afspr if r not in _verborgen]
            _af_key = f"dak_afspr_oe_{len(_zichtbaar)}_{st.session_state.get('dak_afspr_nonce', 0)}"
            _af = st.data_editor(
                pd.DataFrame(_zichtbaar, columns=_acols), num_rows="dynamic",
                use_container_width=True,
                key=_af_key,
                column_config={
                    "Type": st.column_config.SelectboxColumn(options=DAK_AFSPR_TYPES),
                    "Datum": st.column_config.TextColumn(help="jjjj-mm-dd"),
                    "Tijd": st.column_config.TextColumn(help="uu:mm"),
                    "Status": st.column_config.SelectboxColumn(options=DAK_AFSPR_STATUS),
                    "Notitie": st.column_config.TextColumn(width="large"),
                })
            _deleted = (st.session_state.get(_af_key) or {}).get("deleted_rows", []) or []
            _geannuleerd = []
            for _i in _deleted:
                if 0 <= _i < len(_zichtbaar):
                    _row = dict(_zichtbaar[_i])
                    if str(_row.get("Bedrijf") or "").strip() and str(_row.get("Status") or "") != "Geannuleerd":
                        _row["Status"] = "Geannuleerd"
                        _geannuleerd.append(_row)
            # Guard tegen dubbel ingezette afspraken: vouw exact identieke rijen samen (byte-identiek =
            # altijd een echte dubbele, nooit twee aparte afspraken). Een rij met een datum vóór het
            # filter valt in _verborgen terwijl de data_editor (zelfde key, want len(_zichtbaar) blijft
            # gelijk) zijn added_rows opnieuw toepast. Dedup hier _af_rows (gebruikt door agenda/export)
            # én de samengestelde lijst, zodat editor, agenda én Gist-opslag in één render schoon zijn.
            _af_rows = []
            for _r in _af.to_dict("records"):
                if str(_r.get("Bedrijf") or "").strip() and _r not in _af_rows:
                    _af_rows.append(_r)
            _nieuw_afspr = []
            for _r in _verborgen + _af_rows + _geannuleerd:
                if _r not in _nieuw_afspr:
                    _nieuw_afspr.append(_r)
            if _nieuw_afspr != st.session_state.get("dak_afspraken"):
                st.session_state["dak_afspraken"] = _nieuw_afspr
                try:
                    _persist()
                except Exception:  # noqa: BLE001
                    pass
                if _geannuleerd:
                    st.session_state["dak_afspr_nonce"] = st.session_state.get("dak_afspr_nonce", 0) + 1
                    st.rerun()
            else:
                st.session_state["dak_afspraken"] = _nieuw_afspr
            if _verborgen:
                st.caption(f"🔽 {len(_verborgen)} afspra(a)k(en) vóór {_vanaf.strftime('%d-%m-%Y')} verborgen "
                           "(blijven wel bewaard).")
            _conflicten = _afspraak_conflicten(_af_rows)
            if _conflicten:
                st.warning("⚠️ Te krap gepland — overlap of minder dan een uur ertussen:\n"
                           + "\n".join(f"- {c}" for c in _conflicten))
            elif _af_rows:
                st.caption("✅ Planning-check: nergens overlap — overal minstens een uur tussen afspraken op dezelfde dag.")

        with _af_tabs[2]:
            st.markdown("**➕ Afspraak / contact toevoegen**")
            with st.form("dak_afspr_add", clear_on_submit=True):
                gf = st.columns(2)
                _ab = gf[0].text_input("Bedrijf *")
                _atype = gf[1].selectbox("Type", DAK_AFSPR_TYPES)
                gf2 = st.columns(2)
                _adatum = gf2[0].text_input("Datum (jjjj-mm-dd)")
                _atijd = gf2[1].text_input("Tijd (uu:mm)")
                gf3 = st.columns(2)
                _acp = gf3[0].text_input("Contactpersoon")
                _atel = gf3[1].text_input("Telefoon")
                gf4 = st.columns(2)
                _amail = gf4[0].text_input("E-mail")
                _astatus = gf4[1].selectbox("Status", DAK_AFSPR_STATUS)
                _anote = st.text_input("Notitie")
                if st.form_submit_button("Toevoegen", type="primary"):
                    if _ab.strip():
                        st.session_state["dak_afspraken"].append({
                            "Bedrijf": _ab.strip(), "Type": _atype, "Datum": _adatum, "Tijd": _atijd,
                            "Contactpersoon": _acp, "Telefoon": _atel, "E-mail": _amail,
                            "Status": _astatus, "Notitie": _anote})
                        try:
                            _persist()
                        except Exception:  # noqa: BLE001
                            pass
                        st.rerun()
                    else:
                        st.warning("Vul minimaal het bedrijf in.")
            st.divider()
            st.markdown("**📅 Importeer uit Google Agenda (iCal) — niets overtypen**")
            st.caption("Plak het **'Geheime adres in iCal-indeling'** van je agenda (Google Agenda → "
                       "Instellingen → kies je agenda → *Privé-adres in iCal-indeling*). Of zet 'm in "
                       "`secrets.toml` als `dak_ical_url`. Ik haal alle afspraken op waarvan de titel het "
                       "trefwoord bevat en zet ze automatisch in de log — bestaande tijdsloten sla ik over.")
            try:
                _ical_default = st.secrets.get("dak_ical_url", "")
            except Exception:  # noqa: BLE001
                _ical_default = ""
            _ical = st.text_input("iCal-URL", value=st.session_state.get("dak_ical_url", _ical_default),
                                  type="password", key="dak_ical_in",
                                  help="Geheime iCal-link; wordt alleen in deze sessie bewaard (niet in de Gist).")
            _kw = st.text_input("Filter op trefwoord in de titel", value="dak", key="dak_ical_kw")
            if st.button("⬇️ Ophalen uit agenda", key="dak_ical_fetch"):
                st.session_state["dak_ical_url"] = _ical
                if not _ical.strip():
                    st.warning("Vul eerst de iCal-URL in.")
                else:
                    try:
                        _new = _ics_dak_afspraken(_fetch_url(_ical.strip()), keyword=(_kw or "dak").strip().lower(),
                                                  min_datum=_vanaf_s)
                        # Ontdubbel op tijdslot (datum+tijd) tegen wat er al staat — zo komt dezelfde
                        # afspraak niet onder een agenda-naamvariant nóg eens binnen. Geannuleerde
                        # afspraken tellen niet mee: een nieuwe afspraak op dat vrijgekomen slot mag wél.
                        _have = {_afspr_slotkey(r) for r in st.session_state.get("dak_afspraken", [])
                                 if str(r.get("Status") or "") != "Geannuleerd"}
                        _added = []
                        for r in _new:
                            k = _afspr_slotkey(r)
                            if k not in _have:
                                _have.add(k)
                                _added.append(r)
                        st.session_state.setdefault("dak_afspraken", [])
                        st.session_state["dak_afspraken"].extend(_added)
                        if _added:
                            try:
                                _persist()
                            except Exception:  # noqa: BLE001
                                pass
                            st.success(f"{len(_added)} afspraak(en) uit de agenda toegevoegd "
                                       f"({len(_new)} gevonden, rest stond er al).")
                            st.rerun()
                        else:
                            st.info(f"{len(_new)} dak-afspraak(en) gevonden — allemaal al in de log.")
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Ophalen mislukt: {exc}")

        with _af_tabs[1]:
            if _af_rows:
                _afdf = pd.DataFrame(_af_rows).sort_values(["Datum", "Tijd"], na_position="last")
                _komend = _afdf[_afdf["Status"] == "Bezoek gepland"].copy()
                _weekrijen = []  # plat overzicht voor de Excel-export
                if not _komend.empty:
                    from datetime import date as _date
                    _dagen = ["ma", "di", "wo", "do", "vr", "za", "zo"]
                    _conf_dat = {str(c).split(":", 1)[0] for c in _conflicten}

                    def _weekdag(d):
                        try:
                            return _dagen[_date.fromisoformat(str(d)).weekday()]
                        except Exception:  # noqa: BLE001
                            return ""
                    _per_dag = {}
                    for _r in _afdf.to_dict("records"):
                        try:
                            _dd = _date.fromisoformat(str(_r.get("Datum")))
                        except Exception:  # noqa: BLE001
                            continue
                        _per_dag.setdefault(_dd.isoformat(), []).append(
                            (str(_r.get("Tijd") or "").strip(), str(_r.get("Bedrijf") or "").strip(),
                             str(_r.get("Status") or "").strip()))
                    for _iso in _per_dag:
                        _per_dag[_iso].sort()
                    _planmaanden = set()
                    for _x in _komend["Datum"]:
                        try:
                            _pm = _date.fromisoformat(str(_x))
                            _planmaanden.add((_pm.year, _pm.month))
                        except Exception:  # noqa: BLE001
                            continue
                    _mnd = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
                    _emo = {"Bezoek gepland": "🔵", "Bezoek uitgevoerd": "✅", "Offerte ontvangen": "🟠",
                            "Wachten op offerte": "🟠", "Geannuleerd": "⚪"}
                    _today = _date.today()
                    _plan = sorted((_date.fromisoformat(k), t, b) for k in _per_dag for t, b, s in _per_dag[k]
                                   if s == "Bezoek gepland")
                    _upcoming = [x for x in _plan if x[0] >= _today]
                    st.markdown("**📅 Agenda — geplande bezoeken**")
                    _sum = f"**{len(_plan)}** gepland bezoek" + ("en" if len(_plan) != 1 else "")
                    if _upcoming:
                        _nx = _upcoming[0]
                        _sum += f" · eerstvolgende **{_nx[0].day} {_mnd[_nx[0].month - 1]}** — {_nx[2]}"
                    if _conf_dat:
                        _sum += f" · ⚠️ **{len(_conf_dat)}** dag(en) met conflict"
                    st.caption(_sum)
                    _lines = []
                    for _iso in sorted(_per_dag):
                        _d = _date.fromisoformat(_iso)
                        _chips = []
                        for _t, _b, _s in _per_dag[_iso]:
                            _e = "⚠️" if _iso in _conf_dat else _emo.get(_s, "•")
                            _bb = f"~~{_b}~~" if _s == "Geannuleerd" else _b
                            _chips.append(f"{_e} {(_t + ' ') if _t else ''}{_bb}")
                        _pre = "🔴 " if _iso in _conf_dat else ("· " if _d < _today else "")
                        _lines.append(f"{_pre}**{_dagen[_d.weekday()]} {_d.day} {_mnd[_d.month - 1]}** — "
                                      + " · ".join(_chips))
                    st.markdown("  \n".join(_lines) if _lines else "_Nog geen afspraken in beeld._")
                    st.caption("🔵 gepland · ✅ uitgevoerd · 🟠 offerte/wachten · ⚪ geannuleerd"
                               + (" · 🔴 ⚠️ conflict" if _conf_dat else ""))
                    with st.expander("🗓️ Maandkalender (visueel)", expanded=False):
                        for _jr, _mn in sorted(_planmaanden):
                            _render_maand_kalender(_jr, _mn, _per_dag, _conf_dat)
                    for _iso in sorted(_per_dag):
                        _dd = _date.fromisoformat(_iso)
                        if (_dd.year, _dd.month) not in _planmaanden:
                            continue
                        for _t, _b, _sstat in _per_dag[_iso]:
                            _weekrijen.append({"Datum": _iso, "Dag": _dagen[_dd.weekday()], "Tijd": _t,
                                               "Bedrijf": _b, "Status": _sstat,
                                               "Let op": "conflict" if _iso in _conf_dat else ""})
                    _komend.insert(0, "Dag", _komend["Datum"].map(_weekdag))
                    with st.expander("📋 Geplande bezoeken — lijst", expanded=False):
                        st.dataframe(_komend[["Dag", "Datum", "Tijd", "Bedrijf", "Type"]].sort_values(["Datum", "Tijd"]),
                                     use_container_width=True, hide_index=True)
                else:
                    st.info("Nog geen geplande bezoeken — zet bij een afspraak de status op **Bezoek gepland**.")
            else:
                st.info("Nog geen afspraken — voeg er een toe bij **➕ Toevoegen & importeren**.")

        with _af_tabs[3]:
            if st.button("↪️ Fases bijwerken (na bezoek → wachten op offerte)", key="dak_afspr_bump",
                         help="Zet een langsgeweest 'Bezoek gepland' (datum voorbij) op 'Bezoek uitgevoerd', "
                              "en 'Bezoek uitgevoerd' door naar 'Wachten op offerte'. Eén fase per klik."):
                from datetime import date as _date
                _vandaag = _date.today().isoformat()
                _bump = 0
                for _r in st.session_state.get("dak_afspraken", []):
                    _s = str(_r.get("Status") or "")
                    if _s == "Bezoek gepland" and str(_r.get("Datum") or "9999") < _vandaag:
                        _r["Status"] = "Bezoek uitgevoerd"
                        _bump += 1
                    elif _s == "Bezoek uitgevoerd":
                        _r["Status"] = "Wachten op offerte"
                        _bump += 1
                if _bump:
                    st.session_state["dak_afspr_nonce"] = st.session_state.get("dak_afspr_nonce", 0) + 1
                    try:
                        _persist()
                    except Exception:  # noqa: BLE001
                        pass
                    st.success(f"{_bump} afspra(a)k(en) een fase doorgezet.")
                    st.rerun()
                else:
                    st.info("Niets om door te zetten — geen voorbije bezoeken of afgeronde bezoeken open.")
            if st.button("🧹 Dubbele afspraken opruimen (zelfde datum + tijd)", key="dak_afspr_dedup",
                         help="Behandelt afspraken op dezelfde **datum + tijd** als één afspraak — ook bij een "
                              "andere schrijfwijze van de naam (bv. 'Stipt Dakgroep' vs 'Stipt dak groep offerte'). "
                              "De meest complete rij blijft staan. **Geannuleerde** afspraken en afspraken zonder "
                              "datum/tijd blijven ongemoeid (een geannuleerde + een nieuwe op een ander tijdstip "
                              "zijn twee verschillende afspraken)."):
                _rows = st.session_state.get("dak_afspraken", [])

                def _filled(r):
                    return sum(1 for v in r.values() if str(v or "").strip())
                _seen, _uniq = {}, []  # slot-sleutel -> index in _uniq van de bewaarde rij
                for _r in _rows:
                    if str(_r.get("Status") or "") == "Geannuleerd":
                        _uniq.append(_r)  # geannuleerde records nooit samenvoegen of verwijderen
                        continue
                    _k = _afspr_slotkey(_r)
                    if _k not in _seen:
                        _seen[_k] = len(_uniq)
                        _uniq.append(_r)
                    elif _filled(_r) > _filled(_uniq[_seen[_k]]):
                        _uniq[_seen[_k]] = _r  # houd de meest complete rij van dit tijdslot
                _dups = len(_rows) - len(_uniq)
                if _dups:
                    st.session_state["dak_afspraken"] = _uniq
                    st.session_state["dak_afspr_nonce"] = st.session_state.get("dak_afspr_nonce", 0) + 1
                    try:
                        _persist()
                    except Exception:  # noqa: BLE001
                        pass
                    st.success(f"{_dups} dubbele afspra(a)k(en) opgeruimd (zelfde datum + tijd).")
                    st.rerun()
                else:
                    st.info("Geen dubbele afspraken op dezelfde datum + tijd gevonden.")
            st.divider()
            _wipe_ok = st.checkbox("Ik weet het zeker (verwijderen kan niet ongedaan)", key="dak_afspr_wipe_ok")
            if st.button("🗑️ Agenda leegmaken — alleen 'Offerte ontvangen' behouden",
                         key="dak_afspr_wipe", disabled=not _wipe_ok,
                         help="Verwijdert álle afspraken behalve die met status 'Offerte ontvangen' (de afgeronde "
                              "bezoeken met ontvangen offerte). Zet die status eerst op de afspraken die je wilt "
                              "behouden. Daarna kun je opnieuw uit de iCal importeren."):
                _all = st.session_state.get("dak_afspraken", [])
                _keep = [r for r in _all if str(r.get("Status") or "") == "Offerte ontvangen"]
                _removed = len(_all) - len(_keep)
                st.session_state["dak_afspraken"] = _keep
                st.session_state["dak_afspr_nonce"] = st.session_state.get("dak_afspr_nonce", 0) + 1
                try:
                    _persist()
                except Exception:  # noqa: BLE001
                    pass
                st.success(f"{_removed} afspra(a)k(en) gewist — {len(_keep)} met 'Offerte ontvangen' behouden. "
                           "Importeer nu opnieuw uit de iCal (tab ➕ Toevoegen & importeren).")
                st.rerun()
            if store.enabled() and st.button("💾 Afspraken bewaren in Gist", key="dak_afspr_save"):
                try:
                    _persist()
                    st.success("Opgeslagen.")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Opslaan mislukt: {exc}")
            if _af_rows:
                _sheets = {"Afspraken": _afdf}
                if _weekrijen:
                    _sheets["Weekoverzicht"] = pd.DataFrame(_weekrijen)[["Datum", "Dag", "Tijd", "Bedrijf", "Status", "Let op"]]
                _sheets["Planning-check"] = (pd.DataFrame({"Te krap (< 1 uur / overlap)": _conflicten})
                                             if _conflicten else
                                             pd.DataFrame({"Planning-check": ["Geen overlap — minstens 1 uur "
                                                                              "tussen afspraken op dezelfde dag."]}))
                st.download_button("⬇️ Download contacten & afspraken (Excel)",
                                   m.df_to_excel_bytes(_sheets),
                                   file_name="dakrenovatie_afspraken.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   key="dak_afspr_xlsx")
                st.download_button("🖨️ Print / PDF — contacten & afspraken",
                                   _afspraken_pdf_bytes(_af_rows, _conflicten),
                                   file_name="dakrenovatie_afspraken.pdf", mime="application/pdf",
                                   key="dak_afspr_pdf")

    with _cmp_tabs[1]:
        st.markdown("#### 🔍 Posten vergelijken (ook bij verschillende scope)")
        st.caption("Wordt **automatisch** gevuld: detailposten uit geüploade offertes (⬆️ hierboven, AI) "
                   "én een totaalregel uit de offertetabel voor offertes zonder PDF. Handmatig bijwerken "
                   "in de tabel kan, maar hoeft niet. Een lege cel = die post zit niet in die offerte.")
        _pin = pd.DataFrame(st.session_state.get("dak_posten", DAK_POSTEN_DEFAULT))
        _pin["Btw %"] = _pin["Btw %"].fillna(21).astype(int) if "Btw %" in _pin.columns else 21
        with st.expander("✏️ Detailposten handmatig bewerken / toevoegen", expanded=False):
            _pe = st.data_editor(
                _pin, num_rows="dynamic",
                use_container_width=True, key=f"dak_posten_oe_{len(st.session_state.get('dak_posten', []))}",
                column_config={
                    "Prijs excl. btw": st.column_config.NumberColumn(format="€%.2f"),
                    "Btw %": st.column_config.SelectboxColumn(options=[21, 9], default=21,
                                                              help="9% (arbeid/isolatie) of 21% (materiaal)"),
                    "Onderdeel": st.column_config.TextColumn(width="large"),
                })
            _prows = []
            for r in _pe.to_dict("records"):
                if str(r.get("Bedrijf") or "").strip() and str(r.get("Onderdeel") or "").strip():
                    try:
                        r["Btw %"] = int(float(r.get("Btw %") or 21))
                    except Exception:  # noqa: BLE001
                        r["Btw %"] = 21
                    _prows.append(r)
            st.session_state["dak_posten"] = _prows
            if store.enabled() and st.button("💾 Posten bewaren in Gist", key="dak_posten_save"):
                try:
                    _persist()
                    st.success("Opgeslagen.")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Opslaan mislukt: {exc}")

        # Automatisch aanvullen: elke offerte uit de offertetabel zonder eigen posten krijgt een totaalregel.
        _TOTREGEL = "Totaal offerte (excl. btw)"
        _auto = list(_prows)
        _met_posten = {str(r.get("Bedrijf") or "").strip() for r in _prows}
        _auto_added = []
        for _o in st.session_state.get("dakofferte", []):
            _b = str(_o.get("Bedrijf") or "").strip()
            if str(_o.get("Status") or "") == "Afgewezen":
                continue  # afgewezen / oude offertes niet meenemen in de vergelijking
            try:
                _ex = float(_o.get("Excl. btw") or 0)
            except Exception:  # noqa: BLE001
                _ex = 0.0
            if _b and _b not in _met_posten and _ex > 0:
                _auto.append({"Bedrijf": _b, "Onderdeel": _TOTREGEL, "Prijs excl. btw": _ex})
                _auto_added.append(_b)
        if _auto:
            _pm = pd.DataFrame(_auto).pivot_table(
                index="Onderdeel", columns="Bedrijf", values="Prijs excl. btw", aggfunc="sum")
            _bedr_cols = list(_pm.columns)
            _disp = _pm.round(0).copy()
            # Scope-indicator: in hoeveel offertes zit deze post? (maakt scope-verschillen scanbaar)
            _disp.insert(0, "Scope", _pm.notna().sum(axis=1).astype(int).astype(str) + f"/{len(_bedr_cols)}")
            _disp.loc["── Totaal (excl. btw) ──"] = [""] + list(_pm.sum().round(0).values)
            _colcfg = {_c: st.column_config.NumberColumn(format="€%.0f") for _c in _bedr_cols}
            _colcfg["Onderdeel"] = st.column_config.TextColumn(width="large")
            _colcfg["Scope"] = st.column_config.TextColumn(width="small",
                                                           help="In hoeveel offertes deze post voorkomt")
            st.dataframe(_disp.reset_index(), use_container_width=True, hide_index=True, column_config=_colcfg)
            if _auto_added:
                st.caption("🔄 Automatisch aangevuld uit de offertetabel (totaalregel): "
                           + ", ".join(sorted(set(_auto_added))) + ". Upload hun PDF voor detailposten.")
            else:
                st.caption("Lege cel = post zit niet in die offerte. Bedragen excl. btw.")
            # Scope-check alleen over detailposten van offertes die detail hébben (minstens 2 nodig).
            _detb = sorted({str(p["Bedrijf"]).strip() for p in _auto if str(p["Onderdeel"]) != _TOTREGEL})
            if len(_detb) >= 2:
                _sub = _pm.reindex(columns=_detb).drop(index=_TOTREGEL, errors="ignore")
                _ontbreekt = [idx for idx in _sub.index if not _sub.loc[idx].notna().all()]
                if _ontbreekt:
                    st.warning("⚠️ **Scope-verschil** — niet in alle offertes-met-detail: " + ", ".join(_ontbreekt)
                               + ". Vraag de aanbieders deze post toe te voegen, of houd er rekening mee bij "
                               "het vergelijken (een lagere offerte kan posten missen).")
                else:
                    st.success("✅ Alle offertes-met-detail bevatten dezelfde posten — eerlijke vergelijking.")
            st.download_button("⬇️ Download posten-matrix (Excel)",
                               m.df_to_excel_bytes({"Posten-matrix": _disp.reset_index()}),
                               file_name="dakrenovatie_posten.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="dak_posten_xlsx")

    with _cmp_tabs[2]:
        # ---- Insightful scope comparison to help pick the right quote ----
        _detbedr_real = sorted({str(p.get("Bedrijf") or "").strip() for p in _prows if str(p.get("Bedrijf") or "").strip()})
        if not _detbedr_real:
            st.info("Nog geen detailposten per offerte — voeg ze toe bij **🔍 Posten vergelijken** of "
                    "upload offerte-PDF's. Dan verschijnt hier de vergelijking per onderdeel tegen de "
                    "should-cost-baseline.")
        if _detbedr_real:
            st.markdown("#### 📊 Vergelijking & advies — welke offerte?")
            st.caption("Naast de offertes staat een **should-cost baseline**: een onafhankelijke, complete "
                       "bottom-up raming per onderdeel — zo zie je hoever elke offerte boven het 'zou-moeten' zit.")
            _CATS = [
                ("Steiger & toegang", ("steiger", "pannenlift", "kraan", "hoogwerker")),
                ("Sloop & afvoer", ("sloop", "verwijder", "afvoer", "container", "opruim", "bouwafval")),
                ("Isolatie", ("isolatiefolie", "isolatiedeken", "isolatie", "sf40", "rd 3", "rc 3")),
                ("Tengels & panlatten", ("tengel", "panlat")),
                ("Dakpannen", ("betonpan", "keramische", "sneldek", "dakpan")),
                ("Nok & vorst", ("nokvorst", "nok ", "vorst", "ruiter", "ondervorst")),
                ("Kant-/gevelpannen", ("kantpan", "gevelpan")),
                ("Goot & regenwater", ("bakgoot", "gootbeugel", "goot", "regenpijp", "hwa")),
                ("Loodwerk", ("loodaansluiting", "bladlood", "kunstlood", "loodwerk")),
                ("Vogelwering", ("vogelwer", "dakvoet")),
                ("Bevestiging (panhaken/clips)", ("panhak", "vorstklem", "stormklem", "stormvast")),
                ("Dakdoorvoer", ("doorvoer", "rookgas")),
            ]

            def _cat_of(name):
                n = name.lower()
                for _c, _kws in _CATS:
                    if any(k in n for k in _kws):
                        return _c
                return "Overig"
            _SC = "Should-cost (baseline)"
            _byb = {b: [p for p in _prows if str(p.get("Bedrijf") or "").strip() == b] for b in _detbedr_real}
            with st.expander("📐 Should-cost band aanpassen (LCL/UCL per onderdeel)", expanded=False):
                _sc_seed = st.session_state.get("dak_shouldcost") or _dak_shouldcost_posten(dak_opp)
                _sc_in = pd.DataFrame([{"Onderdeel": p["Onderdeel"], "LCL": float(p.get("LCL", p["Prijs excl. btw"])),
                                        "UCL": float(p.get("UCL", p["Prijs excl. btw"])), "Btw %": int(p["Btw %"])}
                                       for p in _sc_seed])
                _sc_key = f"dak_sc_editor_{len(_sc_in)}_{'c' if st.session_state.get('dak_shouldcost') else 'a'}"
                _sc_ed = st.data_editor(_sc_in, num_rows="dynamic", use_container_width=True, key=_sc_key,
                                        column_config={"LCL": st.column_config.NumberColumn(format="€%.0f"),
                                                       "UCL": st.column_config.NumberColumn(format="€%.0f"),
                                                       "Btw %": st.column_config.SelectboxColumn(options=[21, 9]),
                                                       "Onderdeel": st.column_config.TextColumn(width="large")})
                _sc_rows = []
                for _r in _sc_ed.to_dict("records"):
                    if str(_r.get("Onderdeel") or "").strip():
                        _l, _u = float(_r.get("LCL") or 0), float(_r.get("UCL") or 0)
                        _sc_rows.append({"Bedrijf": _SC, "Onderdeel": str(_r["Onderdeel"]).strip(),
                                         "Prijs excl. btw": float(round((_l + _u) / 2)),
                                         "Btw %": int(float(_r.get("Btw %") or 21)), "LCL": _l, "UCL": _u})
                _cs1, _cs2 = st.columns(2)
                if _cs1.button("💾 Should-cost bewaren", key="dak_sc_save"):
                    st.session_state["dak_shouldcost"] = _sc_rows
                    try:
                        _persist()
                        st.success("Should-cost bewaard.")
                    except Exception as _e:  # noqa: BLE001
                        st.error(f"Opslaan mislukt: {_e}")
                if _cs2.button("🔄 Terug naar automatisch (huidig oppervlak)", key="dak_sc_reset"):
                    st.session_state["dak_shouldcost"] = []
                    try:
                        _persist()
                    except Exception:  # noqa: BLE001
                        pass
                    st.rerun()
                st.caption("LCL = ondergrens (scherp), UCL = bovengrens. Leeg/reset = automatische raming op het "
                           "huidige dakoppervlak. Bewaar om je eigen band vast te leggen.")
            _byb[_SC] = _sc_rows if _sc_rows else _dak_shouldcost_posten(dak_opp)
            _detbedr = _detbedr_real + [_SC]
            _assign = {b: {} for b in _detbedr}
            for b in _detbedr:
                for p in _byb[b]:
                    _assign[b].setdefault(_cat_of(str(p.get("Onderdeel") or "")), []).append(p)

            def _cover(hits):
                if not hits:
                    return "—"
                if all("stelpost" in str(p.get("Onderdeel") or "").lower() for p in hits) \
                        and sum(float(p.get("Prijs excl. btw") or 0) for p in hits) == 0:
                    return "stelpost"
                _pr = sum(float(p.get("Prijs excl. btw") or 0) for p in hits)
                return f"€{_pr:.0f}" if _pr > 0 else "incl."
            _vrows = []
            for _cat, _ in _CATS:
                _row = {"Scope": _cat}
                for b in _detbedr:
                    _row[b] = _cover(_assign[b].get(_cat, []))
                _vals = [_row[b] for b in _detbedr]
                _row["Let op"] = "⚠️ niet bij allen" if ("—" in _vals and any(v != "—" for v in _vals)) else ""
                _vrows.append(_row)
            _tot = {"Scope": "TOTAAL (excl. btw)"}
            for b in _detbedr:
                _tot[b] = f"€{round(sum(float(p.get('Prijs excl. btw') or 0) for p in _byb[b])):.0f}"
            _tot["Let op"] = ""
            _vrows.append(_tot)
            _cmpdf = pd.DataFrame(_vrows)
            st.markdown("**€ per scope-onderdeel en totaal (excl. btw)**")
            st.dataframe(_cmpdf, use_container_width=True, hide_index=True)
            st.caption("Per scope-onderdeel: €-bedrag indien apart geprijsd · *incl.* = inbegrepen in de "
                       "bundelprijs · *stelpost* = optie/nog niet vast · *—* = niet in deze offerte. ⚠️ = niet bij "
                       "elke offerte. Onderste rij = totaal per offerte; Westermeer bundelt de renovatie onder de "
                       "dakpannen-regel.")
            with st.expander("🔍 Detail per scope-onderdeel — qty · type · kosten per offerte"):
                for _cat, _ in _CATS:
                    if not any(_assign[b].get(_cat) for b in _detbedr):
                        continue
                    st.markdown(f"**{_cat}**")
                    for b in _detbedr:
                        _items = _assign[b].get(_cat, [])
                        if not _items:
                            st.markdown(f"- *{b}*: — niet geoffreerd")
                            continue
                        for _p in _items:
                            _pr = float(_p.get("Prijs excl. btw") or 0)
                            _nm = str(_p.get("Onderdeel") or "")
                            _pct = int(float(_p.get("Btw %") or 21))
                            if _pr > 0:
                                _ps = f"€{_pr:.0f} excl. ({_pct}% btw)"
                            elif "bundel" in _nm.lower():
                                _ps = "bundelprijs €15.000"
                            elif "stelpost" in _nm.lower():
                                _ps = "stelpost (optie)"
                            else:
                                _ps = "incl. in bundel"
                            st.markdown(f"- *{b}*: {_nm} — **{_ps}**")

            _off_by = {str(o.get("Bedrijf") or "").strip(): o for o in st.session_state.get("dakofferte", [])}
            _scx = sum(float(p["Prijs excl. btw"]) for p in _byb[_SC])
            _scb = sum(float(p["Prijs excl. btw"]) * p["Btw %"] / 100 for p in _byb[_SC])
            _sc_lcl_i = sum(float(p.get("LCL", 0)) * (1 + p["Btw %"] / 100) for p in _byb[_SC])
            _sc_ucl_i = sum(float(p.get("UCL", 0)) * (1 + p["Btw %"] / 100) for p in _byb[_SC])
            _off_by[_SC] = {"Bedrijf": _SC, "Excl. btw": round(_scx), "Incl. btw": round(_scx + _scb),
                            "Isolatie": "Rd ≥ 3,5 (norm)", "Garantie": "—"}
            st.info(f"📐 **Should-cost band (LCL–UCL):** €{_sc_lcl_i:.0f} – €{_sc_ucl_i:.0f} incl. btw "
                    f"(€{_sc_lcl_i / dak_opp:.0f} – €{_sc_ucl_i / dak_opp:.0f}/m²) · mean (midpunt) "
                    f"€{round(_scx + _scb):.0f}. LCL = efficiënt/scherp, UCL = bovengrens. Een offerte **boven de "
                    f"UCL** is duur; **binnen de band** is marktconform.")
            _hl = []
            for b in _detbedr:
                _o = _off_by.get(b, {})
                _ex, _in = float(_o.get("Excl. btw") or 0), float(_o.get("Incl. btw") or 0)
                _hl.append({"Offerte": b, "Regels": len(_byb.get(b, [])), "Excl. btw": round(_ex),
                            "Incl. btw": round(_in),
                            "€/m² incl.": round(_in / dak_opp) if dak_opp else 0,
                            "Effectief btw": f"{(_in - _ex) / _ex * 100:.0f}%" if _ex > 0 and _in > 0 else "—",
                            "Isolatie": str(_o.get("Isolatie") or "—"), "Garantie": str(_o.get("Garantie") or "—")})
            _hldf = pd.DataFrame(_hl)
            st.dataframe(_hldf, use_container_width=True, hide_index=True,
                         column_config={"Excl. btw": st.column_config.NumberColumn(format="€%.0f"),
                                        "Incl. btw": st.column_config.NumberColumn(format="€%.0f"),
                                        "€/m² incl.": st.column_config.NumberColumn(format="€%.0f")})
            _bullets = []
            _valid = [h for h in _hl if h["Incl. btw"] > 0]
            if len(_valid) >= 2:
                _cheap = min(_valid, key=lambda h: h["Incl. btw"])
                _exp = max(_valid, key=lambda h: h["Incl. btw"])
                _gap = _exp["Incl. btw"] - _cheap["Incl. btw"]
                _bullets.append(f"💶 **{_cheap['Offerte']}** is goedkoper — €{_gap:.0f} incl. minder dan "
                                f"**{_exp['Offerte']}** (€{_cheap['Incl. btw']:.0f} vs €{_exp['Incl. btw']:.0f}).")
            for b in _detbedr:
                _mist = [r["Scope"] for r in _vrows if r[b] == "—" and any(r[x] != "—" for x in _detbedr)]
                if _mist:
                    _bullets.append(f"⚠️ **{b}** mist t.o.v. de ander: " + ", ".join(_mist)
                                    + " — vraag aanvulling of reken de optie mee.")
            for b in _detbedr:
                if any(int(float(p.get("Btw %") or 21)) == 9 for p in _byb[b]):
                    _bullets.append(f"🧾 **{b}** rekent **9% btw** op de isolatie-arbeid (terecht; scheelt geld).")
                _sp = [p for p in _byb[b] if "stelpost" in str(p.get("Onderdeel") or "").lower()]
                if _sp:
                    _bullets.append(f"📌 **{b}** heeft {len(_sp)} **stelpost(en)** (optioneel — kan nog bijkomen).")
            _gar = {b: str(_off_by.get(b, {}).get("Garantie") or "") for b in _detbedr}
            if len({v for v in _gar.values() if v}) > 1:
                _bullets.append("🛡️ **Garantie verschilt**: "
                                + " · ".join(f"{b}: {_gar[b]}" for b in _detbedr if _gar[b]) + ".")
            # frame: in de kern dezelfde klus; wie geeft het meeste kosteninzicht?
            _granular = max(_detbedr, key=lambda b: sum(1 for p in _byb[b] if float(p.get("Prijs excl. btw") or 0) > 0))
            _bullets.insert(0, f"🔁 De offertes dekken in de kern **dezelfde dakrenovatie** (zelfde dak/m², isolatie + "
                            f"nieuwe pannen); ze gebruiken alleen andere benamingen. **{_granular}** geeft het meeste "
                            "**kosteninzicht** (meer losse, geprijsde posten); de ander bundelt onder één prijs.")
            if _bullets:
                st.markdown("\n".join("- " + x for x in _bullets))
            # ISDE-subsidie op dakisolatie (Rd ≥ 3,5 m²K/W, ≥ 20 m²) — geldt voor beide offertes
            _isde1 = min(round(16.25 * dak_opp), 975) if dak_opp else 0
            _isde2 = min(round(32.50 * dak_opp), 1950) if dak_opp else 0
            st.info(f"🏷️ **ISDE-subsidie op de dakisolatie** — isolatie met **Rd ≥ 3,5 m²K/W** (en ≥ 20 m²) komt in "
                    f"aanmerking. Beide voldoen ruim: Westermeer **Rd 3,8**, Albers **Rc 3,89–4,11** (SF40BB, "
                    f"meldcode KA28563). Indicatie voor {dak_opp:.0f} m²: **± €{_isde1:.0f} terug** bij één "
                    f"isolatiemaatregel (≈ €16,25/m², max €975), of **tot €{_isde2:.0f}** bij twee maatregelen "
                    f"(≈ €32,50/m², max €1.950). Dit geldt voor **béide** offertes → het verlaagt je **netto** kosten, "
                    "maar verandert de onderlinge keuze nauwelijks. Laat de aannemer de ISDE-aanvraag ondersteunen.")
            st.caption("Vergelijk op **gelijke scope**: een lagere prijs met ontbrekende posten (bv. vogelwering "
                       "of goot/regenpijpen) is niet per se goedkoper. Let ook op **garantietermijn** en of "
                       "stelposten realistisch zijn.")
            # ---- Eerlijke vergelijking: normaliseer elke offerte naar dezelfde (firm) scope ----
            _cat_eur = {b: {c: sum(float(p.get("Prijs excl. btw") or 0) for p in items
                                   if "bundel" not in str(p.get("Onderdeel") or "").lower())
                            for c, items in _assign[b].items()} for b in _detbedr}
            _allcats = {c for b in _detbedr for c in _assign[b]}
            _norm = []
            for b in _detbedr:
                _o = _off_by.get(b, {})
                _qi = float(_o.get("Incl. btw") or 0)
                _add, _added = 0.0, []
                for _cat in sorted(_allcats):
                    if _cat in _assign[b]:
                        continue  # offerte dekt deze scope al
                    _peer = [_cat_eur[p].get(_cat, 0) for p in _detbedr if p != b and _cat_eur[p].get(_cat, 0) > 0]
                    if _peer:
                        _est = sum(_peer) / len(_peer)
                        _add += _est
                        _added.append(f"{_cat} (~€{_est:.0f})")
                _ni = _qi + round(_add * 1.21)
                _norm.append({"Offerte": b, "Zoals geoffreerd": round(_qi), "+ ontbrekende scope": round(_add * 1.21),
                              "Gelijke scope": round(_ni), "− ISDE": _isde1, "Netto": round(_ni - _isde1),
                              "Toegevoegd": ", ".join(_added) or "—"})
            _normdf = pd.DataFrame(_norm)
            st.markdown("**⚖️ Eerlijke vergelijking — zelfde scope, incl. btw, ná ISDE**")
            st.dataframe(_normdf, use_container_width=True, hide_index=True,
                         column_config={_c: st.column_config.NumberColumn(format="€%.0f") for _c in
                                        ["Zoals geoffreerd", "+ ontbrekende scope", "Gelijke scope", "− ISDE", "Netto"]})
            _scnet = next((n["Netto"] for n in _norm if n["Offerte"] == _SC), 0)
            _vld = [n for n in _norm if n["Gelijke scope"] > 0 and n["Offerte"] != _SC]
            if len(_vld) >= 2:
                _wc = min(_vld, key=lambda n: n["Netto"])
                _we = max(_vld, key=lambda n: n["Netto"])
                st.success(f"➡️ Bij **gelijke scope** (ontbrekende posten bijgeschat) en ná ISDE is **{_wc['Offerte']}** "
                           f"het voordeligst: **€{_wc['Netto']:.0f}** netto vs €{_we['Netto']:.0f} — verschil "
                           f"**€{_we['Netto'] - _wc['Netto']:.0f}**.")
            if _vld:
                _parts = []
                for n in _vld:
                    _gs = n["Gelijke scope"]  # incl. btw, gelijke scope
                    if _gs <= _sc_ucl_i:
                        _v = "🟢 binnen de band" if _gs >= _sc_lcl_i else "🔵 onder LCL (scherp)"
                    else:
                        _ovp = (_gs - _sc_ucl_i) / _sc_ucl_i * 100 if _sc_ucl_i else 0
                        _v = f"🔴 €{_gs - _sc_ucl_i:.0f} boven UCL (+{_ovp:.0f}%)"
                    _parts.append(f"**{n['Offerte']}** {_v}")
                st.markdown("📐 **Toets aan de should-cost band** (gelijke scope, incl. btw): " + " · ".join(_parts) + ".")
            st.caption("De **should-cost (baseline)** is een onafhankelijke complete raming; ontbrekende scope bij een "
                       "offerte wordt bijgeschat met de firm-prijs van de andere offertes/baseline (stelposten tellen "
                       "niet mee). Zo vergelijk je op een eerlijke, gelijke basis.")

            _posten_df = pd.DataFrame([{"Bedrijf": p.get("Bedrijf", ""), "Onderdeel": p.get("Onderdeel", ""),
                                        "Prijs excl. btw": float(p.get("Prijs excl. btw") or 0),
                                        "Btw %": int(float(p.get("Btw %") or 21))}
                                       for b in _detbedr for p in _byb[b]])
            _xlsx = {"Kerncijfers": _hldf, "Eerlijke vergelijking": _normdf, "Scope-vergelijking": _cmpdf,
                     "Posten": _posten_df,
                     "ISDE & advies": pd.DataFrame({"Advies / ISDE": [b.replace("**", "") for b in _bullets]
                                                    + [f"ISDE-subsidie: ± €{_isde1:.0f} (1 maatregel) tot "
                                                       f"€{_isde2:.0f} (2 maatregelen) voor {dak_opp:.0f} m²"]})}
            _cda, _cdb = st.columns(2)
            _cda.download_button("⬇️ Vergelijking — Excel", m.df_to_excel_bytes(_xlsx),
                                 file_name="dakrenovatie_vergelijking.xlsx",
                                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 key="dak_vergelijk_xlsx", use_container_width=True)
            try:
                _pdfb = _dak_vergelijking_pdf_bytes(_hl, _cmpdf, _posten_df, dak_opp, _isde1, _isde2, _bullets,
                                                    DAK_MARKT_LO, DAK_MARKT_HI, _normdf,
                                                    sc_lo=_sc_lcl_i / dak_opp if dak_opp else None,
                                                    sc_hi=_sc_ucl_i / dak_opp if dak_opp else None,
                                                    sc_mid=(_scx + _scb) / dak_opp if dak_opp else None)
                _cdb.download_button("🖨️ Vergelijking — PDF (met grafieken)", _pdfb,
                                     file_name="dakrenovatie_vergelijking.pdf", mime="application/pdf",
                                     key="dak_vergelijk_pdf", use_container_width=True)
            except Exception as _exc:  # noqa: BLE001
                _cdb.caption(f"PDF-rapport tijdelijk niet beschikbaar: {_exc}")

            st.markdown("#### 🏆 Stap 6 — Kies je aannemer")
            _cur = next((b for b in _detbedr_real if str(_off_by.get(b, {}).get("Status") or "") == "Gekozen"), "—")
            _opts = ["—"] + _detbedr_real
            _kz = st.selectbox("Welke offerte kies je?", _opts,
                               index=_opts.index(_cur) if _cur in _opts else 0, key="dak_kies")
            if _kz != "—":
                for _o in st.session_state["dakofferte"]:
                    _b = str(_o.get("Bedrijf") or "").strip()
                    if _b == _kz:
                        _o["Status"] = "Gekozen"
                    elif str(_o.get("Status") or "") == "Gekozen":
                        _o["Status"] = "Vergeleken"
                _ch = next((n for n in _norm if n["Offerte"] == _kz), None)
                if _ch:
                    st.success(f"✅ Gekozen: **{_kz}** — netto bij gelijke scope, ná ISDE: **€{_ch['Netto']:.0f}** "
                               f"(zoals geoffreerd €{_ch['Zoals geoffreerd']:.0f}).")
                if st.button("💾 Keuze bewaren in Gist", key="dak_kies_save"):
                    try:
                        _persist()
                        st.success("Keuze opgeslagen.")
                    except Exception as _exc2:  # noqa: BLE001
                        st.error(f"Opslaan mislukt: {_exc2}")

        st.markdown("#### 📋 Advies — is dit marktconform?")
        st.markdown(
            "- De offerte van Westermeer (~€250/m² **excl.** btw, ≈ €336/m² **incl.**) zit **fors boven** "
            "de markt: een hellend pannendak vervangen *mét isolatie* kost in NL ~€110–€160/m² excl. btw "
            "(≈ €180–€260/m² incl.).\n"
            "- **Nuance:** kleine klus (60 m²) → hogere prijs/m²; keramische pannen + Rd 3,8 zitten aan de "
            "betere kant — maar zelfs dan aan de hoge kant.\n"
            "- **Vraag na / onderhandel:** is de **steiger** inbegrepen? Geldt het **9%-btw-tarief op de "
            "isolatie-arbeid** (woning > 2 jaar)? Vraag een **uitsplitsing arbeid/materiaal** en de "
            "**garantietermijn** schriftelijk.\n"
            "- **Afvoer** zit inbegrepen (1× container **3,5 m³** naar erkend recyclingbedrijf) — passend "
            "voor 60 m²; leg wel vast dat een **extra container geen meerwerk** is.\n"
            "- **Doe:** vraag **minstens 2 extra offertes** met dezelfde scope en vergelijk hierboven op €/m².")

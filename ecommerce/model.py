"""Zuivere reken-logica voor de e-commerce planner — geen Streamlit, testbaar.

Stuk-economie (per product), een 12-maands cashprognose en Excel-export met
meerdere tabbladen. Alle bedragen in euro's. De standaardinstellingen gaan uit van
verkopen via Bol.nl (B2C, consumentprijzen incl. 21% btw). De getallen in
STANDAARD_PRODUCTEN / MARKT zijn onderbouwde schattingen om te valideren — geen
beloftes. De Regels-sectie is algemene informatie, geen juridisch/fiscaal advies.
"""

from __future__ import annotations

import io

import pandas as pd

BTW = 0.21  # NL standaardtarief

# Bol.com-achtige standaarden (allemaal aanpasbaar in de UI).
# Commissie varieert ~8-17% per categorie; per verkocht artikel geldt een vaste fee.
BOL = {
    "commissie_pct": 0.12,    # % van de consumentprijs (incl. btw)
    "vaste_fee": 0.99,        # € per verkocht artikel
    "betaal_pct": 0.02,       # betaal-/transactiekosten
    "verzending": 3.50,       # verzending naar de klant (LVB/PostNL)
    "retour_pct": 0.07,       # aandeel retouren (elektronica ~5-10%)
    "advertentie": 3.00,      # advertentiekosten per verkoop (CAC)
    "verwijderingsbijdrage": 0.10,  # WEEE + batterijbijdrage per stuk (elektronica)
}

# Onderbouwde, aanpasbare startportfolio (home-energy / domotica beachhead).
# Inkoop = geland inkoopbedrag excl. btw (inkoop + vracht + eventueel invoerrecht), per stuk.
# Prijs = consumentprijs incl. btw op Bol.nl.
STANDAARD_PRODUCTEN = [
    {"Product": "Energie-slimme stekker (1 stuk)", "Inkoop": 5.5, "Prijs": 19.95},
    {"Product": "Energie-slimme stekker (2-pack)", "Inkoop": 9.5, "Prijs": 34.95},
    {"Product": "Zigbee starterskit (hub + 3 stekkers + gids)", "Inkoop": 30.0, "Prijs": 89.0},
    {"Product": "Waterlek-stopsensor", "Inkoop": 15.0, "Prijs": 44.95},
    {"Product": "Deur-/raamsensor (3-pack)", "Inkoop": 8.0, "Prijs": 27.95},
    {"Product": "Radiator-/tochtbespaarset", "Inkoop": 7.0, "Prijs": 24.95},
]

MARKT = {
    "stats": [
        ("NL smart-home markt (2023)", "$1,25 mld", ""),
        ("NL smart-home markt (2030)", "$5,10 mld", "22,3% groei/jr"),
        ("Europa smart homes (2024)", "€25,3 mld", ""),
        ("Europa smart homes (2033)", "€44,0 mld", "6,3% groei/jr"),
        ("Groei Zigbee-apparaten", "~9,2%/jr", "tot 2035"),
        ("NL thuisbatterij-installaties (2025)", "~88.000", "≈4× t.o.v. 2024"),
    ],
    "segmenten": {
        "Beveiliging & toegang (camera's, sloten, sensoren)": 31.65,
        "Energie & slimme apparaten": 22.0,
        "Verlichting": 18.0,
        "Comfort/overig": 28.35,
    },
    "vermijden": [
        "Thermostaten — Tado, Nest, Honeywell domineren",
        "Energie/P1-uitlezers — HomeWizard (NL) domineert",
        "Slimme verlichting — Philips Hue / Signify (NL)",
        "Hubs & camera's — wereldspelers, dunne marges",
    ],
    "beachhead": [
        "De doe-het-zelf energiebespaarder / Home Assistant-groep — koopt veel goedkope apparaten, herhaald",
        "Open gat: vertrouwen & kwaliteitscontrole ('stekkers die je huis niet in brand zetten')",
        "Ze volgen makers die testen & bewijzen — dat kun jij zijn",
    ],
    "moat": [
        "Verkoop vertrouwen + bewijs, geen commodity-apparaat",
        "Publiceer gemeten '€X/jaar bespaard'-content (jouw data + energie-edge)",
        "Lever een gratis tool (besparingscalculator) die naar je shop leidt",
        "Samengestelde, gecertificeerde bundels > losse stekkers (hogere orderwaarde, jouw gids voegt waarde toe)",
    ],
    "risicos": [
        "Netspanning-elektronica = CE/RED-certificering + aansprakelijkheid — verkoop gecertificeerde white-label, bouw geen eigen radio's",
        "Marges op commodity-apparaten zijn dun — winst zit in bundels, merk, content",
        "Begin met batterij-/laagspanningssensoren + accessoires om aansprakelijkheid te beperken",
    ],
    "bronnen": [
        ("Statista — NL Smart Home", "https://www.statista.com/outlook/279/144/smart-home/netherlands"),
        ("NextMSC — NL Smart Home naar $5,1 mld", "https://www.nextmsc.com/news/netherlands-smart-home-market"),
        ("MarketDataForecast — Europa Smart Homes", "https://www.marketdataforecast.com/market-reports/europe-smart-homes-market"),
        ("Home Assistant community — veilige stekkers",
         "https://community.home-assistant.io/t/smart-plugs-in-the-netherlands-that-wont-burn-down-your-house/372528"),
    ],
}

# Nederlandse regels & regelgeving voor een webshop. Algemene info — geen advies.
REGELS = {
    "🏢 Inschrijving & belasting": [
        "Schrijf je in bij de **KvK** (eenmanszaak, ~€80 eenmalig) — je krijgt een btw-id.",
        "Standaard **btw 21%**; je rekent btw aan klanten en draagt die af.",
        "**KOR (kleineondernemersregeling):** omzet < €20.000/jaar → vrijgesteld van btw (optioneel; dan geen btw-aftrek).",
        "**Inkomstenbelasting** via aangifte; mogelijk zelfstandigen- en startersaftrek bij genoeg uren.",
        "Zakelijke rekening + nette boekhouding (bewaarplicht 7 jaar).",
    ],
    "🛒 Consumentenrecht (verplicht)": [
        "**Wettelijke bedenktijd: 14 dagen** herroepingsrecht bij online verkoop — klant mag zonder reden retourneren.",
        "**Wettelijke garantie (conformiteit):** product moet doen wat de klant redelijkerwijs mag verwachten — vaak 2+ jaar.",
        "Toon vooraf duidelijk: prijs **incl. btw**, levertijd, en je **bedrijfsgegevens (KvK- + btw-nummer)**.",
        "**Algemene voorwaarden** en een helder **retourbeleid** zijn verplicht.",
    ],
    "⚡ Product & milieu": [
        "**CE-markering** verplicht; draadloze apparaten (Zigbee/wifi) vallen ook onder de **RED**-richtlijn.",
        "**AEEA/WEEE:** meld elektronica aan bij het Nationaal (W)EEE Register → **verwijderingsbijdrage** per stuk.",
        "**Batterijen:** aanmelden bij Stibat → batterijbeheerbijdrage.",
        "**Verpakkingen:** Afvalfonds geldt pas boven 50.000 kg/jaar — als starter meestal vrijgesteld.",
    ],
    "🔒 Online & privacy": [
        "**AVG/GDPR:** privacyverklaring en zorgvuldige omgang met klantgegevens; cookiemelding.",
        "Optioneel keurmerk **Thuiswinkel Waarborg** wekt vertrouwen bij Nederlandse kopers.",
    ],
    "📦 Import (buiten de EU)": [
        "Vraag een **EORI-nummer** aan voor invoer.",
        "Bij invoer: **21% invoer-btw** (terugvorderbaar) + eventueel **invoerrechten** (afhankelijk van productcode).",
        "Reken vracht + rechten mee in je **geland inkoopbedrag**.",
    ],
}

REGELS_BRONNEN = [
    ("KvK — starten", "https://www.kvk.nl/starten/"),
    ("Belastingdienst — KOR", "https://www.belastingdienst.nl/wps/wcm/connect/nl/btw/content/hulpmiddel-kleineondernemersregeling"),
    ("ACM ConsuWijzer — online verkopen", "https://www.consuwijzer.nl/"),
    ("Nationaal (W)EEE Register", "https://www.nationaalweeeregister.nl/"),
]


def stuk_economie(prijs_incl, inkoop_geland, commissie_pct=BOL["commissie_pct"],
                  vaste_fee=BOL["vaste_fee"], betaal_pct=BOL["betaal_pct"],
                  verzending=BOL["verzending"], retour_pct=BOL["retour_pct"],
                  advertentie=BOL["advertentie"], verwijderingsbijdrage=BOL["verwijderingsbijdrage"],
                  btw=BTW) -> dict:
    """Stuk-economie voor één product op een Bol-achtig platform.

    Geeft de volledige kostenopbouw plus nettowinst, marge % (op omzet excl. btw)
    en opslag (prijs / inkoop). Retouren gaan ervan uit dat de verzending verloren is
    en de helft van de geretourneerde goederen wordt afgeschreven.
    """
    prijs_incl = float(prijs_incl or 0)
    inkoop_geland = float(inkoop_geland or 0)
    omzet_excl = prijs_incl / (1 + btw)
    btw_bedrag = prijs_incl - omzet_excl
    commissie = prijs_incl * commissie_pct
    betaal = prijs_incl * betaal_pct
    retour_kosten = retour_pct * (verzending + 0.5 * inkoop_geland)
    totale_kosten = (inkoop_geland + commissie + vaste_fee + betaal + verzending
                     + retour_kosten + advertentie + verwijderingsbijdrage)
    winst = omzet_excl - totale_kosten
    return {
        "prijs_incl": prijs_incl,
        "btw": btw_bedrag,
        "omzet_excl": omzet_excl,
        "inkoop": inkoop_geland,
        "commissie": commissie,
        "vaste_fee": vaste_fee,
        "betaal": betaal,
        "verzending": verzending,
        "retour_kosten": retour_kosten,
        "advertentie": advertentie,
        "verwijderingsbijdrage": verwijderingsbijdrage,
        "totale_kosten": totale_kosten,
        "winst": winst,
        "marge_pct": (winst / omzet_excl) if omzet_excl else 0.0,
        "opslag_x": (prijs_incl / inkoop_geland) if inkoop_geland else 0.0,
    }


def portfolio_tabel(producten, **fees) -> pd.DataFrame:
    """Bereken de stuk-economie voor een lijst {Product, Inkoop, Prijs}-dicts."""
    rijen = []
    for p in producten:
        e = stuk_economie(p["Prijs"], p["Inkoop"], **fees)
        rijen.append({
            "Product": p["Product"],
            "Inkoop (geland)": round(e["inkoop"], 2),
            "Prijs (incl. btw)": round(e["prijs_incl"], 2),
            "Winst/stuk": round(e["winst"], 2),
            "Marge %": round(e["marge_pct"] * 100, 1),
            "Opslag": round(e["opslag_x"], 2),
        })
    df = pd.DataFrame(rijen)
    return df.sort_values("Winst/stuk", ascending=False).reset_index(drop=True)


def prognose(stuks_m1, groei_pct, maanden, vaste_kosten_mnd, startinvestering,
             winst_per_stuk, omzet_excl_per_stuk) -> tuple[pd.DataFrame, int | None]:
    """Eenvoudige maand-op-maand cashprognose. Geeft (dataframe, break-even-maand)."""
    rijen, cumulatief, be_maand = [], -abs(startinvestering), None
    stuks = float(stuks_m1)
    for m in range(1, maanden + 1):
        s = round(stuks)
        omzet = s * omzet_excl_per_stuk
        bruto = s * winst_per_stuk          # contributie (na variabele kosten)
        netto = bruto - vaste_kosten_mnd    # na vaste maandkosten
        cumulatief += netto
        if be_maand is None and cumulatief >= 0:
            be_maand = m
        rijen.append({
            "Maand": m,
            "Stuks": s,
            "Omzet (excl. btw)": round(omzet, 0),
            "Brutowinst": round(bruto, 0),
            "Vaste kosten": round(vaste_kosten_mnd, 0),
            "Netto/maand": round(netto, 0),
            "Cumulatieve cash": round(cumulatief, 0),
        })
        stuks *= (1 + groei_pct)
    return pd.DataFrame(rijen), be_maand


def df_to_excel_bytes(sheets: dict) -> bytes:
    """Schrijf {tabblad: DataFrame} naar één .xlsx en geef de bytes terug."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        for naam, df in sheets.items():
            df.to_excel(xl, sheet_name=naam[:31], index=False)
    return buf.getvalue()

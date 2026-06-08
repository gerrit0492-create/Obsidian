"""Zuivere reken-logica voor de e-commerce planner — geen Streamlit, testbaar.

Niche: plug-in (stekker)batterijen + installatie/advies in Nederland. Stuk-economie
per product of dienst, een 12-maands cashprognose en Excel-export. Alle bedragen in
euro's. Producten gaan uit van een marktplaats (Bol.nl, prijzen incl. 21% btw);
diensten (installatie/advies) kennen geen marktplaats-fees. De getallen in
STANDAARD_PRODUCTEN / MARKT zijn onderbouwde schattingen om te valideren — geen
beloftes. De Regels-sectie is algemene info, geen juridisch/fiscaal advies.
"""

from __future__ import annotations

import io

import pandas as pd

BTW = 0.21  # NL standaardtarief

# Bol.com-achtige standaarden (allemaal aanpasbaar in de UI).
BOL = {
    "commissie_pct": 0.12,    # % van de consumentprijs (incl. btw)
    "vaste_fee": 0.99,        # € per verkocht artikel
    "betaal_pct": 0.02,       # betaal-/transactiekosten
    "verzending": 3.50,       # verzending naar de klant
    "retour_pct": 0.07,       # aandeel retouren
    "advertentie": 3.00,      # advertentie-/acquisitiekosten per verkoop (CAC)
    "verwijderingsbijdrage": 0.10,  # WEEE + batterijbijdrage per stuk
}

# Startportfolio voor de plug-in batterij + installatie-niche (laag instapbudget).
# Inkoop = geland inkoopbedrag excl. btw; Prijs = consumentprijs incl. btw.
# Dienst = True → installatie/advies: geen marktplaats-fees, verzending of WEEE.
STANDAARD_PRODUCTEN = [
    {"Product": "Stekkerbatterij 2,56 kWh (reseller)", "Inkoop": 850.0, "Prijs": 1199.0, "Dienst": False},
    {"Product": "Montage-/wandsteun voor batterij", "Inkoop": 9.0, "Prijs": 34.95, "Dienst": False},
    {"Product": "Slimme energiemeter (P1-dongle)", "Inkoop": 12.0, "Prijs": 39.95, "Dienst": False},
    {"Product": "Aansluitset + kabels", "Inkoop": 6.0, "Prijs": 24.95, "Dienst": False},
    {"Product": "Installatie + aansluiting (per klus)", "Inkoop": 25.0, "Prijs": 295.0, "Dienst": True},
    {"Product": "Energie-advies op afstand (per sessie)", "Inkoop": 0.0, "Prijs": 75.0, "Dienst": True},
]

MARKT = {
    "stats": [
        ("NL thuisbatterij-installaties (2025)", "~88.000", "≈4× t.o.v. 2024"),
        ("Installatietempo eind 2025", "~5.000/mnd", "groeiend"),
        ("Saldering stopt", "1 jan 2027", "drijft de vraag"),
        ("Stekkerbatterij prijs", "€500–€1.900", "plug-and-play"),
        ("Installatie (vaste batterij)", "€500–€1.500", "marge in arbeid"),
        ("Max teruglevering plug-in", "800 W", "NVWA-norm"),
    ],
    "segmenten": {
        "Batterij (reseller, dunne marge)": 15.0,
        "Accessoires (montage, meters, kabels)": 30.0,
        "Installatie + advies (dienst)": 45.0,
        "Overig": 10.0,
    },
    "vermijden": [
        "Batterijen op voorraad leggen en op Bol verkopen — commissie + prijsvergelijking eet je marge",
        "Concurreren op prijs met de merken (Marstek, Zendure, HomeWizard, Anker)",
        "Vaste batterijen plaatsen zonder elektro-competentie en aansprakelijkheidsdekking",
    ],
    "beachhead": [
        "Zonnepaneel-bezitters die ná de saldering hun overschot willen opslaan — zelfverbruik",
        "Plug-and-play stekkerbatterijen: laag instapbudget, geen vaste installatie nodig",
        "Jij als betrouwbare, technische adviseur/installateur in de regio — geen doos-schuiver",
    ],
    "moat": [
        "Verkoop vertrouwen + advies, niet de laagste prijs (batterijen worden kapot vergeleken via StekkerDeal)",
        "Jouw engineering-geloofwaardigheid + gemeten '€X/jaar'-content",
        "Lokale installatie + service: moeilijk te kopiëren door online doos-schuivers",
        "Marge zit in accessoires + installatie/advies, niet in de batterij zelf",
    ],
    "risicos": [
        "Plug-in: max 800 W teruglevering en verplichte aanmelding bij de netbeheerder (Energieleveren.nl)",
        "Officieel geen teruglevering via een stopcontact — plug-in is vooral voor zelfverbruik",
        "Installatie vraagt elektrotechnische competentie en een veilig, juist gezekerde groep",
        "Batterij-aansprakelijkheid: lever alleen gecertificeerde merken, geen onbekende import",
    ],
    "bronnen": [
        ("Solarmagazine — markt explosief",
         "https://solarmagazine.nl/nieuws-zonne-energie/i42510/dne-research-markt-voor-thuisbatterijen-groeit-explosief-door-einde-salderingsregeling"),
        ("Totaaladvies — stekkerbatterij", "https://totaaladvies.nl/thuisbatterijen/stekkerbatterij"),
        ("Netbeheer NL — aanmelden",
         "https://www.netbeheernederland.nl/artikelen/nieuws/meld-thuisbatterijen-aan-op-energieleverennl"),
        ("Zonneplan — wet & regelgeving stekkerbatterij",
         "https://www.zonneplan.nl/thuisbatterij/thuisbatterij-met-stekker/wet-en-regelgeving"),
    ],
}

# Nederlandse regels & regelgeving voor de webshop/dienst. Algemene info — geen advies.
REGELS = {
    "🏢 Inschrijving & belasting": [
        "Schrijf je in bij de **KvK** (eenmanszaak, ~€80 eenmalig) — je krijgt een btw-id.",
        "Standaard **btw 21%**; je rekent btw aan klanten en draagt die af.",
        "**KOR:** omzet < €20.000/jaar → vrijgesteld van btw (optioneel; dan geen btw-aftrek).",
        "**Inkomstenbelasting** via aangifte; mogelijk zelfstandigen- en startersaftrek.",
        "Zakelijke rekening + nette boekhouding (bewaarplicht 7 jaar).",
    ],
    "🔋 Thuisbatterij / stekkerbatterij": [
        "**Aanmeldplicht:** meld elke thuisbatterij (ook plug-in) bij de netbeheerder via **Energieleveren.nl**.",
        "**Plug-in max 800 W** teruglevering naar de groep (NVWA-norm); officieel **geen teruglevering via een stopcontact** — plug-in is vooral **zelfverbruik**.",
        "**Veilige aansluiting:** een vaste batterij hoort op een juist gezekerde groep door een bekwame installateur.",
        "**Gecertificeerde cellen:** verkoop merken met **CE + IEC 62619 + UN38.3**; geen onbekende import (brand-/aansprakelijkheidsrisico).",
        "**EU-batterijverordening 2023/1542:** batterijpaspoort (QR) vanaf 2027 + WEEE/inzamelplicht.",
    ],
    "🛒 Consumentenrecht (verplicht)": [
        "**14 dagen bedenktijd** (herroepingsrecht) bij online verkoop — let op: voor diensten/installatie gelden aparte regels.",
        "**Wettelijke garantie (conformiteit):** product/dienst moet doen wat de klant mag verwachten.",
        "Toon vooraf: prijs **incl. btw**, levertijd, en je **bedrijfsgegevens (KvK- + btw-nummer)**.",
        "**Algemene voorwaarden** en een helder retour-/annuleringsbeleid zijn verplicht.",
    ],
    "🔒 Online, privacy & import": [
        "**AVG/GDPR:** privacyverklaring en zorgvuldige omgang met klantgegevens.",
        "Optioneel keurmerk **Thuiswinkel Waarborg** wekt vertrouwen.",
        "**Import (buiten EU):** EORI-nummer, 21% invoer-btw (terugvorderbaar) + eventueel invoerrechten — reken mee in je inkoopprijs.",
    ],
}

REGELS_BRONNEN = [
    ("KvK — starten", "https://www.kvk.nl/starten/"),
    ("Belastingdienst — KOR", "https://www.belastingdienst.nl/wps/wcm/connect/nl/btw/content/hulpmiddel-kleineondernemersregeling"),
    ("Energieleveren.nl — aanmelden batterij", "https://www.energieleveren.nl/"),
    ("Zonneplan — regels stekkerbatterij", "https://www.zonneplan.nl/thuisbatterij/thuisbatterij-met-stekker/wet-en-regelgeving"),
]


def stuk_economie(prijs_incl, inkoop_geland, commissie_pct=BOL["commissie_pct"],
                  vaste_fee=BOL["vaste_fee"], betaal_pct=BOL["betaal_pct"],
                  verzending=BOL["verzending"], retour_pct=BOL["retour_pct"],
                  advertentie=BOL["advertentie"], verwijderingsbijdrage=BOL["verwijderingsbijdrage"],
                  dienst=False, btw=BTW) -> dict:
    """Stuk-economie voor één product (marktplaats) of dienst (geen marktplaats-fees).

    Diensten (installatie/advies) hebben geen commissie, vaste fee, verzending,
    retouren of verwijderingsbijdrage — alleen inkoop (materiaal/reiskosten) en CAC.
    """
    prijs_incl = float(prijs_incl or 0)
    inkoop_geland = float(inkoop_geland or 0)
    omzet_excl = prijs_incl / (1 + btw)
    if dienst:
        commissie = vaste = betaal = verz = retour = weee = 0.0
    else:
        commissie = prijs_incl * commissie_pct
        vaste = vaste_fee
        betaal = prijs_incl * betaal_pct
        verz = verzending
        retour = retour_pct * (verzending + 0.5 * inkoop_geland)
        weee = verwijderingsbijdrage
    totale_kosten = inkoop_geland + commissie + vaste + betaal + verz + retour + advertentie + weee
    winst = omzet_excl - totale_kosten
    return {
        "prijs_incl": prijs_incl,
        "btw": prijs_incl - omzet_excl,
        "omzet_excl": omzet_excl,
        "inkoop": inkoop_geland,
        "commissie": commissie,
        "vaste_fee": vaste,
        "betaal": betaal,
        "verzending": verz,
        "retour_kosten": retour,
        "advertentie": advertentie,
        "verwijderingsbijdrage": weee,
        "totale_kosten": totale_kosten,
        "winst": winst,
        "marge_pct": (winst / omzet_excl) if omzet_excl else 0.0,
        "opslag_x": (prijs_incl / inkoop_geland) if inkoop_geland else 0.0,
        "soort": "Dienst" if dienst else "Product",
    }


def portfolio_tabel(producten, **fees) -> pd.DataFrame:
    """Bereken de stuk-economie voor een lijst {Product, Inkoop, Prijs, Dienst}-dicts."""
    rijen = []
    for p in producten:
        d = bool(p.get("Dienst", False))
        e = stuk_economie(p["Prijs"], p["Inkoop"], dienst=d, **fees)
        rijen.append({
            "Product": p["Product"],
            "Soort": e["soort"],
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
        bruto = s * winst_per_stuk
        netto = bruto - vaste_kosten_mnd
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

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
    "🇨🇳 Inkoop uit China — veilig & gecertificeerd": [
        "Eis altijd **CE volgens IEC 62619** (energieopslag) / **IEC 62133** (cellen) + **UN38.3** (transport).",
        "Let op: **CE = veiligheid, niet kwaliteit** — een CE-sticker zegt niets over levensduur of cel-kwaliteit.",
        "Vraag de **Declaration of Conformity + testrapporten** op en verifieer bij een notified body (bv. DEKRA Arnhem) — zelf-verklaarde of valse CE komt voor.",
        "Koop bij **gevestigde merken/cellen** (CATL, EVE, BYD, Pylontech, Dyness, Growatt, Deye) — geen onbekende no-name import.",
        "Als **importeur ben jij de 'producent'** in de EU: jij draagt de aansprakelijkheid, WEEE/batterij-registratie en het batterijpaspoort.",
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
    "🧰 Diensten & ZZP (advies/installatie)": [
        "**ZZP/DBA:** werk met een modelovereenkomst (Belastingdienst) om schijnzelfstandigheid te voorkomen — let op de strengere DBA-handhaving sinds 2025.",
        "**Verzekering:** beroepsaansprakelijkheid (advies) + bedrijfsaansprakelijkheid (AVB) voor installatiewerk.",
        "**Installatie:** werk volgens **NEN 1010/3140**; streef naar InstallQ-erkenning of partner met een erkende elektricien.",
        "**Energielabel/advies:** een officieel energielabel vereist **EP-W/EP-U (NTA 8800)** + jaarlijkse bijscholing.",
        "**Warmtepomp/koeltechniek:** voor werk aan koudemiddelen geldt een **F-gassen-certificaat**.",
        "**Diensten:** herroepingsrecht werkt anders dan bij producten — leg schriftelijk vast als de klant wil dat je vóór de bedenktijd start.",
    ],
}

REGELS_BRONNEN = [
    ("KvK — starten", "https://www.kvk.nl/starten/"),
    ("Belastingdienst — KOR", "https://www.belastingdienst.nl/wps/wcm/connect/nl/btw/content/hulpmiddel-kleineondernemersregeling"),
    ("Energieleveren.nl — aanmelden batterij", "https://www.energieleveren.nl/"),
    ("Zonneplan — regels stekkerbatterij", "https://www.zonneplan.nl/thuisbatterij/thuisbatterij-met-stekker/wet-en-regelgeving"),
    ("Intertek — IEC 62133 batterijveiligheid", "https://www.intertek.com/batteries/iec-62133/"),
    ("Thuisbatterij NL — Chinese batterijen", "https://thuisbatterijnederland.nl/chinese-thuisbatterijen/"),
]

# Gefaseerde installateur-/advies-route — van laag budget naar gecertificeerd.
INSTALLATEUR_ROUTE = {
    "fases": [
        {"fase": "Fase 1 — Adviseur + plug-in (geen certificering nodig)", "punten": [
            "Elektricien is geen beschermd beroep — voor plug-and-play stekkerbatterijen mag je adviseren en opzetten zónder erkenning.",
            "Bied: energie-/besparingsadvies, productkeuze, levering (reseller) en setup + aanmelding bij Energieleveren.nl.",
            "Regel: KvK-inschrijving + bedrijfsaansprakelijkheidsverzekering (AVB).",
            "Marge: advies/dienst hoog (~90%), batterij dun → verkoop die direct, niet via Bol.",
        ]},
        {"fase": "Fase 2 — Gecertificeerd voor vaste installaties", "punten": [
            "Voor vaste batterijen/laadpalen op een groep gelden NEN 1010 (aanleg) en NEN 3140 (veilig werken).",
            "Behaal NEN 3140 (VP/VOP) en werk richting InstallQ-erkenning (via Sterkin/KvINL).",
            "Of partner met een gecertificeerde elektricien — jij doet advies + verkoop, hij de aansluiting.",
            "Hogere marge per klus (€500–1.500 arbeid), hogere drempel + verzekering.",
        ]},
        {"fase": "Fase 3 — Opschalen & terugkerende omzet", "punten": [
            "Reseller-deal met een merk (Marstek/Zendure/HomeWizard) voor betere inkoop.",
            "Onderhouds-/monitoring-abonnementen = voorspelbare terugkerende omzet.",
            "Samenwerken met zonnepanelen-installateurs (zij panelen, jij batterij/advies/laadpaal).",
            "Eigen monteur(s) of installatie uitbesteden; jij op advies + sales.",
        ]},
    ],
    "tarieven": [
        ("Energie-/besparingsadvies", "€75–150 / sessie"),
        ("Plug-in setup + aanmelding netbeheerder", "€100–200 / klus"),
        ("Vaste batterij/laadpaal installatie", "€500–1.500 / klus (arbeid)"),
        ("Onderhoud + monitoring", "€75–150 / jaar per klant"),
    ],
    "leads": [
        "Lokale SEO + Google Mijn Bedrijf ('thuisbatterij installateur [jouw regio]').",
        "Werkspot / Marktplaats / lokale Facebook-groepen voor de eerste klussen.",
        "Gratis ROI-/besparingscalculator als leadmagnet (jouw kracht — bouw je zelf).",
        "Partner met zonnepanelen-bedrijven en energieadviseurs.",
        "Gemeten '€X/jaar bespaard'-content; mond-tot-mond in de wijk.",
    ],
    "verzekering": [
        "Bedrijfsaansprakelijkheidsverzekering (AVB) + beroepsaansprakelijkheid voor advies.",
        "Werk aantoonbaar volgens NEN 1010/3140; lever alleen gecertificeerde batterijen.",
        "Leg adviezen en aansluitingen vast (foto's, opleverrapport).",
    ],
    "bronnen": [
        ("InstallQ — erkenning", "https://www.installq.nl/"),
        ("NEN 1010 / 3140 — Landport", "https://www.landportenergy.nl/energieopslag-en-regelgeving-nen-1010-en-nen-3140/"),
        ("Schulte — certificeringen installateur", "https://schulte-energie-techniek.nl/Kennisbank/thuisbatterijen/welke-certificeringen-moet-een-installateur-hebben/"),
    ],
}

# Meer high-value niches die bij Gerrits profiel passen — diep uitgewerkt.
NICHES = [
    {
        "naam": "🧮 Cost engineering / calculatie als ZZP-dienst", "fit": "10/10",
        "marge": "Zeer hoog (€65–95/uur)", "drempel": "Laag (nul kapitaal)",
        "waarom": "Je diepste expertise; nul voorraad, hoogste uurtarief, en het versterkt direct je baanzoektocht.",
        "wat": "Verkoop je vak: should-cost, calculatie, nacalculatie, kostprijsmodellen en kostenreductie als losse opdracht, project of interim.",
        "klant": "MKB-maakbedrijven (verspaning, plaatwerk, assemblage, machinebouw) zonder eigen cost engineer; inkoop-/engineeringafdelingen die offertes willen onderbouwen.",
        "verdienmodel": [
            "Uurtarief ZZP: €65–95/uur (senior cost engineer).",
            "Per project: should-cost-analyse of kostprijsmodel tegen vaste prijs.",
            "Interim/detachering: dag- of weektarief.",
            "Terugkerend: periodieke nacalculatie / kostprijs-updates.",
        ],
        "start": [
            "KvK eenmanszaak + beroepsaansprakelijkheidsverzekering.",
            "Maak één sterk portfolio-stuk: een should-cost/kostprijsmodel (je Cost-Forge tool toont dit al).",
            "Benader 10 lokale maakbedrijven met een concreet aanbod ('ik haal €X uit je kostprijs').",
            "Start naast je baanzoektocht — interim-opdrachten gaan vaak over in een vaste baan.",
        ],
        "eisen": [
            "Geen certificering verplicht — je ervaring (DAF/VDL/Wärtsilä) is je bewijs.",
            "Beroepsaansprakelijkheidsverzekering aan te raden.",
            "Goede NDA/voorwaarden (je werkt met gevoelige kostendata).",
        ],
        "klanten_werven": [
            "LinkedIn: deel concrete cases ('zo vond ik een gemiste korting').",
            "Maakindustrie-netwerken: Brainport, Koninklijke Metaalunie, lokale bedrijventerreinen.",
            "Interim-bureaus voor cost engineering / technische ZZP-platforms.",
            "Direct bellen/mailen met inkoop- en engineeringmanagers van MKB-maakbedrijven.",
        ],
        "cijfers": "20 declarabele uur/week × €80 × ~45 weken ≈ €72.000 omzet/jaar, nul voorraad.",
        "risicos": [
            "Acquisitie kost tijd; reken op een opstartperiode.",
            "Vertrouwelijkheid van klant-kostendata goed regelen.",
            "Inkomen schommelt zonder vaste opdracht.",
        ],
        "bronnen": [("Mijnzzp — tarieven werkvoorbereider", "https://www.mijnzzp.nl/Beroep/121-Werkvoorbereider-bouw/Salaris-en-tarief"),
                    ("Koninklijke Metaalunie", "https://www.metaalunie.nl/")],
    },
    {
        "naam": "💡 Onafhankelijk energie-/besparingsadvies", "fit": "9/10",
        "marge": "Hoog (dienst)", "drempel": "Laag → midden (label)",
        "waarom": "Energietransitie + subsidies; jouw data-edge maakt het advies geloofwaardig.",
        "wat": "Onafhankelijk advies aan huiseigenaren/VvE's: isolatie, warmtepomp, zon, batterij, dynamisch contract — eventueel met officieel energielabel (EPA).",
        "klant": "Huiseigenaren die willen verduurzamen maar door de bomen het bos niet zien; VvE's; makelaars (energielabel bij verkoop).",
        "verdienmodel": [
            "Adviesgesprek + rapport: €150–400 per woning.",
            "Energielabel (EP-W): €150–300 per woning.",
            "Begeleiding ISDE-subsidie en offertevergelijking: meerwerk.",
            "Terugkerend via makelaar-/VvE-contracten.",
        ],
        "start": [
            "Begin met onafhankelijk besparingsadvies (geen certificering nodig).",
            "Officiële energielabels afgeven? Behaal EP-W (NTA 8800): opleiding 4–6 dagen + examen + jaarlijkse bijscholing.",
            "Maak een ROI-/besparingscalculator als leadmagnet (jouw kracht).",
        ],
        "eisen": [
            "Besparingsadvies: geen verplichte certificering.",
            "Officieel energielabel afgeven: EP-W/EP-U certificering (NTA 8800) + jaarlijkse bijscholing.",
            "Onafhankelijkheid: verkoop geen producten als je 'onafhankelijk' claimt.",
        ],
        "klanten_werven": [
            "Lokale SEO ('energieadvies [regio]') + Google Mijn Bedrijf.",
            "Samenwerken met makelaars (label bij verkoop) en VvE-beheerders.",
            "Gemeente-energieloketten en lokale duurzaamheidsacties.",
            "Content: 'wat levert maatregel X echt op?' met cijfers.",
        ],
        "cijfers": "10 woningen/week × €200 gem. ≈ €2.000/week; labels schalen goed bij.",
        "risicos": [
            "Voor labels: certificering + jaarlijkse kosten/bijscholing.",
            "Onafhankelijkheid bewaken (geen verkoopprikkel).",
            "Seizoensgevoelig (piek rond subsidies/energieprijzen).",
        ],
        "bronnen": [("RVO — EPA-info", "https://www.rvo.nl/onderwerpen/wetten-en-regels-gebouwen/informatie-epa"),
                    ("Indeed — EPA-opleiding", "https://nl.indeed.com/carrieregids/baan-vinden/epa-adviseur-opleiding")],
    },
    {
        "naam": "📊 Energiemanagement & maatwerk-dashboards voor MKB", "fit": "8/10",
        "marge": "Hoog + terugkerend", "drempel": "Laag",
        "waarom": "Jouw tooling-edge (Power BI/Streamlit) + voorspelbare maandomzet.",
        "wat": "Bouw en verkoop energie-/kostendashboards en slimme sturing (batterij/EV/dynamisch tarief) voor MKB: advies + tooling + abonnement.",
        "klant": "MKB met zonnepanelen/batterij/wagenpark; bedrijven met hoge energiekosten die inzicht en sturing willen.",
        "verdienmodel": [
            "Eenmalig: dashboard/analyse op maat €1.500–5.000.",
            "Abonnement: monitoring + rapportage €50–200/maand.",
            "Advies: optimalisatie dynamisch laden/ontladen per uur.",
        ],
        "start": [
            "Hergebruik je eigen dashboards (Power BI / Streamlit, P1/energie).",
            "Maak één demo met geanonimiseerde data die een echte besparing toont.",
            "Benader 5 lokale MKB's met zonnepanelen/batterij.",
        ],
        "eisen": [
            "Geen certificering; wel AVG-proof omgaan met data.",
            "Heldere SLA/abonnementsvoorwaarden.",
        ],
        "klanten_werven": [
            "Cross-sell bij je installatie-/energieadvies-klanten.",
            "LinkedIn-cases met meetbare besparing.",
            "Partner met installateurs/energieadviseurs.",
        ],
        "cijfers": "5 abonnementen × €150/mnd = €9.000/jaar terugkerend + projectomzet.",
        "risicos": [
            "Maatwerk schaalt minder; standaardiseer je dashboard.",
            "Datakoppelingen (P1, omvormer, laadpaal) verschillen per klant.",
        ],
        "bronnen": [],
    },
    {
        "naam": "🔌 EV-laadpaal installatie + advies", "fit": "8/10",
        "marge": "Goed (arbeid)", "drempel": "Midden (NEN/erkenning)",
        "waarom": "Explosieve groei; ligt naast de batterij en volgt dezelfde installateur-route.",
        "wat": "Advies, levering en installatie van laadpalen voor thuis/MKB, vaak gecombineerd met batterij/zon en smart charging.",
        "klant": "EV-rijders thuis, MKB met wagenpark/personeel, VvE's.",
        "verdienmodel": [
            "Laadpaal + installatie: €800–1.500 (deels arbeid).",
            "Configuratie load balancing / smart charging.",
            "Onderhoud/monitoring-abonnement.",
        ],
        "start": [
            "Combineer met de batterij-installateur-route (zelfde NEN-eisen).",
            "Word erkend installatiepartner van een laadpaal-merk.",
            "Begin met thuislaadpalen (eenvoudiger), dan MKB/load balancing.",
        ],
        "eisen": [
            "NEN 1010/3140; vaste aansluiting door een bekwaam persoon.",
            "Merk-erkenning vaak vereist voor garantie/firmware.",
            "Soms aanmelding zwaardere aansluiting bij de netbeheerder.",
        ],
        "klanten_werven": [
            "Lokale SEO 'laadpaal installateur [regio]'.",
            "Partner met autodealers, zonnepanelen- en batterijbedrijven.",
            "MKB met wagenpark direct benaderen.",
        ],
        "cijfers": "8 installaties/maand × ~€400 marge ≈ €3.200/maand.",
        "risicos": [
            "Certificering/merk-erkenning nodig.",
            "Prijsdruk; differentieer met smart charging + service.",
        ],
        "bronnen": [],
    },
    {
        "naam": "🛠️ Onderhoud/monitoring-abonnementen", "fit": "8/10",
        "marge": "Terugkerend", "drempel": "Laag",
        "waarom": "Voorspelbare maandomzet bovenop installaties — stapelt op je klantenbasis.",
        "wat": "Terugkerende service op zonne-/batterij-/laadsystemen: monitoring, jaarlijkse check, storingsdienst.",
        "klant": "Je eigen geïnstalleerde klanten + klanten van installateurs zonder servicetak.",
        "verdienmodel": [
            "Abonnement €75–150/jaar per klant.",
            "Storingsbezoek op uurtarief.",
            "Monitoring-dashboard inbegrepen (jouw tooling).",
        ],
        "start": [
            "Bied het aan bij elke installatie-/adviesklant (attach).",
            "Neem servicecontracten over van installateurs zonder servicetak.",
        ],
        "eisen": [
            "NEN 3140 voor werken aan installaties.",
            "Heldere SLA + responstijden.",
        ],
        "klanten_werven": [
            "Attach bij elke installatie/advies.",
            "Aanbieden aan zonnepanelen-bedrijven als white-label service.",
        ],
        "cijfers": "100 abonnementen × €100/jaar = €10.000/jaar voorspelbaar.",
        "risicos": [
            "Schaalt met de klantenbasis; begint klein.",
            "Responsverplichtingen (SLA).",
        ],
        "bronnen": [],
    },
    {
        "naam": "🔥 Warmtepomp-advies (niet per se installatie)", "fit": "7/10",
        "marge": "Hoog ticket", "drempel": "Midden (kennis)",
        "waarom": "Hoge investering bij de klant → advies is waardevol; subsidies maken het complex.",
        "wat": "Onafhankelijk advies of een warmtepomp past, welk type/vermogen, ROI en ISDE-subsidie — zonder zelf te installeren.",
        "klant": "Huiseigenaren die twijfelen over een warmtepomp; VvE's.",
        "verdienmodel": [
            "Advies/haalbaarheidsrapport €250–500 per woning.",
            "Begeleiding offertes + ISDE-subsidie.",
            "Doorverwijzing naar installateurs (partner-fee).",
        ],
        "start": [
            "Begin met advies (geen installatie-certificering nodig).",
            "Bouw kennis op over types, vermogen, isolatie-eisen en ISDE.",
            "Combineer met energieadvies/EPA.",
        ],
        "eisen": [
            "Advies: geen verplichte certificering; installatie wel (F-gassen e.d.).",
            "Onafhankelijkheid bewaken.",
        ],
        "klanten_werven": [
            "Energieloketten, gemeente-acties, makelaars.",
            "Content over ROI/subsidie; lokale SEO.",
        ],
        "cijfers": "Hoog ticket: 4 adviezen/week × €350 ≈ €1.400/week.",
        "risicos": [
            "Vereist gedegen kennis (verkeerd advies = ontevreden klant).",
            "Subsidieregels veranderen.",
        ],
        "bronnen": [("RVO — ISDE", "https://www.rvo.nl/subsidies-financiering/isde")],
    },
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


# Zes founder-rollen om elk idee mee te pressure-testen (bron: "Success Steps").
FOUNDER_PROMPTS = [
    {"nr": 1, "titel": "Pressure-test het idee",
     "role": "een bikkelhard eerlijke startup co-founder die ideeën test vóór er tijd, geld of energie verspild wordt.",
     "task": "Beoordeel of dit idee helder, waardevol, onderscheidend en de moeite waard is.",
     "steps": "1) Vat het kernprobleem samen dat het oplost. 2) Benoem de aannames die nog onbewezen zijn. "
              "3) Geef een eerlijk go / twijfel / no-go met de belangrijkste reden."},
    {"nr": 2, "titel": "Vind de scherpste klant",
     "role": "een founder-strateeg die het segment met de hoogste pijn en hoogste koopintentie vindt.",
     "task": "Bepaal het beste eerste klantsegment, zodat er geen tijd verspild wordt aan 'iedereen'.",
     "steps": "1) Noem 2-3 mogelijke segmenten. 2) Kies welk segment de pijn het meest urgent voelt en waarom. "
              "3) Beschrijf die ideale eerste klant concreet (wie, waar te vinden, betaalbereidheid)."},
    {"nr": 3, "titel": "Spot de blinde vlekken",
     "role": "een strategische co-founder die zwakke aannames, verborgen risico's en te optimistisch denken uitdaagt.",
     "task": "Benoem wat ik over het hoofd zie in idee, aanbod, markt of groeiplan.",
     "steps": "1) Welke aannames behandel ik als feiten? 2) Welke risico's onderschat ik? "
              "3) Wat zou dit kunnen laten mislukken, en hoe dek ik dat af?"},
    {"nr": 4, "titel": "Kies de volgende zet",
     "role": "een founder-operator die de zet met de hoogste hefboom kiest in plaats van bezig-zijn.",
     "task": "Vertel de één belangrijkste volgende stap voor mijn huidige situatie.",
     "steps": "1) Wat is op dit moment de grootste bottleneck? 2) Welke acties hebben de meeste hefboom? "
              "3) Geef de ene stap voor deze week, concreet."},
    {"nr": 5, "titel": "Bouw het tractieplan",
     "role": "een tractie-strateeg die founders echt klantsignaal laat halen vóór ze opschalen.",
     "task": "Maak een plan om vraag te testen, eerste klanten te krijgen en te leren wat de markt echt wil.",
     "steps": "1) Wat is de snelste, goedkoopste manier om vraag te testen? 2) Welk meetbaar signaal = 'het werkt'? "
              "3) Geef een 2-wekenplan met concrete stappen."},
    {"nr": 6, "titel": "Founder-beslissingsfilter",
     "role": "een strategische adviseur die kansen filtert op focus, hefboom, risico en bedrijfsfase.",
     "task": "Beoordeel of deze kans/beslissing nú mijn aandacht verdient.",
     "steps": "1) Past het bij mijn fase en focus? 2) Wat is de verwachte opbrengst vs. het risico/de afleiding? "
              "3) Geef een helder doen / niet-nu / niet-doen met reden."},
]


# Niche-scan: scoor elke niche flexibel op 6 criteria → score 0-100 + verdict.
# (key, label, help, omgekeerd?, gewicht) — 'omgekeerd' = lager is beter.
SCAN_CRITERIA = [
    ("vraag", "Vraag & groei", "Is er (stijgende) vraag naar deze niche?", False, 25),
    ("marge", "Marge / ROI", "Hoge marge en weinig kapitaal nodig?", False, 25),
    ("concurrentie", "Concurrentie", "Hoeveel concurrentie? (lager = beter)", True, 15),
    ("investering", "Investering / risico", "Hoge investering of voorraadrisico? (lager = beter)", True, 15),
    ("fit", "Jouw fit / edge", "Past het bij jouw kennis, interesse of voorsprong?", False, 10),
    ("moat", "Moat / herhaling", "Moeilijk te kopiëren of herhaalaankoop?", False, 10),
]


def score_niche(scores: dict) -> tuple[float, str]:
    """Gewogen score 0-100 + verdict uit losse 1-5 scores per criterium."""
    total = maxw = 0.0
    for key, _label, _help, omgekeerd, gewicht in SCAN_CRITERIA:
        s = max(1, min(5, int(scores.get(key, 3))))
        eff = (6 - s) if omgekeerd else s
        total += gewicht * (eff / 5)
        maxw += gewicht
    pct = round(100 * total / maxw)
    if pct >= 70:
        verdict = "🟢 De moeite waard"
    elif pct >= 50:
        verdict = "🟡 Klein testen"
    else:
        verdict = "🔴 Overslaan"
    return pct, verdict


def scan_effectief(scores: dict) -> dict:
    """Effectieve score per criterium (omgekeerde meegerekend) — voor de radar."""
    out = {}
    for key, label, _help, omgekeerd, _gewicht in SCAN_CRITERIA:
        s = max(1, min(5, int(scores.get(key, 3))))
        out[label] = (6 - s) if omgekeerd else s
    return out


# Producten/diensten per niche → vult de portfolio zodra je de actieve niche kiest.
# (Niche-naam exact gelijk aan NICHES[*]['naam']; '(eigen / vrij)' valt terug op STANDAARD_PRODUCTEN.)
NICHE_PORTFOLIOS = {
    "🧮 Cost engineering / calculatie als ZZP-dienst": [
        {"Product": "Should-cost analyse (per project)", "Inkoop": 50.0, "Prijs": 1500.0, "Dienst": True},
        {"Product": "Kostprijsmodel op maat", "Inkoop": 50.0, "Prijs": 2500.0, "Dienst": True},
        {"Product": "Cost engineering consult (per uur)", "Inkoop": 0.0, "Prijs": 85.0, "Dienst": True},
        {"Product": "Nacalculatie / kostprijs-update", "Inkoop": 0.0, "Prijs": 750.0, "Dienst": True},
    ],
    "💡 Onafhankelijk energie-/besparingsadvies": [
        {"Product": "Energie-/besparingsadvies (woning)", "Inkoop": 10.0, "Prijs": 250.0, "Dienst": True},
        {"Product": "Energielabel EP-W", "Inkoop": 15.0, "Prijs": 225.0, "Dienst": True},
        {"Product": "Subsidie- + offertebegeleiding (ISDE)", "Inkoop": 0.0, "Prijs": 150.0, "Dienst": True},
    ],
    "📊 Energiemanagement & maatwerk-dashboards voor MKB": [
        {"Product": "Energie-/kostendashboard op maat", "Inkoop": 50.0, "Prijs": 2500.0, "Dienst": True},
        {"Product": "Monitoring-abonnement (per maand)", "Inkoop": 5.0, "Prijs": 99.0, "Dienst": True},
        {"Product": "Optimalisatie dynamisch laden (advies)", "Inkoop": 0.0, "Prijs": 500.0, "Dienst": True},
    ],
    "🔌 EV-laadpaal installatie + advies": [
        {"Product": "Laadpaal (reseller)", "Inkoop": 500.0, "Prijs": 699.0, "Dienst": False},
        {"Product": "Installatie laadpaal (per klus)", "Inkoop": 40.0, "Prijs": 450.0, "Dienst": True},
        {"Product": "Smart charging / load balancing config", "Inkoop": 0.0, "Prijs": 150.0, "Dienst": True},
        {"Product": "Montagemateriaal + kabel", "Inkoop": 20.0, "Prijs": 79.0, "Dienst": False},
    ],
    "🛠️ Onderhoud/monitoring-abonnementen": [
        {"Product": "Onderhoudsabonnement (per jaar)", "Inkoop": 10.0, "Prijs": 120.0, "Dienst": True},
        {"Product": "Storingsbezoek (per uur)", "Inkoop": 5.0, "Prijs": 75.0, "Dienst": True},
        {"Product": "Monitoring-dashboard (per maand)", "Inkoop": 2.0, "Prijs": 9.95, "Dienst": True},
    ],
    "🔥 Warmtepomp-advies (niet per se installatie)": [
        {"Product": "Warmtepomp-haalbaarheidsadvies", "Inkoop": 15.0, "Prijs": 350.0, "Dienst": True},
        {"Product": "Offerte- + ISDE-begeleiding", "Inkoop": 0.0, "Prijs": 200.0, "Dienst": True},
        {"Product": "Doorverwijsfee (partner)", "Inkoop": 0.0, "Prijs": 100.0, "Dienst": True},
    ],
}

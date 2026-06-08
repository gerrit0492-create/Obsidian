# E-commerce planner — home-energy / domotica (NL)

Een planningsdashboard voor het starten van een smart-home / energiebespaar-webshop
in Nederland. Gemaakt voor een cost engineer: expliciete stuk-economie, een
productportfolio-vergelijking, een 12-maands businesscase, de markt/strategie én de
**Nederlandse regels & belasting** — met Excel-export door alles heen.

> Alle getallen zijn **onderbouwde schattingen om te valideren**, geen beloftes.
> Pas alles aan naar je eigen situatie (inkoopofferte, echte Bol-fees, jouw CAC).
> De Regels-sectie is algemene info — **geen juridisch of fiscaal advies**.

## Wat zit erin
- **🧮 Marge-calculator** — stuk-economie per product: omzet excl. btw, commissie,
  vaste fee, betaalkosten, verzending, retouren, advertentie én verwijderingsbijdrage
  → winst/stuk, marge %, opslag, met een kostenwaterval en een verdict in gewone taal.
- **📦 Productportfolio** — een aanpasbare tabel (voorzien van een home-energy/domotica
  startset) gerangschikt op winst/stuk, met Excel-export.
- **📈 Businesscase** — kies een hoofdproduct, zet aantallen/groei/vaste kosten/start­budget
  → een 12-maands cashprognose, break-even-maand en een volledige Excel-export.
- **🌍 Markt & strategie** — NL/EU marktomvang & groei, segmenten om te vermijden
  (gevestigde spelers), je beachhead, je moat, de risico's en bronnen.
- **📋 Regels & belasting** — KvK, btw & KOR, consumentenrecht (14 dagen bedenktijd,
  wettelijke garantie), CE/RED, WEEE/batterijbijdrage, AVG, import — met bronnen.

## Het kerninzicht (al zichtbaar in de standaardwaarden)
Eén losse stekker van €19,95 levert **~€0,17** op — fees + advertentiekosten eten hem op.
De **starterskit van €89 levert ~€22 (≈30% marge)**. Verkoop **bundels/kits**, geen
goedkope losse apparaten.

## Starten
```bash
pip install -r requirements.txt
streamlit run app.py
```
Opent op http://localhost:8501. `model.py` bevat de zuivere reken-logica (zonder
Streamlit) en is los testbaar.

## Maak het kloppend vóór je erop vertrouwt
- Vraag een echte **inkoopofferte** (Alibaba) voor het gelande inkoopbedrag incl. vracht.
- Check de **Bol-commissie** voor jouw categorie (varieert ~8–17%).
- Gebruik **gecertificeerde (CE/RED)** white-label apparaten — bouw geen eigen radio's.
- Behandel advertentiekosten (CAC) als de doorslaggevende factor bij goedkope artikelen.
- Houd rekening met de **Nederlandse regels** in het tabblad Regels & belasting.

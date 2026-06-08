# E-commerce planner — stekkerbatterij + installatie (NL)

Een planningsdashboard voor een laag-budget start rond **plug-in (stekker)batterijen
+ installatie/advies** in Nederland. Gemaakt voor een cost engineer: expliciete
stuk-economie, een product-/dienstenportfolio, een 12-maands businesscase, de
markt/strategie én de **Nederlandse regels & belasting** — met Excel-export.

> Alle getallen zijn **onderbouwde schattingen om te valideren**, geen beloftes.
> De Regels-sectie is algemene info — **geen juridisch of fiscaal advies**.

## Wat zit erin
- **🧮 Marge-calculator** — stuk-economie per product óf dienst (toggle: diensten
  kennen geen marktplaats-fees), met een kostenwaterval en een verdict.
- **📦 Productportfolio** — aanpasbare tabel (batterij, accessoires én diensten),
  gerangschikt op winst/stuk, met een ‘Dienst?’-kolom en Excel-export.
- **📈 Businesscase** — kies een hoofdproduct/-dienst, zet aantallen/groei/vaste
  kosten/startbudget → 12-maands cashprognose + break-even + Excel.
- **🌍 Markt & strategie** — thuisbatterij-cijfers, saldering-afbouw, je beachhead,
  je moat, wat te vermijden, risico's en bronnen.
- **📋 Regels & belasting** — KvK, btw/KOR, **stekkerbatterij-regels** (800 W,
  aanmeldplicht Energieleveren.nl, geen teruglevering via stopcontact), CE/IEC 62619/
  UN38.3, consumentenrecht, AVG, import — met bronnen.

## Het kerninzicht (zichtbaar in de standaardwaarden)
- **De batterij verliest geld op een marktplaats** (Bol-commissie + prijsvergelijking
  via StekkerDeal) → verkoop die **direct of bij installatie**, niet op Bol.
- De winst zit in **accessoires** (~15–25%) en vooral **installatie/advies**
  (€216 winst per klus, ~88%; advies ~95%). Dat is een **laag-budget, hoge-marge** start.

## Starten
```bash
pip install -r requirements.txt
streamlit run app.py
```
Opent op http://localhost:8501. `model.py` bevat de zuivere reken-logica en is testbaar.

## Maak het kloppend vóór je erop vertrouwt
- Vraag echte **inkoopprijzen** op bij een merk-/groothandelaar (reseller-deal).
- Verkoop batterijen **direct** (eigen site/lokaal + installatie), niet via Bol-commissie.
- Houd je aan de **stekkerbatterij-regels** (800 W, aanmelding netbeheerder, zelfverbruik).
- Lever alleen **gecertificeerde** batterijen (CE/IEC 62619/UN38.3) — aansprakelijkheid.
- Installatie vraagt **elektrotechnische competentie** en aansprakelijkheidsdekking.

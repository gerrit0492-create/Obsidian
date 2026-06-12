# Dakofferte — klopt het Albers-bedrag in "Offerte uitwerken"?

> Mijn eigen redenering eerst, zodat jij geen "domme vragen" hoeft te stellen.

## Korte conclusie
**Nee, Albers staat niet goed — en ik kan het op dit moment niet zélf correct
invullen.** Niet omdat ik niet wil, maar omdat de juiste Albers-bedragen alleen
in jouw Albers-offerte staan, en die zit **niet in de repo** en niet in iets
waar ik bij kan. Bedragen verzinnen doe ik bewust niet — dat is bij geld het
slechtste wat een tool kan doen.

## Hoe "Offerte uitwerken" aan zijn cijfers komt
De kaart leest twee dingen uit de app-data:
1. de **offerteregel** (Bedrijf · excl. btw · incl. btw) uit de offertetabel;
2. de **detailposten** van dat bedrijf uit "Posten vergelijken".

- Zijn er **detailposten** → die worden uitgesplitst (subtotaal, btw 9 %/21 %,
  totaal, €/m²).
- **Geen** detailposten → de tool valt terug op het **offertetotaal** uit de
  offerteregel.

## Status per offerte
| Offerte | Waar komen de cijfers vandaan | Detailposten | Klopt het? |
|---|---|---|---|
| **Dakbedrijf Westermeer** | PDF **staat in de repo** (`vault/attachments/Offerte-Westermeer-OFF-2026-0189.pdf`) + 3 seed-posten in de code | ja (15.000 + 900 + 780, alles 21 %) | ✅ €16.680 excl · €20.183 incl · €336/m² |
| **B. Albers Dakwerken** | **AI-parse van jouw upload** — die PDF is **niet** in de repo bewaard | nee | ❌ excl/incl door de AI fout gelezen |

## Waarom Albers fout staat (oorzaak-gevolg)
1. Je hebt de Albers-PDF in de app geüpload; de AI (Groq) las er een excl- en
   incl-bedrag uit.
2. Die twee bedragen kloppen niet met elkaar (effectief btw-tarief ~32 %, dat
   kán niet — NL is 9 % of 21 %). → de AI heeft minstens één bedrag misgelezen.
3. Albers heeft **geen detailposten**, dus "Offerte uitwerken" gebruikt juist
   dat **foute offertetotaal**.
4. De rekenkunde in de kaart is goed (21 %/9 %), maar **fout erin = fout eruit**.

> De tool *signaleert* dit al: bij Albers verschijnt de waarschuwing
> *"effectief btw-tarief buiten 9–21 %"*. Het probleem is de **bron**, niet de
> berekening.

## Wat ik wél en niet kan
- **Niet:** de juiste Albers-bedragen "weten" of verzinnen. Een offerte is privé;
  web-search vindt het bedrijf (b-albers-dakwerken.nl), niet jóuw prijs.
- **Niet:** jouw opgeslagen data (de Gist van de app) bewerken — daar heb ik geen
  toegang toe; dat is de bewerkbare tabel in de app zelf.
- **Wel:** zodra de Albers-offerte voor mij beschikbaar is, lees ik 'm uit en zet
  ik posten + bedragen + btw% correct neer in een PR — net als Westermeer.

## De echte oplossing (zo doet de tool het werk, zoals jij bedoelt)
Kies één route:
1. **Albers-PDF in de repo** — leg 'm in `vault/attachments/` (zoals de
   Westermeer-PDF). Dan lees ík 'm uit en vul ik alles in via een PR. ← meest
   "de tool doet het zelf".
2. **Stuur/plak de Albers-offerte hier** (foto of de regels + bedragen + btw%).
   Ik zet 't om in posten + totalen (PR).
3. Je typt alleen de juiste **excl/incl** in de offertetabel; ik zet de posten
   als skelet klaar.

## Wat ik minimaal nodig heb
Per Albers-post: omschrijving · bedrag **excl. btw** · **btw% (9 of 21)**. Bijv.:

| Post | Excl. btw | Btw % |
|---|---|---|
| Dakpannen type 1 (bv. keramisch) | € … | 21 |
| Dakpannen type 2 (bv. beton) | € … | 21 |
| Steiger | € … | 21 |
| Regenpijpen vervangen | € … | 21 |
| Dakrenovatie-arbeid + isolatie | € … | 9 |
| Loodwerk | € … | 21 |

…plus het **totaal excl.** en **incl.** als controle.

---
*Gemaakt als analyse vooraf — niet om jou te laten zoeken, maar om transparant te
maken wat ik wel/niet kan en wat de tool nodig heeft om Albers kloppend te maken.*

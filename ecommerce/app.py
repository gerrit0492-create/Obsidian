"""E-commerce planner — marge, portfolio, businesscase, markt en NL-regels.

Een planningstool voor het starten van een home-energy / domotica-webshop in
Nederland. Gemaakt voor een cost engineer: de stuk-economie is expliciet en de
hele analyse exporteert naar Excel. Alle getallen zijn aanpasbare schattingen om
te valideren — geen beloftes. De Regels-sectie is algemene info, geen advies.

Starten:  streamlit run app.py
"""

from __future__ import annotations

import json
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import model as m
import ai
import store

st.set_page_config(page_title="E-commerce planner", page_icon="🛒", layout="wide")
_header = st.container()  # titel + caption worden gevuld zodra de actieve niche bekend is


def eur(x: float) -> str:
    return f"€{x:,.2f}"


# Dakrenovatie offerte-tracker — startdata (vooringevuld met de Westermeer-offerte).
DAK_DEFAULT = [
    {"Bedrijf": "Dakbedrijf Westermeer", "Offertenr.": "OFF-2026-0189", "Datum": "2026-06-11",
     "Geldig t/m": "2026-06-25", "Excl. btw": 16680.0, "Incl. btw": 20182.80, "Status": "Ontvangen",
     "Notities": "60 m² × €250/m² + lood €900 + vogelwering €780; isolatie Rd 3,8; betaling 50/50"},
    {"Bedrijf": "", "Offertenr.": "", "Datum": "", "Geldig t/m": "", "Excl. btw": 0.0,
     "Incl. btw": 0.0, "Status": "Aangevraagd", "Notities": ""},
    {"Bedrijf": "", "Offertenr.": "", "Datum": "", "Geldig t/m": "", "Excl. btw": 0.0,
     "Incl. btw": 0.0, "Status": "Aangevraagd", "Notities": ""},
]
DAK_MARKT_LO, DAK_MARKT_HI = 180.0, 260.0  # €/m² incl. btw, NL-indicatie

# Gedetailleerde uitsplitsing van de Westermeer-offerte mét marktindicatie per onderdeel.
DAK_DETAIL = [
    {"Onderdeel": "Complete dakrenovatie 60 m² — isolatie Rd 3,8, keramische pannen, tengels/panlatten, afvoer (3,5 m³ container)",
     "Offerte (excl. btw)": 15000.0, "Eenheidsprijs": "€250/m²",
     "Marktindicatie (excl. btw)": "€110–160/m² → €6.600–9.600", "Oordeel": "🔴 ~1,5–2× markt"},
    {"Onderdeel": "Loodwerk dakkapel voorzijde (loodaansluiting rondom)",
     "Offerte (excl. btw)": 900.0, "Eenheidsprijs": "post",
     "Marktindicatie (excl. btw)": "loodslab €85–300/m²", "Oordeel": "🟡 tot hoge kant"},
    {"Onderdeel": "Vogelwering (≈ 12 m)",
     "Offerte (excl. btw)": 780.0, "Eenheidsprijs": "€65/m",
     "Marktindicatie (excl. btw)": "€15–35/m → €180–420", "Oordeel": "🔴 ~2–4× markt"},
]
DAK_SUBTOTAAL, DAK_BTW, DAK_TOTAAL = 16680.0, 3502.80, 20182.80

# Posten per offerte (lang formaat) — voor de onderlinge vergelijking met scope-verschillen.
DAK_POSTEN_DEFAULT = [
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "Dakrenovatie (incl. isolatie + afvoer 3,5 m³)", "Prijs excl. btw": 15000.0},
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "Loodwerk dakkapel", "Prijs excl. btw": 900.0},
    {"Bedrijf": "Dakbedrijf Westermeer", "Onderdeel": "Vogelwering", "Prijs excl. btw": 780.0},
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
    {"Onderdeel": "Keramische betonpannen (antraciet) — materiaal", "Laag": 16.0, "Hoog": 26.0},
    {"Onderdeel": "Pannen leggen — arbeid", "Laag": 16.0, "Hoog": 24.0},
    {"Onderdeel": "Nok-/kantpannen (droge nok/vorst), hulpstukken, bevestiging", "Laag": 6.0, "Hoog": 10.0},
    {"Onderdeel": "Dakrandafwerking — boeiboord/windveer, daktrim", "Laag": 3.0, "Hoog": 6.0},
    {"Onderdeel": "Steiger (toegerekend per m²)", "Laag": 7.0, "Hoog": 12.0},
    {"Onderdeel": "Materiaaltransport, kraan/hijswerk, klein materieel", "Laag": 3.0, "Hoog": 6.0},
]
DAK_RENO_AK = 0.10   # algemene kosten / overhead (werkvoorbereiding, projectleiding, CAR, administratie)
DAK_RENO_WR = 0.07   # winst & risico
DAK_RENO_BTW = 0.21  # offerte rekent vlak 21%; isolatie-arbeid (woning > 2 jr) kan 9% zijn


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
NS = st.session_state["niche_state"]  # {niche: {"producten":[...], "bc":{...}}}


def _persist():
    return store.save({"niches": NS, "scans": st.session_state.get("scans", []),
                       "dakofferte": st.session_state.get("dakofferte", []),
                       "dak_posten": st.session_state.get("dak_posten", [])})


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

_labels = ["🧮 Marge-calculator", "📦 Productportfolio", "📈 Businesscase",
           "🌍 Markt & strategie", "📋 Regels & belasting"]
if show_route:
    _labels.append("🧰 Installateur-route")
_labels += ["💡 Niches (overzicht)", "🔎 Niche-scan", "📑 Onderzoek & groei", "🚀 Founder-check",
            "🏠 Dakofferte-tracker"]
_it = iter(st.tabs(_labels))
tab_calc = next(_it); tab_port = next(_it); tab_case = next(_it); tab_markt = next(_it); tab_regels = next(_it)
tab_route = next(_it) if show_route else None
tab_niches = next(_it); tab_scan = next(_it); tab_onderzoek = next(_it); tab_founder = next(_it)
tab_dak = next(_it)


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
    dak_opp = dc[0].number_input("Dakoppervlak (m²)", 1.0, 1000.0, 60.0, 1.0, key="dak_opp")
    dc[1].metric("Marktindicatie", f"€{DAK_MARKT_LO:.0f}–€{DAK_MARKT_HI:.0f}/m²", "incl. btw")
    dc[2].caption("Bron: Werkspot / Oranje Dakbeheer / Homedeal — indicatie, geen taxatie.")

    with st.expander("📄 Offerte Dakbedrijf Westermeer — volledige uitsplitsing + marktprijzen", expanded=True):
        st.dataframe(
            pd.DataFrame(DAK_DETAIL), use_container_width=True, hide_index=True,
            column_config={"Offerte (excl. btw)": st.column_config.NumberColumn(format="€%.0f")})
        tt = st.columns(3)
        tt[0].metric("Subtotaal excl. btw", eur(DAK_SUBTOTAAL))
        tt[1].metric("Btw 21%", eur(DAK_BTW))
        tt[2].metric("Totaal incl. btw", eur(DAK_TOTAAL), f"≈ €{DAK_TOTAAL / 60:.0f}/m² alles-in")
        st.caption("ℹ️ €336/m² is **alles incl. btw** (incl. loodwerk + vogelwering). De **dakrenovatie "
                   "zelf** = €15.000 ÷ 60 m² = **€250/m² excl. btw** (≈ €302/m² incl.) — dát is de eerlijke "
                   "vergelijking met de marktprijs per m².")
        st.caption("Marktindicaties: dakrenovatie+isolatie €110–160/m² (Werkspot/Homedeal), "
                   "vogelwering €15–35/m geïnstalleerd (Joslaan/Montaflex), loodslab €85–300/m² (Gevelpro). "
                   "Betaling: 50% bij aanvang, 50% binnen 7 dagen na oplevering · uitvoering max. 3 werkdagen.")
        from pathlib import Path as _P
        _fn = "Offerte-Westermeer-OFF-2026-0189.pdf"
        _cands = [_P(__file__).parent.parent / "vault" / "attachments" / _fn,
                  _P.cwd() / "vault" / "attachments" / _fn]
        _pdf_path = next((p for p in _cands if p.exists()), None)
        if _pdf_path:
            _bytes = _pdf_path.read_bytes()
            st.download_button("📄 Originele offerte (PDF) downloaden", _bytes,
                               file_name=_fn, mime="application/pdf")
            if st.checkbox("👁️ Offerte-tekst hier tonen", key="dak_show_pdf"):
                _txt = ai.extract_pdf_text(_bytes, maxpages=12)
                if _txt.strip():
                    st.text_area("Offerte-tekst (uit de PDF)", _txt, height=420)
                else:
                    st.info("Tekst uitlezen lukte niet — download de PDF met de knop hierboven.")
        else:
            st.info("De originele offerte is hier nog niet geladen — **reboot** de app "
                    "(Manage app → Reboot) zodat het repo-bestand wordt opgehaald.")

    with st.expander("🧮 Should-cost dakrenovatie — wat zou het dak mógen kosten?", expanded=False):
        st.caption("Onafhankelijke bottom-up referentie (€/m² excl. btw) om de dakrenovatie te toetsen — "
                   "zoals een cost engineer een should-cost opbouwt. Hellend pannendak vervangen incl. "
                   "isolatie; schaalt mee met het dakoppervlak hierboven. Loodwerk + vogelwering zijn apart.")
        _rb = pd.DataFrame(DAK_RENO_SHOULDCOST)
        _dlo, _dhi = float(_rb["Laag"].sum()), float(_rb["Hoog"].sum())  # directe kosten €/m²
        st.dataframe(_rb, use_container_width=True, hide_index=True,
                     column_config={"Laag": st.column_config.NumberColumn("Laag (€/m²)", format="€%.0f"),
                                    "Hoog": st.column_config.NumberColumn("Hoog (€/m²)", format="€%.0f")})
        # Opbouw naar should-price: directe kosten + algemene kosten + winst & risico.
        _ak_lo, _ak_hi = _dlo * DAK_RENO_AK, _dhi * DAK_RENO_AK
        _wr_lo, _wr_hi = (_dlo + _ak_lo) * DAK_RENO_WR, (_dhi + _ak_hi) * DAK_RENO_WR
        _slo, _shi = _dlo + _ak_lo + _wr_lo, _dhi + _ak_hi + _wr_hi  # should-price excl. btw €/m²
        _btw_lo, _btw_hi = _slo * DAK_RENO_BTW, _shi * DAK_RENO_BTW
        _silo, _sihi = _slo + _btw_lo, _shi + _btw_hi  # should-price incl. btw €/m²
        _opb = pd.DataFrame([
            {"Opbouw": "Directe kosten (materiaal + arbeid)", "Laag (€/m²)": _dlo, "Hoog (€/m²)": _dhi},
            {"Opbouw": f"+ Algemene kosten ({DAK_RENO_AK * 100:.0f}%)", "Laag (€/m²)": _ak_lo, "Hoog (€/m²)": _ak_hi},
            {"Opbouw": f"+ Winst & risico ({DAK_RENO_WR * 100:.0f}%)", "Laag (€/m²)": _wr_lo, "Hoog (€/m²)": _wr_hi},
            {"Opbouw": "= Should-price excl. btw", "Laag (€/m²)": _slo, "Hoog (€/m²)": _shi},
            {"Opbouw": f"+ BTW ({DAK_RENO_BTW * 100:.0f}%)", "Laag (€/m²)": _btw_lo, "Hoog (€/m²)": _btw_hi},
            {"Opbouw": "= Should-price incl. btw", "Laag (€/m²)": _silo, "Hoog (€/m²)": _sihi},
        ])
        st.dataframe(_opb, use_container_width=True, hide_index=True,
                     column_config={"Laag (€/m²)": st.column_config.NumberColumn(format="€%.0f"),
                                    "Hoog (€/m²)": st.column_config.NumberColumn(format="€%.0f")})
        rc = st.columns(2)
        rc[0].metric("Should-price excl. btw", f"€{_slo:.0f}–€{_shi:.0f}/m²")
        rc[1].metric("Should-price incl. btw", f"€{_silo:.0f}–€{_sihi:.0f}/m²")
        st.caption(f"Voor {dak_opp:.0f} m²: {eur(_slo * dak_opp)} – {eur(_shi * dak_opp)} excl. btw → "
                   f"**{eur(_silo * dak_opp)} – {eur(_sihi * dak_opp)} incl. btw**.")
        _wm_m2 = 15000.0 / dak_opp  # dakrenovatie-deel van Westermeer (zonder lood/vogelwering)
        _wm_v = ("🟢 marktconform" if _wm_m2 <= _shi
                 else "🟡 aan de hoge kant" if _wm_m2 <= _shi * 1.25 else "🔴 fors boven should-price")
        st.markdown(f"**Westermeer dakrenovatie:** {eur(15000.0)} excl. = **€{_wm_m2:.0f}/m²** → {_wm_v} "
                    f"(should-price €{_slo:.0f}–€{_shi:.0f}/m²).")
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
                   "should-*price* van die je met een offerte mag vergelijken. Ter controle: een hellend "
                   "pannendak + isolatie kost all-in ≈ €110–160/m² excl. btw (Werkspot/Homedeal, 2025/2026). "
                   "De BTW-regel rekent met 21% (gelijk aan de offerte); valt de **isolatie-arbeid** onder "
                   "het 9%-tarief (woning > 2 jr) dan ligt de incl.-prijs iets lager. Pannen-materiaal is "
                   "geënt op de richtprijs antraciet betonpan ≈ €26–36/m² incl. btw (consumentenprijs; de "
                   "should-cost rekent op inkoop, dus de onderkant ligt lager). Loodwerk + vogelwering apart. "
                   "Indicatie, geen offerte.")
        st.download_button("⬇️ Download should-cost dakrenovatie (Excel)",
                           m.df_to_excel_bytes({"Directe kosten": _rb, "Opbouw should-price": _opb}),
                           file_name="dakrenovatie_shouldcost.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="dak_reno_xlsx")

    with st.expander("⬆️ Offerte uploaden — posten automatisch toevoegen", expanded=False):
        _up = st.file_uploader("Offerte (PDF)", type=["pdf"], key="dak_up")
        if _up is not None and st.button("Verwerk upload (AI)", key="dak_up_btn", type="primary"):
            if not ai.available():
                st.warning("Automatisch uitlezen vereist een LLM-key (Groq). Voeg anders handmatig toe.")
            else:
                with st.spinner("PDF uitlezen + posten herkennen…"):
                    _txt = ai.extract_pdf_text(_up.read())
                    _od = ai.parse_offerte(_txt) if _txt else None
                if not _od or not str(_od.get("bedrijf") or "").strip():
                    st.error("Kon de offerte niet automatisch uitlezen. Voeg 'm handmatig toe.")
                else:
                    _bn = str(_od["bedrijf"]).strip()
                    st.session_state["dakofferte"].append({
                        "Bedrijf": _bn, "Offertenr.": _od.get("offertenummer", ""),
                        "Datum": _od.get("datum", ""), "Geldig t/m": _od.get("geldig", ""),
                        "Excl. btw": float(_od.get("totaal_excl", 0) or 0),
                        "Incl. btw": float(_od.get("totaal_incl", 0) or 0),
                        "Status": "Ontvangen", "Notities": "automatisch uit PDF"})
                    _np = 0
                    for _p in _od.get("posten", []):
                        try:
                            _pr = float(_p.get("prijs_excl", 0) or 0)
                        except Exception:  # noqa: BLE001
                            _pr = 0.0
                        if str(_p.get("onderdeel") or "").strip():
                            st.session_state["dak_posten"].append(
                                {"Bedrijf": _bn, "Onderdeel": str(_p["onderdeel"]).strip(),
                                 "Prijs excl. btw": _pr})
                            _np += 1
                    try:
                        _persist()
                    except Exception:  # noqa: BLE001
                        pass
                    st.success(f"Offerte van {_bn} toegevoegd met {_np} posten — zie de tabel en posten-matrix.")
                    st.rerun()
        st.caption("De posten/totalen worden automatisch uit de PDF gehaald (met je Groq-key). "
                   "Op Streamlit Cloud wordt de PDF zelf niet bewaard; de uitgelezen gegevens wél (Gist).")

    with st.expander("➕ Nieuwe offerte handmatig toevoegen", expanded=False):
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
        _dv = _dv.sort_values("Incl. btw").reset_index(drop=True)
        st.dataframe(
            _dv[["Bedrijf", "Offertenr.", "Geldig t/m", "Excl. btw", "Incl. btw", "€/m² incl.",
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

    st.markdown("#### 🔍 Posten vergelijken (ook bij verschillende scope)")
    st.caption("Voer per offerte de posten in (Bedrijf · Onderdeel · Prijs excl. btw). Een lege cel = "
               "die post zit **niet** in die offerte — zo zie je scope-verschillen meteen.")
    _pe = st.data_editor(
        pd.DataFrame(st.session_state.get("dak_posten", DAK_POSTEN_DEFAULT)), num_rows="dynamic",
        use_container_width=True, key=f"dak_posten_oe_{len(st.session_state.get('dak_posten', []))}",
        column_config={
            "Prijs excl. btw": st.column_config.NumberColumn(format="€%.2f"),
            "Onderdeel": st.column_config.TextColumn(width="large"),
        })
    _prows = [r for r in _pe.to_dict("records")
              if str(r.get("Bedrijf") or "").strip() and str(r.get("Onderdeel") or "").strip()]
    st.session_state["dak_posten"] = _prows
    if store.enabled() and st.button("💾 Posten bewaren in Gist", key="dak_posten_save"):
        try:
            _persist()
            st.success("Opgeslagen.")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Opslaan mislukt: {exc}")

    if _prows:
        _pm = pd.DataFrame(_prows).pivot_table(
            index="Onderdeel", columns="Bedrijf", values="Prijs excl. btw", aggfunc="sum")
        _ontbreekt = [idx for idx in _pm.index if not _pm.loc[idx].notna().all()]
        _disp = _pm.round(0).copy()
        _disp.loc["── Totaal (excl. btw) ──"] = _pm.sum()
        st.dataframe(_disp.reset_index(), use_container_width=True, hide_index=True)
        st.caption("Lege cel = post zit niet in die offerte. Bedragen excl. btw.")
        if _ontbreekt:
            st.warning("⚠️ **Scope-verschil** — niet in alle offertes: " + ", ".join(_ontbreekt)
                       + ". Vraag de aanbieders deze post toe te voegen, of houd er rekening mee bij "
                       "het vergelijken (een lagere offerte kan posten missen).")
        else:
            st.success("✅ Alle offertes bevatten dezelfde posten — eerlijke vergelijking.")

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

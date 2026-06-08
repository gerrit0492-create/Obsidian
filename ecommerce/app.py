"""E-commerce planner — marge, portfolio, businesscase, markt en NL-regels.

Een planningstool voor het starten van een home-energy / domotica-webshop in
Nederland. Gemaakt voor een cost engineer: de stuk-economie is expliciet en de
hele analyse exporteert naar Excel. Alle getallen zijn aanpasbare schattingen om
te valideren — geen beloftes. De Regels-sectie is algemene info, geen advies.

Starten:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import model as m
import ai

st.set_page_config(page_title="E-commerce planner", page_icon="🛒", layout="wide")
st.title("🛒 E-commerce planner — stekkerbatterij + installatie")
st.caption("Plan marge, productmix, de businesscase, de markt én de Nederlandse regels op één plek. "
           "Alle getallen zijn aanpasbare schattingen om te valideren — geen beloftes.")


def eur(x: float) -> str:
    return f"€{x:,.2f}"


@st.cache_data
def _startgids_bytes():
    import startgids
    return startgids.build_pdf_bytes(), startgids.build_excel_bytes()


# --- Gedeelde platform-aannames (zijbalk) ----------------------------------
st.sidebar.header("⚙️ Platform-aannames")
st.sidebar.caption("Standaard: verkopen via Bol.nl (B2C, prijzen incl. 21% btw).")
fees = {
    "commissie_pct": st.sidebar.slider("Commissie %", 0.0, 25.0, m.BOL["commissie_pct"] * 100, 0.5) / 100,
    "vaste_fee": st.sidebar.number_input("Vaste fee/artikel (€)", 0.0, 5.0, m.BOL["vaste_fee"], 0.05),
    "betaal_pct": st.sidebar.slider("Betaalkosten %", 0.0, 5.0, m.BOL["betaal_pct"] * 100, 0.1) / 100,
    "verzending": st.sidebar.number_input("Verzending naar klant (€)", 0.0, 15.0, m.BOL["verzending"], 0.25),
    "retour_pct": st.sidebar.slider("Retouren %", 0.0, 30.0, m.BOL["retour_pct"] * 100, 1.0) / 100,
    "advertentie": st.sidebar.number_input("Advertentie/verkoop — CAC (€)", 0.0, 30.0, m.BOL["advertentie"], 0.25),
    "verwijderingsbijdrage": st.sidebar.number_input(
        "Verwijderingsbijdrage WEEE/batterij (€)", 0.0, 2.0, m.BOL["verwijderingsbijdrage"], 0.05,
        help="Verplichte recyclingbijdrage voor elektronica/batterijen in NL."),
}
st.sidebar.caption("Bol-commissie varieert echt ~8–17% per categorie. Pas aan naar jouw situatie.")

st.sidebar.divider()
st.sidebar.markdown("#### 📘 Startgids (alles samengevat)")
try:
    _pdf, _xl = _startgids_bytes()
    st.sidebar.download_button("📄 Startgids (PDF)", _pdf, file_name="Startgids_ecommerce.pdf",
                               mime="application/pdf", use_container_width=True)
    st.sidebar.download_button("📊 Startgids (Excel)", _xl, file_name="Startgids_ecommerce.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
except Exception as exc:  # noqa: BLE001
    st.sidebar.caption(f"Startgids niet beschikbaar: {exc}")

tab_calc, tab_port, tab_case, tab_markt, tab_regels, tab_route, tab_niches, tab_founder = st.tabs(
    ["🧮 Marge-calculator", "📦 Productportfolio", "📈 Businesscase",
     "🌍 Markt & strategie", "📋 Regels & belasting", "🧰 Installateur-route",
     "💡 Meer niches", "🚀 Founder-check"])


# --- 1. Marge-calculator ---------------------------------------------------
with tab_calc:
    st.subheader("Stuk-economie")
    c1, c2 = st.columns(2)
    prijs = c1.number_input("Verkoopprijs (incl. btw) €", 1.0, 5000.0, 1199.0, 1.0)
    inkoop = c2.number_input("Geland inkoopbedrag/stuk (excl. btw) €", 0.0, 4000.0, 850.0, 5.0,
                             help="Inkoop + vracht + eventueel invoerrecht — of materiaal/reiskosten bij een dienst.")
    dienst = st.toggle("Dit is een dienst (installatie/advies) — geen marktplaats-fees", value=False)
    e = m.stuk_economie(prijs, inkoop, dienst=dienst, **fees)

    k = st.columns(4)
    k[0].metric("Winst / stuk", eur(e["winst"]))
    k[1].metric("Marge %", f"{e['marge_pct'] * 100:.1f}%")
    k[2].metric("Opslag", f"{e['opslag_x']:.2f}×")
    k[3].metric("Omzet excl. btw", eur(e["omzet_excl"]))

    if e["marge_pct"] < 0.10:
        st.error("⚠️ Marge onder 10% — fees + advertentiekosten eten dit op. Bundel het, "
                 "verhoog de prijs, of verlaag de CAC.")
    elif e["marge_pct"] < 0.20:
        st.warning("Dunne marge (10–20%). Werkbaar, maar weinig ruimte voor ads/retouren.")
    else:
        st.success("Gezonde marge (20%+). Dit soort product/bundel is de basis om op te bouwen.")

    # Waterval: omzet → kosten → winst
    labels = ["Omzet excl. btw", "Inkoop", "Commissie", "Vaste fee", "Betaalkosten",
              "Verzending", "Retouren", "Advertentie", "Verwijderingsbijdr.", "Winst"]
    values = [e["omzet_excl"], -e["inkoop"], -e["commissie"], -e["vaste_fee"], -e["betaal"],
              -e["verzending"], -e["retour_kosten"], -e["advertentie"], -e["verwijderingsbijdrage"],
              e["winst"]]
    measure = ["absolute"] + ["relative"] * 8 + ["total"]
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
    st.caption("Pas inkoop/prijs aan of voeg rijen toe. ‘Inkoop’ is geland excl. btw; ‘Prijs’ is incl. btw.")
    seed = st.session_state.get("producten", m.STANDAARD_PRODUCTEN)
    edited = st.data_editor(
        pd.DataFrame(seed), num_rows="dynamic", use_container_width=True, key="port_edit",
        column_config={
            "Inkoop": st.column_config.NumberColumn("Inkoop (geland €)", format="%.2f"),
            "Prijs": st.column_config.NumberColumn("Prijs (incl. btw €)", format="%.2f"),
            "Dienst": st.column_config.CheckboxColumn("Dienst?", help="Installatie/advies: geen marktplaats-fees"),
        })
    producten = [r for r in edited.to_dict("records") if r.get("Product")]
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
    producten = st.session_state.get("producten", m.STANDAARD_PRODUCTEN)
    namen = [p["Product"] for p in producten] or ["—"]
    default_idx = next((i for i, p in enumerate(producten) if p.get("Dienst")), 0)
    keuze = st.selectbox("Hoofdproduct/-dienst (stuurt de prognose)", namen, index=default_idx)
    gekozen = next((p for p in producten if p["Product"] == keuze),
                   producten[0] if producten else {"Prijs": 295.0, "Inkoop": 25.0, "Dienst": True})
    e = m.stuk_economie(gekozen["Prijs"], gekozen["Inkoop"],
                        dienst=bool(gekozen.get("Dienst", False)), **fees)

    a = st.columns(4)
    stuks1 = a[0].number_input("Stuks/klussen in maand 1", 1, 5000, 15, 1)
    groei = a[1].slider("Maandelijkse groei %", 0.0, 30.0, 10.0, 1.0) / 100
    vast = a[2].number_input("Vaste kosten / maand €", 0.0, 5000.0, 150.0, 25.0,
                             help="Webshop/Bol, tools, verzekering, enz.")
    start = a[3].number_input("Startinvestering €", 0.0, 50000.0, 750.0, 50.0,
                              help="Laag starten: accessoirevoorraad + gereedschap + opzet.")

    prog, be = m.prognose(stuks1, groei, 12, vast, start, e["winst"], e["omzet_excl"])
    s = st.columns(4)
    s[0].metric("Winst / stuk", eur(e["winst"]))
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


# --- 5. Regels & belasting -------------------------------------------------
with tab_regels:
    st.subheader("Nederlandse regels & regelgeving voor je webshop")
    st.caption("Algemene informatie om rekening mee te houden — geen juridisch of fiscaal advies. "
               "Check je eigen situatie bij KvK en Belastingdienst.")
    cols = st.columns(2)
    for i, (titel, punten) in enumerate(m.REGELS.items()):
        with cols[i % 2]:
            st.markdown(f"#### {titel}")
            for p in punten:
                st.markdown(f"- {p}")

    st.info("💡 Twee dingen die je marge raken (al meegerekend): de **verwijderingsbijdrage** "
            "(WEEE/batterij) per stuk, en het **14-daagse retourrecht** dat retouren onvermijdelijk "
            "maakt — houd de retour-aanname realistisch.")
    st.markdown("#### Bronnen")
    st.markdown("  ·  ".join(f"[{naam}]({url})" for naam, url in m.REGELS_BRONNEN))


# --- 6. Installateur-route -------------------------------------------------
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


# --- 7. Meer niches (diep uitgewerkt) --------------------------------------
with tab_niches:
    st.subheader("Meer high-value niches — diep uitgewerkt")
    st.caption("Gerangschikt op fit (cost engineer + energie + data/tooling). "
               "Klap een niche open voor de volledige playbook.")
    st.info("🧠 Sterkste fit: **cost engineering/calculatie als ZZP-dienst** — nul kapitaal, "
            "hoogste uurtarief, en het versterkt je baanzoektocht. Daarna energie-/besparingsadvies.")
    for n in m.NICHES:
        with st.expander(f"{n['naam']}  —  fit {n['fit']} · marge {n['marge']} · drempel {n['drempel']}"):
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


# --- 8. Founder-check ------------------------------------------------------
with tab_founder:
    st.subheader("🚀 Founder-check — pressure-test elk idee")
    st.caption("Typ je idee in en draai de zes founder-rollen erop. Werkt met je gratis "
               "Groq-key (Secrets); zonder key krijg je de prompts om te kopiëren.")
    idea = st.text_area("Jouw idee / niche", placeholder="Bijv. 3D-print STL-designs voor gereedschapshouders…")
    ctx = st.text_input("Context — doelgroep, budget, fase (optioneel)")
    opties = [f"{p['nr']}. {p['titel']}" for p in m.FOUNDER_PROMPTS]
    keuze = st.multiselect("Welke analyses draaien?", opties, default=opties[:3])

    def _bouw_prompt(p):
        return (f"Je bent {p['role']}\n\nTaak: {p['task']}\n\nVolg deze stappen:\n{p['steps']}\n\n"
                f"IDEE: {idea}\nCONTEXT: {ctx or 'niet opgegeven — benoem je aanname'}\n\n"
                "Antwoord in het Nederlands, concreet en eerlijk; geen wollige taal. "
                "Vraag niets terug — geef direct je analyse.")

    if ai.available():
        if st.button("Analyseer", type="primary"):
            if not idea.strip():
                st.warning("Vul eerst je idee in.")
            else:
                for p in m.FOUNDER_PROMPTS:
                    if f"{p['nr']}. {p['titel']}" not in keuze:
                        continue
                    with st.spinner(f"{p['nr']}. {p['titel']}…"):
                        out = ai.complete(_bouw_prompt(p))
                    st.markdown(f"#### {p['nr']}. {p['titel']}")
                    st.markdown(out or "_(geen antwoord — probeer opnieuw)_")
                    st.divider()
    else:
        st.info("Geen LLM-key gevonden. Zet **GROQ_API_KEY** (gratis, geen creditcard) in Secrets "
                "om dit automatisch te draaien. Of kopieer hieronder de prompts naar je eigen AI.")
        for p in m.FOUNDER_PROMPTS:
            with st.expander(f"{p['nr']}. {p['titel']}"):
                st.code(f"Je bent {p['role']}\n\nTaak: {p['task']}\n\nStappen:\n{p['steps']}")

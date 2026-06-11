"""Dakrenovatie — offertes volgen & vergelijken (Streamlit).

Compiègnehof 11, Eindhoven. Voer offertes in, vergelijk op €/m² incl. btw,
zie meteen of het marktconform is, en exporteer naar Excel.

Starten:  streamlit run app.py
"""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Dakrenovatie offertes", page_icon="🏠", layout="wide")
st.title("🏠 Dakrenovatie — offertes volgen & vergelijken")
st.caption("Compiègnehof 11, Eindhoven · volledige dakrenovatie (hoofddak + erker + dakkapel).")

# Marktindicatie €/m² incl. btw voor hellend pannendak mét isolatie (NL 2025/26).
MARKT_LO, MARKT_HI = 180.0, 260.0

c = st.columns(3)
opp = c[0].number_input("Dakoppervlak (m²)", 1.0, 1000.0, 60.0, 1.0)
c[1].metric("Marktindicatie", f"€{MARKT_LO:.0f}–€{MARKT_HI:.0f}/m²", "incl. btw")
c[2].caption("Bron: Werkspot / Oranje Dakbeheer / Homedeal — indicatie, geen taxatie.")

DEFAULT = [
    {"Bedrijf": "Dakbedrijf Westermeer", "Offertenr.": "OFF-2026-0189", "Datum": "2026-06-11",
     "Geldig t/m": "2026-06-25", "Excl. btw": 16680.0, "Incl. btw": 20182.80, "Status": "Ontvangen",
     "Notities": "60 m² × €250/m² + lood €900 + vogelwering €780; isolatie Rd 3,8; betaling 50/50"},
    {"Bedrijf": "", "Offertenr.": "", "Datum": "", "Geldig t/m": "", "Excl. btw": 0.0,
     "Incl. btw": 0.0, "Status": "Aangevraagd", "Notities": ""},
    {"Bedrijf": "", "Offertenr.": "", "Datum": "", "Geldig t/m": "", "Excl. btw": 0.0,
     "Incl. btw": 0.0, "Status": "Aangevraagd", "Notities": ""},
]

st.subheader("Offertes")
st.caption("Vul per offerte een rij in of voeg rijen toe. €/m² en het oordeel worden automatisch berekend.")
edited = st.data_editor(
    pd.DataFrame(st.session_state.get("offertes", DEFAULT)), num_rows="dynamic",
    use_container_width=True, key="oe",
    column_config={
        "Excl. btw": st.column_config.NumberColumn(format="€%.2f"),
        "Incl. btw": st.column_config.NumberColumn(format="€%.2f"),
        "Status": st.column_config.SelectboxColumn(
            options=["Aangevraagd", "Ontvangen", "Vergeleken", "Gekozen", "Afgewezen"]),
    })
rows = [r for r in edited.to_dict("records") if str(r.get("Bedrijf") or "").strip()]
st.session_state["offertes"] = rows


def _oordeel(eur_m2):
    if eur_m2 <= MARKT_HI:
        return "🟢 marktconform"
    if eur_m2 <= MARKT_HI * 1.25:
        return "🟡 aan de hoge kant"
    return "🔴 fors boven markt"


if rows:
    view = pd.DataFrame(rows)
    view["€/m² incl."] = (view["Incl. btw"] / opp).round(0)
    view["Oordeel"] = view["€/m² incl."].apply(_oordeel)
    view = view.sort_values("Incl. btw").reset_index(drop=True)

    st.dataframe(
        view[["Bedrijf", "Offertenr.", "Geldig t/m", "Excl. btw", "Incl. btw", "€/m² incl.",
              "Oordeel", "Status", "Notities"]],
        use_container_width=True, hide_index=True,
        column_config={
            "Excl. btw": st.column_config.NumberColumn(format="€%.0f"),
            "Incl. btw": st.column_config.NumberColumn(format="€%.0f"),
            "€/m² incl.": st.column_config.NumberColumn(format="€%.0f"),
        })

    chart = view[["Bedrijf", "€/m² incl."]].set_index("Bedrijf")
    st.bar_chart(chart, use_container_width=True)
    st.caption(f"Groen ≤ €{MARKT_HI:.0f}/m² · geel tot €{MARKT_HI * 1.25:.0f}/m² · rood daarboven (incl. btw).")

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        view.to_excel(xl, sheet_name="Offertes", index=False)
    st.download_button("⬇️ Download vergelijking (Excel)", buf.getvalue(),
                       file_name="dakrenovatie_offertes.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.subheader("📋 Advies — is dit marktconform?")
st.markdown(
    "- **Korte conclusie:** de offerte van Westermeer (~€250/m² **excl.** btw, ≈ €336/m² **incl.**) "
    "zit **fors boven** de markt. Een hellend pannendak vervangen *mét isolatie* kost in NL gemiddeld "
    "**€110–€160/m² excl. btw** (≈ €180–€260/m² incl.).\n"
    "- **Nuance:** kleine klus (60 m²) → hogere prijs/m² door vaste kosten; keramische pannen + Rd 3,8 "
    "zitten aan de betere kant. Maar zelfs dan is het aan de hoge kant.\n"
    "- **Vraag na / onderhandel:** is de **steiger** inbegrepen? Geldt het **9%-btw-tarief op de "
    "isolatie-arbeid** (woning > 2 jaar)? Vraag een **uitsplitsing arbeid/materiaal** en de "
    "**garantietermijn** schriftelijk.\n"
    "- **Doe:** vraag **minstens 2 extra offertes** met dezelfde scope en vergelijk op **€/m² incl. btw** "
    "(de tabel hierboven doet dat automatisch).")

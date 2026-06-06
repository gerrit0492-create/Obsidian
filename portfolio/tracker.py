"""Private job-application tracker — for your eyes only.

Tracker (who/what/when/status + follow-ups) plus a live 'Vacatures' tab that
pulls current openings. Run it on your own machine:

    streamlit run tracker.py

PRIVACY
- Not part of the public portfolio (app.py) and never deployed — nobody else sees it.
- Data is stored locally in ``data/applications.xlsx`` (git-ignored): never uploaded.
- Optional password: set TRACKER_PASSWORD in .streamlit/secrets.toml.
- Live search: set ADZUNA_APP_ID / ADZUNA_APP_KEY for best NL results (free key
  at developer.adzuna.com); without it a keyless fallback is used.
"""

from __future__ import annotations

import io
import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

import vacancies
import overview

HERE = Path(__file__).parent
DATA = HERE / "data" / "applications.xlsx"

COLUMNS = [
    "Company", "Role", "Location", "Travel", "Source", "Contact", "Link",
    "Priority", "Applied", "Status", "Next action", "Next date", "Notes",
]
DATE_COLS = ["Applied", "Next date"]
STATUSES = ["Lead", "Applied", "Screening", "Interview", "Offer", "Rejected", "On hold", "Closed"]
SOURCES = ["Direct", "Bureau", "Vacature", "LinkedIn", "Referral", "Other"]
PRIORITIES = ["High", "Medium", "Low"]
CLOSED = {"Rejected", "Closed"}
PIPELINE = ["Lead", "Applied", "Screening", "Interview", "Offer"]

st.set_page_config(page_title="Application tracker", page_icon="🔒", layout="wide")


def _setting(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


def _gate() -> None:
    expected = _setting("TRACKER_PASSWORD")
    if not expected:
        st.warning(
            "No password set. Fine when you run it only on your own computer. "
            "To lock it, add TRACKER_PASSWORD to .streamlit/secrets.toml."
        )
        return
    if st.session_state.get("tracker_authed"):
        return
    pw = st.text_input("Password", type="password")
    if pw and pw == expected:
        st.session_state["tracker_authed"] = True
        st.rerun()
    elif pw:
        st.error("Wrong password.")
    st.stop()


def _load() -> pd.DataFrame:
    if DATA.exists():
        df = pd.read_excel(DATA)
    else:
        df = pd.DataFrame(columns=COLUMNS)
    for col in COLUMNS:               # add any missing columns (old files keep working)
        if col not in df.columns:
            df[col] = pd.NA
    df = df[COLUMNS]
    for col in DATE_COLS:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _save(df: pd.DataFrame) -> None:
    DATA.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(DATA, index=False)


def _to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def _add_vacancies_to_tracker(found: list[dict]) -> int:
    """Append newly-found vacancies (as Leads) to the saved tracker; returns count added."""
    df = _load()
    existing = {(str(c).strip().lower(), str(r).strip().lower())
                for c, r in zip(df["Company"], df["Role"])}
    new_rows = []
    for v in found:
        key = (v["Company"].strip().lower(), v["Title"].strip().lower())
        if not v["Company"] or key in existing:
            continue
        existing.add(key)
        new_rows.append({
            "Company": v["Company"], "Role": v["Title"], "Location": v["Location"],
            "Travel": "", "Source": "Vacature", "Contact": "", "Link": v["Link"],
            "Priority": "Medium", "Applied": pd.NaT, "Status": "Lead",
            "Next action": "Bekijk vacature + solliciteer", "Next date": pd.NaT,
            "Notes": f"Gevonden via {v['Source']}" + (f" · {v['Posted']}" if v["Posted"] else ""),
        })
    if new_rows:
        _save(pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)[COLUMNS])
    return len(new_rows)


st.title("🔒 Application tracker")
st.caption("Private — stored locally in data/applications.xlsx (git-ignored), never uploaded.")
_gate()

tab_track, tab_vac = st.tabs(["📋 Tracker", "🔎 Vacatures (live)"])

# ===========================================================================
# Tracker
# ===========================================================================
with tab_track:
    df = _load()

    active = df[~df["Status"].isin(CLOSED)]
    applied_plus = df[df["Status"].isin(["Applied", "Screening", "Interview", "Offer"])]
    k = st.columns(5)
    k[0].metric("Total", len(df))
    k[1].metric("Active", len(active))
    k[2].metric("Applied+", len(applied_plus))
    k[3].metric("Interviews", int((df["Status"] == "Interview").sum()))
    k[4].metric("Offers", int((df["Status"] == "Offer").sum()))

    st.subheader("Pipeline")
    pcols = st.columns(len(PIPELINE))
    for col, s in zip(pcols, PIPELINE):
        col.metric(s, int((df["Status"] == s).sum()))

    st.subheader("Applications")
    st.caption("Add a row at the bottom, edit any cell, or select a row and press ⌫ to delete. Then Save.")
    edited = st.data_editor(
        df, num_rows="dynamic", use_container_width=True, hide_index=True, key="editor",
        column_config={
            "Link": st.column_config.LinkColumn("Link", display_text="open", width="small"),
            "Applied": st.column_config.DateColumn("Applied", format="YYYY-MM-DD"),
            "Next date": st.column_config.DateColumn("Next date", format="YYYY-MM-DD"),
            "Status": st.column_config.SelectboxColumn("Status", options=STATUSES, default="Lead"),
            "Source": st.column_config.SelectboxColumn("Source", options=SOURCES),
            "Priority": st.column_config.SelectboxColumn("Priority", options=PRIORITIES, default="Medium"),
            "Notes": st.column_config.TextColumn("Notes", width="large"),
        },
    )

    c1, c2, c3, _ = st.columns([1, 1, 1.4, 3])
    if c1.button("💾 Save", type="primary"):
        _save(edited)
        st.success("Saved to data/applications.xlsx")
    c2.download_button(
        "⬇️ Excel", data=_to_excel_bytes(edited), file_name="applications.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    c3.download_button(
        "📱 Mobiel overzicht (HTML)",
        data=overview.render(edited, st.session_state.get("vacancies")).encode("utf-8"),
        file_name="job_overview.html", mime="text/html",
        help="Self-contained snapshot — save it on your phone and open offline.",
    )

    st.subheader("Follow-ups")
    fu = edited.copy()
    fu["Next date"] = pd.to_datetime(fu["Next date"], errors="coerce")
    fu = fu.dropna(subset=["Next date"]).sort_values("Next date")
    fu = fu[~fu["Status"].isin(CLOSED)]
    if fu.empty:
        st.info("No upcoming follow-ups. Set a 'Next date' on an application to see it here.")
    else:
        today = pd.Timestamp(date.today())
        overdue = int((fu["Next date"] < today).sum())
        if overdue:
            st.error(f"🔴 {overdue} follow-up(s) overdue.")
        for _, row in fu.iterrows():
            when = row["Next date"].date()
            flag = "🔴 overdue" if row["Next date"] < today else "🟢"
            prio = f" · {row['Priority']}" if (pd.notna(row.get("Priority")) and row.get("Priority")) else ""
            st.markdown(
                f"**{when}** {flag} — **{row['Company'] or '—'}** · {row['Role'] or ''} "
                f"· _{row['Status'] or ''}_{prio} → {row['Next action'] or '—'}"
            )

# ===========================================================================
# Vacatures (live)
# ===========================================================================
with tab_vac:
    st.subheader("Live vacatures zoeken")
    has_key = bool(_setting("ADZUNA_APP_ID") and _setting("ADZUNA_APP_KEY"))
    st.caption(
        ("Bron: Adzuna (NL) — goede dekking." if has_key else
         "Bron: keyless fallback (lichtere dekking). Voor de beste resultaten: zet een "
         "gratis ADZUNA_APP_ID / ADZUNA_APP_KEY in secrets.toml (developer.adzuna.com).")
    )
    f1, f2, f3 = st.columns([3, 1, 1])
    kw_raw = f1.text_input("Zoektermen (komma-gescheiden)", value=", ".join(vacancies.DEFAULT_KEYWORDS))
    where = f2.text_input("Regio", value="Eindhoven")
    distance = f3.slider("Straal (km)", 5, 100, 40, step=5)

    if st.button("🔄 Update vacatures", type="primary"):
        kws = [k.strip() for k in kw_raw.split(",") if k.strip()]
        with st.spinner("Zoeken naar actuele vacatures…"):
            results = vacancies.search(
                keywords=kws, where=where.strip() or "Eindhoven", distance=distance,
                app_id=_setting("ADZUNA_APP_ID"), app_key=_setting("ADZUNA_APP_KEY"),
            )
        st.session_state["vacancies"] = results

    results = st.session_state.get("vacancies")
    if results is None:
        st.info("Klik op **Update vacatures** om de laatst beschikbare functies op te halen.")
    elif not results:
        st.warning("Geen vacatures gevonden. Probeer bredere zoektermen of een grotere straal "
                   "(of zet een Adzuna-key voor betere NL-dekking).")
    else:
        vdf = pd.DataFrame(results)[["Title", "Company", "Location", "Posted", "Source", "Link"]]
        st.success(f"{len(vdf)} vacatures gevonden.")
        st.dataframe(
            vdf, use_container_width=True, hide_index=True,
            column_config={"Link": st.column_config.LinkColumn("Link", display_text="open")},
        )
        st.download_button(
            "📱 Download dit overzicht (HTML)",
            data=overview.render(edited, results).encode("utf-8"),
            file_name="job_overview.html", mime="text/html",
            help="Self-contained snapshot — save it on your phone and open offline.",
        )
        st.caption("Nieuwe bedrijven/functies worden als 'Lead' toegevoegd; bestaande worden overgeslagen.")
        if st.button("➕ Voeg nieuwe toe aan tracker"):
            st.warning("Sla eerst je wijzigingen in de Tracker-tab op — dit herlaadt de lijst.")
            added = _add_vacancies_to_tracker(results)
            st.success(f"{added} nieuwe vacature(s) toegevoegd. Ga naar de Tracker-tab.")

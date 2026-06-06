"""Private job-application tracker — for your eyes only.

Who/what/when/status + follow-ups for every application. Run it on your own
machine:

    streamlit run tracker.py

PRIVACY
- This page is NOT part of the public portfolio (app.py) and is never deployed,
  so nobody else sees it.
- Your data is stored locally in ``data/applications.xlsx`` which is git-ignored,
  so it is never uploaded or committed.
- Optionally set a password: put TRACKER_PASSWORD in .streamlit/secrets.toml.
"""

from __future__ import annotations

import io
import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

HERE = Path(__file__).parent
DATA = HERE / "data" / "applications.xlsx"

COLUMNS = ["Company", "Role", "Source", "Contact", "Applied", "Status", "Next action", "Next date", "Notes"]
DATE_COLS = ["Applied", "Next date"]
STATUSES = ["Lead", "Applied", "Screening", "Interview", "Offer", "Rejected", "On hold", "Closed"]
CLOSED = {"Rejected", "Closed"}

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
            "No password set. This is fine when you run it only on your own computer. "
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
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = pd.NA
        df = df[COLUMNS]
    else:
        df = pd.DataFrame({c: pd.Series(dtype="object") for c in COLUMNS})
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


st.title("🔒 Application tracker")
st.caption("Private — stored locally in data/applications.xlsx (git-ignored), never uploaded.")
_gate()

df = _load()

# --- KPIs ------------------------------------------------------------------
active = df[~df["Status"].isin(CLOSED)]
k = st.columns(4)
k[0].metric("Total", len(df))
k[1].metric("Active", len(active))
k[2].metric("Interviews", int((df["Status"] == "Interview").sum()))
k[3].metric("Offers", int((df["Status"] == "Offer").sum()))

# --- Editable table --------------------------------------------------------
st.subheader("Applications")
st.caption("Add a row at the bottom, edit any cell, or tick a row and press ⌫ to delete. Then Save.")
edited = st.data_editor(
    df,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    key="editor",
    column_config={
        "Applied": st.column_config.DateColumn("Applied", format="YYYY-MM-DD"),
        "Next date": st.column_config.DateColumn("Next date", format="YYYY-MM-DD"),
        "Status": st.column_config.SelectboxColumn("Status", options=STATUSES, default="Lead"),
        "Notes": st.column_config.TextColumn("Notes", width="large"),
    },
)

c1, c2 = st.columns([1, 3])
if c1.button("💾 Save", type="primary"):
    _save(edited)
    st.success("Saved to data/applications.xlsx")
c2.download_button(
    "⬇️ Excel",
    data=_to_excel_bytes(edited),
    file_name="applications.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# --- Follow-up timeline ----------------------------------------------------
st.subheader("Follow-ups")
fu = edited.copy()
fu["Next date"] = pd.to_datetime(fu["Next date"], errors="coerce")
fu = fu.dropna(subset=["Next date"]).sort_values("Next date")
fu = fu[~fu["Status"].isin(CLOSED)]
if fu.empty:
    st.info("No upcoming follow-ups. Set a 'Next date' on an application to see it here.")
else:
    today = pd.Timestamp(date.today())
    for _, row in fu.iterrows():
        when = row["Next date"].date()
        overdue = row["Next date"] < today
        flag = "🔴 overdue" if overdue else "🟢"
        st.markdown(
            f"**{when}** {flag} — **{row['Company'] or '—'}** · {row['Role'] or ''} "
            f"· _{row['Status'] or ''}_ → {row['Next action'] or '—'}"
        )

"""Standalone local tracker — Tracker + live Vacatures tabs.

Run on your own machine:  streamlit run tracker.py
(The same private area is also available, password-gated, inside app.py.)

PRIVACY: data is stored locally in data/applications.xlsx (git-ignored) and is
never uploaded. Optional password: set PRIVATE_PASSWORD in .streamlit/secrets.toml.
"""

from __future__ import annotations

import streamlit as st

import private

st.set_page_config(page_title="Application tracker", page_icon="🔒", layout="wide")
st.title("🔒 Application tracker")
st.caption("Private — stored locally in data/applications.xlsx (git-ignored), never uploaded.")

if private.unlock(require_password=False):
    t1, t2, t3 = st.tabs(["📋 Tracker", "🔎 Vacatures (live)", "✍️ Op maat"])
    with t1:
        private.render_tracker()
    with t2:
        private.render_vacancies()
    with t3:
        try:
            private.render_tailor()
        except Exception as exc:  # noqa: BLE001
            st.error(f"'Op maat' kon niet laden: {exc}. Reboot de app voor de nieuwste code.")

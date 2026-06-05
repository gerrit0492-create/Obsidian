"""Car Charging Costs — a Streamlit dashboard over EV charger meterdata.

Reads the charger's CSV export (upload one, use the bundled sample, or fetch
from the charger on your local network) and shows cost/energy KPIs, monthly
trends, a per-card breakdown, the session log, and Excel/CSV downloads.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from charging import load_sessions, monthly_by_car, monthly_summary, parse_metadata

DEFAULT_CSV = Path(__file__).parent / "data" / "sample_meterdata.csv"
CHARGER_URL = "http://pblr-0012237.local/charging-history"

st.set_page_config(page_title="Car Charging Costs", page_icon="🔌", layout="wide")
st.title("🔌 Car Charging Costs")


def _setting(name: str, default: str = "") -> str:
    """Read a setting from Streamlit secrets, falling back to env vars."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


def _require_password() -> None:
    expected = _setting("APP_PASSWORD")
    if not expected or st.session_state.get("authed"):
        return
    pw = st.text_input("Password", type="password")
    if pw and pw == expected:
        st.session_state["authed"] = True
        return
    if pw:
        st.error("Wrong password.")
    st.stop()


def _car_map() -> dict:
    raw = _setting("CAR_MAP")
    if not raw:
        return {}
    try:
        return {str(k): str(v) for k, v in json.loads(raw).items()}
    except Exception:
        return {}


_require_password()

# --- Data source -----------------------------------------------------------
st.sidebar.header("Data")
uploaded = st.sidebar.file_uploader("Upload meterdata CSV", type=["csv"])

source_text: str | None = None
if uploaded is not None:
    source_text = uploaded.getvalue().decode("utf-8", "replace")
else:
    with st.sidebar.expander("Fetch from charger (same network only)"):
        url = st.text_input("Charger URL", value=CHARGER_URL)
        if st.button("Fetch now"):
            try:
                import requests

                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                source_text = resp.text
                st.success("Fetched from charger.")
            except Exception as exc:  # noqa: BLE001
                st.error(
                    f"Couldn't reach the charger: {exc}. This only works when the app "
                    "runs on the same network as the charger."
                )
    if source_text is None and DEFAULT_CSV.exists():
        source_text = DEFAULT_CSV.read_text(encoding="utf-8")
        st.sidebar.caption("Showing bundled sample data — upload a CSV to use your own.")

if not source_text:
    st.info("Upload a meterdata CSV in the sidebar to begin.")
    st.stop()

meta = parse_metadata(source_text)
df = load_sessions(io.StringIO(source_text), car_map=_car_map())

caption = []
if meta.serial:
    caption.append(f"Charger {meta.serial}")
if meta.period_from:
    caption.append(f"{meta.period_from[:10]} → {meta.period_to[:10]}")
if caption:
    st.caption(" · ".join(caption))

# --- Filters ---------------------------------------------------------------
st.sidebar.header("Filters")
min_d, max_d = df["start"].min().date(), df["start"].max().date()
date_range = st.sidebar.date_input(
    "Date range", (min_d, max_d), min_value=min_d, max_value=max_d
)
cars = sorted(df["car"].dropna().unique())
chosen = st.sidebar.multiselect("Cars", cars, default=cars)

mask = df["car"].isin(chosen)
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_d, end_d = date_range
    mask &= (df["date"] >= start_d) & (df["date"] <= end_d)
fdf = df[mask].copy()

if fdf.empty:
    st.warning("No sessions match the current filters.")
    st.stop()

# --- KPIs ------------------------------------------------------------------
total_cost = fdf["cost"].sum()
total_kwh = fdf["energy_kwh"].sum()
n_sessions = int((fdf["energy_kwh"] > 0).sum())
avg_cost = total_cost / n_sessions if n_sessions else 0.0
eur_per_kwh = total_cost / total_kwh if total_kwh else 0.0
total_hours = fdf["duration_h"].sum()

k = st.columns(5)
k[0].metric("Charging sessions", f"{n_sessions}")
k[1].metric("Energy", f"{total_kwh:,.1f} kWh")
k[2].metric("Cost", f"€{total_cost:,.2f}")
k[3].metric("Avg €/session", f"€{avg_cost:,.2f}")
k[4].metric("Effective €/kWh", f"€{eur_per_kwh:,.3f}")

st.divider()

# --- Monthly trends --------------------------------------------------------
msum = monthly_summary(fdf)
left, right = st.columns(2)
with left:
    st.subheader("Cost per month (by car)")
    mbc = monthly_by_car(fdf)
    fig = px.bar(mbc, x="month", y="cost", color="car", text_auto=".0f")
    fig.update_layout(yaxis_title="€", xaxis_title="", legend_title="")
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("Energy per month")
    fig = px.bar(msum, x="month", y="energy_kwh", text_auto=".0f")
    fig.update_layout(yaxis_title="kWh", xaxis_title="", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# --- Cumulative cost + per-card --------------------------------------------
left, right = st.columns([3, 2])
with left:
    st.subheader("Cumulative cost")
    cum = fdf.sort_values("start")
    cum = cum.assign(cumulative_cost=cum["cost"].cumsum())
    fig = px.area(cum, x="start", y="cumulative_cost")
    fig.update_layout(yaxis_title="€", xaxis_title="")
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("By car")
    by_car = (
        fdf.groupby("car")
        .agg(sessions=("session", "count"), energy_kwh=("energy_kwh", "sum"), cost=("cost", "sum"))
        .reset_index()
    )
    fig = px.bar(by_car, x="car", y="cost", color="car", text_auto=".2f")
    fig.update_layout(yaxis_title="€", xaxis_title="", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# --- Session log + downloads ----------------------------------------------
st.subheader("Sessions")
show = (
    fdf[["session", "start", "stop", "energy_kwh", "cost", "duration_h", "car", "validation"]]
    .sort_values("start", ascending=False)
    .rename(
        columns={
            "session": "Session",
            "start": "Start",
            "stop": "Stop",
            "energy_kwh": "kWh",
            "cost": "Cost (€)",
            "duration_h": "Hours",
            "car": "Car",
            "validation": "Validation",
        }
    )
)
st.dataframe(show, use_container_width=True, hide_index=True)


def to_excel(sessions: pd.DataFrame, months: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        sessions.to_excel(xl, sheet_name="Sessions", index=False)
        months.to_excel(xl, sheet_name="Monthly", index=False)
    return buf.getvalue()


d1, d2 = st.columns(2)
d1.download_button(
    "⬇️ Excel",
    to_excel(show, msum),
    file_name="charging_costs.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
d2.download_button(
    "⬇️ CSV",
    show.to_csv(index=False).encode("utf-8"),
    file_name="charging_sessions.csv",
    mime="text/csv",
)

# --- Home energy (HomeWizard P1) ------------------------------------------
st.divider()
st.subheader("🏠 Home energy (HomeWizard P1)")
st.caption(
    "Live reading from your P1 meter — works when this app runs on your home network. "
    "Enable the Local API in the HomeWizard app (v1), or paste a v2 token."
)
h1, h2, h3 = st.columns(3)
hw_host = h1.text_input("P1 address (IP or hostname)", value="")
hw_token = h2.text_input("v2 token (optional)", type="password")
home_price = h3.number_input("Home €/kWh", min_value=0.0, value=0.35, step=0.01, format="%.2f")

if st.button("Read P1 now"):
    if not hw_host.strip():
        st.error("Enter your P1 meter's IP address or hostname.")
    else:
        try:
            from homewizard import fetch

            r = fetch(hw_host.strip(), token=hw_token.strip() or None)
            m = st.columns(4)
            m[0].metric("Live power", f"{r.active_power_w:,.0f} W" if r.active_power_w is not None else "—")
            m[1].metric("Imported (lifetime)", f"{r.import_kwh:,.0f} kWh" if r.import_kwh is not None else "—")
            m[2].metric("Exported (lifetime)", f"{r.export_kwh:,.0f} kWh" if r.export_kwh is not None else "—")
            if r.import_kwh is not None:
                m[3].metric("Home cost (lifetime)", f"€{r.import_kwh * home_price:,.0f}")
            if r.import_kwh:
                share = total_kwh / r.import_kwh * 100
                st.info(
                    f"Car charging in view ({total_kwh:,.0f} kWh) is ~{share:.1f}% of the home's "
                    f"lifetime imported energy ({r.import_kwh:,.0f} kWh). Note: the home figure is "
                    "lifetime, the car figure is the selected period — for a true side-by-side, "
                    "log P1 readings over time."
                )
        except Exception as exc:  # noqa: BLE001
            st.error(
                f"Couldn't read the P1 meter: {exc}. This only works on the same network as the "
                "device (and the Local API must be enabled in the HomeWizard app for v1)."
            )

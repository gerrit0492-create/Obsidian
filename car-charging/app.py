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

from charging import (
    daily_summary,
    load_sessions,
    monthly_by_car,
    monthly_effective_price,
    monthly_summary,
    parse_metadata,
)

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

# Month-over-month deltas (latest full month vs the previous one), shown on the cards.
_msum = monthly_summary(fdf)
d_sessions = d_energy = d_cost = None
if len(_msum) >= 2:
    last, prev = _msum.iloc[-1], _msum.iloc[-2]
    d_sessions = f"{int(last['sessions'] - prev['sessions']):+d}"
    d_energy = f"{last['energy_kwh'] - prev['energy_kwh']:+,.1f} kWh"
    d_cost = f"€{last['cost'] - prev['cost']:+,.2f}"

k = st.columns(5)
k[0].metric("Charging sessions", f"{n_sessions}", delta=d_sessions)
k[1].metric("Energy", f"{total_kwh:,.1f} kWh", delta=d_energy)
k[2].metric("Cost", f"€{total_cost:,.2f}", delta=d_cost, delta_color="inverse")
k[3].metric("Avg €/session", f"€{avg_cost:,.2f}")
k[4].metric("Effective €/kWh", f"€{eur_per_kwh:,.3f}")
if d_cost is not None:
    st.caption("Δ on cards = latest month vs the previous month.")

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

# --- Charging habits -------------------------------------------------------
st.divider()
st.subheader("When you charge")
hab = fdf.dropna(subset=["start"]).copy()
left, right = st.columns([3, 1])
with left:
    hab["hour"] = hab["start"].dt.hour
    hab["weekday"] = hab["start"].dt.day_name()
    weekday_order = [
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
    ]
    fig = px.density_heatmap(
        hab,
        x="hour",
        y="weekday",
        z="energy_kwh",
        histfunc="sum",
        nbinsx=24,
        category_orders={"weekday": weekday_order},
        color_continuous_scale="Blues",
    )
    fig.update_layout(
        xaxis_title="Hour of day", yaxis_title="", coloraxis_colorbar_title="kWh"
    )
    fig.update_xaxes(dtick=2, range=[-0.5, 23.5])
    st.plotly_chart(fig, use_container_width=True)
with right:
    start_frac = hab["start"].dt.hour + hab["start"].dt.minute / 60.0
    if not start_frac.empty:
        avg_h = start_frac.mean()
        st.metric("Typical plug-in time", f"{int(avg_h):02d}:{int((avg_h % 1) * 60):02d}")
    night = hab[(hab["hour"] >= 23) | (hab["hour"] < 7)]["energy_kwh"].sum()
    night_share = night / hab["energy_kwh"].sum() * 100 if hab["energy_kwh"].sum() else 0
    st.metric("Charged 23:00–07:00", f"{night_share:.0f}%")

# --- Charge speed ----------------------------------------------------------
st.divider()
st.subheader("Charge speed")
sp = fdf.dropna(subset=["power_kw"])
left, right = st.columns(2)
with left:
    st.caption("Distribution of average power per session")
    fig = px.histogram(sp, x="power_kw", nbins=20)
    fig.update_layout(xaxis_title="kW", yaxis_title="Sessions", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.caption("Average power by car")
    by_car_power = sp.groupby("car")["power_kw"].mean().reset_index()
    fig = px.bar(by_car_power, x="car", y="power_kw", color="car", text_auto=".1f")
    fig.update_layout(yaxis_title="kW", xaxis_title="", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# --- Daily trend + forecast ------------------------------------------------
st.divider()
st.subheader("Daily trend & forecast")
daily = daily_summary(fdf)
daily["cost_7d_avg"] = daily["cost"].rolling(7, min_periods=1).mean()
fig = px.bar(daily, x="date", y="cost")
fig.add_scatter(x=daily["date"], y=daily["cost_7d_avg"], mode="lines", name="7-day avg")
fig.update_layout(yaxis_title="€", xaxis_title="", legend_title="")
st.plotly_chart(fig, use_container_width=True)

span_days = (fdf["date"].max() - fdf["date"].min()).days + 1
avg_daily_cost = total_cost / span_days if span_days else 0.0
avg_daily_kwh = total_kwh / span_days if span_days else 0.0
f = st.columns(3)
f[0].metric("Avg cost / day", f"€{avg_daily_cost:,.2f}")
f[1].metric("Projected / month", f"€{avg_daily_cost * 30:,.2f}")
f[2].metric("Projected / year", f"€{avg_daily_cost * 365:,.0f}")
st.caption(
    f"Run-rate projection from {avg_daily_kwh:,.1f} kWh/day over the selected "
    f"{span_days}-day period — not a seasonal forecast."
)

# --- Price drift -----------------------------------------------------------
st.divider()
st.subheader("Effective price per kWh over time")
mprice = monthly_effective_price(fdf)
fig = px.line(mprice, x="month", y="eur_per_kwh", markers=True)
fig.update_layout(yaxis_title="€/kWh", xaxis_title="")
if pd.notna(meta.price_per_kwh):
    fig.add_hline(
        y=meta.price_per_kwh,
        line_dash="dot",
        annotation_text=f"charger setting €{meta.price_per_kwh:.3f}",
        annotation_position="top left",
    )
st.plotly_chart(fig, use_container_width=True)

# --- Cost per 100 km (estimate) -------------------------------------------
st.divider()
st.subheader("Cost per 100 km (estimate)")
st.caption("Enter each car's consumption to turn energy into running cost.")
eff_cols = st.columns(len(chosen) or 1)
effs = {
    car: eff_cols[i].number_input(
        f"{car} — kWh/100km", min_value=1.0, value=18.0, step=0.5, key=f"eff_{car}"
    )
    for i, car in enumerate(chosen)
}
per100_rows = []
for car in chosen:
    sub = fdf[fdf["car"] == car]
    energy = sub["energy_kwh"].sum()
    cost = sub["cost"].sum()
    eff = effs[car]
    km = energy / eff * 100 if eff else 0.0
    per100_rows.append(
        {
            "Car": car,
            "kWh": round(energy, 1),
            "Est. km": round(km),
            "Cost (€)": round(cost, 2),
            "€/100km": round(cost / km * 100, 2) if km else 0.0,
        }
    )
per100 = pd.DataFrame(per100_rows)
st.dataframe(per100, use_container_width=True, hide_index=True)

# --- Session log + downloads ----------------------------------------------
st.divider()
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


def to_excel(
    sessions: pd.DataFrame,
    months: pd.DataFrame,
    by_car: pd.DataFrame,
    days: pd.DataFrame,
    price: pd.DataFrame,
    per_100km: pd.DataFrame,
) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        sessions.to_excel(xl, sheet_name="Sessions", index=False)
        months.to_excel(xl, sheet_name="Monthly", index=False)
        by_car.to_excel(xl, sheet_name="By car", index=False)
        days.to_excel(xl, sheet_name="Daily", index=False)
        price.to_excel(xl, sheet_name="Effective price", index=False)
        per_100km.to_excel(xl, sheet_name="Cost per 100km", index=False)
    return buf.getvalue()


d1, d2 = st.columns(2)
d1.download_button(
    "⬇️ Excel",
    to_excel(show, msum, by_car, daily, mprice, per100),
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

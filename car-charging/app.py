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
    split_peak_offpeak,
)

DEFAULT_CSV = Path(__file__).parent / "data" / "sample_meterdata.csv"
CHARGER_URL = "http://pblr-0012237.local/charging-history"

st.set_page_config(page_title="Car Charging Costs", page_icon="🔌", layout="wide")
st.title("🔌 Car Charging Costs")

# A fixed, high-contrast qualitative palette so each car keeps one colour
# across every chart in the app (the actual map is built once cars are known).
CAR_PALETTE = px.colors.qualitative.Bold
INK = "#1f2a44"


def style_fig(fig, *, legend: bool = True):
    """Apply one consistent, professional look to every Plotly figure."""
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Inter, Segoe UI, Helvetica, sans-serif", size=13, color=INK),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=""),
        hoverlabel=dict(font_size=12),
        showlegend=legend,
        bargap=0.18,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#eef1f6", zeroline=False)
    return fig


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


def _car_wltp() -> dict:
    """Map car name -> manufacturer WLTP consumption (kWh/100km), from CAR_WLTP."""
    raw = _setting("CAR_WLTP")
    if not raw:
        return {}
    try:
        return {str(k): float(v) for k, v in json.loads(raw).items()}
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

# One colour per car, stable across every chart and regardless of the filter.
CAR_COLOR = {car: CAR_PALETTE[i % len(CAR_PALETTE)] for i, car in enumerate(cars)}

# Day/night (dal) tariff settings — drive the "Best time to charge" view.
st.sidebar.header("Tariff (day/night)")
st.sidebar.caption(
    "Your real home prices. Both default to the charger's logged price; set a "
    "lower dal price to estimate day/night savings."
)
# Default to the charger's own price so figures match the CSV until you set a split.
default_price = round(float(meta.price_per_kwh), 2) if pd.notna(meta.price_per_kwh) else 0.30
dal_start = st.sidebar.number_input("Off-peak starts (hour)", 0, 23, 23)
dal_end = st.sidebar.number_input("Off-peak ends (hour)", 0, 23, 7)
weekend_off = st.sidebar.checkbox("Weekends fully off-peak", value=True)
price_normaal = st.sidebar.number_input(
    "Peak €/kWh (normaal)", min_value=0.0, value=default_price, step=0.01, format="%.2f"
)
price_dal = st.sidebar.number_input(
    "Off-peak €/kWh (dal)", min_value=0.0, value=default_price, step=0.01, format="%.2f"
)


def hour_is_off(hour: int) -> bool:
    """Off-peak by clock hour only (ignores the weekend rule), for shading charts."""
    if dal_start <= dal_end:
        return dal_start <= hour < dal_end
    return hour >= dal_start or hour < dal_end

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
mbc = monthly_by_car(fdf)
left, right = st.columns(2)
with left:
    st.subheader("Cost per month")
    fig = px.bar(
        mbc, x="month", y="cost", color="car", text_auto=".2f",
        color_discrete_map=CAR_COLOR, category_orders={"car": cars},
    )
    fig.update_traces(hovertemplate="%{x}<br>%{fullData.name}: €%{y:.2f}<extra></extra>")
    fig.update_layout(barmode="stack", yaxis_title="€", xaxis_title="", yaxis_tickprefix="€")
    st.plotly_chart(style_fig(fig), use_container_width=True)
with right:
    st.subheader("Energy per month")
    fig = px.bar(
        mbc, x="month", y="energy_kwh", text_auto=".0f", color="car",
        color_discrete_map=CAR_COLOR, category_orders={"car": cars},
    )
    fig.update_traces(hovertemplate="%{x}<br>%{fullData.name}: %{y:.1f} kWh<extra></extra>")
    fig.update_layout(barmode="stack", yaxis_title="kWh", xaxis_title="", yaxis_ticksuffix=" kWh")
    st.plotly_chart(style_fig(fig), use_container_width=True)

# --- Cumulative cost + cost share -----------------------------------------
left, right = st.columns([3, 2])
with left:
    st.subheader("Cumulative cost by car")
    cum = fdf.sort_values("start").copy()
    cum["cumulative_cost"] = cum.groupby("car")["cost"].cumsum()
    fig = px.area(
        cum, x="start", y="cumulative_cost", color="car",
        color_discrete_map=CAR_COLOR, category_orders={"car": cars},
    )
    fig.update_traces(hovertemplate="%{x|%d %b %Y}<br>%{fullData.name}: €%{y:.2f}<extra></extra>")
    fig.update_layout(yaxis_title="€", xaxis_title="", yaxis_tickprefix="€")
    st.plotly_chart(style_fig(fig), use_container_width=True)
with right:
    st.subheader("Cost share by car")
    by_car = (
        fdf.groupby("car")
        .agg(sessions=("session", "count"), energy_kwh=("energy_kwh", "sum"), cost=("cost", "sum"))
        .reset_index()
    )
    fig = px.pie(
        by_car, names="car", values="cost", hole=0.55,
        color="car", color_discrete_map=CAR_COLOR, category_orders={"car": cars},
    )
    fig.update_traces(
        textposition="inside",
        texttemplate="%{label}<br>€%{value:.0f}",
        hovertemplate="%{label}: €%{value:.2f} (%{percent})<extra></extra>",
    )
    fig.update_layout(
        annotations=[dict(text=f"€{total_cost:,.0f}", x=0.5, y=0.5, font_size=18, showarrow=False)]
    )
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

# --- Charging habits -------------------------------------------------------
st.divider()
st.subheader("When you charge")
hab = fdf.dropna(subset=["start"]).copy()
hab["hour"] = hab["start"].dt.hour
hab["weekday"] = hab["start"].dt.day_name()
weekday_order = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]
left, right = st.columns([3, 1])
with left:
    fig = px.density_heatmap(
        hab,
        x="hour",
        y="weekday",
        z="energy_kwh",
        histfunc="sum",
        nbinsx=24,
        category_orders={"weekday": weekday_order},
        color_continuous_scale="Tealgrn",
    )
    fig.update_traces(hovertemplate="%{y} at %{x}:00<br>%{z:.1f} kWh<extra></extra>")
    fig.update_layout(
        xaxis_title="Hour of day", yaxis_title="",
        coloraxis_colorbar=dict(title="kWh", thickness=12),
    )
    fig.update_xaxes(dtick=2, range=[-0.5, 23.5])
    # Outline the off-peak (dal) hours so habits can be read against the tariff.
    off_hours = [h for h in range(24) if hour_is_off(h)]
    for h in off_hours:
        fig.add_vrect(x0=h - 0.5, x1=h + 0.5, fillcolor="#2a9d8f", opacity=0.10, line_width=0)
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)
with right:
    total_hab = hab["energy_kwh"].sum()
    start_frac = hab["start"].dt.hour + hab["start"].dt.minute / 60.0
    if not start_frac.empty:
        avg_h = start_frac.mean()
        st.metric("Typical plug-in time", f"{int(avg_h):02d}:{int((avg_h % 1) * 60):02d}")
    night = hab[(hab["hour"] >= 23) | (hab["hour"] < 7)]["energy_kwh"].sum()
    st.metric("Charged 23:00–07:00", f"{night / total_hab * 100 if total_hab else 0:.0f}%")
    weekend = hab[hab["weekday"].isin(["Saturday", "Sunday"])]["energy_kwh"].sum()
    st.metric("Weekend share", f"{weekend / total_hab * 100 if total_hab else 0:.0f}%")

# --- Best time to charge (day/night tariff) -------------------------------
st.divider()
st.subheader("⏰ Best time to charge")
split = split_peak_offpeak(
    fdf, dal_start=int(dal_start), dal_end=int(dal_end), weekend_offpeak=weekend_off
)
off_kwh = split["energy_offpeak"].sum()
peak_kwh = split["energy_peak"].sum()
tou_total = off_kwh + peak_kwh
off_share = off_kwh / tou_total * 100 if tou_total else 0.0
home_cost = off_kwh * price_dal + peak_kwh * price_normaal
all_off_cost = tou_total * price_dal
savings = peak_kwh * (price_normaal - price_dal)
window_txt = f"{int(dal_start):02d}:00–{int(dal_end):02d}:00" + (
    " + weekends" if weekend_off else ""
)

c = st.columns(4)
c[0].metric("Charged off-peak", f"{off_share:.0f}%")
c[1].metric("Cost at home tariff", f"€{home_cost:,.2f}")
c[2].metric("If all off-peak", f"€{all_off_cost:,.2f}")
c[3].metric("Potential saving", f"€{savings:,.2f}")
st.caption(
    "What-if on your **home** day/night tariff (sidebar) — separate from the flat "
    "price the charger logs in the CSV."
)

if abs(price_normaal - price_dal) < 1e-9:
    st.info(
        "Set a lower **off-peak (dal)** price than **peak (normaal)** in the sidebar "
        "to estimate day/night savings — both currently match the charger's flat price, "
        "so there's nothing to compare yet."
    )
elif savings > 0.01:
    st.success(
        f"**Charge during the dal window ({window_txt}).** You charged {off_share:.0f}% "
        f"off-peak — shifting the rest would save about €{savings:,.2f} at "
        f"€{price_normaal:.2f}/€{price_dal:.2f} per kWh (peak/off-peak)."
    )
else:
    st.success(
        f"Nicely timed — almost all of your charging already falls in the dal window "
        f"({window_txt})."
    )

left, right = st.columns(2)
with left:
    st.caption("Off-peak vs peak energy by car")
    tou = (
        split.groupby("car")[["energy_offpeak", "energy_peak"]]
        .sum()
        .reset_index()
        .melt(id_vars="car", var_name="period", value_name="kwh")
    )
    tou["period"] = tou["period"].map({"energy_offpeak": "Off-peak", "energy_peak": "Peak"})
    fig = px.bar(
        tou, x="car", y="kwh", color="period", barmode="stack",
        color_discrete_map={"Off-peak": "#2a9d8f", "Peak": "#e9c46a"},
    )
    fig.update_layout(yaxis_title="kWh", xaxis_title="", yaxis_ticksuffix=" kWh")
    st.plotly_chart(style_fig(fig), use_container_width=True)
with right:
    st.caption("Energy by hour of day (green = off-peak)")
    hh = split.dropna(subset=["start"]).copy()
    hh["hour"] = hh["start"].dt.hour
    by_hour = (
        hh.groupby("hour")["energy_kwh"].sum().reindex(range(24), fill_value=0).reset_index()
    )
    by_hour["period"] = by_hour["hour"].map(lambda h: "Off-peak" if hour_is_off(h) else "Peak")
    fig = px.bar(
        by_hour, x="hour", y="energy_kwh", color="period",
        color_discrete_map={"Off-peak": "#2a9d8f", "Peak": "#e9c46a"},
    )
    fig.update_layout(yaxis_title="kWh", xaxis_title="Hour of day", yaxis_ticksuffix=" kWh")
    fig.update_xaxes(dtick=2)
    st.plotly_chart(style_fig(fig), use_container_width=True)

tou_summary = pd.DataFrame(
    {
        "Period": ["Off-peak (dal)", "Peak (normaal)", "Total"],
        "kWh": [round(off_kwh, 1), round(peak_kwh, 1), round(tou_total, 1)],
        "Price (€/kWh)": [price_dal, price_normaal, None],
        "Cost (€)": [
            round(off_kwh * price_dal, 2),
            round(peak_kwh * price_normaal, 2),
            round(home_cost, 2),
        ],
    }
)

# --- Charge speed ----------------------------------------------------------
st.divider()
st.subheader("Charge speed")
sp = fdf.dropna(subset=["power_kw"])
left, right = st.columns(2)
with left:
    st.caption("Power per session, spread by car")
    fig = px.box(
        sp, x="car", y="power_kw", color="car", points="all",
        color_discrete_map=CAR_COLOR, category_orders={"car": cars},
    )
    fig.update_layout(yaxis_title="kW", xaxis_title="", yaxis_ticksuffix=" kW")
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)
with right:
    st.caption("Average power by car")
    by_car_power = sp.groupby("car")["power_kw"].mean().reset_index()
    fig = px.bar(
        by_car_power, x="car", y="power_kw", color="car", text_auto=".1f",
        color_discrete_map=CAR_COLOR, category_orders={"car": cars},
    )
    fig.update_traces(hovertemplate="%{x}: %{y:.2f} kW<extra></extra>")
    fig.update_layout(yaxis_title="kW", xaxis_title="", yaxis_ticksuffix=" kW")
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

# --- Daily trend + forecast ------------------------------------------------
st.divider()
st.subheader("Daily trend & forecast")
daily = daily_summary(fdf)
daily["cost_7d_avg"] = daily["cost"].rolling(7, min_periods=1).mean()
daily_by_car = fdf.groupby(["date", "car"])["cost"].sum().reset_index()
fig = px.bar(
    daily_by_car, x="date", y="cost", color="car",
    color_discrete_map=CAR_COLOR, category_orders={"car": cars},
)
fig.add_scatter(
    x=daily["date"], y=daily["cost_7d_avg"], mode="lines", name="7-day avg",
    line=dict(color=INK, width=2, dash="dot"),
)
fig.update_layout(barmode="stack", yaxis_title="€", xaxis_title="", yaxis_tickprefix="€")
st.plotly_chart(style_fig(fig), use_container_width=True)

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
mprice_car = (
    fdf.groupby(["month", "car"])
    .agg(energy_kwh=("energy_kwh", "sum"), cost=("cost", "sum"))
    .reset_index()
)
mprice_car["eur_per_kwh"] = mprice_car["cost"] / mprice_car["energy_kwh"]
fig = px.line(
    mprice_car, x="month", y="eur_per_kwh", color="car", markers=True,
    color_discrete_map=CAR_COLOR, category_orders={"car": cars},
)
fig.update_traces(hovertemplate="%{x}<br>%{fullData.name}: €%{y:.3f}/kWh<extra></extra>")
fig.update_layout(yaxis_title="€/kWh", xaxis_title="", yaxis_tickprefix="€")
if pd.notna(meta.price_per_kwh):
    fig.add_hline(
        y=meta.price_per_kwh,
        line_dash="dot",
        line_color="#888",
        annotation_text=f"charger setting €{meta.price_per_kwh:.3f}",
        annotation_position="top left",
    )
st.plotly_chart(style_fig(fig), use_container_width=True)

# --- Cost per 100 km (estimate) -------------------------------------------
st.divider()
st.subheader("Cost per 100 km (estimate)")
st.caption(
    "Defaults to each car's manufacturer WLTP consumption (set via the CAR_WLTP "
    "secret); adjust for your real-world driving."
)
wltp = _car_wltp()
eff_cols = st.columns(len(chosen) or 1)
effs = {
    car: eff_cols[i].number_input(
        f"{car} — kWh/100km" + (" (WLTP)" if car in wltp else ""),
        min_value=1.0,
        value=float(wltp.get(car, 18.0)),
        step=0.5,
        key=f"eff_{car}",
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
left, right = st.columns([2, 3])
with left:
    st.dataframe(per100, use_container_width=True, hide_index=True)
with right:
    if not per100.empty:
        fig = px.bar(
            per100, x="Car", y="€/100km", color="Car", text_auto=".2f",
            color_discrete_map=CAR_COLOR, category_orders={"Car": cars},
        )
        fig.update_traces(hovertemplate="%{x}: €%{y:.2f}/100km<extra></extra>")
        fig.update_layout(yaxis_title="€/100km", xaxis_title="", yaxis_tickprefix="€")
        st.plotly_chart(style_fig(fig, legend=False), use_container_width=True)

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


def _number_format(col: str) -> str | None:
    name = str(col).lower()
    if "per_kwh" in name:
        return "€#,##0.000"
    if "cost" in name or "€" in str(col) or "eur" in name:
        return "€#,##0.00"
    if "kwh" in name:
        return "#,##0.0"
    if "km" in name:
        return "#,##0"
    return None


def to_excel(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Write a formatted, multi-sheet workbook with native charts."""
    from openpyxl.chart import BarChart, Reference
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        for name, frame in sheets.items():
            frame.to_excel(xl, sheet_name=name, index=False)
        wb = xl.book
        header_fill = PatternFill("solid", fgColor="1F2A44")
        header_font = Font(bold=True, color="FFFFFF")
        for name, frame in sheets.items():
            ws = wb[name]
            for col_idx, col in enumerate(frame.columns, start=1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill, cell.font = header_fill, header_font
                cell.alignment = Alignment(horizontal="center")
                values = [str(v) for v in frame[col]] if len(frame) else []
                width = max([len(str(col))] + [len(v) for v in values]) + 2
                ws.column_dimensions[get_column_letter(col_idx)].width = min(max(width, 11), 42)
                fmt = _number_format(col)
                if fmt and len(frame):
                    for row in range(2, len(frame) + 2):
                        ws.cell(row=row, column=col_idx).number_format = fmt
            ws.freeze_panes = "A2"
            if len(frame):
                ws.auto_filter.ref = ws.dimensions

        def add_bar(sheet: str, value_col: int, title: str, anchor: str) -> None:
            ws = wb[sheet]
            if ws.max_row < 2:
                return
            chart = BarChart()
            chart.type, chart.title, chart.legend = "col", title, None
            chart.height, chart.width = 8, 18
            chart.add_data(
                Reference(ws, min_col=value_col, min_row=1, max_row=ws.max_row),
                titles_from_data=True,
            )
            chart.set_categories(Reference(ws, min_col=1, min_row=2, max_row=ws.max_row))
            ws.add_chart(chart, anchor)

        add_bar("Monthly", 4, "Cost per month (€)", "F2")
        add_bar("By car", 4, "Cost by car (€)", "F2")
        add_bar("Cost per 100km", 5, "€ per 100 km", "G2")
    return buf.getvalue()


summary = pd.DataFrame(
    {
        "Metric": [
            "Charging sessions", "Energy (kWh)", "Cost (€)", "Avg €/session",
            "Effective €/kWh", "Total charging hours", "Off-peak share (%)",
            "Period", "Cars",
        ],
        "Value": [
            n_sessions, round(total_kwh, 1), round(total_cost, 2), round(avg_cost, 2),
            round(eur_per_kwh, 3), round(total_hours, 1), round(off_share, 0),
            f"{fdf['date'].min()} → {fdf['date'].max()}", ", ".join(chosen),
        ],
    }
)

d1, d2 = st.columns(2)
d1.download_button(
    "⬇️ Excel",
    to_excel(
        {
            "Summary": summary,
            "Sessions": show,
            "Monthly": msum,
            "By car": by_car,
            "Daily": daily,
            "Effective price": mprice,
            "Peak vs off-peak": tou_summary,
            "Cost per 100km": per100,
        }
    ),
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
    "Direct read works on your home network. To read it from anywhere (e.g. this "
    "hosted app), point the relay URL at a Home Assistant endpoint that republishes "
    "the meter JSON — see the README."
)
h1, h2, h3 = st.columns(3)
hw_host = h1.text_input("P1 address (IP or hostname)", value="")
hw_token = h2.text_input("Token (optional)", type="password")
home_price = h3.number_input("Home €/kWh", min_value=0.0, value=0.35, step=0.01, format="%.2f")
hw_remote = st.text_input(
    "…or remote relay URL (works away from home)",
    value=_setting("P1_REMOTE_URL"),
    placeholder="https://your-relay.example/p1.json",
)

if st.button("Read P1 now"):
    if not hw_host.strip() and not hw_remote.strip():
        st.error("Enter your P1 meter's address, or a remote relay URL.")
    else:
        try:
            from homewizard import fetch, fetch_url

            token = hw_token.strip() or None
            if hw_remote.strip():
                r = fetch_url(hw_remote.strip(), token=token)
            else:
                r = fetch(hw_host.strip(), token=token)
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
                f"Couldn't read the P1 meter: {exc}. A direct address only works on the same "
                "network (enable the Local API in the HomeWizard app); from elsewhere, use a "
                "remote relay URL."
            )

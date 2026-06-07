"""Pure business-model math for the e-commerce planner — no Streamlit, unit-testable.

Unit economics (per product), a 12-month cash projection, and multi-sheet Excel
export. All money is in euros. Marketplace defaults model selling on Bol.nl (B2C,
consumer prices include 21% VAT). Numbers in DEFAULT_PRODUCTS / MARKET are
researched estimates to validate, not promises.
"""

from __future__ import annotations

import io

import pandas as pd

VAT = 0.21  # NL standard rate

# Bol.com-style marketplace defaults (all editable in the UI).
# Commission varies ~8-17% by category; a fixed fee applies per sold item.
BOL = {
    "commission_pct": 0.12,   # % of the consumer (incl-VAT) price
    "fixed_fee": 0.99,        # € per sold item
    "payment_pct": 0.02,      # payment/transaction handling
    "outbound": 3.50,         # shipping to the customer (LVB/PostNL)
    "returns_pct": 0.07,      # share of orders returned (electronics ~5-10%)
    "ad_per_unit": 3.00,      # advertising cost to acquire one sale (CAC)
}

# Researched, editable starting portfolio (home-energy / domotica beachhead).
# Cost = landed cost ex VAT (sourcing + inbound freight + any duty), per unit.
# Price = consumer price incl. VAT on Bol.nl.
DEFAULT_PRODUCTS = [
    {"Product": "Energy smart plug (single)", "Cost": 5.5, "Price": 19.95},
    {"Product": "Energy smart plug (2-pack)", "Cost": 9.5, "Price": 34.95},
    {"Product": "Zigbee starter kit (hub + 3 plugs + guide)", "Cost": 30.0, "Price": 89.0},
    {"Product": "Water-leak shut-off sensor", "Cost": 15.0, "Price": 44.95},
    {"Product": "Door/window sensor (3-pack)", "Cost": 8.0, "Price": 27.95},
    {"Product": "Radiator / draught saver kit", "Cost": 7.0, "Price": 24.95},
]

MARKET = {
    "stats": [
        ("NL smart-home market (2023)", "$1.25B", ""),
        ("NL smart-home market (2030)", "$5.10B", "22.3% CAGR"),
        ("Europe smart homes (2024)", "€25.3B", ""),
        ("Europe smart homes (2033)", "€44.0B", "6.3% CAGR"),
        ("Zigbee devices growth", "~9.2%/yr", "to 2035"),
        ("NL dog-owning households", "1.8M", "context: pet niche"),
    ],
    "segments": {
        "Security & access (cameras, locks, sensors)": 31.65,
        "Energy & smart appliances": 22.0,
        "Lighting": 18.0,
        "Comfort/other": 28.35,
    },
    "avoid": [
        "Thermostats — Tado, Nest, Honeywell own it",
        "Energy/P1 readers — HomeWizard (Dutch) dominates",
        "Smart lighting — Philips Hue / Signify (Dutch)",
        "Hubs & cameras — global giants, thin margins",
    ],
    "beachhead": [
        "DIY energy-saver / Home Assistant crowd — buys many cheap devices, repeatedly",
        "Open gap: trust & quality vetting ('smart plugs that won't burn down the house')",
        "They follow creators who test & prove — you can be that creator",
    ],
    "moat": [
        "Sell trust + proof, not a commodity device",
        "Publish measured '€X/year saved' content (your data + energy edge)",
        "Ship a free companion tool (savings calculator) that funnels to the shop",
        "Curated, certified bundles > single plugs (higher order value, your guide adds value)",
    ],
    "risks": [
        "Mains-voltage electronics = CE/RED certification + liability — resell certified white-label, don't build radios",
        "Commodity device margins are thin — profit lives in bundles, brand, content",
        "Start with battery/low-voltage sensors + accessories to limit liability",
    ],
    "sources": [
        ("Statista — NL Smart Home", "https://www.statista.com/outlook/279/144/smart-home/netherlands"),
        ("NextMSC — NL Smart Home to $5.1B", "https://www.nextmsc.com/news/netherlands-smart-home-market"),
        ("MarketDataForecast — Europe Smart Homes", "https://www.marketdataforecast.com/market-reports/europe-smart-homes-market"),
        ("Home Assistant community — safe smart plugs",
         "https://community.home-assistant.io/t/smart-plugs-in-the-netherlands-that-wont-burn-down-your-house/372528"),
    ],
}


def unit_economics(price_incl, cost_landed, commission_pct=BOL["commission_pct"],
                   fixed_fee=BOL["fixed_fee"], payment_pct=BOL["payment_pct"],
                   outbound=BOL["outbound"], returns_pct=BOL["returns_pct"],
                   ad_per_unit=BOL["ad_per_unit"], vat=VAT) -> dict:
    """Per-unit economics for one product sold on a Bol-style marketplace.

    Returns the full cost breakdown plus net profit, margin % (on ex-VAT revenue)
    and markup (price / landed cost). Returns assume half the returned goods are
    written off plus the outbound shipping is lost.
    """
    price_incl = float(price_incl or 0)
    cost_landed = float(cost_landed or 0)
    revenue_ex = price_incl / (1 + vat)
    vat_amount = price_incl - revenue_ex
    commission = price_incl * commission_pct
    payment = price_incl * payment_pct
    returns_cost = returns_pct * (outbound + 0.5 * cost_landed)
    total_cost = cost_landed + commission + fixed_fee + payment + outbound + returns_cost + ad_per_unit
    profit = revenue_ex - total_cost
    return {
        "price_incl": price_incl,
        "vat": vat_amount,
        "revenue_ex": revenue_ex,
        "cogs": cost_landed,
        "commission": commission,
        "fixed_fee": fixed_fee,
        "payment": payment,
        "outbound": outbound,
        "returns_cost": returns_cost,
        "ad": ad_per_unit,
        "total_cost": total_cost,
        "profit": profit,
        "margin_pct": (profit / revenue_ex) if revenue_ex else 0.0,
        "markup_x": (price_incl / cost_landed) if cost_landed else 0.0,
    }


def portfolio_table(products, **fees) -> pd.DataFrame:
    """Compute per-unit economics for a list of {Product, Cost, Price} dicts."""
    rows = []
    for p in products:
        e = unit_economics(p["Price"], p["Cost"], **fees)
        rows.append({
            "Product": p["Product"],
            "Cost (landed)": round(e["cogs"], 2),
            "Price (incl VAT)": round(e["price_incl"], 2),
            "Profit/unit": round(e["profit"], 2),
            "Margin %": round(e["margin_pct"] * 100, 1),
            "Markup": round(e["markup_x"], 2),
        })
    df = pd.DataFrame(rows)
    return df.sort_values("Profit/unit", ascending=False).reset_index(drop=True)


def project(units_m1, growth_pct, months, fixed_monthly, startup,
            profit_per_unit, revenue_ex_per_unit) -> tuple[pd.DataFrame, int | None]:
    """A simple month-by-month cash projection. Returns (dataframe, break_even_month)."""
    rows, cumulative, be_month = [], -abs(startup), None
    units = float(units_m1)
    for m in range(1, months + 1):
        u = round(units)
        revenue = u * revenue_ex_per_unit
        gross = u * profit_per_unit          # contribution (after variable costs)
        net = gross - fixed_monthly          # after monthly fixed costs
        cumulative += net
        if be_month is None and cumulative >= 0:
            be_month = m
        rows.append({
            "Month": m,
            "Units": u,
            "Revenue (ex VAT)": round(revenue, 0),
            "Gross profit": round(gross, 0),
            "Fixed costs": round(fixed_monthly, 0),
            "Net / month": round(net, 0),
            "Cumulative cash": round(cumulative, 0),
        })
        units *= (1 + growth_pct)
    return pd.DataFrame(rows), be_month


def df_to_excel_bytes(sheets: dict) -> bytes:
    """Write {sheet_name: DataFrame} to a single .xlsx workbook and return the bytes."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        for name, df in sheets.items():
            df.to_excel(xl, sheet_name=name[:31], index=False)
    return buf.getvalue()

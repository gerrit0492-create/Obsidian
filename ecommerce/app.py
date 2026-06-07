"""E-commerce planner — margin, portfolio, business case and market in one dashboard.

A planning tool for launching a home-energy / domotica (smart-home) webshop in NL.
Everything is editable; the pre-loaded numbers are researched estimates to validate,
not promises. Built for a cost engineer: the unit economics are explicit and the
whole analysis exports to Excel.

Run:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import model as m

st.set_page_config(page_title="E-commerce planner", page_icon="🛒", layout="wide")
st.title("🛒 E-commerce planner — home-energy / domotica")
st.caption("Plan margin, product mix, the business case and the market in one place. "
           "All numbers are editable estimates to validate — not promises.")


def eur(x: float) -> str:
    return f"€{x:,.2f}"


# --- Shared marketplace assumptions (sidebar) ------------------------------
st.sidebar.header("⚙️ Marketplace assumptions")
st.sidebar.caption("Defaults model selling on Bol.nl (B2C, prices incl. 21% VAT).")
fees = {
    "commission_pct": st.sidebar.slider("Commission %", 0.0, 25.0, m.BOL["commission_pct"] * 100, 0.5) / 100,
    "fixed_fee": st.sidebar.number_input("Fixed fee / item (€)", 0.0, 5.0, m.BOL["fixed_fee"], 0.05),
    "payment_pct": st.sidebar.slider("Payment %", 0.0, 5.0, m.BOL["payment_pct"] * 100, 0.1) / 100,
    "outbound": st.sidebar.number_input("Shipping to customer (€)", 0.0, 15.0, m.BOL["outbound"], 0.25),
    "returns_pct": st.sidebar.slider("Returns %", 0.0, 30.0, m.BOL["returns_pct"] * 100, 1.0) / 100,
    "ad_per_unit": st.sidebar.number_input("Ad cost / sale — CAC (€)", 0.0, 30.0, m.BOL["ad_per_unit"], 0.25),
}
st.sidebar.caption("Bol commission really varies ~8–17% by category. Tune these to your reality.")

tab_calc, tab_port, tab_case, tab_market = st.tabs(
    ["🧮 Margin calculator", "📦 Product portfolio", "📈 Business case", "🌍 Market & strategy"])


# --- 1. Margin calculator --------------------------------------------------
with tab_calc:
    st.subheader("Per-unit economics")
    c1, c2 = st.columns(2)
    price = c1.number_input("Consumer price (incl. VAT) €", 1.0, 1000.0, 89.0, 1.0)
    cost = c2.number_input("Landed cost / unit (ex VAT) €", 0.1, 800.0, 30.0, 0.5,
                           help="Sourcing + inbound freight + any import duty, per unit.")
    e = m.unit_economics(price, cost, **fees)

    k = st.columns(4)
    k[0].metric("Profit / unit", eur(e["profit"]))
    k[1].metric("Margin %", f"{e['margin_pct'] * 100:.1f}%")
    k[2].metric("Markup", f"{e['markup_x']:.2f}×")
    k[3].metric("Revenue ex VAT", eur(e["revenue_ex"]))

    if e["margin_pct"] < 0.10:
        st.error("⚠️ Margin under 10% — fees + ad cost eat this. Bundle it, raise the price, or cut CAC.")
    elif e["margin_pct"] < 0.20:
        st.warning("Thin margin (10–20%). Workable, but leaves little room for ads/returns.")
    else:
        st.success("Healthy margin (20%+). This is the kind of product/bundle to build on.")

    # Waterfall: revenue → costs → profit
    labels = ["Revenue ex VAT", "Product", "Commission", "Fixed fee", "Payment",
              "Shipping", "Returns", "Advertising", "Profit"]
    values = [e["revenue_ex"], -e["cogs"], -e["commission"], -e["fixed_fee"], -e["payment"],
              -e["outbound"], -e["returns_cost"], -e["ad"], e["profit"]]
    measure = ["absolute"] + ["relative"] * 7 + ["total"]
    fig = go.Figure(go.Waterfall(
        orientation="v", measure=measure, x=labels, y=values,
        connector={"line": {"color": "#cdd5df"}},
        decreasing={"marker": {"color": "#e76f51"}},
        increasing={"marker": {"color": "#2a9d8f"}},
        totals={"marker": {"color": "#16223d"}}))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10),
                      yaxis_title="€ per unit")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("ℹ️ How this is calculated"):
        st.markdown(
            "- **Revenue ex VAT** = price ÷ 1.21 (you remit the 21% VAT).\n"
            "- **Commission / payment** are charged on the consumer (incl-VAT) price.\n"
            "- **Returns** assume the outbound shipping is lost and half the returned goods written off.\n"
            "- **Profit** = revenue ex VAT − all of the above. Margin % is on ex-VAT revenue.")


# --- 2. Product portfolio --------------------------------------------------
with tab_port:
    st.subheader("Compare products — best margin on top")
    st.caption("Edit costs/prices or add rows. ‘Cost’ is landed cost ex VAT; ‘Price’ is incl. VAT.")
    seed = st.session_state.get("products", m.DEFAULT_PRODUCTS)
    edited = st.data_editor(
        pd.DataFrame(seed), num_rows="dynamic", use_container_width=True, key="port_edit",
        column_config={
            "Cost": st.column_config.NumberColumn("Cost (landed €)", format="%.2f"),
            "Price": st.column_config.NumberColumn("Price (incl VAT €)", format="%.2f"),
        })
    products = [r for r in edited.to_dict("records") if r.get("Product")]
    st.session_state["products"] = products

    table = m.portfolio_table(products, **fees)
    st.dataframe(
        table, use_container_width=True, hide_index=True,
        column_config={
            "Profit/unit": st.column_config.NumberColumn(format="€%.2f"),
            "Margin %": st.column_config.NumberColumn(format="%.1f%%"),
            "Cost (landed)": st.column_config.NumberColumn(format="€%.2f"),
            "Price (incl VAT)": st.column_config.NumberColumn(format="€%.2f"),
            "Markup": st.column_config.NumberColumn(format="%.2f×"),
        })

    if not table.empty:
        bar = go.Figure(go.Bar(
            x=table["Profit/unit"], y=table["Product"], orientation="h",
            marker_color=["#2a9d8f" if v >= 20 else "#e9c46a" if v >= 10 else "#e76f51"
                          for v in table["Margin %"]],
            text=[f"{p:.2f}€ · {mg:.0f}%" for p, mg in zip(table["Profit/unit"], table["Margin %"])]))
        bar.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                          xaxis_title="Profit / unit (€)", yaxis={"autorange": "reversed"})
        st.plotly_chart(bar, use_container_width=True)
        st.download_button("⬇️ Download portfolio (Excel)",
                           m.df_to_excel_bytes({"Portfolio": table}),
                           file_name="ecommerce_portfolio.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# --- 3. Business case ------------------------------------------------------
with tab_case:
    st.subheader("12-month business case")
    products = st.session_state.get("products", m.DEFAULT_PRODUCTS)
    names = [p["Product"] for p in products] or ["—"]
    default_idx = next((i for i, p in enumerate(products)
                        if "kit" in p["Product"].lower()), 0)
    pick = st.selectbox("Lead product (drives the projection)", names, index=default_idx)
    chosen = next((p for p in products if p["Product"] == pick), products[0] if products else
                  {"Price": 89.0, "Cost": 30.0})
    e = m.unit_economics(chosen["Price"], chosen["Cost"], **fees)

    a = st.columns(4)
    units1 = a[0].number_input("Units in month 1", 1, 5000, 40, 5)
    growth = a[1].slider("Monthly growth %", 0.0, 30.0, 10.0, 1.0) / 100
    fixed = a[2].number_input("Fixed costs / month €", 0.0, 5000.0, 150.0, 25.0,
                              help="Bol subscription, tools, storage, etc.")
    startup = a[3].number_input("Startup investment €", 0.0, 50000.0, 1500.0, 100.0,
                                help="First stock batch + photos + setup.")

    proj, be = m.project(units1, growth, 12, fixed, startup, e["profit"], e["revenue_ex"])
    s = st.columns(4)
    s[0].metric("Profit / unit", eur(e["profit"]))
    s[1].metric("Year-1 revenue (ex VAT)", eur(proj["Revenue (ex VAT)"].sum()))
    s[2].metric("Year-1 net", eur(proj["Net / month"].sum()))
    s[3].metric("Break-even", f"Month {be}" if be else "not in 12 mo")

    if not be:
        st.warning("This lead product doesn't break even in a year at these volumes — "
                   "pick a higher-margin bundle, raise volume, or cut fixed costs/CAC.")

    line = go.Figure()
    line.add_bar(x=proj["Month"], y=proj["Net / month"], name="Net / month", marker_color="#94a3b8")
    line.add_trace(go.Scatter(x=proj["Month"], y=proj["Cumulative cash"], name="Cumulative cash",
                              mode="lines+markers", line=dict(color="#16223d", width=3)))
    line.add_hline(y=0, line_dash="dot", line_color="#e76f51")
    line.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10),
                       xaxis_title="Month", yaxis_title="€", legend=dict(orientation="h"))
    st.plotly_chart(line, use_container_width=True)

    st.dataframe(proj, use_container_width=True, hide_index=True)
    full = m.df_to_excel_bytes({
        "Business case": proj,
        "Portfolio": m.portfolio_table(products, **fees),
        "Assumptions": pd.DataFrame([
            {"Item": "Lead product", "Value": pick},
            {"Item": "Units month 1", "Value": units1},
            {"Item": "Monthly growth %", "Value": growth * 100},
            {"Item": "Fixed costs / month", "Value": fixed},
            {"Item": "Startup investment", "Value": startup},
            {"Item": "Commission %", "Value": fees["commission_pct"] * 100},
            {"Item": "Ad cost / sale (CAC)", "Value": fees["ad_per_unit"]},
            {"Item": "Returns %", "Value": fees["returns_pct"] * 100},
        ]),
    })
    st.download_button("⬇️ Download full business case (Excel)", full,
                       file_name="ecommerce_business_case.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# --- 4. Market & strategy --------------------------------------------------
with tab_market:
    st.subheader("Market & strategy — home-energy / domotica (NL)")
    cols = st.columns(3)
    for i, (label, val, sub) in enumerate(m.MARKET["stats"]):
        cols[i % 3].metric(label, val, sub or None)

    seg = m.MARKET["segments"]
    pie = go.Figure(go.Pie(labels=list(seg), values=list(seg.values()), hole=0.5))
    pie.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                      title="Smart-home revenue by segment (EU, %)")
    st.plotly_chart(pie, use_container_width=True)

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("#### 🎯 Your beachhead")
        for x in m.MARKET["beachhead"]:
            st.markdown(f"- {x}")
        st.markdown("#### 🧠 Your moat")
        for x in m.MARKET["moat"]:
            st.markdown(f"- {x}")
    with g2:
        st.markdown("#### 🚫 Don't compete here")
        for x in m.MARKET["avoid"]:
            st.markdown(f"- {x}")
        st.markdown("#### ⚠️ Risks to manage")
        for x in m.MARKET["risks"]:
            st.markdown(f"- {x}")

    st.markdown("#### Sources")
    st.markdown("  ·  ".join(f"[{name}]({url})" for name, url in m.MARKET["sources"]))

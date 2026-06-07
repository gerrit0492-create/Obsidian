# E-commerce planner — home-energy / domotica (NL)

A planning dashboard for launching a smart-home / energy-saving webshop in the
Netherlands. Built for a cost engineer: explicit unit economics, a product
portfolio comparison, a 12-month business case, and the market/strategy — with
Excel export throughout.

> All numbers are **researched estimates to validate**, not promises. Edit
> everything to your own reality (sourcing quotes, real Bol fees, your CAC).

## What's inside
- **🧮 Margin calculator** — per-unit economics for one product: revenue ex VAT,
  marketplace commission, fixed fee, payment, shipping, returns and ad cost →
  profit/unit, margin %, markup, with a cost-waterfall and a plain-language verdict.
- **📦 Product portfolio** — an editable table of products (pre-loaded with a
  home-energy/domotica starter set) ranked by profit/unit, with an Excel export.
- **📈 Business case** — pick a lead product, set volume/growth/fixed costs/startup
  budget → a 12-month cash projection, break-even month, and a full Excel export.
- **🌍 Market & strategy** — NL/EU smart-home market size & growth, the segments to
  avoid (incumbents), your beachhead, your moat, the risks, and sources.

## The headline insight (already visible in the defaults)
A single €19.95 smart plug nets **~€0.27** — marketplace fees + ad cost eat it.
The **€89 starter kit nets ~€22 (≈30% margin)**. Sell **bundles/kits**, not cheap
commodity devices.

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```
Opens at http://localhost:8501. `model.py` holds the pure math (no Streamlit) and
is unit-testable on its own.

## Adjust to reality before trusting it
- Get a real **sourcing quote** (Alibaba) for landed cost incl. inbound freight.
- Check the **Bol commission** for your category (it varies ~8–17%).
- Use **certified (CE/RED)** white-label devices — don't build your own mains radios.
- Treat ad cost (CAC) as the swing factor; it's what makes or breaks low-price items.

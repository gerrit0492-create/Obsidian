# Car Charging Costs

A [Streamlit](https://streamlit.io) dashboard for tracking EV **charging costs** from a home
charger's `meterdata` CSV export. Shows cost/energy KPIs, monthly trends, a cumulative-cost
curve, a per-card breakdown, the session log, and Excel/CSV downloads.

## Data
The charger exports a semicolon-delimited CSV with a `#` metadata header and Dutch number
formatting (`,` decimal, `.` thousands). [`charging.py`](./charging.py) parses it into a tidy
DataFrame; the app reads it three ways:
- **Upload** a CSV in the sidebar, or
- use the **bundled sample** (`data/sample_meterdata.csv`), or
- **Fetch from the charger** at `http://pblr-0012237.local/charging-history` — this only works
  when the app runs **on the same network as the charger** (the `.local` name doesn't resolve
  from the cloud).

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```
Opens at http://localhost:8501.

## Deploy
It's a standard Streamlit app, so it runs on any of:
- **Streamlit Community Cloud** — point it at the repo, set `app.py` as the entry point.
- **Azure App Service** (Python) — start command:
  `python -m streamlit run app.py --server.port $PORT --server.address 0.0.0.0`.
- **Render** — same start command (see the `cost-forge-2` setup for reference).

> Note: a hosted instance can't reach the `.local` charger. For live data, either run it on
> your home network or upload the latest CSV.

## HomeWizard P1 (home energy)
The dashboard can also read a **HomeWizard P1 meter** on your network to show live home power,
lifetime imported/exported energy, an estimated home cost, and a rough "car as % of home"
figure. In the app, scroll to **Home energy (HomeWizard P1)**, enter the meter's IP (enable the
**Local API** in the HomeWizard app for v1, or paste a **v2 token**), and click **Read P1 now**.

> It's a live snapshot plus lifetime totals — for home cost *over time*, log readings
> periodically. Works on your home network only (a hosted instance can't reach the meter).

## Settings (env vars / Streamlit secrets)
| Name | Purpose |
| ---- | ------- |
| `APP_PASSWORD` | If set, the app asks for this password before showing anything (use it when deploying publicly). |
| `CAR_MAP` | JSON mapping RFID card UID → car name, e.g. `{"AAAA000000A1": "Car A", "BBBB000000B2": "Car B"}`. Kept out of the code so UIDs aren't committed. Without it, cards show their label. |

## Privacy
The bundled `data/sample_meterdata.csv` is **anonymized demo data** — no real serial, UIDs, or
timestamps. Keep your real export out of any public repo (upload it in the app instead), and
set your real card→car mapping via the `CAR_MAP` setting rather than committing it.

## Tests
```bash
python test_charging.py
```

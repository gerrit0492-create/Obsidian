"""Render a self-contained, mobile-friendly HTML snapshot of the job search.

Pure functions: produce an offline page (applications + follow-ups + the latest
vacancies) you can save on your phone and open in any browser. Not live —
regenerate from the tracker to refresh.
"""

from __future__ import annotations

import html
from datetime import date

import pandas as pd

CLOSED = {"Rejected", "Closed"}

CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,'Segoe UI',Roboto,sans-serif;color:#16223d;background:#f4f6f8}
.wrap{max-width:680px;margin:0 auto;padding:16px}
h1{font-size:1.4rem;margin:.2rem 0}
.sub{color:#76839a;font-size:.85rem;margin-bottom:14px}
h2{font-size:1.05rem;margin:22px 0 8px;color:#16223d}
.kpis{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:6px}
.kpi{background:#16223d;color:#fff;border-radius:10px;padding:8px 12px;font-size:.8rem;font-weight:600}
.card{background:#fff;border:1px solid #e7ebf0;border-radius:12px;padding:12px 14px;margin:8px 0}
.card .co{font-weight:700}
.card .meta{color:#66738a;font-size:.85rem;margin-top:2px}
.pill{display:inline-block;border-radius:999px;padding:2px 9px;font-size:.74rem;font-weight:600;margin-right:6px}
.s-lead{background:#eef2f6;color:#3c4a5e}.s-active{background:#e6f5f2;color:#1d7d6e}
.s-warn{background:#fdecec;color:#c0392b}
a{color:#1d7d6e;text-decoration:none}
.empty{color:#8a97a8;font-size:.9rem}
"""


def _e(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    return html.escape(str(x))


def _d(x) -> str:
    t = pd.to_datetime(x, errors="coerce")
    return "" if pd.isna(t) else t.date().isoformat()


def render(apps: pd.DataFrame, vacancies=None, title="Sollicitatie-overzicht") -> str:
    apps = apps.copy() if apps is not None else pd.DataFrame()
    today = pd.Timestamp(date.today())

    total = len(apps)
    active = apps[~apps["Status"].isin(CLOSED)] if "Status" in apps else apps
    interviews = int((apps.get("Status") == "Interview").sum()) if "Status" in apps else 0
    offers = int((apps.get("Status") == "Offer").sum()) if "Status" in apps else 0
    kpis = "".join(f'<span class="kpi">{lbl}: {val}</span>' for lbl, val in
                   [("Totaal", total), ("Actief", len(active)), ("Interviews", interviews), ("Offers", offers)])

    # Active applications
    cards = ""
    for _, r in active.iterrows():
        link = f' · <a href="{_e(r.get("Link"))}">open</a>' if _e(r.get("Link")) else ""
        nxt = f'<br>→ {_e(r.get("Next action"))}' + (f' ({_d(r.get("Next date"))})' if _d(r.get("Next date")) else "") if _e(r.get("Next action")) else ""
        cards += (f'<div class="card"><span class="pill s-active">{_e(r.get("Status"))}</span>'
                  f'<span class="co">{_e(r.get("Company"))}</span> — {_e(r.get("Role"))}'
                  f'<div class="meta">{_e(r.get("Location"))}{link}{nxt}</div></div>')
    if not cards:
        cards = '<div class="empty">Geen actieve sollicitaties.</div>'

    # Follow-ups
    fu = ""
    if "Next date" in apps.columns:
        f = apps.copy()
        f["Next date"] = pd.to_datetime(f["Next date"], errors="coerce")
        f = f.dropna(subset=["Next date"])
        f = f[~f["Status"].isin(CLOSED)].sort_values("Next date")
        for _, r in f.iterrows():
            overdue = r["Next date"] < today
            pill = '<span class="pill s-warn">over tijd</span>' if overdue else ""
            fu += (f'<div class="card">{pill}<b>{_d(r["Next date"])}</b> — '
                   f'{_e(r.get("Company"))} · {_e(r.get("Next action")) or "—"}</div>')
    if not fu:
        fu = '<div class="empty">Geen geplande opvolging.</div>'

    # Vacancies
    vac = ""
    for v in (vacancies or []):
        link = f' · <a href="{_e(v.get("Link"))}">open</a>' if _e(v.get("Link")) else ""
        posted = f' · {_e(v.get("Posted"))}' if _e(v.get("Posted")) else ""
        vac += (f'<div class="card"><span class="co">{_e(v.get("Title"))}</span>'
                f'<div class="meta">{_e(v.get("Company"))} · {_e(v.get("Location"))}{posted}{link}</div></div>')
    vac_section = f"<h2>Vacatures ({len(vacancies)})</h2>{vac}" if vacancies else ""

    return f"""<!doctype html><html lang="nl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head>
<body><div class="wrap">
  <h1>{html.escape(title)}</h1>
  <div class="sub">Momentopname · {date.today().isoformat()}</div>
  <div class="kpis">{kpis}</div>
  <h2>Actieve sollicitaties</h2>{cards}
  <h2>Opvolging</h2>{fu}
  {vac_section}
</div></body></html>"""

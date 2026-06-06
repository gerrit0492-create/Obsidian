"""Fetch current vacancies for the tracker's 'Vacatures' tab.

Sources:
- Adzuna (best NL coverage) — needs a FREE app_id/app_key from
  https://developer.adzuna.com (2 min). Set them as ADZUNA_APP_ID /
  ADZUNA_APP_KEY in .streamlit/secrets.toml.
- Arbeitnow (keyless EU job board) — automatic fallback; lighter NL coverage.

The ``_norm_*`` parsers are pure (unit-tested); the ``search_*`` functions do
the HTTP. Run only where you have internet (i.e. locally).
"""

from __future__ import annotations

TIMEOUT = 20

# A broad set of titles that fit Gerrit's profile.
DEFAULT_KEYWORDS = [
    "cost engineer", "cost estimator", "calculator", "werkvoorbereider",
    "manufacturing engineer", "kostprijs calculatie", "should cost",
]


def _norm_adzuna(results) -> list[dict]:
    out = []
    for r in results or []:
        out.append({
            "Title": (r.get("title") or "").strip(),
            "Company": ((r.get("company") or {}).get("display_name") or "").strip(),
            "Location": ((r.get("location") or {}).get("display_name") or "").strip(),
            "Link": r.get("redirect_url", ""),
            "Posted": (r.get("created") or "")[:10],
            "Description": (r.get("description") or "")[:1500],
            "Source": "Adzuna",
        })
    return out


def _norm_arbeitnow(data, keywords) -> list[dict]:
    out = []
    kws = [k.lower() for k in keywords]
    for j in data or []:
        text = f"{j.get('title', '')} {j.get('description', '')}".lower()
        if not any(k in text for k in kws):
            continue
        out.append({
            "Title": (j.get("title") or "").strip(),
            "Company": (j.get("company_name") or "").strip(),
            "Location": (j.get("location") or "").strip(),
            "Link": j.get("url", ""),
            "Posted": "",
            "Description": (j.get("description") or "")[:1500],
            "Source": "Arbeitnow",
        })
    return out


def _dedupe(rows) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        key = (r["Title"].lower(), r["Company"].lower())
        if not r["Title"] or key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def search_adzuna(app_id, app_key, what, where="Eindhoven", distance=40, max_results=30):
    import requests

    resp = requests.get(
        "https://api.adzuna.com/v1/api/jobs/nl/search/1",
        params={
            "app_id": app_id, "app_key": app_key, "results_per_page": max_results,
            "what": what, "where": where, "distance": distance,
            "content-type": "application/json",
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return _norm_adzuna(resp.json().get("results"))


def search_arbeitnow(keywords, pages=3):
    import requests

    out = []
    for page in range(1, pages + 1):
        resp = requests.get(
            "https://www.arbeitnow.com/api/job-board-api",
            params={"page": page}, timeout=TIMEOUT,
        )
        resp.raise_for_status()
        out += _norm_arbeitnow(resp.json().get("data"), keywords)
    return out


def search(keywords=None, where="Eindhoven", distance=40, app_id="", app_key="", max_per=20):
    """Broad search across the configured sources; returns a deduped list of dicts."""
    keywords = keywords or DEFAULT_KEYWORDS
    rows: list[dict] = []
    if app_id and app_key:
        for kw in keywords:
            try:
                rows += search_adzuna(app_id, app_key, kw, where, distance, max_per)
            except Exception:  # noqa: BLE001 — one bad query shouldn't sink the rest
                pass
    if not rows:  # no key, or Adzuna returned nothing → keyless fallback
        try:
            rows += search_arbeitnow(keywords)
        except Exception:  # noqa: BLE001
            pass
    return _dedupe(rows)

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

import re

TIMEOUT = 20

# A broad set of titles that fit Gerrit's profile.
DEFAULT_KEYWORDS = [
    "cost engineer", "cost estimator", "calculator", "werkvoorbereider",
    "manufacturing engineer", "kostprijs calculatie", "should cost",
]


def _fmt_salary(lo, hi) -> str:
    """Adzuna salary_min/max (yearly EUR) → a compact '€45k–€60k' string."""
    def k(v):
        try:
            return f"€{round(float(v) / 1000)}k"
        except (TypeError, ValueError):
            return ""
    a, b = k(lo), k(hi)
    if a and b and a != b:
        return f"{a}–{b}"
    return a or b


def _norm_adzuna(results) -> list[dict]:
    out = []
    for r in results or []:
        out.append({
            "Title": (r.get("title") or "").strip(),
            "Company": ((r.get("company") or {}).get("display_name") or "").strip(),
            "Location": ((r.get("location") or {}).get("display_name") or "").strip(),
            "Link": r.get("redirect_url", ""),
            "Posted": (r.get("created") or "")[:10],
            "Salary": _fmt_salary(r.get("salary_min"), r.get("salary_max")),
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


def _norm_jooble(jobs) -> list[dict]:
    out = []
    for j in jobs or []:
        snippet = re.sub(r"<[^>]+>", "", j.get("snippet") or "").strip()
        out.append({
            "Title": (j.get("title") or "").strip(),
            "Company": (j.get("company") or "").strip(),
            "Location": (j.get("location") or "").strip(),
            "Link": j.get("link", ""),
            "Posted": (j.get("updated") or "")[:10],
            "Salary": (j.get("salary") or "").strip(),
            "Description": snippet[:1500],
            "Source": "Jooble",
        })
    return out


def _jsearch_salary(j) -> str:
    cur = j.get("job_salary_currency") or ""
    sym = {"EUR": "€", "USD": "$", "GBP": "£"}.get(cur, (cur + " " if cur else ""))

    def k(v):
        try:
            return f"{sym}{round(float(v) / 1000)}k"
        except (TypeError, ValueError):
            return ""
    a, b = k(j.get("job_min_salary")), k(j.get("job_max_salary"))
    if a and b and a != b:
        return f"{a}–{b}"
    return a or b


def _norm_jsearch(data) -> list[dict]:
    out = []
    for j in data or []:
        loc = ", ".join(x for x in (j.get("job_city"), j.get("job_country")) if x)
        out.append({
            "Title": (j.get("job_title") or "").strip(),
            "Company": (j.get("employer_name") or "").strip(),
            "Location": loc.strip(),
            "Link": j.get("job_apply_link") or j.get("job_google_link") or "",
            "Posted": (j.get("job_posted_at_datetime_utc") or "")[:10],
            "Salary": _jsearch_salary(j),
            "Description": (j.get("job_description") or "").strip()[:1500],
            "Source": "JSearch",
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


def search_jooble(api_key, what, where="Eindhoven", max_results=20):
    import requests

    resp = requests.post(
        f"https://jooble.org/api/{api_key}",
        json={"keywords": what, "location": where},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return _norm_jooble(resp.json().get("jobs"))[:max_results]


def search_jsearch(api_key, what, where="Netherlands", max_results=20):
    import requests

    resp = requests.get(
        "https://jsearch.p.rapidapi.com/search",
        headers={"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
        params={"query": f"{what} in {where}", "page": "1", "num_pages": "1"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return _norm_jsearch(resp.json().get("data"))[:max_results]


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


def search(keywords=None, where="Eindhoven", distance=40, app_id="", app_key="",
           jooble_key="", jsearch_key="", max_per=20):
    """Broad search across the configured sources; returns a deduped list of dicts."""
    keywords = keywords or DEFAULT_KEYWORDS
    rows: list[dict] = []
    if app_id and app_key:
        for kw in keywords:
            try:
                rows += search_adzuna(app_id, app_key, kw, where, distance, max_per)
            except Exception:  # noqa: BLE001 — one bad query shouldn't sink the rest
                pass
    if jooble_key:
        for kw in keywords:
            try:
                rows += search_jooble(jooble_key, kw, where, max_per)
            except Exception:  # noqa: BLE001
                pass
    if jsearch_key:
        for kw in keywords:
            try:
                rows += search_jsearch(jsearch_key, kw, where or "Netherlands", max_per)
            except Exception:  # noqa: BLE001
                pass
    if not rows:  # no keys, or sources returned nothing → keyless fallback
        try:
            rows += search_arbeitnow(keywords)
        except Exception:  # noqa: BLE001
            pass
    return _dedupe(rows)

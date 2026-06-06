"""Optional cloud persistence for the tracker via a private GitHub Gist.

Set GIST_TOKEN (a GitHub token with the 'gist' scope) and GIST_ID (the id of a
private gist you created) in .streamlit/secrets.toml or the app's Secrets. With
both set, the tracker reads/writes your applications to that gist — so the data
survives reboots and is the same on every device. Without them it falls back to
the local Excel file.

Pure HTTP helpers; the app handles DataFrame <-> records conversion.
"""

from __future__ import annotations

import json

FILE = "applications.json"
API = "https://api.github.com/gists"
TIMEOUT = 15


def enabled(token: str, gist_id: str) -> bool:
    return bool(token and gist_id)


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


def load(token: str, gist_id: str) -> list[dict]:
    """Return the list of application records stored in the gist (or [])."""
    import requests

    resp = requests.get(f"{API}/{gist_id}", headers=_headers(token), timeout=TIMEOUT)
    resp.raise_for_status()
    files = resp.json().get("files", {})
    content = (files.get(FILE) or {}).get("content") or "[]"
    try:
        data = json.loads(content)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def save(token: str, gist_id: str, records: list[dict]) -> None:
    """Write the application records to the gist."""
    import requests

    body = {"files": {FILE: {"content": json.dumps(records, ensure_ascii=False, indent=2, default=str)}}}
    resp = requests.patch(f"{API}/{gist_id}", headers=_headers(token), json=body, timeout=TIMEOUT)
    resp.raise_for_status()

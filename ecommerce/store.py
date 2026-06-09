"""Permanente opslag van de e-commerce planner-state in een privé GitHub Gist.

Bewaart per-niche keuzes (portfolio, businesscase, scan) + zelf-gemaakte niches,
zodat ze een reboot/refresh overleven. Heeft GIST_TOKEN + ECOM_GIST_ID in de
secrets nodig; zonder die twee werkt de app gewoon (alleen per sessie).
"""

from __future__ import annotations

import json
import os

API = "https://api.github.com/gists"
FILE = "ecommerce_state.json"


def _setting(name: str) -> str:
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # noqa: BLE001
        pass
    return os.environ.get(name, "")


def enabled() -> bool:
    return bool(_setting("GIST_TOKEN") and _setting("ECOM_GIST_ID"))


def load() -> dict:
    """Haal de opgeslagen state op; {} als er niets is of opslag uitstaat."""
    token, gid = _setting("GIST_TOKEN"), _setting("ECOM_GIST_ID")
    if not (token and gid):
        return {}
    import requests
    r = requests.get(f"{API}/{gid}", headers={"Authorization": f"Bearer {token}"}, timeout=20)
    r.raise_for_status()
    content = (r.json().get("files", {}).get(FILE, {}) or {}).get("content", "")
    return json.loads(content) if content.strip() else {}


def save(data: dict) -> bool:
    """Schrijf de state weg naar de Gist. False als opslag uitstaat."""
    token, gid = _setting("GIST_TOKEN"), _setting("ECOM_GIST_ID")
    if not (token and gid):
        return False
    import requests
    r = requests.patch(
        f"{API}/{gid}", headers={"Authorization": f"Bearer {token}"},
        json={"files": {FILE: {"content": json.dumps(data, ensure_ascii=False, indent=2)}}},
        timeout=20)
    r.raise_for_status()
    return True

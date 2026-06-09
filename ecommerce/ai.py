"""LLM-helper voor de Founder-check — werkt met een gratis key (Groq/Gemini) of Anthropic.

Houdt model.py zuiver (geen Streamlit). Leest de key uit Streamlit-secrets met
fallback naar omgevingsvariabelen. Zonder key werkt de tool nog steeds: dan toont
de app de prompts om te kopiëren.
"""

from __future__ import annotations

import os


def setting(name: str) -> str:
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # noqa: BLE001
        pass
    return os.environ.get(name, "")


def available() -> bool:
    return bool(setting("GROQ_API_KEY") or setting("GEMINI_API_KEY")
               or setting("GOOGLE_API_KEY") or setting("ANTHROPIC_API_KEY"))


def complete(prompt: str, max_tokens: int = 900):
    """Roept de geconfigureerde LLM aan (Groq/Gemini gratis, of Anthropic). None bij fout."""
    import requests
    qk = setting("GROQ_API_KEY")
    gk = setting("GEMINI_API_KEY") or setting("GOOGLE_API_KEY")
    ak = setting("ANTHROPIC_API_KEY")
    try:
        if qk:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {qk}", "content-type": "application/json"},
                json={"model": "llama-3.3-70b-versatile", "max_tokens": max_tokens,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=60)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        if gk:
            r = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.0-flash:generateContent?key={gk}",
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"maxOutputTokens": max_tokens}},
                timeout=60)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if ak:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ak, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-haiku-4-5-20251001", "max_tokens": max_tokens,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=60)
            r.raise_for_status()
            return r.json()["content"][0]["text"].strip()
    except Exception:  # noqa: BLE001
        return None
    return None


def suggest_products(niche: str, context: str = ""):
    """Laat de LLM 3-5 producten/diensten + prijzen voorstellen voor een niche.

    Geeft een lijst van {Product, Inkoop, Prijs, Dienst}-dicts, of None bij geen
    key/parsefout. Bedragen in euro's; Inkoop excl. btw, Prijs incl. btw.
    """
    import json
    import re as _re
    prompt = (
        f"Stel 3 tot 5 verkoopbare producten/diensten voor de e-commerce niche '{niche}' voor "
        f"een Nederlandse starter met laag budget. Context: {context or 'geen'}.\n"
        "Geef ALLEEN geldige JSON terug: een array van objecten met exact de sleutels "
        "\"Product\" (korte NL naam), \"Inkoop\" (geland inkoopbedrag excl. btw, getal), "
        "\"Prijs\" (consumentprijs incl. btw, getal), \"Dienst\" (true voor een dienst/advies, "
        "anders false). Geen uitleg, alleen de JSON-array."
    )
    raw = complete(prompt, 700)
    if not raw:
        return None
    try:
        match = _re.search(r"\[.*\]", raw, _re.S)
        items = json.loads(match.group(0) if match else raw)
        out = []
        for it in items:
            out.append({
                "Product": str(it.get("Product", "")).strip(),
                "Inkoop": float(it.get("Inkoop", 0) or 0),
                "Prijs": float(it.get("Prijs", 0) or 0),
                "Dienst": bool(it.get("Dienst", False)),
            })
        return [x for x in out if x["Product"]] or None
    except Exception:  # noqa: BLE001
        return None

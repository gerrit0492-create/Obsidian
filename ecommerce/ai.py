"""LLM-helper voor de Founder-check — werkt met een gratis key (Groq/Gemini) of Anthropic.

Houdt model.py zuiver (geen Streamlit). Leest de key uit Streamlit-secrets met
fallback naar omgevingsvariabelen. Zonder key werkt de tool nog steeds: dan toont
de app de prompts om te kopiëren.
"""

from __future__ import annotations

import os

# Deze planner gebruikt altijd gratis Groq/Gemini eerst; Anthropic is alleen een
# betaalde fallback en draait op het goedkope Haiku. Fable (premium) is hier bewust
# niet in gebruik: de analyses/founder-check zijn intern en het gratis model volstaat,
# dus Fable verbetert het resultaat niet genoeg om de kosten te rechtvaardigen.
# (Fable wordt wel gebruikt voor de motivatiebrieven/CV in de portfolio, waar de
# schrijfkwaliteit er echt toe doet.)
ANTHROPIC_MODEL = "claude-haiku-4-5"


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


def complete(prompt: str, max_tokens: int = 900, kind: str = "prose"):
    """Roept de geconfigureerde LLM aan. None bij fout.

    Volgorde is altijd: gratis Groq -> Gemini -> betaalde Anthropic Haiku. Alleen
    providers met een key worden geprobeerd. `kind` blijft bestaan voor de aanroepers
    maar verandert het model niet meer (deze planner gebruikt geen premium Fable).
    """
    import requests
    qk = setting("GROQ_API_KEY")
    gk = setting("GEMINI_API_KEY") or setting("GOOGLE_API_KEY")
    ak = setting("ANTHROPIC_API_KEY")

    def _groq():
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {qk}", "content-type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

    def _gemini():
        r = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash:generateContent?key={gk}",
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"maxOutputTokens": max_tokens}},
            timeout=60)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    def _anthropic():
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ak, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": ANTHROPIC_MODEL, "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=60)
        r.raise_for_status()
        data = r.json()
        if data.get("stop_reason") == "refusal":
            return None
        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text").strip()
        return text or None

    providers = {"groq": (qk, _groq), "gemini": (gk, _gemini), "anthropic": (ak, _anthropic)}
    order = ["groq", "gemini", "anthropic"]
    for name in order:
        key, fn = providers[name]
        if not key:
            continue
        try:
            return fn()
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
        "Gebruik REALISTISCHE Nederlandse marktbedragen (2025/2026): voor een product is "
        "\"Inkoop\" het gelande inkoopbedrag excl. btw (inkoop + vracht) en \"Prijs\" de gangbare "
        "consumentprijs incl. 21% btw, met een gezonde marge; voor een dienst is \"Inkoop\" de "
        "materiaal-/reiskosten (vaak 0) en \"Prijs\" een realistisch uur- of projecttarief.\n"
        "Geef ALLEEN geldige JSON terug: een array van objecten met exact de sleutels "
        "\"Product\" (korte NL naam), \"Inkoop\" (getal), \"Prijs\" (getal), \"Dienst\" (true voor "
        "een dienst/advies, anders false). Geen uitleg, alleen de JSON-array."
    )
    raw = complete(prompt, 700, kind="json")
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


def extract_pdf_text(data: bytes, maxpages: int = 12) -> str:
    """Haal platte tekst uit een geüploade PDF (pdfminer.six). '' bij fout."""
    try:
        import io
        from pdfminer.high_level import extract_text
        return extract_text(io.BytesIO(data), maxpages=maxpages) or ""
    except Exception:  # noqa: BLE001
        return ""


def parse_offerte(text: str):
    """Laat de LLM een offerte-tekst omzetten naar gestructureerde posten + totalen.

    Geeft een dict {bedrijf, offertenummer, datum, geldig, posten:[{onderdeel, prijs_excl}],
    totaal_excl, totaal_incl} of None.
    """
    text = (text or "").strip()
    if not text:
        return None
    import json
    import re as _re
    prompt = (
        "Hieronder de tekst van een (dak)offerte. Haal de gegevens eruit en geef ALLEEN geldige JSON "
        "terug met exact deze sleutels:\n"
        '{"bedrijf": "...", "offertenummer": "...", "datum": "jjjj-mm-dd", "geldig": "jjjj-mm-dd", '
        '"posten": [{"onderdeel": "korte omschrijving", "prijs_excl": getal}], '
        '"totaal_excl": getal, "totaal_incl": getal}\n'
        "Bedragen zijn euro-getallen (gebruik punten/geen euroteken). Elke duidelijke prijspost wordt "
        "een item in 'posten'. Geen uitleg, alleen de JSON.\n\nTEKST:\n" + text[:6000]
    )
    raw = complete(prompt, 1300, kind="json")
    if not raw:
        return None
    try:
        match = _re.search(r"\{.*\}", raw, _re.S)
        return json.loads(match.group(0) if match else raw)
    except Exception:  # noqa: BLE001
        return None

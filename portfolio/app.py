"""Personal portfolio / job-application site — bilingual (NL/EN), Streamlit.

Run with:  streamlit run app.py
All your text lives in content.py — edit that, not this file.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from content import CONTENT, PROFILE

HERE = Path(__file__).parent

st.set_page_config(page_title=PROFILE["name"], page_icon="💼", layout="wide")

# --- Styling ---------------------------------------------------------------
st.markdown(
    """
    <style>
      .block-container {max-width: 980px; padding-top: 2rem;}
      .hero {background: linear-gradient(135deg,#1f2a44 0%,#2a9d8f 100%);
             color:#fff; padding:34px 36px; border-radius:18px; margin-bottom:8px;}
      .hero h1 {margin:0; font-size:2.1rem; font-weight:800; line-height:1.1;}
      .hero .role {margin:.35rem 0 .1rem; font-size:1.15rem; font-weight:600; opacity:.95;}
      .hero p {margin:.5rem 0 0; font-size:1.02rem; opacity:.9; max-width:60ch;}
      .chip {display:inline-block; background:#eef3f4; color:#1f2a44; border:1px solid #dde6e7;
             border-radius:999px; padding:6px 13px; margin:4px 6px 4px 0; font-size:.92rem;}
      .card {background:#fff; border:1px solid #e7ebf0; border-radius:14px;
             padding:18px 20px; height:100%; box-shadow:0 1px 2px rgba(0,0,0,.03);}
      .metric {font-size:1.9rem; font-weight:800; color:#2a9d8f; line-height:1;}
      .card h4 {margin:.5rem 0 .25rem; color:#1f2a44;}
      .card p {margin:0; color:#475569; font-size:.95rem;}
      .tag {display:inline-block; background:#f1f5f9; color:#334155; border-radius:6px;
            padding:2px 8px; margin:6px 6px 0 0; font-size:.8rem;}
      a.btn {display:inline-block; text-decoration:none; background:#1f2a44; color:#fff !important;
             padding:9px 16px; border-radius:10px; margin:10px 8px 0 0; font-weight:600;}
      a.btn.ghost {background:#fff; color:#1f2a44 !important; border:1px solid #cbd5e1;}
      h2 {margin-top:2.2rem;}
      footer {visibility:hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Language switch -------------------------------------------------------
top = st.columns([6, 1])
with top[1]:
    lang_code = st.selectbox(
        "Taal / Language", ["NL", "EN"], label_visibility="collapsed"
    )
c = CONTENT["nl" if lang_code == "NL" else "en"]


def chips(items: list[str]) -> str:
    return "".join(f'<span class="chip">{x}</span>' for x in items)


# --- Hero ------------------------------------------------------------------
cv_path = HERE / PROFILE["cv_file"]
buttons = [f'<a class="btn" href="mailto:{PROFILE["email"]}">✉️ {c["cta_contact"]}</a>']
if PROFILE.get("linkedin"):
    buttons.append(f'<a class="btn ghost" href="{PROFILE["linkedin"]}" target="_blank">in LinkedIn</a>')
if PROFILE.get("github"):
    buttons.append(f'<a class="btn ghost" href="{PROFILE["github"]}" target="_blank">GitHub</a>')

st.markdown(
    f"""
    <div class="hero">
      <h1>{PROFILE["name"]}</h1>
      <div class="role">{c["role"]}</div>
      <p>{c["tagline"]}</p>
    </div>
    {''.join(buttons)}
    """,
    unsafe_allow_html=True,
)
if cv_path.exists():
    st.download_button(f"⬇️ {c['cta_cv']}", cv_path.read_bytes(), file_name="CV.pdf", mime="application/pdf")

# --- About -----------------------------------------------------------------
st.markdown(f"## {c['about_title']}")
about_cols = st.columns([3, 1])
about_cols[0].write(c["about"])
photo = HERE / PROFILE.get("photo", "")
if photo.exists():
    about_cols[1].image(str(photo), use_container_width=True)
st.caption(f"📍 {PROFILE['location']}")

# --- Strengths -------------------------------------------------------------
st.markdown(f"## {c['skills_title']}")
st.markdown(chips(c["skills"]), unsafe_allow_html=True)

# --- Impact / highlights ---------------------------------------------------
st.markdown(f"## {c['highlights_title']}")
cols = st.columns(len(c["highlights"]))
for col, h in zip(cols, c["highlights"]):
    col.markdown(
        f'<div class="card"><div class="metric">{h["metric"]}</div>'
        f'<h4>{h["title"]}</h4><p>{h["text"]}</p></div>',
        unsafe_allow_html=True,
    )

# --- Projects --------------------------------------------------------------
st.markdown(f"## {c['projects_title']}")
pcols = st.columns(2)
for i, p in enumerate(c["projects"]):
    tags = "".join(f'<span class="tag">{t}</span>' for t in p.get("tags", []))
    link = f'<br><a href="{p["link"]}" target="_blank">{p["link"]}</a>' if p.get("link") else ""
    pcols[i % 2].markdown(
        f'<div class="card" style="margin-bottom:14px"><h4>{p["title"]}</h4>'
        f'<p>{p["text"]}</p>{tags}{link}</div>',
        unsafe_allow_html=True,
    )

# --- Experience ------------------------------------------------------------
st.markdown(f"## {c['experience_title']}")
for e in c["experience"]:
    st.markdown(
        f'<div style="display:flex;gap:14px;padding:8px 0;border-bottom:1px solid #eef1f5">'
        f'<div style="min-width:120px;color:#64748b;font-weight:600">{e["period"]}</div>'
        f'<div><b>{e["role"]}</b><br><span style="color:#475569">{e["org"]}</span></div></div>',
        unsafe_allow_html=True,
    )

# --- Contact ---------------------------------------------------------------
st.markdown(f"## {c['contact_title']}")
st.write(c["contact_text"])
st.markdown(" ".join(buttons), unsafe_allow_html=True)
st.markdown("---")
st.caption(f"{c['footer']} · {PROFILE['email']}")

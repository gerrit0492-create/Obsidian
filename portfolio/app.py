"""Personal one-page site — public portfolio + a password-gated private area.

Run with:  streamlit run app.py
Public portfolio text lives in content.py; the private area (tracker + live
vacancies) lives in private.py and only unlocks with PRIVATE_PASSWORD.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

import private
from content import CONTENT, PROFILE

HERE = Path(__file__).parent

st.set_page_config(page_title=PROFILE["name"], page_icon="💼", layout="wide")

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
      html, body, [class*="css"], .stMarkdown { font-family: 'Inter', -apple-system, "Segoe UI", Roboto, sans-serif; }
      .block-container { max-width: 900px; padding-top: 1.4rem; padding-bottom: 3rem; }
      .hero { background:radial-gradient(120% 140% at 100% 0%, #21345c 0%, #16223d 55%); color:#fff; padding:40px 42px; border-radius:18px; position:relative; overflow:hidden; box-shadow:0 18px 44px rgba(22,34,61,.22); }
      .hero:before { content:""; position:absolute; left:0; top:0; bottom:0; width:5px; background:#2a9d8f; }
      .hero .eyebrow { text-transform:uppercase; letter-spacing:.14em; font-size:.78rem; font-weight:700; color:#7fd1c4; margin:0 0 .55rem; }
      .hero h1 { margin:0; font-size:2.5rem; font-weight:800; letter-spacing:-.02em; line-height:1.04; }
      .hero .headline { margin:.7rem 0 0; font-size:1.25rem; font-weight:700; line-height:1.35; color:#fff; max-width:34ch; }
      .hero .tag { margin:.7rem 0 0; font-size:1.02rem; line-height:1.55; color:#bcc7da; max-width:62ch; }
      .hero .meta { margin-top:1.1rem; font-size:.9rem; color:#9fadc4; }
      .hero .meta a { color:#cdd6e6; text-decoration:none; border-bottom:1px solid rgba(205,214,230,.35); }
      .badge { display:inline-block; background:rgba(42,157,143,.16); color:#7fd1c4; border:1px solid rgba(127,209,196,.4);
               border-radius:999px; padding:4px 13px; font-size:.78rem; font-weight:600; margin-bottom:1rem; }
      .sec { margin:2.6rem 0 .9rem; }
      .sec h2 { margin:0; font-size:1.5rem; font-weight:700; color:#16223d; letter-spacing:-.01em; }
      .sec .rule { height:3px; width:46px; background:#2a9d8f; border-radius:3px; margin-top:.55rem; }
      .chip { display:inline-block; background:#f1f5f6; color:#16223d; border:1px solid #e3e9ea;
              border-radius:8px; padding:6px 12px; margin:5px 7px 0 0; font-size:.9rem; font-weight:500; }
      .card { background:#fff; border:1px solid #e8ecf1; border-radius:14px; padding:20px 22px; height:100%;
              box-shadow:0 2px 12px rgba(22,34,61,.05); transition:transform .15s ease, box-shadow .15s ease; }
      .card:hover { transform:translateY(-3px); box-shadow:0 10px 26px rgba(22,34,61,.12); }
      .metric { font-size:1.5rem; font-weight:800; color:#2a9d8f; line-height:1.1; letter-spacing:-.01em; }
      .card h4 { margin:.55rem 0 .3rem; color:#16223d; font-size:1.02rem; }
      .card p { margin:0; color:#566377; font-size:.94rem; line-height:1.55; }
      .tagx { display:inline-block; background:#eef2f6; color:#3c4a5e; border-radius:6px; padding:3px 9px; margin:9px 6px 0 0; font-size:.77rem; font-weight:500; }
      a.btn { display:inline-block; text-decoration:none; background:#16223d; color:#fff !important; padding:10px 18px; border-radius:10px; margin:14px 8px 0 0; font-weight:600; font-size:.95rem; }
      a.btn.ghost { background:#fff; color:#16223d !important; border:1px solid #cdd5df; }
      .exp { display:flex; gap:18px; padding:12px 0; border-bottom:1px solid #eef1f5; }
      .exp .period { min-width:120px; color:#8a97a8; font-weight:600; font-size:.92rem; }
      .exp .role { font-weight:700; color:#16223d; } .exp .org { color:#566377; }
      .about { font-size:1.04rem; line-height:1.7; color:#34404f; }
      footer, #MainMenu { visibility:hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


def section(title: str) -> None:
    st.markdown(f'<div class="sec"><h2>{title}</h2><div class="rule"></div></div>', unsafe_allow_html=True)


def render_portfolio(c: dict) -> None:
    meta_bits = [f'<a href="mailto:{PROFILE["email"]}">{PROFILE["email"]}</a>', PROFILE["location"]]
    if PROFILE.get("linkedin"):
        meta_bits.append(f'<a href="{PROFILE["linkedin"]}" target="_blank">LinkedIn</a>')
    buttons = [f'<a class="btn" href="mailto:{PROFILE["email"]}">✉️ {c["cta_contact"]}</a>']
    if PROFILE.get("linkedin"):
        buttons.append(f'<a class="btn ghost" href="{PROFILE["linkedin"]}" target="_blank">in LinkedIn</a>')
    badge = f'<div class="badge">● {c["available"]}</div>' if c.get("available") else ""

    st.markdown(
        f"""
        <div class="hero">{badge}
          <div class="eyebrow">{c["role"]}</div>
          <h1>{PROFILE["name"]}</h1>
          {f'<div class="headline">{c["headline"]}</div>' if c.get("headline") else ''}
          <div class="tag">{c["tagline"]}</div>
          <div class="meta">{' · '.join(meta_bits)}</div>
        </div>
        {''.join(buttons)}
        """,
        unsafe_allow_html=True,
    )
    cv_path = HERE / PROFILE["cv_file"]
    if cv_path.exists():
        st.download_button(f"⬇️ {c['cta_cv']}", cv_path.read_bytes(), file_name="CV.pdf", mime="application/pdf")

    section(c["about_title"])
    ac = st.columns([3, 1])
    ac[0].markdown(f'<p class="about">{c["about"]}</p>', unsafe_allow_html=True)
    photo = HERE / PROFILE.get("photo", "")
    if photo.exists():
        ac[1].image(str(photo), use_container_width=True)

    section(c["skills_title"])
    st.markdown("".join(f'<span class="chip">{x}</span>' for x in c["skills"]), unsafe_allow_html=True)

    section(c["highlights_title"])
    cols = st.columns(len(c["highlights"]))
    for col, h in zip(cols, c["highlights"]):
        col.markdown(f'<div class="card"><div class="metric">{h["metric"]}</div>'
                     f'<h4>{h["title"]}</h4><p>{h["text"]}</p></div>', unsafe_allow_html=True)

    section(c["projects_title"])
    pcols = st.columns(2)
    for i, p in enumerate(c["projects"]):
        tags = "".join(f'<span class="tagx">{t}</span>' for t in p.get("tags", []))
        link = f'<br><a href="{p["link"]}" target="_blank">{p["link"]}</a>' if p.get("link") else ""
        pcols[i % 2].markdown(f'<div class="card" style="margin-bottom:16px"><h4>{p["title"]}</h4>'
                              f'<p>{p["text"]}</p>{tags}{link}</div>', unsafe_allow_html=True)

    section(c["experience_title"])
    for e in c["experience"]:
        st.markdown(f'<div class="exp"><div class="period">{e["period"]}</div>'
                    f'<div><span class="role">{e["role"]}</span><br><span class="org">{e["org"]}</span></div></div>',
                    unsafe_allow_html=True)

    section(c["contact_title"])
    st.markdown(f'<p class="about">{c["contact_text"]}</p>', unsafe_allow_html=True)
    st.markdown(" ".join(buttons), unsafe_allow_html=True)
    st.markdown(f'<p style="margin-top:2.4rem;color:#94a2b3;font-size:.85rem">{c["footer"]} · {PROFILE["email"]}</p>',
                unsafe_allow_html=True)


# --- Language switch (affects the public portfolio) ------------------------
top = st.columns([6, 1])
with top[1]:
    lang_code = st.selectbox("Language / Taal", ["EN", "NL"], label_visibility="collapsed")
c = CONTENT["en" if lang_code == "EN" else "nl"]

tab_public, tab_private = st.tabs(["📄 Portfolio", "🔒 Privé"])
with tab_public:
    render_portfolio(c)
with tab_private:
    if private.unlock(require_password=True):
        sub_w, sub_t, sub_v = st.tabs(["▶️ Work", "📋 Overview", "🔎 Vacatures"])
        with sub_w:
            private.render_work()
        with sub_t:
            private.render_tracker()
        with sub_v:
            private.render_vacancies()

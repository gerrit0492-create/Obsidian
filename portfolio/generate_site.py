"""Generate a static HTML portfolio (docs/index.html) for free GitHub Pages hosting.

Reads the same content.py, so there's one source of truth. Bilingual via a small
JS language toggle; no server needed. Run:

    python generate_site.py

Then enable GitHub Pages (Settings → Pages → Deploy from branch → main → /docs).
"""

from __future__ import annotations

import html
import shutil
from pathlib import Path

from content import CONTENT, PROFILE

HERE = Path(__file__).parent
DOCS = HERE.parent / "docs"          # repo-root /docs — GitHub Pages serves from here

CSS = """
*{box-sizing:border-box} html{scroll-behavior:smooth}
body{margin:0;font-family:'Inter',-apple-system,'Segoe UI',Roboto,sans-serif;color:#16223d;background:#fff}
.wrap{max-width:880px;margin:0 auto;padding:28px 20px 80px}
.top{display:flex;justify-content:flex-end;gap:6px;margin-bottom:14px}
.langbtn{border:1px solid #cdd5df;background:#fff;color:#16223d;border-radius:8px;padding:5px 12px;
  font-weight:600;cursor:pointer;font-size:.85rem}
.langbtn.active{background:#16223d;color:#fff;border-color:#16223d}
.hero{background:#16223d;color:#fff;padding:38px 40px;border-radius:16px;position:relative;overflow:hidden}
.hero:before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;background:#2a9d8f}
.eyebrow{text-transform:uppercase;letter-spacing:.14em;font-size:.78rem;font-weight:700;color:#7fd1c4;margin:0 0 .55rem}
.hero h1{margin:0;font-size:2.35rem;font-weight:800;letter-spacing:-.02em;line-height:1.05}
.tag{margin:.8rem 0 0;font-size:1.05rem;line-height:1.55;color:#cdd6e6;max-width:60ch}
.meta{margin-top:1.1rem;font-size:.9rem;color:#9fadc4}
.meta a{color:#cdd6e6}
.badge{display:inline-block;background:rgba(42,157,143,.16);color:#7fd1c4;border:1px solid rgba(127,209,196,.4);
  border-radius:999px;padding:4px 13px;font-size:.78rem;font-weight:600;margin-bottom:1rem}
.btns{margin:16px 0 0}
a.btn{display:inline-block;text-decoration:none;background:#16223d;color:#fff;padding:10px 18px;border-radius:10px;
  margin:8px 8px 0 0;font-weight:600;font-size:.95rem}
a.btn.ghost{background:#fff;color:#16223d;border:1px solid #cdd5df}
.sec{margin:2.6rem 0 .9rem}
.sec h2{margin:0;font-size:1.5rem;font-weight:700;letter-spacing:-.01em}
.rule{height:3px;width:46px;background:#2a9d8f;border-radius:3px;margin-top:.55rem}
.about{font-size:1.04rem;line-height:1.7;color:#34404f;max-width:70ch}
.chip{display:inline-block;background:#f1f5f6;border:1px solid #e3e9ea;border-radius:8px;padding:6px 12px;
  margin:5px 7px 0 0;font-size:.9rem;font-weight:500}
.grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.card{background:#fff;border:1px solid #e8ecf1;border-radius:14px;padding:20px 22px;box-shadow:0 2px 12px rgba(22,34,61,.05)}
.metric{font-size:2rem;font-weight:800;color:#2a9d8f;line-height:1;letter-spacing:-.02em}
.card h4{margin:.55rem 0 .3rem;font-size:1.02rem}
.card p{margin:0;color:#566377;font-size:.94rem;line-height:1.55}
.tagx{display:inline-block;background:#eef2f6;color:#3c4a5e;border-radius:6px;padding:3px 9px;margin:9px 6px 0 0;
  font-size:.77rem;font-weight:500}
.exp{display:flex;gap:18px;padding:12px 0;border-bottom:1px solid #eef1f5}
.exp .period{min-width:120px;color:#8a97a8;font-weight:600;font-size:.92rem}
.exp .role{font-weight:700}.exp .org{color:#566377}
.foot{margin-top:2.4rem;color:#94a2b3;font-size:.85rem}
@media(max-width:680px){.grid,.grid2{grid-template-columns:1fr}.hero{padding:28px 24px}.hero h1{font-size:1.9rem}}
"""


def e(s) -> str:
    return html.escape(str(s))


def render_lang(code: str, c: dict, has_cv: bool) -> str:
    meta = [f'<a href="mailto:{e(PROFILE["email"])}">{e(PROFILE["email"])}</a>', e(PROFILE["location"])]
    if PROFILE.get("linkedin"):
        meta.append(f'<a href="{e(PROFILE["linkedin"])}" target="_blank" rel="noopener">LinkedIn</a>')
    btns = [f'<a class="btn" href="mailto:{e(PROFILE["email"])}">✉️ {e(c["cta_contact"])}</a>']
    if PROFILE.get("linkedin"):
        btns.append(f'<a class="btn ghost" href="{e(PROFILE["linkedin"])}" target="_blank" rel="noopener">LinkedIn</a>')
    if has_cv:
        btns.append(f'<a class="btn ghost" href="cv.pdf" target="_blank">⬇️ {e(c["cta_cv"])}</a>')
    badge = f'<div class="badge">● {e(c["available"])}</div>' if c.get("available") else ""

    def sec(t):
        return f'<div class="sec"><h2>{e(t)}</h2><div class="rule"></div></div>'

    chips = "".join(f'<span class="chip">{e(x)}</span>' for x in c["skills"])
    highs = "".join(
        f'<div class="card"><div class="metric">{e(h["metric"])}</div><h4>{e(h["title"])}</h4>'
        f'<p>{e(h["text"])}</p></div>' for h in c["highlights"]
    )
    projs = ""
    for p in c["projects"]:
        tags = "".join(f'<span class="tagx">{e(t)}</span>' for t in p.get("tags", []))
        link = (f'<br><a href="{e(p["link"])}" target="_blank" rel="noopener">{e(p["link"])}</a>'
                if p.get("link") else "")
        projs += f'<div class="card"><h4>{e(p["title"])}</h4><p>{e(p["text"])}</p>{tags}{link}</div>'
    exps = "".join(
        f'<div class="exp"><div class="period">{e(x["period"])}</div>'
        f'<div><span class="role">{e(x["role"])}</span><br><span class="org">{e(x["org"])}</span></div></div>'
        for x in c["experience"]
    )
    return f"""
    <div class="lang" data-lang="{code}">
      <div class="hero">{badge}
        <div class="eyebrow">{e(c["role"])}</div>
        <h1>{e(PROFILE["name"])}</h1>
        <div class="tag">{e(c["tagline"])}</div>
        <div class="meta">{' · '.join(meta)}</div>
      </div>
      <div class="btns">{''.join(btns)}</div>
      {sec(c["about_title"])}<p class="about">{e(c["about"])}</p>
      {sec(c["skills_title"])}<div>{chips}</div>
      {sec(c["highlights_title"])}<div class="grid">{highs}</div>
      {sec(c["projects_title"])}<div class="grid2">{projs}</div>
      {sec(c["experience_title"])}<div>{exps}</div>
      {sec(c["contact_title"])}<p class="about">{e(c["contact_text"])}</p>
      <div class="btns">{''.join(btns)}</div>
      <div class="foot">{e(c["footer"])} · {e(PROFILE["email"])}</div>
    </div>"""


def build() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    has_cv = (HERE / PROFILE["cv_file"]).exists()
    if has_cv:
        shutil.copyfile(HERE / PROFILE["cv_file"], DOCS / "cv.pdf")
    (DOCS / ".nojekyll").write_text("")  # serve files as-is

    body = render_lang("en", CONTENT["en"], has_cv) + render_lang("nl", CONTENT["nl"], has_cv)
    page = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(PROFILE['name'])} — {e(CONTENT['en']['role'])}</title>
<meta name="description" content="{e(CONTENT['en']['tagline'])}">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body><div class="wrap">
  <div class="top">
    <button class="langbtn active" data-set="en">EN</button>
    <button class="langbtn" data-set="nl">NL</button>
  </div>
  {body}
</div>
<script>
  function setLang(l){{
    document.querySelectorAll('.lang').forEach(d=>d.style.display=(d.dataset.lang===l)?'block':'none');
    document.querySelectorAll('.langbtn').forEach(b=>b.classList.toggle('active',b.dataset.set===l));
    document.documentElement.lang=l; localStorage.setItem('lang',l);
  }}
  document.querySelectorAll('.langbtn').forEach(b=>b.onclick=()=>setLang(b.dataset.set));
  setLang(localStorage.getItem('lang')||'en');
</script>
</body></html>"""
    (DOCS / "index.html").write_text(page, encoding="utf-8")
    print(f"Wrote {DOCS/'index.html'}" + (" + cv.pdf" if has_cv else ""))


if __name__ == "__main__":
    build()

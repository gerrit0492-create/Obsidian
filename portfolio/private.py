"""Shared private area: the application tracker + live vacancy search.

Used by both the combined one-page app (app.py, behind a password) and the
standalone local tracker (tracker.py). Streamlit-driven render functions plus the
data helpers. Tracker data lives in the git-ignored data/applications.xlsx.
"""

from __future__ import annotations

import io
import os
import re
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

import overview
import vacancies
import generate_cv
import generate_letter
import store

HERE = Path(__file__).parent
DATA = HERE / "data" / "applications.xlsx"
PORTFOLIO_URL_DEFAULT = "https://gerrit0492-create.github.io/Obsidian/"

COLUMNS = [
    "Company", "Role", "Location", "Travel", "Source", "Contact", "Email", "Phone",
    "Link", "Priority", "Match", "Fit", "Applied", "Status", "Next action", "Next date",
    "Notes", "Log",
]
DATE_COLS = ["Applied", "Next date"]
STATUSES = ["Lead", "Applied", "Screening", "Interview", "Offer", "Rejected", "On hold", "Closed"]
SOURCES = ["Direct", "Bureau", "Vacature", "LinkedIn", "Referral", "Other"]
PRIORITIES = ["High", "Medium", "Low"]
FIT_OPTIONS = ["", "Ja", "Misschien", "Nee"]
CLOSED = {"Rejected", "Closed"}
PIPELINE = ["Lead", "Applied", "Screening", "Interview", "Offer"]

DOCS = ("CV.pdf", "CV.docx", "Motivatiebrief.pdf", "Motivatiebrief.docx")
_MIME = {"pdf": "application/pdf",
         "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def setting(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


def unlock(require_password: bool) -> bool:
    """Gate the private area. Returns True when access is granted.

    require_password=True (public deploy): a password is mandatory; without one
    configured the area stays locked. require_password=False (local tracker):
    a password is optional.
    """
    expected = setting("PRIVATE_PASSWORD") or setting("TRACKER_PASSWORD")
    if not expected:
        if require_password:
            st.info("🔒 Private area. Set PRIVATE_PASSWORD in .streamlit/secrets.toml to enable it.")
            return False
        st.warning("No password set — fine on your own computer. Set PRIVATE_PASSWORD to lock it.")
        return True
    if st.session_state.get("private_authed"):
        return True
    pw = st.text_input("Password", type="password", key="private_pw")
    if pw and pw == expected:
        st.session_state["private_authed"] = True
        st.rerun()
    elif pw:
        st.error("Wrong password.")
    return False


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[COLUMNS]
    for col in DATE_COLS:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _records(df: pd.DataFrame) -> list[dict]:
    out = []
    for r in df.to_dict("records"):
        rec = {}
        for k, v in r.items():
            if pd.isna(v):
                rec[k] = None
            elif k in DATE_COLS:
                t = pd.to_datetime(v, errors="coerce")
                rec[k] = None if pd.isna(t) else t.date().isoformat()
            else:
                rec[k] = v
        out.append(rec)
    return out


def _load_source() -> pd.DataFrame:
    token, gid = setting("GIST_TOKEN"), setting("GIST_ID")
    if store.enabled(token, gid):
        try:
            recs = store.load(token, gid)
            return _normalise(pd.DataFrame(recs) if recs else pd.DataFrame(columns=COLUMNS))
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Gist niet bereikbaar ({exc}) — lokale data gebruikt.")
    df = pd.read_excel(DATA) if DATA.exists() else pd.DataFrame(columns=COLUMNS)
    return _normalise(df)


def load_apps(force: bool = False) -> pd.DataFrame:
    """Cached load (per session) so the editor has a stable base; refresh with force=True."""
    if force or "apps_df" not in st.session_state:
        st.session_state["apps_df"] = _load_source()
    return st.session_state["apps_df"].copy()


def save_apps(df: pd.DataFrame) -> None:
    df = _normalise(df)
    token, gid = setting("GIST_TOKEN"), setting("GIST_ID")
    if store.enabled(token, gid):
        try:
            store.save(token, gid, _records(df))
        except Exception as exc:  # noqa: BLE001
            st.error(f"Opslaan naar Gist mislukt: {exc}")
    else:
        DATA.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(DATA, index=False)
    st.session_state["apps_df"] = df.copy()


def _to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def _overview_bytes(apps, vacs) -> bytes:
    try:
        url = setting("PORTFOLIO_URL", PORTFOLIO_URL_DEFAULT)
        return overview.render(apps, vacs, portfolio_url=url).encode("utf-8")
    except Exception as exc:  # noqa: BLE001
        import html as _h
        return (f"<!doctype html><meta charset=utf-8><p>Kon overzicht niet maken: "
                f"{_h.escape(str(exc))}</p>").encode("utf-8")


def add_vacancies(found: list[dict]) -> int:
    df = load_apps()
    existing = {(str(c).strip().lower(), str(r).strip().lower())
                for c, r in zip(df["Company"], df["Role"])}
    new_rows = []
    for v in found:
        key = (v["Company"].strip().lower(), v["Title"].strip().lower())
        if not v["Company"] or key in existing:
            continue
        existing.add(key)
        desc = v.get("Description", "")
        note = f"Gevonden via {v['Source']}" + (f" · {v['Posted']}" if v.get("Posted") else "")
        if desc:
            note += "\n" + desc[:600]
        new_rows.append({
            "Company": v["Company"], "Role": v["Title"], "Location": v["Location"],
            "Source": "Vacature", "Link": v["Link"], "Priority": "Medium",
            "Match": _match_score(f"{v.get('Title', '')} {desc}"),
            "Applied": pd.NaT, "Status": "Lead", "Next action": "Bekijk vacature + solliciteer",
            "Next date": pd.NaT, "Notes": note,
        })
    if new_rows:
        save_apps(pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)[COLUMNS])
    return len(new_rows)


def render_tracker() -> None:
    df = load_apps()

    token, gid = setting("GIST_TOKEN"), setting("GIST_ID")
    sc1, sc2 = st.columns([4, 1])
    sc1.caption("☁️ Opslag: privé GitHub Gist — gesynct op al je apparaten, blijft bewaard."
                if store.enabled(token, gid) else
                "💾 Opslag: lokaal bestand (op de cloud niet blijvend). Zet GIST_TOKEN + GIST_ID voor sync.")
    if sc2.button("🔄 Herladen", help="Haal de laatste data op (bv. na bewerken op een ander apparaat)"):
        load_apps(force=True)
        st.rerun()

    st.markdown(
        """<style>
        .kpis{display:flex;gap:10px;flex-wrap:wrap;margin:.2rem 0 .7rem}
        .kpi{flex:1;min-width:84px;background:#16223d;color:#fff;border-radius:12px;padding:10px 12px}
        .kpi .n{font-size:1.5rem;font-weight:800;line-height:1}
        .kpi .l{font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;opacity:.82;margin-top:2px}
        .stage{font-weight:700;color:#16223d;border-bottom:3px solid #2a9d8f;padding-bottom:4px;
               margin-bottom:8px;font-size:.92rem}
        .appcard{background:#fff;border:1px solid #e6ebf1;border-left:4px solid #2a9d8f;border-radius:10px;
                 padding:8px 10px;margin-bottom:6px;box-shadow:0 1px 4px rgba(22,34,61,.05)}
        .appcard .co{font-weight:700;color:#16223d;font-size:.88rem;line-height:1.15}
        .appcard .rl{color:#566377;font-size:.78rem}
        .appcard .nx{font-size:.74rem;margin-top:3px;color:#475569}
        .appcard .od{color:#c0392b;font-weight:600}
        </style>""",
        unsafe_allow_html=True,
    )

    # --- KPIs ---
    active = df[~df["Status"].isin(CLOSED)]
    kpis = [("Totaal", len(df)), ("Actief", len(active)),
            ("Interviews", int((df["Status"] == "Interview").sum())),
            ("Offers", int((df["Status"] == "Offer").sum()))]
    st.markdown("<div class='kpis'>" + "".join(
        f"<div class='kpi'><div class='n'>{n}</div><div class='l'>{lbl}</div></div>" for lbl, n in kpis
    ) + "</div>", unsafe_allow_html=True)

    # --- Pipeline board ---
    st.markdown("#### Pijplijn")
    st.caption("**→** schuift een sollicitatie een fase op · **📦** maakt direct CV + brief.")
    today = pd.Timestamp(date.today())
    stage_next = dict(zip(PIPELINE, PIPELINE[1:]))
    cols = st.columns(len(PIPELINE))
    for ci, stage in enumerate(PIPELINE):
        with cols[ci]:
            sub = df[df["Status"] == stage]
            st.markdown(f"<div class='stage'>{stage} · {len(sub)}</div>", unsafe_allow_html=True)
            for idx, row in sub.iterrows():
                nd = pd.to_datetime(row.get("Next date"), errors="coerce")
                nxt = ""
                if str(row.get("Next action") or "").strip():
                    od = pd.notna(nd) and nd < today
                    when = f" ({nd.date()})" if pd.notna(nd) else ""
                    nxt = f"<div class='nx {'od' if od else ''}'>→ {row['Next action']}{when}</div>"
                loc = f" · {row['Location']}" if str(row.get("Location") or "").strip() else ""
                m = row.get("Match")
                fit = row.get("Fit") if pd.notna(row.get("Fit")) else ""
                bits = [f"match {int(m)}%" if pd.notna(m) else "", f"past: {fit}" if fit else ""]
                meta = " · ".join(x for x in bits if x)
                metah = f"<div class='nx'>{meta}</div>" if meta else ""
                st.markdown(
                    f"<div class='appcard'><div class='co'>{row.get('Company') or '—'}</div>"
                    f"<div class='rl'>{row.get('Role') or ''}{loc}</div>{metah}{nxt}</div>",
                    unsafe_allow_html=True,
                )
                if stage in stage_next and st.button(f"→ {stage_next[stage]}", key=f"adv_{idx}"):
                    d2 = load_apps()
                    d2.loc[idx, "Status"] = stage_next[stage]
                    save_apps(d2)
                    st.rerun()

    other = df[df["Status"].isin(CLOSED) | (df["Status"] == "On hold")]
    if len(other):
        with st.expander(f"Overig / afgerond ({len(other)})"):
            for _, row in other.iterrows():
                st.markdown(f"- _{row.get('Status') or ''}_ — **{row.get('Company') or '—'}** · {row.get('Role') or ''}")

    # --- Per-application: follow, judge fit, append-only log, documents ---
    st.markdown("#### Volgen & documenten")
    opts = [i for i in df.index if str(df.at[i, "Company"] or "").strip()]
    if not opts:
        st.caption("Nog geen sollicitaties — voeg er een toe via Vacatures of de tabel hieronder.")
    else:
        sel = st.selectbox("Sollicitatie", opts, key="detail_sel",
                           format_func=lambda i: f"{df.at[i, 'Company']} — {df.at[i, 'Role'] or ''}".strip(" —"))
        row = df.loc[sel]
        m1, m2, m3 = st.columns(3)
        mv = row.get("Match")
        m1.metric("Match", f"{int(mv)}%" if pd.notna(mv) else "—")
        m2.metric("Past het?", row.get("Fit") if (pd.notna(row.get("Fit")) and row.get("Fit")) else "—")
        if m3.button("🔁 Herbereken match"):
            d = load_apps()
            d.at[sel, "Match"] = _match_score(f"{d.at[sel, 'Role'] or ''} {d.at[sel, 'Notes'] or ''}")
            save_apps(d)
            st.rerun()

        if setting("ANTHROPIC_API_KEY"):
            if st.button("🤖 AI-beoordeling van de match"):
                try:
                    st.session_state["ai_verdict"] = _ai_assess(f"{row.get('Role', '')}\n{row.get('Notes', '')}")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"AI-beoordeling mislukt: {exc}")
            if st.session_state.get("ai_verdict"):
                st.info(st.session_state["ai_verdict"])
        else:
            st.caption("Tip: zet ANTHROPIC_API_KEY in secrets voor een AI-oordeel over de match.")

        with st.form(f"logform_{sel}", clear_on_submit=True):
            entry = st.text_input("Update toevoegen aan logboek (wordt toegevoegd, niet overschreven)")
            if st.form_submit_button("➕ Toevoegen") and entry.strip():
                d = load_apps()
                stamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                prev = str(d.at[sel, "Log"]) if pd.notna(d.at[sel, "Log"]) else ""
                d.at[sel, "Log"] = f"{stamp} — {entry.strip()}" + (("\n" + prev) if prev else "")
                save_apps(d)
                st.rerun()
        log = str(row.get("Log")) if pd.notna(row.get("Log")) else ""
        if log.strip():
            st.text_area("Logboek (nieuwste boven)", value=log, height=130, disabled=True, key=f"logview_{sel}")

        rsn = st.text_input("Waarom dit bedrijf (voor de brief)", key="detail_reason")
        if st.button("📄 Genereer CV + motivatiebrief", type="primary", key="detail_gen"):
            try:
                files, _ = _application_package(row.get("Company", ""), row.get("Role", ""),
                                               row.get("Contact", ""), rsn, str(row.get("Notes") or ""))
                st.session_state["detail_files"] = files
                st.session_state["detail_slug"] = _slug(str(row.get("Company") or ""))
            except Exception as exc:  # noqa: BLE001
                st.error(f"Genereren mislukt: {exc}")
        if st.session_state.get("detail_files"):
            _dl_buttons(st.session_state["detail_files"], "detaildl", st.session_state.get("detail_slug", ""))

    # --- Follow-ups ---
    st.markdown("#### Opvolging")
    fu = df.copy()
    fu["Next date"] = pd.to_datetime(fu["Next date"], errors="coerce")
    fu = fu.dropna(subset=["Next date"])
    fu = fu[~fu["Status"].isin(CLOSED)].sort_values("Next date")
    if fu.empty:
        st.info("Geen geplande opvolging. Zet een 'Next date' op een sollicitatie (in de tabel hieronder).")
    else:
        overdue = int((fu["Next date"] < today).sum())
        if overdue:
            st.error(f"🔴 {overdue} opvolging(en) over tijd.")
        for _, row in fu.iterrows():
            flag = "🔴" if row["Next date"] < today else "🟢"
            st.markdown(f"{flag} **{row['Next date'].date()}** — {row.get('Company') or '—'} · "
                        f"_{row.get('Status') or ''}_ → {row.get('Next action') or '—'}")

    # --- Power editing (table) ---
    with st.expander("✏️ Alle sollicitaties bewerken (tabel)"):
        st.caption("Voeg onderaan een rij toe, bewerk cellen, selecteer + ⌫ om te verwijderen. Dan Opslaan.")
        edited = st.data_editor(
            df, num_rows="dynamic", use_container_width=True, hide_index=True, key="editor",
            column_config={
                "Link": st.column_config.LinkColumn("Link", display_text="open", width="small"),
                "Applied": st.column_config.DateColumn("Applied", format="YYYY-MM-DD"),
                "Next date": st.column_config.DateColumn("Next date", format="YYYY-MM-DD"),
                "Status": st.column_config.SelectboxColumn("Status", options=STATUSES, default="Lead"),
                "Source": st.column_config.SelectboxColumn("Source", options=SOURCES),
                "Priority": st.column_config.SelectboxColumn("Priority", options=PRIORITIES, default="Medium"),
                "Fit": st.column_config.SelectboxColumn("Fit", options=FIT_OPTIONS),
                "Match": st.column_config.NumberColumn("Match", format="%d%%"),
                "Notes": st.column_config.TextColumn("Notes", width="large"),
                "Log": st.column_config.TextColumn("Log", width="large"),
            },
        )
        e1, e2, e3 = st.columns(3)
        if e1.button("💾 Opslaan", type="primary"):
            save_apps(edited)
            st.success("Opgeslagen.")
            st.rerun()
        e2.download_button("⬇️ Excel", data=_to_excel_bytes(edited), file_name="applications.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        e3.download_button("📱 Mobiel overzicht", data=_overview_bytes(edited, st.session_state.get("vacancies")),
                           file_name="job_overview.html", mime="text/html")


def render_vacancies() -> None:
    st.subheader("Live vacatures zoeken")

    app_id = st.session_state.get("adz_id") or setting("ADZUNA_APP_ID")
    app_key = st.session_state.get("adz_key") or setting("ADZUNA_APP_KEY")
    with st.expander("🔑 Adzuna-key — betere NL-resultaten", expanded=not (app_id and app_key)):
        st.caption("Gratis key via developer.adzuna.com (registreer → App ID + App Key). "
                   "Plak hieronder; blijft in deze sessie. Of zet ADZUNA_APP_ID/KEY in secrets.")
        ka, kb = st.columns(2)
        app_id = ka.text_input("Adzuna App ID", value=app_id)
        app_key = kb.text_input("Adzuna App Key", value=app_key, type="password")
        st.session_state["adz_id"], st.session_state["adz_key"] = app_id, app_key

    st.caption("Bron: Adzuna (NL) — volledige dekking." if (app_id and app_key) else
               "Nog geen key → lichte keyless-bron. Vul hierboven je Adzuna-key in voor volledige NL-dekking.")
    f1, f2, f3 = st.columns([3, 1, 1])
    kw_raw = f1.text_input("Zoektermen (komma-gescheiden)", value=", ".join(vacancies.DEFAULT_KEYWORDS))
    where = f2.text_input("Regio", value="Eindhoven")
    distance = f3.slider("Straal (km)", 5, 100, 40, step=5)

    if st.button("🔄 Update vacatures", type="primary"):
        kws = [k.strip() for k in kw_raw.split(",") if k.strip()]
        with st.spinner("Zoeken…"):
            st.session_state["vacancies"] = vacancies.search(
                keywords=kws, where=where.strip() or "Eindhoven", distance=distance,
                app_id=app_id, app_key=app_key)

    results = st.session_state.get("vacancies")
    if results is None:
        st.info("Klik op **Update vacatures** om de laatst beschikbare functies op te halen.")
    elif not results:
        st.warning("Geen vacatures gevonden. Probeer bredere termen of een grotere straal.")
    else:
        st.success(f"{len(results)} vacatures gevonden. Klik bij een vacature op **Solliciteer** "
                   "→ CV + motivatiebrief worden meteen op maat gemaakt.")
        cc1, cc2 = st.columns(2)
        contact = cc1.text_input("Contactpersoon voor de brief", value="de heer/mevrouw", key="vac_contact")
        reason = cc2.text_input("Waarom dit bedrijf (optioneel)", value="", key="vac_reason")

        for i, v in enumerate(results[:25]):
            col = st.columns([6, 2])
            link = f" · [vacature]({v['Link']})" if v.get("Link") else ""
            posted = f" · {v['Posted']}" if v.get("Posted") else ""
            score = _match_score(f"{v.get('Title', '')} {v.get('Description', '')}")
            col[0].markdown(f"**{v['Title']}** — {v['Company']}  \n{v['Location']}{posted} · "
                            f"match {score}%{link}")
            if col[1].button("✍️ Solliciteer", key=f"gen_{i}"):
                try:
                    add_vacancies([v])  # also track it (skipped if already there)
                    files, _ = _application_package(v["Company"], v["Title"], contact, reason, v.get("Description", ""))
                    st.session_state[f"files_{i}"] = files
                except Exception as exc:  # noqa: BLE001
                    st.session_state[f"files_{i}"] = None
                    col[0].error(f"Kon documenten niet maken: {exc}")
            if st.session_state.get(f"files_{i}"):
                _dl_buttons(st.session_state[f"files_{i}"], f"vdl_{i}", _slug(v["Company"]))

        st.divider()
        d1, d2 = st.columns(2)
        d1.download_button("📱 Overzicht (HTML)", data=_overview_bytes(load_apps(), results),
                           file_name="job_overview.html", mime="text/html")
        if d2.button("➕ Alles toevoegen aan tracker"):
            st.success(f"{add_vacancies(results)} nieuwe vacature(s) toegevoegd aan de tracker.")


# Keywords we scan a vacancy text for, to tailor the CV's keyword line.
MASTER_KEYWORDS = [
    "cost engineer", "cost engineering", "cost estimator", "calculator", "calculatie",
    "kostprijs", "kostencalculatie", "should-cost", "nacalculatie", "offertecalculatie",
    "werkvoorbereider", "werkvoorbereiding", "manufacturing engineer", "industrialisatie",
    "routing", "maakstrategie", "lean", "six sigma", "green belt", "dmaic", "kaizen",
    "5s", "fmea", "sap", "power bi", "excel", "vba", "python", "cnc", "procesverbetering",
    "inkoop", "supply chain", "project management", "engineering",
]


def _matched_keywords(vacancy_text: str) -> list[str]:
    text = (vacancy_text or "").lower()
    return [k for k in MASTER_KEYWORDS if k in text]


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", (text or "sollicitatie")).strip("_") or "sollicitatie"


def _match_score(text: str) -> int:
    """A simple 'smart' fit score: how well a vacancy text overlaps the profile keywords."""
    return int(min(100, round(len(_matched_keywords(text)) / 8 * 100)))


def _application_package(company, role, contact="", reason="", vacancy_text=""):
    """Build a tailored CV + motivation letter (PDF + Word); return (files_dict, matched)."""
    matched = _matched_keywords(f"{vacancy_text} {role}")
    kwline = (", ".join(matched) + " — " + generate_cv.KEYWORDS) if matched else generate_cv.KEYWORDS
    role_title = (role or "").strip() or generate_cv.ROLE
    comp = (company or "").strip() or "[Bedrijf]"
    cont = (contact or "").strip() or "de heer/mevrouw"
    rsn = (reason or "").strip() or (
        f"de functie {role_title} en jullie organisatie goed aansluiten bij mijn ervaring in "
        "kostentechniek en de maakindustrie")
    files = {}
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        generate_cv.build_pdf(tdp / "CV.pdf", role_title=role_title, keywords=kwline)
        generate_cv.build_docx(tdp / "CV.docx", role_title=role_title, keywords=kwline)
        generate_letter.build_pdf(tdp / "Motivatiebrief.pdf", company=comp, role=role_title, contact=cont, reason=rsn)
        generate_letter.build_docx(tdp / "Motivatiebrief.docx", company=comp, role=role_title, contact=cont, reason=rsn)
        for name in DOCS:
            files[name] = (tdp / name).read_bytes()
    return files, matched


def _dl_buttons(files: dict, prefix: str, slug: str) -> None:
    """Render each generated document as its own download button (no zip)."""
    items = list(files.items())
    cols = st.columns(len(items))
    for j, (fn, fb) in enumerate(items):
        ext = fn.rsplit(".", 1)[-1]
        cols[j].download_button(f"⬇️ {fn}", fb, file_name=f"{slug}_{fn}",
                                mime=_MIME.get(ext, "application/octet-stream"), key=f"{prefix}_{j}")


def _ai_assess(vacancy_text: str):
    """Optional real-AI fit verdict via the Anthropic API (needs ANTHROPIC_API_KEY)."""
    key = setting("ANTHROPIC_API_KEY")
    if not key:
        return None
    import requests
    profile = generate_cv.PROFILE + " Vaardigheden: " + generate_cv.SKILLS
    prompt = (f"Kandidaatprofiel:\n{profile}\n\nVacature:\n{vacancy_text}\n\n"
              "Beoordeel in het Nederlands of deze vacature bij de kandidaat past. "
              "Geef een matchscore 0-100 en 2-3 zinnen onderbouwing.")
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": "claude-haiku-4-5-20251001", "max_tokens": 400,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=40)
    r.raise_for_status()
    return r.json()["content"][0]["text"]



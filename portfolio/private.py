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
import zipfile
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
    "Link", "Priority", "Applied", "Status", "Next action", "Next date", "Notes",
]
DATE_COLS = ["Applied", "Next date"]
STATUSES = ["Lead", "Applied", "Screening", "Interview", "Offer", "Rejected", "On hold", "Closed"]
SOURCES = ["Direct", "Bureau", "Vacature", "LinkedIn", "Referral", "Other"]
PRIORITIES = ["High", "Medium", "Low"]
CLOSED = {"Rejected", "Closed"}
PIPELINE = ["Lead", "Applied", "Screening", "Interview", "Offer"]


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
        new_rows.append({
            "Company": v["Company"], "Role": v["Title"], "Location": v["Location"],
            "Source": "Vacature", "Link": v["Link"], "Priority": "Medium",
            "Applied": pd.NaT, "Status": "Lead", "Next action": "Bekijk vacature + solliciteer",
            "Next date": pd.NaT, "Notes": f"Gevonden via {v['Source']}" + (f" · {v['Posted']}" if v["Posted"] else ""),
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
                st.markdown(
                    f"<div class='appcard'><div class='co'>{row.get('Company') or '—'}</div>"
                    f"<div class='rl'>{row.get('Role') or ''}{loc}</div>{nxt}</div>",
                    unsafe_allow_html=True,
                )
                b = st.columns(2)
                if stage in stage_next and b[0].button("→", key=f"adv_{idx}", help=f"Naar {stage_next[stage]}"):
                    d2 = load_apps()
                    d2.loc[idx, "Status"] = stage_next[stage]
                    save_apps(d2)
                    st.rerun()
                if b[1].button("📦", key=f"cardpkg_{idx}", help="Genereer CV + brief"):
                    try:
                        pkg, _ = _application_package(row.get("Company", ""), row.get("Role", ""),
                                                     row.get("Contact", ""), "", str(row.get("Notes") or ""))
                        st.session_state[f"cardpkg_{idx}"] = pkg
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Pakket mislukt: {exc}")
                if st.session_state.get(f"cardpkg_{idx}"):
                    st.download_button("⬇️ pakket", st.session_state[f"cardpkg_{idx}"],
                                       file_name=f"sollicitatie_{_slug(str(row.get('Company') or ''))}.zip",
                                       mime="application/zip", key=f"carddl_{idx}")

    other = df[df["Status"].isin(CLOSED) | (df["Status"] == "On hold")]
    if len(other):
        with st.expander(f"Overig / afgerond ({len(other)})"):
            for _, row in other.iterrows():
                st.markdown(f"- _{row.get('Status') or ''}_ — **{row.get('Company') or '—'}** · {row.get('Role') or ''}")

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
                "Notes": st.column_config.TextColumn("Notes", width="large"),
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
            col = st.columns([6, 2, 2])
            link = f" · [vacature]({v['Link']})" if v.get("Link") else ""
            posted = f" · {v['Posted']}" if v.get("Posted") else ""
            col[0].markdown(f"**{v['Title']}** — {v['Company']}  \n{v['Location']}{posted}{link}")
            if col[1].button("✍️ Solliciteer", key=f"gen_{i}"):
                try:
                    add_vacancies([v])  # also track it (skipped if already there)
                    pkg, _ = _application_package(v["Company"], v["Title"], contact, reason, v.get("Description", ""))
                    st.session_state[f"pkg_{i}"] = pkg
                except Exception as exc:  # noqa: BLE001
                    st.session_state[f"pkg_{i}"] = None
                    col[0].error(f"Kon pakket niet maken: {exc}")
            if st.session_state.get(f"pkg_{i}"):
                col[2].download_button("📦 Download", data=st.session_state[f"pkg_{i}"],
                                       file_name=f"sollicitatie_{_slug(v['Company'])}.zip",
                                       mime="application/zip", key=f"dl_{i}")

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


def _application_package(company, role, contact="", reason="", vacancy_text=""):
    """Build a tailored CV + motivation letter (PDF + Word) and return (zip_bytes, matched)."""
    matched = _matched_keywords(f"{vacancy_text} {role}")
    kwline = (", ".join(matched) + " — " + generate_cv.KEYWORDS) if matched else generate_cv.KEYWORDS
    role_title = (role or "").strip() or generate_cv.ROLE
    comp = (company or "").strip() or "[Bedrijf]"
    cont = (contact or "").strip() or "de heer/mevrouw"
    rsn = (reason or "").strip() or (
        f"de functie {role_title} en jullie organisatie goed aansluiten bij mijn ervaring in "
        "kostentechniek en de maakindustrie")
    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        generate_cv.build_pdf(tdp / "CV.pdf", role_title=role_title, keywords=kwline)
        generate_cv.build_docx(tdp / "CV.docx", role_title=role_title, keywords=kwline)
        generate_letter.build_pdf(tdp / "Motivatiebrief.pdf", company=comp, role=role_title, contact=cont, reason=rsn)
        generate_letter.build_docx(tdp / "Motivatiebrief.docx", company=comp, role=role_title, contact=cont, reason=rsn)
        with zipfile.ZipFile(buf, "w") as z:
            for f in ("CV.pdf", "CV.docx", "Motivatiebrief.pdf", "Motivatiebrief.docx"):
                z.write(tdp / f, arcname=f)
    return buf.getvalue(), matched


def render_tailor() -> None:
    st.subheader("Sollicitatie op maat — CV + brief per vacature")
    st.caption("Vul de velden in (en plak desgewenst de vacaturetekst); je krijgt een afgestemde "
               "CV én motivatiebrief in PDF + Word als één download.")
    c1, c2 = st.columns(2)
    company = c1.text_input("Bedrijf")
    role = c2.text_input("Functie (zoals in de vacature)")
    contact = c1.text_input("Contactpersoon", value="de heer/mevrouw")
    reason = c2.text_input("Waarom dit bedrijf", value="jullie focus op complexe high-tech maakindustrie")
    vac = st.text_area("Vacaturetekst (optioneel — voor keyword-afstemming)", height=170)

    if st.button("✍️ Genereer CV + brief", type="primary"):
        try:
            pkg, matched = _application_package(company, role, contact, reason, vac)
            st.session_state["pkg"] = pkg
            st.session_state["pkg_matched"] = matched
            st.session_state["pkg_name"] = _slug(company)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Kon het pakket niet maken: {exc}. Tip: reboot de app zodat de nieuwste "
                     "code en pakketten (python-docx) geladen zijn.")

    if st.session_state.get("pkg"):
        matched = st.session_state.get("pkg_matched") or []
        if matched:
            st.success("Keywords uit de vacature meegenomen: " + ", ".join(matched))
        st.download_button(
            "📦 Download pakket (CV + brief · PDF + Word)",
            data=st.session_state["pkg"],
            file_name=f"sollicitatie_{st.session_state.get('pkg_name', '')}.zip",
            mime="application/zip",
        )

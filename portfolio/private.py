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


def load_apps() -> pd.DataFrame:
    if DATA.exists():
        df = pd.read_excel(DATA)
    else:
        df = pd.DataFrame(columns=COLUMNS)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[COLUMNS]
    for col in DATE_COLS:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def save_apps(df: pd.DataFrame) -> None:
    DATA.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(DATA, index=False)


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

    active = df[~df["Status"].isin(CLOSED)]
    applied_plus = df[df["Status"].isin(["Applied", "Screening", "Interview", "Offer"])]
    k = st.columns(5)
    k[0].metric("Total", len(df))
    k[1].metric("Active", len(active))
    k[2].metric("Applied+", len(applied_plus))
    k[3].metric("Interviews", int((df["Status"] == "Interview").sum()))
    k[4].metric("Offers", int((df["Status"] == "Offer").sum()))

    st.subheader("Pipeline")
    pcols = st.columns(len(PIPELINE))
    for col, s in zip(pcols, PIPELINE):
        col.metric(s, int((df["Status"] == s).sum()))

    st.subheader("Applications")
    st.caption("Add a row at the bottom, edit any cell, or select a row and press ⌫ to delete. Then Save.")
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

    c1, c2, c3, _ = st.columns([1, 1, 1.4, 3])
    if c1.button("💾 Save", type="primary"):
        save_apps(edited)
        st.success("Saved to data/applications.xlsx")
    c2.download_button("⬇️ Excel", data=_to_excel_bytes(edited), file_name="applications.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    c3.download_button("📱 Mobiel overzicht (HTML)",
                       data=_overview_bytes(edited, st.session_state.get("vacancies")),
                       file_name="job_overview.html", mime="text/html",
                       help="Self-contained snapshot — save it on your phone and open offline.")

    # --- Per-application package: CV + motivation letter, tied to a tracked app ---
    st.subheader("Sollicitatiepakket (CV + motivatiebrief)")
    apps_list = [r for r in edited.to_dict("records") if str(r.get("Company") or "").strip()]
    if not apps_list:
        st.caption("Voeg een sollicitatie toe (hierboven, of via Vacatures) om een pakket te maken.")
    else:
        labels = [f"{r['Company']} — {r.get('Role') or ''}".strip(" —") for r in apps_list]
        idx = st.selectbox("Kies sollicitatie", range(len(labels)),
                           format_func=lambda i: labels[i], key="pkg_pick")
        chosen = apps_list[idx]
        rsn = st.text_input("Waarom dit bedrijf (optioneel)", key="pkg_reason")
        if st.button("✍️ Genereer CV + brief", key="pkg_make", type="primary"):
            try:
                pkg, matched = _application_package(
                    chosen["Company"], chosen.get("Role", ""), chosen.get("Contact", ""),
                    rsn, str(chosen.get("Notes") or ""))
                st.session_state["trk_pkg"] = pkg
                st.session_state["trk_pkg_name"] = _slug(chosen["Company"])
                if matched:
                    st.caption("Keywords meegenomen: " + ", ".join(matched))
            except Exception as exc:  # noqa: BLE001
                st.error(f"Kon pakket niet maken: {exc}. Reboot de app voor de nieuwste code/pakketten.")
        if st.session_state.get("trk_pkg"):
            st.download_button("📦 Download pakket (CV + brief · PDF + Word)",
                               data=st.session_state["trk_pkg"],
                               file_name=f"sollicitatie_{st.session_state.get('trk_pkg_name', '')}.zip",
                               mime="application/zip", key="trk_dl")

    st.subheader("Follow-ups")
    fu = edited.copy()
    fu["Next date"] = pd.to_datetime(fu["Next date"], errors="coerce")
    fu = fu.dropna(subset=["Next date"]).sort_values("Next date")
    fu = fu[~fu["Status"].isin(CLOSED)]
    if fu.empty:
        st.info("No upcoming follow-ups. Set a 'Next date' on an application to see it here.")
    else:
        today = pd.Timestamp(date.today())
        overdue = int((fu["Next date"] < today).sum())
        if overdue:
            st.error(f"🔴 {overdue} follow-up(s) overdue.")
        for _, row in fu.iterrows():
            flag = "🔴 overdue" if row["Next date"] < today else "🟢"
            prio = f" · {row['Priority']}" if (pd.notna(row.get("Priority")) and row.get("Priority")) else ""
            st.markdown(
                f"**{row['Next date'].date()}** {flag} — **{row['Company'] or '—'}** · {row['Role'] or ''} "
                f"· _{row['Status'] or ''}_{prio} → {row['Next action'] or '—'}"
            )


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

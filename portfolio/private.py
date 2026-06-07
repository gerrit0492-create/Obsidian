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
from urllib.parse import quote_plus

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

DOCS = ("CV.pdf", "CV.docx", "Motivatiebrief_NL.pdf", "Motivatiebrief_NL.docx",
        "Motivation_EN.pdf", "Motivation_EN.docx")
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
        if v.get("Salary"):
            note += f" · {v['Salary']}"
        if desc:
            note += "\n" + desc
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


def render_work() -> None:
    """One job per screen with big tap actions — review your New queue fast."""
    st.markdown(
        """<style>
        .jobcard{background:#fff;border:1px solid #e6ebf1;border-top:5px solid #2a9d8f;border-radius:16px;
                 padding:20px 22px;box-shadow:0 3px 14px rgba(22,34,61,.07);margin-bottom:12px}
        .jobcard .co{font-size:1.25rem;font-weight:800;color:#16223d;line-height:1.15}
        .jobcard .rl{color:#566377;font-size:1rem;margin-top:2px}
        .jobcard .mt{display:inline-block;background:#eef5f3;color:#1d7d6e;border-radius:999px;
                     padding:3px 12px;font-weight:700;font-size:.85rem;margin-top:10px}
        .jobcard .ds{color:#475569;font-size:.9rem;line-height:1.5;margin-top:12px}
        div[data-testid="stButton"] button{padding:12px 0;font-size:1rem;font-weight:600}
        </style>""",
        unsafe_allow_html=True,
    )
    df = load_apps()
    queue = [i for i in df.index if str(df.at[i, "Company"] or "").strip()
             and _lifecycle(df.at[i, "Status"], df.at[i, "Fit"]) == "New"]
    queue.sort(key=lambda i: (df.at[i, "Match"] if pd.notna(df.at[i, "Match"]) else -1), reverse=True)

    st.markdown("#### Review new jobs")
    if not queue:
        st.success("🎉 Nothing left to review. New jobs arrive via 🔎 Vacatures (auto).")
        return

    pos = min(st.session_state.get("work_pos", 0), len(queue) - 1)
    sel = queue[pos]
    row = df.loc[sel]
    st.caption(f"{pos + 1} of {len(queue)} new · best match first")

    m = row.get("Match")
    mt = f"<span class='mt'>match {int(m)}%</span>" if pd.notna(m) else ""
    loc = f" · {row['Location']}" if str(row.get("Location") or "").strip() else ""
    link = (f'<br><a href="{row.get("Link")}" target="_blank">open vacancy ↗</a>'
            if str(row.get("Link") or "").strip() else "")
    notes = str(row.get("Notes") or "")
    snippet = (notes[:260] + "…") if len(notes) > 260 else notes
    st.markdown(
        f"<div class='jobcard'><div class='co'>{row.get('Company') or '—'}</div>"
        f"<div class='rl'>{row.get('Role') or ''}{loc}</div>{mt}"
        f"<div class='ds'>{snippet}{link}</div></div>",
        unsafe_allow_html=True,
    )
    rh = _research_html(str(row.get("Company") or ""), str(row.get("Role") or ""), str(row.get("Link") or ""))
    if rh:
        st.markdown(rh, unsafe_allow_html=True)
    if len(notes) > 260:
        with st.expander("📄 Volledige vacaturetekst"):
            st.write(notes)

    b = st.columns(3)
    if b[0].button("🗑️ Discard", use_container_width=True, key="w_disc"):
        st.session_state["work_undo"] = {"i": sel, "Status": str(row.get("Status") or ""),
                                         "Fit": str(row.get("Fit") or ""), "co": str(row.get("Company") or "")}
        d = load_apps()
        d.at[sel, "Status"], d.at[sel, "Fit"] = "Rejected", "Nee"
        save_apps(d)
        st.rerun()
    if b[1].button("➡️ Skip", use_container_width=True, key="w_skip"):
        st.session_state["work_pos"] = pos + 1
        st.rerun()
    if b[2].button("⭐ Select", use_container_width=True, key="w_sel"):
        st.session_state["work_undo"] = {"i": sel, "Status": str(row.get("Status") or ""),
                                         "Fit": str(row.get("Fit") or ""), "co": str(row.get("Company") or "")}
        d = load_apps()
        d.at[sel, "Fit"] = "Ja"
        save_apps(d)
        st.rerun()

    u = st.session_state.get("work_undo")
    if u and st.button(f"↩️ Undo last ({u['co']})", use_container_width=True, key="w_undo"):
        d = load_apps()
        if u["i"] in d.index:
            d.at[u["i"], "Status"], d.at[u["i"], "Fit"] = (u["Status"] or "Lead"), u["Fit"]
            save_apps(d)
        st.session_state.pop("work_undo", None)
        st.rerun()

    if st.button("📄 Generate CV + motivation letters (NL + EN)", use_container_width=True, key="w_gen"):
        try:
            files, _ = _application_package(row.get("Company", ""), row.get("Role", ""),
                                           row.get("Contact", ""), notes)
            st.session_state["w_files"] = files
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not generate: {exc}")
    if st.session_state.get("w_files"):
        _dl_buttons(st.session_state["w_files"], "wdl", _slug(str(row.get("Company") or "")))


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

    # --- Compact pipeline overview ---
    today = pd.Timestamp(date.today())
    st.caption("Pijplijn — " + " · ".join(f"{s}: {int((df['Status'] == s).sum())}" for s in PIPELINE))

    # --- One application: the whole process in one overview ---
    st.markdown("#### Sollicitatie")
    opts = [i for i in df.index if str(df.at[i, "Company"] or "").strip()]
    if not opts:
        st.info("Nog geen sollicitaties. Ga naar **🔎 Vacatures**, zoek en klik **➕ In tracker**.")
    else:
        def _category(i):
            return _lifecycle(df.at[i, "Status"], df.at[i, "Fit"])

        cats = {c: sum(1 for i in opts if _category(i) == c) for c in ("New", "Selected", "Applied", "Discarded")}
        labels = [f"{c} ({cats[c]})" for c in ("New", "Selected", "Applied", "Discarded")] + ["All"]
        choice = st.radio("Selectie", labels, horizontal=True, key="crit", label_visibility="collapsed")
        crit = choice.split(" (")[0]

        shown = [i for i in opts if crit == "All" or _category(i) == crit]
        shown.sort(key=lambda i: (df.at[i, "Match"] if pd.notna(df.at[i, "Match"]) else -1), reverse=True)
        if not shown:
            st.caption("Geen sollicitaties in deze status.")
        else:
            view = df.loc[shown, ["Company", "Role", "Status", "Match", "Fit", "Next action", "Next date"]]
            st.dataframe(
                view, use_container_width=True, hide_index=True,
                column_config={
                    "Next action": st.column_config.TextColumn("Volgende actie"),
                    "Next date": st.column_config.DateColumn("Volgende datum", format="YYYY-MM-DD"),
                    "Match": st.column_config.NumberColumn("Match", format="%d%%"),
                },
            )
            st.caption(f"{len(shown)} sollicitatie(s) — kies er een hieronder om te openen en bewerken.")
            sel = st.selectbox(
                "Kies sollicitatie", shown, key="sel",
                format_func=lambda i: f"{df.at[i, 'Company']} — {df.at[i, 'Role'] or ''} "
                                      f"[{df.at[i, 'Status'] or 'Lead'}]".strip())
            row = df.loc[sel]

            st.markdown(f"**{row.get('Company') or '—'}** — {row.get('Role') or ''} · "
                        f"{row.get('Location') or ''}")
            rh = _research_html(str(row.get("Company") or ""), str(row.get("Role") or ""), str(row.get("Link") or ""))
            if rh:
                st.markdown(rh, unsafe_allow_html=True)
            dnotes = str(row.get("Notes") or "")
            if dnotes.strip():
                with st.expander("📄 Volledige vacaturetekst"):
                    st.write(dnotes)
            discarded = str(row.get("Status")) in CLOSED or str(row.get("Fit")) == "Nee"
            qa = st.columns(2)
            if discarded:
                if qa[0].button("↩️ Restore to New", key=f"restore_{sel}"):
                    d = load_apps()
                    d.at[sel, "Status"], d.at[sel, "Fit"] = "Lead", ""
                    save_apps(d)
                    st.rerun()
            else:
                if qa[0].button("🗑️ Discard", key=f"discard_{sel}"):
                    d = load_apps()
                    d.at[sel, "Status"], d.at[sel, "Fit"] = "Rejected", "Nee"
                    save_apps(d)
                    st.rerun()
            mc = st.columns(3)
            mv = row.get("Match")
            mc[0].metric("Match", f"{int(mv)}%" if pd.notna(mv) else "—")
            mc[1].metric("Past het?", row.get("Fit") if (pd.notna(row.get("Fit")) and row.get("Fit")) else "—")
            if mc[2].button("🔁 Herbereken match"):
                d = load_apps()
                d.at[sel, "Match"] = _match_score(f"{d.at[sel, 'Role'] or ''} {d.at[sel, 'Notes'] or ''}")
                save_apps(d)
                st.rerun()

            # One form: status + fit + follow-up + optional log entry
            cur_nd = pd.to_datetime(row.get("Next date"), errors="coerce")
            cur_status = row.get("Status") if row.get("Status") in STATUSES else "Lead"
            cur_fit = row.get("Fit") if (pd.notna(row.get("Fit")) and row.get("Fit") in FIT_OPTIONS) else ""
            with st.form(f"edit_{sel}"):
                fc = st.columns(2)
                status = fc[0].selectbox("Status", STATUSES, index=STATUSES.index(cur_status))
                fit = fc[1].selectbox("Past het?", FIT_OPTIONS, index=FIT_OPTIONS.index(cur_fit))
                na = st.text_input("Volgende actie", value=str(row.get("Next action") or ""))
                nd = st.date_input("Volgende datum", value=cur_nd.date() if pd.notna(cur_nd) else None)
                note = st.text_input("Notitie toevoegen aan logboek (optioneel)")
                if st.form_submit_button("💾 Opslaan", type="primary"):
                    d = load_apps()
                    d.at[sel, "Status"] = status
                    d.at[sel, "Fit"] = fit
                    d.at[sel, "Next action"] = na
                    d.at[sel, "Next date"] = pd.Timestamp(nd) if nd else pd.NaT
                    if note.strip():
                        stamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                        prev = str(d.at[sel, "Log"]) if pd.notna(d.at[sel, "Log"]) else ""
                        d.at[sel, "Log"] = f"{stamp} — {note.strip()}" + (("\n" + prev) if prev else "")
                    save_apps(d)
                    st.success("Opgeslagen.")
                    st.rerun()

            log = str(row.get("Log")) if pd.notna(row.get("Log")) else ""
            if log.strip():
                st.text_area("Logboek (nieuwste boven)", value=log, height=120, disabled=True, key=f"logv_{sel}")

            if setting("ANTHROPIC_API_KEY"):
                if st.button("🤖 AI-beoordeling van de match"):
                    try:
                        st.session_state[f"ai_{sel}"] = _ai_assess(f"{row.get('Role', '')}\n{row.get('Notes', '')}")
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"AI-beoordeling mislukt: {exc}")
                if st.session_state.get(f"ai_{sel}"):
                    st.info(st.session_state[f"ai_{sel}"])

            st.markdown("**Documenten**")
            st.caption("CV + motivatiebrieven (NL + EN), automatisch afgestemd op deze vacature.")
            if st.button("📄 Genereer CV + motivatiebrieven (NL + EN)", key=f"gen_{sel}"):
                try:
                    files, _ = _application_package(row.get("Company", ""), row.get("Role", ""),
                                                   row.get("Contact", ""), str(row.get("Notes") or ""))
                    st.session_state[f"files_{sel}"] = files
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Genereren mislukt: {exc}")
            if st.session_state.get(f"files_{sel}"):
                _dl_buttons(st.session_state[f"files_{sel}"], f"ddl_{sel}", _slug(str(row.get("Company") or "")))

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

    jooble_key = st.session_state.get("jooble_key") or setting("JOOBLE_API_KEY")
    with st.expander("🔑 Jooble-key — extra NL-bron", expanded=False):
        st.caption("Gratis key via jooble.org/api/about. Plak hieronder; blijft in deze sessie. "
                   "Of zet JOOBLE_API_KEY in secrets.")
        jooble_key = st.text_input("Jooble API key", value=jooble_key, type="password")
        st.session_state["jooble_key"] = jooble_key

    jsearch_key = st.session_state.get("jsearch_key") or setting("JSEARCH_API_KEY")
    with st.expander("🔑 JSearch-key — Google for Jobs / LinkedIn / Indeed", expanded=False):
        st.caption("Gratis tier via rapidapi.com → JSearch (RapidAPI-key). Plak hieronder; blijft "
                   "in deze sessie. Of zet JSEARCH_API_KEY in secrets.")
        jsearch_key = st.text_input("JSearch (RapidAPI) key", value=jsearch_key, type="password")
        st.session_state["jsearch_key"] = jsearch_key

    srcs = ([n for n, on in (("Adzuna", app_id and app_key), ("Jooble", jooble_key),
                             ("JSearch", jsearch_key)) if on])
    has_key = bool(srcs)
    st.caption(f"Bron(nen): {', '.join(srcs)} — volledige NL-dekking." if has_key else
               "Nog geen key → lichte keyless-bron. Vul een Adzuna- of Jooble-key in voor volledige NL-dekking.")
    auto = st.toggle("⚡ Auto: ophalen + nieuwe direct in tracker", value=True, key="auto_vac",
                     help="Haalt bij openen automatisch vacatures op en zet de nieuwe (geen afgewezen) in de tracker.")
    f1, f2, f3 = st.columns([3, 1, 1])
    kw_raw = f1.text_input("Zoektermen (komma-gescheiden)", value=", ".join(vacancies.DEFAULT_KEYWORDS))
    where = f2.text_input("Regio", value="Eindhoven")
    distance = f3.slider("Straal (km)", 5, 100, 40, step=5)

    def _do_search():
        kws = [k.strip() for k in kw_raw.split(",") if k.strip()]
        return vacancies.search(keywords=kws, where=where.strip() or "Eindhoven",
                                distance=distance, app_id=app_id, app_key=app_key,
                                jooble_key=jooble_key, jsearch_key=jsearch_key)

    # Auto: on first visit this session, fetch and add new ones to the tracker.
    if auto and has_key and not st.session_state.get("auto_done"):
        with st.spinner("Vacatures automatisch ophalen…"):
            st.session_state["vacancies"] = _do_search()
        added = add_vacancies(st.session_state["vacancies"] or [])
        st.session_state["auto_done"] = True
        if added:
            st.success(f"⚡ {added} nieuwe vacature(s) automatisch in de tracker gezet.")

    if st.button("🔄 Update vacatures", type="primary"):
        with st.spinner("Zoeken…"):
            st.session_state["vacancies"] = _do_search()
        if auto:
            add_vacancies(st.session_state["vacancies"] or [])

    results = st.session_state.get("vacancies")
    if results is None:
        st.info("Klik op **Update vacatures** om de laatst beschikbare functies op te halen.")
    elif not results:
        st.warning("Geen vacatures gevonden. Probeer bredere termen of een grotere straal.")
    else:
        cur = load_apps()

        def _key(co, ro):
            return (str(co or "").strip().lower(), str(ro or "").strip().lower())

        rejected = {_key(r["Company"], r["Role"]) for _, r in cur.iterrows()
                    if str(r.get("Status")) == "Rejected" or str(r.get("Fit")) == "Nee"}
        existing = {_key(r["Company"], r["Role"]) for _, r in cur.iterrows()}
        good, bad = _learned_sets(cur)

        ranked = []
        for v in results:
            k = _key(v.get("Company"), v.get("Title"))
            if k in rejected:                       # discard what you already rejected
                continue
            rec = _recommend(f"{v.get('Title', '')} {v.get('Description', '')}", good, bad)
            ranked.append((rec, k in existing, v))
        ranked.sort(key=lambda x: -x[0])

        learned = " · het dashboard leert van je keuzes (Ja/Nee)." if (good or bad) else ""
        st.success(f"{len(ranked)} vacatures (afgewezen verborgen){learned}")
        if st.button("⚡ Nieuwe automatisch toevoegen (slim)", type="primary"):
            new_vs = [v for _, inx, v in ranked if not inx]
            st.success(f"{add_vacancies(new_vs)} nieuwe toegevoegd · bekende/afgewezen overgeslagen.")
            st.rerun()

        for i, (rec, inx, v) in enumerate(ranked[:30]):
            col = st.columns([6, 2])
            link = f" · [vacature]({v['Link']})" if v.get("Link") else ""
            posted = f" · {v['Posted']}" if v.get("Posted") else ""
            star = "⭐ " if rec >= 60 else ""
            col[0].markdown(f"{star}**{v['Title']}** — {v['Company']}  \n{v['Location']}{posted} · "
                            f"score {rec}%{link}")
            if inx or st.session_state.get(f"added_{i}"):
                col[1].caption("in tracker ✓")
            elif col[1].button("➕ In tracker", key=f"add_{i}"):
                add_vacancies([v])
                st.session_state[f"added_{i}"] = True
                st.rerun()

        st.divider()
        st.download_button("📱 Overzicht (HTML)", data=_overview_bytes(cur, results),
                           file_name="job_overview.html", mime="text/html")


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


def _research_html(company: str, role: str, link: str) -> str:
    """A row of tap targets: open the vacancy + one-click research links.

    Adzuna only returns a short blurb, so the real detail is on the posting and
    via a quick web/LinkedIn search — surface those instead of a tiny link.
    """
    company, role = (company or "").strip(), (role or "").strip()
    cr = quote_plus(f'"{company}" {role} vacature'.strip())
    chips = []
    if str(link or "").strip():
        chips.append((f"🔗 {('Open vacature')}", link))
    if company:
        chips.append(("🔎 Google", f"https://www.google.com/search?q={cr}"))
        chips.append(("💼 LinkedIn", f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(f'{company} {role}'.strip())}"))
        chips.append(("🏢 Werken bij", f"https://www.google.com/search?q={quote_plus(f'werken bij {company}')}"))
    if not chips:
        return ""
    style = ("display:inline-block;margin:6px 8px 0 0;padding:8px 14px;border-radius:9px;"
             "background:#16223d;color:#fff !important;text-decoration:none;font-weight:600;font-size:.9rem")
    ghost = style.replace("#16223d", "#eef2f6").replace("#fff", "#16223d")
    out = []
    for i, (label, href) in enumerate(chips):
        out.append(f'<a href="{href}" target="_blank" style="{style if i == 0 else ghost}">{label}</a>')
    return "<div style='margin:4px 0 6px'>" + "".join(out) + "</div>"


def _match_score(text: str) -> int:
    """A simple 'smart' fit score: how well a vacancy text overlaps the profile keywords."""
    return int(min(100, round(len(_matched_keywords(text)) / 8 * 100)))


def _learned_sets(df):
    """Learn which keywords you tend to accept vs reject, from your tracker history."""
    good, bad = set(), set()
    for _, r in df.iterrows():
        kws = set(_matched_keywords(f"{r.get('Role', '')} {r.get('Notes', '')}"))
        status, fit = str(r.get("Status") or ""), str(r.get("Fit") or "")
        if status == "Rejected" or fit == "Nee":
            bad |= kws
        elif fit == "Ja" or status in ("Applied", "Screening", "Interview", "Offer"):
            good |= kws
    return good, bad


def _recommend(text, good, bad) -> int:
    """Recommendation score that adapts to your accept/reject history."""
    t = (text or "").lower()
    g = sum(1 for k in good if k in t)
    b = sum(1 for k in bad if k in t)
    return max(0, min(100, _match_score(text) + g * 8 - b * 10))


def _lifecycle(status, fit) -> str:
    s, f = str(status or ""), str(fit or "")
    if s in CLOSED or f == "Nee":
        return "Discarded"
    if s in ("Applied", "Screening", "Interview", "Offer"):
        return "Applied"
    if f == "Ja":
        return "Selected"
    return "New"


def _application_package(company, role, contact="", vacancy_text=""):
    """Build a tailored CV + NL/EN motivation letters (PDF + Word).

    The letters relate the CV to the vacancy automatically via ``matched`` (the
    keywords the vacancy and profile share) — no manual 'why this company' text.
    Returns (files_dict, matched).
    """
    matched = _matched_keywords(f"{vacancy_text} {role}")
    kwline = (", ".join(matched) + " — " + generate_cv.KEYWORDS) if matched else generate_cv.KEYWORDS
    role_title = (role or "").strip() or generate_cv.ROLE
    comp = (company or "").strip()
    cont = (contact or "").strip()
    # Smart, vacancy-aligned body when an API key is set; else the clean template.
    body_nl = _ai_letter(comp, role_title, vacancy_text, "nl")
    body_en = _ai_letter(comp, role_title, vacancy_text, "en")
    files = {}
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        generate_cv.build_pdf(tdp / "CV.pdf", role_title=role_title, keywords=kwline)
        generate_cv.build_docx(tdp / "CV.docx", role_title=role_title, keywords=kwline)
        generate_letter.build_pdf(tdp / "Motivatiebrief_NL.pdf", company=comp, role=role_title,
                                  contact=cont, highlights=matched, lang="nl", body=body_nl)
        generate_letter.build_docx(tdp / "Motivatiebrief_NL.docx", company=comp, role=role_title,
                                   contact=cont, highlights=matched, lang="nl", body=body_nl)
        generate_letter.build_pdf(tdp / "Motivation_EN.pdf", company=comp, role=role_title,
                                  contact=cont, highlights=matched, lang="en", body=body_en)
        generate_letter.build_docx(tdp / "Motivation_EN.docx", company=comp, role=role_title,
                                   contact=cont, highlights=matched, lang="en", body=body_en)
        for name in DOCS:
            files[name] = (tdp / name).read_bytes()
    return files, matched


def _dl_buttons(files: dict, prefix: str, slug: str) -> None:
    """Render each generated document as its own download button (no zip), 3 per row."""
    items = list(files.items())
    for start in range(0, len(items), 3):
        chunk = items[start:start + 3]
        cols = st.columns(len(chunk))
        for j, (fn, fb) in enumerate(chunk):
            ext = fn.rsplit(".", 1)[-1]
            cols[j].download_button(f"⬇️ {fn}", fb, file_name=f"{slug}_{fn}",
                                    mime=_MIME.get(ext, "application/octet-stream"),
                                    key=f"{prefix}_{start + j}")


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


def _ai_letter(company, role, vacancy_text, lang="nl"):
    """A vacancy-aligned motivation-letter body via the Anthropic API.

    Reads what the vacancy asks and matches it to what Gerrit provides. Returns a list
    of paragraph strings (no greeting/signature), or None if there's no API key, no
    vacancy text, or the call fails — in which case the clean template is used instead.
    """
    key = setting("ANTHROPIC_API_KEY")
    vacancy_text = str(vacancy_text or "").strip()
    if not key or not vacancy_text:
        return None
    import requests
    profile = generate_cv.PROFILE + " Competencies: " + generate_cv.SKILLS
    lang_name = "Dutch" if lang == "nl" else "English"
    prompt = (
        f"You write the BODY of a job motivation letter for {generate_letter.SENDER}, a cost engineer.\n"
        f"Company: {company or '[the company]'}\nRole: {role or 'Cost Engineer'}\n\n"
        f"WHAT THE COMPANY ASKS (vacancy text):\n{vacancy_text}\n\n"
        f"WHAT THE CANDIDATE OFFERS (profile):\n{profile}\n\n"
        f"Write 2-3 short paragraphs in {lang_name} that (1) show you understood what THIS "
        f"vacancy asks for, (2) match it concretely to what the candidate provides — cost "
        f"estimating, should-cost, post-calculation, margin and quote control, cross-functional "
        f"work, and data tooling where relevant, and (3) are specific and confident but not "
        f"boastful, in a Dutch business tone. Rules: NO buzzword lists (never dump 'Kaizen, "
        f"DMAIC, 5S, FMEA'), no clichés, no date, no greeting, no sign-off or signature. "
        f"Return ONLY the paragraphs, separated by a blank line."
    )
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 700,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=45)
        r.raise_for_status()
        text = r.json()["content"][0]["text"].strip()
        paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        return paras or None
    except Exception:  # noqa: BLE001 — any failure falls back to the template
        return None



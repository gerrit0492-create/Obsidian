"""Obsidian Notes — a Streamlit app to add notes straight to a GitHub repo.

Notes are committed to GITHUB_REPO under NOTES_DIR, where Claude Code can read
them. Deploy it (e.g. on Render) to add notes from any browser, including a phone.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import os

import streamlit as st

from github_notes import Config, create_note, list_notes, read_note

st.set_page_config(page_title="Obsidian Notes", page_icon="📝", layout="centered")


def _setting(name: str, default: str = "") -> str:
    """Read a setting from Streamlit secrets, falling back to env vars."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


def _require_password() -> None:
    """Gate the app behind APP_PASSWORD, if one is configured."""
    expected = _setting("APP_PASSWORD")
    if not expected or st.session_state.get("authed"):
        return
    pw = st.text_input("Password", type="password")
    if pw and pw == expected:
        st.session_state["authed"] = True
        return
    if pw:
        st.error("Wrong password.")
    st.stop()


def _config() -> Config | None:
    token = _setting("GITHUB_TOKEN")
    if not token:
        return None
    return Config(
        token=token,
        repo=_setting("GITHUB_REPO", "gerrit0492-create/Obsidian"),
        branch=_setting("GITHUB_BRANCH", "main"),
        notes_dir=_setting("NOTES_DIR", "notes"),
    )


st.title("📝 Obsidian Notes")
_require_password()

cfg = _config()
if cfg is None:
    st.warning(
        "No **GITHUB_TOKEN** configured. Set it (and optionally GITHUB_REPO) as a "
        "secret or environment variable so notes can be saved to GitHub. See the README."
    )
    st.stop()

st.caption(f"Saving to `{cfg.repo}` → `{cfg.notes_dir}/` on branch `{cfg.branch}`")

new_tab, recent_tab = st.tabs(["✍️ New note", "🗂 Recent notes"])

with new_tab:
    with st.form("new_note", clear_on_submit=True):
        title = st.text_input("Title")
        tags = st.text_input("Tags (comma-separated)", help="Optional")
        body = st.text_area("Note", height=240)
        submitted = st.form_submit_button("Save to GitHub")
    if submitted:
        if not (title.strip() or body.strip()):
            st.error("Add a title or some text first.")
        else:
            try:
                tag_list = tags.split(",") if tags else []
                result = create_note(cfg, title, body, tag_list)
                content = result.get("content", {})
                st.success(f"Saved **{content.get('path', '')}**")
                if content.get("html_url"):
                    st.markdown(f"[View on GitHub]({content['html_url']})")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not save: {exc}")

with recent_tab:
    if st.button("Refresh"):
        st.rerun()
    try:
        notes = list_notes(cfg)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not list notes: {exc}")
        notes = []
    if not notes:
        st.info("No notes yet — add one in the first tab.")
    else:
        names = sorted((n["name"] for n in notes), reverse=True)
        chosen = st.selectbox(f"{len(names)} notes", names)
        selected = next((n for n in notes if n["name"] == chosen), None)
        if selected:
            try:
                st.markdown(read_note(cfg, selected["path"]))
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not read note: {exc}")

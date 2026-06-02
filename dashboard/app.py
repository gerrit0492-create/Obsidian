"""Obsidian Vault Dashboard — a Streamlit front-end over a folder of notes.

Run with:  streamlit run app.py
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from note_analysis import analyze_vault

# Default to the repo's starter vault (../vault relative to this file).
DEFAULT_VAULT = Path(__file__).resolve().parent.parent / "vault"

st.set_page_config(page_title="Obsidian Vault Dashboard", page_icon="📓", layout="wide")
st.title("📓 Obsidian Vault Dashboard")

vault_input = st.sidebar.text_input(
    "Vault folder",
    value=str(DEFAULT_VAULT),
    help="Path to a folder of Obsidian markdown notes.",
)

vault_path = Path(vault_input).expanduser()
if not vault_path.is_dir():
    st.error(f"Not a directory: `{vault_path}`")
    st.stop()

report = analyze_vault(vault_path)

# --- Summary metrics -------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Notes", report.total_notes)
c2.metric("Words", f"{report.total_words:,}")
c3.metric("Broken links", len(report.broken_links))
c4.metric("Orphans", len(report.orphans))
c5.metric("No frontmatter", len(report.missing_frontmatter))

st.divider()

left, right = st.columns([2, 3])

with left:
    st.subheader("Notes")
    if report.notes:
        st.dataframe(
            {
                "Note": [n.path for n in report.notes],
                "Words": [n.words for n in report.notes],
                "Links": [len(n.links) for n in report.notes],
                "Broken": [len(n.broken_links) for n in report.notes],
                "Frontmatter": ["✓" if n.has_frontmatter else "—" for n in report.notes],
            },
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No markdown notes found in this folder.")

    if report.broken_links:
        st.subheader("⚠️ Broken links")
        for note, link in report.broken_links:
            st.markdown(f"- `{note}` → `[[{link}]]`")

    if report.orphans:
        st.subheader("🔌 Orphan notes")
        for path in report.orphans:
            st.markdown(f"- `{path}`")

    if report.missing_frontmatter:
        st.subheader("📄 Missing frontmatter")
        for path in report.missing_frontmatter:
            st.markdown(f"- `{path}`")

with right:
    st.subheader("Preview")
    note_paths = [n.path for n in report.notes]
    if note_paths:
        selected = st.selectbox("Open a note", note_paths)
        content = (vault_path / selected).read_text(encoding="utf-8", errors="replace")
        st.markdown(content)
    else:
        st.info("Nothing to preview.")

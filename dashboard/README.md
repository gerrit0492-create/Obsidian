# Vault Dashboard (Streamlit)

A small [Streamlit](https://streamlit.io) app that gives an Obsidian vault a visual
front-end: summary stats, a broken-link / orphan / missing-frontmatter report, and a note
browser with rendered markdown preview. The analysis layer
([`note_analysis.py`](./note_analysis.py)) mirrors the repo's
[`tools/note-lint`](../tools) so the numbers match.

## Run
```bash
cd dashboard
pip install -r requirements.txt
streamlit run app.py
```
Streamlit prints a local URL (default <http://localhost:8501>). The app defaults to the
repo's `../vault`; change the **Vault folder** field in the sidebar to point at any vault.

## Test
The analysis layer is dependency-free and has a standalone test:
```bash
python test_note_analysis.py     # or: pytest
```

## Files
| File | Purpose |
| ---- | ------- |
| `app.py` | The Streamlit UI (metrics, issue lists, note preview). |
| `note_analysis.py` | Dependency-free vault analysis (stdlib only). |
| `test_note_analysis.py` | Tests for the analysis layer. |
| `requirements.txt` | Just `streamlit`. |

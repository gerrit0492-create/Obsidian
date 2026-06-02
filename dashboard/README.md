# Obsidian Notes (Streamlit)

A small [Streamlit](https://streamlit.io) app to **add notes straight into your GitHub repo**,
where Claude Code can read them. **Deploy it** (e.g. on Render) and you can jot notes from any
browser — including your phone — with no Obsidian or git client.

Notes are committed to `GITHUB_REPO` under `NOTES_DIR/` (default `notes/`) via the GitHub
Contents API.

## Configuration
Set these as environment variables, or as Streamlit secrets:

| Name | Required | Default | Purpose |
| ---- | -------- | ------- | ------- |
| `GITHUB_TOKEN` | ✅ | — | Token with **Contents: Read & write** on the repo |
| `GITHUB_REPO` | | `gerrit0492-create/Obsidian` | `owner/repo` to write to |
| `GITHUB_BRANCH` | | `main` | Branch to commit to |
| `NOTES_DIR` | | `notes` | Folder for notes within the repo |
| `APP_PASSWORD` | recommended | — | If set, the app asks for this before letting anyone write |

### Create the token
GitHub → **Settings → Developer settings → Fine-grained tokens → Generate new token**.
Scope it to **only the `Obsidian` repo**, with **Repository permissions → Contents: Read and
write**. Paste the value into `GITHUB_TOKEN`.

## Run locally
```bash
cd dashboard
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then fill in your token
streamlit run app.py
```
`.streamlit/secrets.toml` is git-ignored — your token never gets committed.

## Deploy on Render (use it from your phone)
A `render.yaml` blueprint is included at the repo root.
1. Render → **New → Blueprint** → point it at this repo.
2. Set **`GITHUB_TOKEN`** and **`APP_PASSWORD`** in the service's Environment (they're marked
   `sync: false`, so Render prompts you and never stores them in git).
3. Deploy, open the URL on your phone, enter the password, and start adding notes.

> ⚠️ **Security:** this app can write to your repo. **Always set `APP_PASSWORD`** before
> deploying publicly, or anyone with the URL could add notes (or spam commits) to your repo.
> Keep the token **fine-grained** (single repo, Contents-only) so a leak is contained.

## Files
| File | Purpose |
| ---- | ------- |
| `app.py` | Streamlit UI: new-note form + recent-notes view. |
| `github_notes.py` | GitHub Contents API helpers (create / list / read). |
| `note_analysis.py` | Dependency-free vault analysis, mirrors `tools/note-lint`. |
| `test_github_notes.py`, `test_note_analysis.py` | Standalone tests (`python test_*.py`). |

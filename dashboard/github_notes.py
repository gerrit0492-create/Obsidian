"""Write and read notes in a GitHub repo via the Contents API.

Used by the Streamlit note-entry app so notes persist to GitHub (where Claude
can read them) even when the app runs on an ephemeral host like Render.

Configuration (env vars or Streamlit secrets):
  GITHUB_TOKEN   - token with Contents read/write on the repo (required to write)
  GITHUB_REPO    - "owner/repo", e.g. "gerrit0492-create/Obsidian"
  GITHUB_BRANCH  - branch to commit to (default: "main")
  NOTES_DIR      - folder for notes within the repo (default: "notes")

``slugify`` and ``build_note`` are pure functions (no network, no third-party
imports) so they can be unit-tested without installing ``requests``.
"""

from __future__ import annotations

import base64
import datetime as dt
import re
from dataclasses import dataclass

API_ROOT = "https://api.github.com"
TIMEOUT = 20


@dataclass
class Config:
    token: str
    repo: str
    branch: str = "main"
    notes_dir: str = "notes"

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }


def slugify(title: str) -> str:
    """Turn a title into a safe filename stem."""
    slug = title.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug or "note"


def build_note(
    title: str,
    body: str,
    tags: list[str] | None = None,
    now: dt.datetime | None = None,
) -> tuple[str, str]:
    """Return ``(filename, markdown)`` for a new note. Pure / testable."""
    now = now or dt.datetime.now()
    date = now.strftime("%Y-%m-%d")
    stamp = now.strftime("%Y-%m-%d-%H%M%S")
    tag_list = [t.strip() for t in (tags or []) if t.strip()]

    front = ["---", f"created: {date}"]
    if tag_list:
        front.append("tags: [" + ", ".join(tag_list) + "]")
    front.append("---")

    heading = title.strip() or "Untitled note"
    content = "\n".join(front) + f"\n\n# {heading}\n\n{body.strip()}\n"
    filename = f"{stamp}-{slugify(title)}.md"
    return filename, content


def create_note(
    cfg: Config, title: str, body: str, tags: list[str] | None = None
) -> dict:
    """Create a note file in the repo. Returns the GitHub API response JSON."""
    import requests

    filename, content = build_note(title, body, tags)
    path = f"{cfg.notes_dir}/{filename}"
    url = f"{API_ROOT}/repos/{cfg.repo}/contents/{path}"
    payload = {
        "message": f"Add note: {title.strip() or filename}",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": cfg.branch,
    }
    resp = requests.put(url, headers=cfg.headers, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def list_notes(cfg: Config) -> list[dict]:
    """List markdown notes in the notes dir. Returns GitHub file objects."""
    import requests

    url = f"{API_ROOT}/repos/{cfg.repo}/contents/{cfg.notes_dir}"
    resp = requests.get(
        url, headers=cfg.headers, params={"ref": cfg.branch}, timeout=TIMEOUT
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    items = resp.json()
    return [
        i
        for i in items
        if i.get("type") == "file" and i.get("name", "").endswith(".md")
    ]


def read_note(cfg: Config, path: str) -> str:
    """Return the decoded text of a note at ``path``."""
    import requests

    url = f"{API_ROOT}/repos/{cfg.repo}/contents/{path}"
    resp = requests.get(
        url, headers=cfg.headers, params={"ref": cfg.branch}, timeout=TIMEOUT
    )
    resp.raise_for_status()
    data = resp.json()
    return base64.b64decode(data["content"]).decode("utf-8", errors="replace")

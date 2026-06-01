"""Analyze a folder of Obsidian markdown notes.

A small, dependency-free port of ``tools/note-lint.mjs`` so the Streamlit app and
its tests can share the same logic. Uses only the Python standard library.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

WIKILINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")
# Leading YAML frontmatter block: --- ... --- at the very start of the file.
FRONTMATTER_RE = re.compile(r"^---\r?\n.*?\r?\n---\r?\n", re.DOTALL)


@dataclass
class Note:
    """A single markdown note and the facts we derive from it."""

    path: str  # vault-relative path, e.g. "Notes/Welcome.md"
    name: str  # basename without the .md extension
    words: int
    has_frontmatter: bool
    links: list[str]
    broken_links: list[str] = field(default_factory=list)
    incoming: int = 0

    @property
    def is_orphan(self) -> bool:
        return not self.links and self.incoming == 0


@dataclass
class VaultReport:
    directory: str
    notes: list[Note]

    @property
    def total_notes(self) -> int:
        return len(self.notes)

    @property
    def total_words(self) -> int:
        return sum(n.words for n in self.notes)

    @property
    def broken_links(self) -> list[tuple[str, str]]:
        return [(n.path, link) for n in self.notes for link in n.broken_links]

    @property
    def missing_frontmatter(self) -> list[str]:
        return [n.path for n in self.notes if not n.has_frontmatter]

    @property
    def orphans(self) -> list[str]:
        return [n.path for n in self.notes if n.is_orphan]


def _link_target_name(raw: str) -> str:
    """Normalize a wikilink target to a bare note name for matching."""
    # Drop alias ([[Note|Alias]]), heading ([[Note#H]]) and block ref ([[Note^id]]).
    target = raw.split("|")[0].split("#")[0].split("^")[0].strip()
    # Links may include a folder path: [[folder/Note]] -> "Note".
    return target.split("/")[-1].strip()


def _count_words(text: str) -> int:
    stripped = text.strip()
    return len(stripped.split()) if stripped else 0


def find_markdown_files(directory: Path) -> list[Path]:
    """Recursively collect .md files, skipping hidden folders (e.g. .obsidian)."""
    files: list[Path] = []
    for path in sorted(directory.rglob("*.md")):
        rel_parts = path.relative_to(directory).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        if path.is_file():
            files.append(path)
    return files


def analyze_vault(directory: str | Path) -> VaultReport:
    """Scan ``directory`` for markdown notes and return a :class:`VaultReport`."""
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f'not a directory: "{directory}"')

    files = find_markdown_files(directory)
    known = {f.stem for f in files}

    notes: list[Note] = []
    for file in files:
        text = file.read_text(encoding="utf-8", errors="replace")
        rel = str(file.relative_to(directory))

        has_frontmatter = FRONTMATTER_RE.match(text) is not None
        body = FRONTMATTER_RE.sub("", text, count=1) if has_frontmatter else text

        links = [
            name
            for match in WIKILINK_RE.finditer(text)
            if (name := _link_target_name(match.group(1)))
        ]
        broken = [link for link in links if link not in known]

        notes.append(
            Note(
                path=rel,
                name=file.stem,
                words=_count_words(body),
                has_frontmatter=has_frontmatter,
                links=links,
                broken_links=broken,
            )
        )

    # Tally incoming links so we can flag orphans (no links in or out).
    incoming: dict[str, int] = {}
    for note in notes:
        for link in note.links:
            incoming[link] = incoming.get(link, 0) + 1
    for note in notes:
        note.incoming = incoming.get(note.name, 0)

    return VaultReport(directory=str(directory), notes=notes)

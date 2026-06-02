"""Standalone tests for note_analysis.

Run with:  python test_note_analysis.py   (no third-party deps required)
Also discoverable by pytest.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from note_analysis import analyze_vault


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_analyze_vault() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, "A.md", "---\ntitle: A\n---\n\nLinks to [[B]] and [[Missing]].\n")
        _write(root, "B.md", "# B\n\nJust some words here.\n")
        _write(root, "sub/C.md", "# C\n")  # orphan, no frontmatter
        _write(root, ".obsidian/skip.md", "hidden, should be ignored")

        report = analyze_vault(root)

        assert report.total_notes == 3, report.total_notes
        assert report.broken_links == [("A.md", "Missing")], report.broken_links
        assert sorted(report.missing_frontmatter) == [
            "B.md",
            str(Path("sub/C.md")),
        ], report.missing_frontmatter
        assert report.orphans == [str(Path("sub/C.md"))], report.orphans


if __name__ == "__main__":
    test_analyze_vault()
    print("All tests passed.")

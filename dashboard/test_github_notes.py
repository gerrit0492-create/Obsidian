"""Standalone tests for github_notes pure functions.

Run with:  python test_github_notes.py   (no third-party deps required)
"""

from __future__ import annotations

import datetime as dt

from github_notes import build_note, slugify


def test_slugify() -> None:
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("  Multiple   spaces ") == "multiple-spaces"
    assert slugify("***") == "note"


def test_build_note() -> None:
    now = dt.datetime(2026, 6, 2, 7, 30, 0)
    filename, content = build_note("My Idea", "Body text", ["a", "b"], now=now)
    assert filename == "2026-06-02-073000-my-idea.md", filename
    assert content.startswith("---\ncreated: 2026-06-02\ntags: [a, b]\n---"), content
    assert "# My Idea" in content
    assert content.rstrip().endswith("Body text")


def test_build_note_no_tags() -> None:
    filename, content = build_note("Untitled", "", now=dt.datetime(2026, 1, 1, 0, 0, 0))
    assert "tags:" not in content
    assert "# Untitled" in content


if __name__ == "__main__":
    test_slugify()
    test_build_note()
    test_build_note_no_tags()
    print("All tests passed.")

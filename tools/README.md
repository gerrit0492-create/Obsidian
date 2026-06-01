# note-lint

A zero-dependency Node.js CLI (Node 16+) that scans a folder of Obsidian markdown notes and
reports common issues. No `npm install` needed — it only uses Node built-ins.

## Usage
```bash
node note-lint.mjs [dir] [--json] [--strict]
```

| Argument / flag | Meaning |
| --------------- | ------- |
| `dir` | Folder to scan (default: current directory). Hidden folders like `.obsidian` are skipped. |
| `--json` | Emit a machine-readable JSON report instead of the text summary. |
| `--strict` | Exit with code `1` if any broken links are found — handy in CI. |
| `-h`, `--help` | Show help. |

## What it checks
- **Broken `[[wikilinks]]`** — links whose target note doesn't exist. Aliases
  (`[[Note|Alias]]`), headings (`[[Note#Section]]`), block refs (`[[Note^id]]`) and folder
  paths (`[[folder/Note]]`) are all resolved to the bare note name.
- **Missing frontmatter** — notes without a leading `--- … ---` YAML block.
- **Orphan notes** — notes with no links in *or* out.
- **Stats** — total notes and total word count (frontmatter excluded from the count).

## Examples
```bash
# Lint the starter vault in this repo
node note-lint.mjs ../vault

# JSON output (pipe into jq, etc.)
node note-lint.mjs ../vault --json | jq '.brokenLinks'

# Fail a CI job when links are broken
node note-lint.mjs ../vault --strict
```

## Install globally (optional)
```bash
npm link          # exposes a `note-lint` command on your PATH
note-lint ~/vault
```

## License
MIT

# Obsidian

A small monorepo for working with [Obsidian](https://obsidian.md), containing three independent parts:

| Folder | What it is |
| ------ | ---------- |
| [`plugin/`](./plugin) | **Obsidian Companion** — a TypeScript plugin built against the official Obsidian plugin API. Adds a live word-count + reading-time readout to the status bar and quick daily-heading insertion. |
| [`vault/`](./vault) | A starter **vault structure** with reusable note **templates** (daily note, meeting, project). |
| [`tools/`](./tools) | **note-lint** — a zero-dependency Node.js CLI that scans a vault of markdown notes and reports broken `[[wikilinks]]`, missing frontmatter, orphan notes, and word-count stats. |

## Quick start

### Plugin
```bash
cd plugin
npm install
npm run dev      # watch + rebuild into main.js
```
Then copy/symlink the `plugin/` folder into `<your-vault>/.obsidian/plugins/obsidian-companion/`
and enable it in Obsidian's community-plugins settings. See [`plugin/README.md`](./plugin/README.md).

### Vault
Open the [`vault/`](./vault) folder directly as a vault in Obsidian, or copy its `Templates/`
into your own vault and point the core **Templates** plugin at it.

### Tools
```bash
cd tools
node note-lint.mjs ../vault          # lint the starter vault
node note-lint.mjs ../vault --json   # machine-readable output
node note-lint.mjs ../vault --strict # non-zero exit if broken links exist (CI)
```

## Layout
```
.
├── plugin/   # TypeScript Obsidian plugin
├── vault/    # starter vault + templates
└── tools/    # markdown-processing CLI
```

## License
MIT

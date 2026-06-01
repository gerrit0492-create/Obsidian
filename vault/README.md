# Starter Vault

A minimal Obsidian vault layout. Open it directly (**File → Open folder as vault**) or copy
pieces of it into your own vault.

## Layout
```
vault/
├── Daily Notes/   # one note per day
├── Notes/         # general notes (start with Welcome.md)
├── Projects/      # longer-running efforts
└── Templates/     # reusable note skeletons
```

## Templates
The files in `Templates/` use the **core Templates plugin** syntax
(`{{title}}`, `{{date}}`, `{{date:YYYY-MM-DD}}`, `{{time}}`):

| Template | Purpose |
| -------- | ------- |
| `Daily Note.md` | A dated daily log with focus / tasks / notes sections. |
| `Meeting Note.md` | Agenda, discussion, decisions and action items (with frontmatter). |
| `Project.md` | Goal, milestones and related links (with frontmatter). |

To wire them up: **Settings → Templates → Template folder location → `Templates`**, then use
the **Insert template** command (assign it a hotkey for quick access).

## Linting
Check this vault for broken links and stats with the repo's tool:
```bash
node ../tools/note-lint.mjs .
```

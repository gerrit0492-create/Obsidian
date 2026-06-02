---
created: 2026-06-02
tags: [workflow, claude]
---

# How I use Claude with my notes

My setup, decided 2026-06-02.

- **Where notes live:** markdown files in the GitHub repo `gerrit0492-create/Obsidian`, under `notes/`.
- **How I edit them:** the GitHub mobile app on my iPhone (open repo → `notes/` → edit → commit). No Obsidian or sync app required.
- **How Claude uses them:** in a Claude Code session on this repo, I ask Claude to read, summarize, expand, or add notes. It runs in the cloud off GitHub, so it works straight from my phone.

## Why not Obsidian on iPhone?
Syncing an Obsidian vault to GitHub on iOS needs Working Copy (a paid git app) plus fiddly
folder-linking. Since the goal is "Claude uses my notes," the repo itself is the source of
truth and Obsidian is optional.

## If I get a computer later
On a Mac or PC I can use the **Claude Desktop app** with an **Obsidian MCP** connector to read
my local vault directly — no GitHub needed. Worth revisiting then.

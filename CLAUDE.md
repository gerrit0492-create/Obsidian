# Project notes

A small monorepo for working with Obsidian. See `README.md` for the layout:
`plugin/` (TypeScript Obsidian plugin), `vault/` (starter vault + templates),
`tools/` (note-lint CLI).

## Conventions
- Communicate with the user in English
- For changes spanning several files, make all edits in one commit
- Match the style of the surrounding code — don't introduce new patterns
- Don't refactor or rename things that weren't part of the requested change
- The plugin build artifact `plugin/main.js` and `node_modules/` are git-ignored — never commit them
- When a feature adds or changes a data view, keep its export (e.g. the Excel/CSV download) in sync in the same commit so the download always matches the UI

## Building & checking
- Plugin: `cd plugin && npm install && npm run build` (runs the `tsc` typecheck + esbuild bundle)
- Notes: `node tools/note-lint.mjs vault` to report broken links / orphans / stats

## Before pushing to git
1. **Back up**: create a git tag from current HEAD (`git tag backup/pre-<description> HEAD`)
2. **Verify MCP**: confirm the GitHub MCP tools are available
3. Once the backup is done and MCP is verified, push

## Git constraints
- Develop on a feature branch; open a PR to merge into `main`
- Only push to `gerrit0492-create/obsidian`
- **Never push to the `claude/funny-goldberg-*` branch** — the user did not choose
  it. Push to the branch the user is actually working on, and always back up
  (tag) and verify MCP first.
- Never force-push or `reset --hard` without explicit user instruction

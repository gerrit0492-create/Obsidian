# Project notes

A small monorepo for working with Obsidian. See `README.md` for the layout:
`plugin/` (TypeScript Obsidian plugin), `vault/` (starter vault + templates),
`tools/` (note-lint CLI).

## Conventions
- **Work carefully and precisely.** Don't guess. Verify numbers/counts against the
  actual data, check that UI elements truly render (not just that the code compiles),
  re-read the relevant code before changing it, and double-check the result matches
  what the user will actually see. Accuracy over speed.
- Communicate with the user in English
- For changes spanning several files, make all edits in one commit
- Match the style of the surrounding code — don't introduce new patterns
- Don't refactor or rename things that weren't part of the requested change
- The plugin build artifact `plugin/main.js` and `node_modules/` are git-ignored — never commit them
- When a feature adds or changes a data view, keep its export (e.g. the Excel/CSV download) in sync in the same commit so the download always matches the UI
- **Generalise, don't hardcode one case.** If the user asks for something once and
  it works for one instance, apply the same rule to all comparable instances —
  drive it from the data, not from a single hardcoded name. (E.g. the "Westermeer
  rule": every offerte, not just Westermeer, gets a full breakdown and a
  retrievable original PDF.)
- **Keep source documents available and findable.** Uploaded source files (e.g.
  offerte PDF's) are saved to `vault/attachments/` so they stay downloadable/
  viewable in the app and survive in the repo — never only parse-and-discard.
- **Always compare apples-to-apples.** When comparing quotes/offers, first
  normalise them to the same scope: add each quote's missing scope at the firm
  price the others charge for it (stelposten excluded), then compare incl. btw and
  net of subsidy (e.g. ISDE). Never rank quotes on headline price alone when their
  scope differs.

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

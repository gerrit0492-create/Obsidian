# Obsidian Companion

A small TypeScript plugin built against the official [Obsidian plugin API](https://docs.obsidian.md/Plugins).

## Features
- **Live status-bar readout** — shows the word count and an estimated reading time for the
  active note, updating as you type or switch notes.
- **Insert daily heading** — a command (and ribbon icon) that inserts a formatted date
  heading at the cursor, e.g. `# 2026-06-01 Monday`.
- **Show word count** — a command that pops a notice with the current note's word count.
- **Settings** — toggle the status bar, customize the heading date format
  ([Moment.js tokens](https://momentjs.com/docs/#/displaying/format/)), and set your reading speed.

## Develop
```bash
npm install
npm run dev     # esbuild watch → main.js (rebuilds on save)
npm run build   # type-check (tsc --noEmit) + minified production bundle
```

The entry point is [`src/main.ts`](./src/main.ts); esbuild bundles it to `main.js`
(git-ignored — it's a build artifact).

## Install into a vault
1. Build the plugin (`npm run build`).
2. Copy `manifest.json`, `main.js`, and `styles.css` into
   `<your-vault>/.obsidian/plugins/obsidian-companion/` (or symlink this whole folder there
   while developing).
3. In Obsidian: **Settings → Community plugins**, reload, and enable **Obsidian Companion**.

> Requires Obsidian `1.4.0` or newer. Works on desktop and mobile.

## License
MIT

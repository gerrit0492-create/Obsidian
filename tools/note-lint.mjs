#!/usr/bin/env node
// note-lint — scan a folder of Obsidian markdown notes and report broken
// [[wikilinks]], notes missing frontmatter, orphan notes, and word stats.
// Zero dependencies; requires Node 16+.

import { readdir, readFile } from "node:fs/promises";
import { join, relative, extname, basename } from "node:path";
import process from "node:process";

const WIKILINK_RE = /\[\[([^\]]+?)\]\]/g;
// Leading YAML frontmatter block: --- ... --- at the very start of the file.
const FRONTMATTER_RE = /^---\r?\n.*?\r?\n---\r?\n/s;

function parseArgs(argv) {
	const args = { dir: ".", json: false, strict: false, help: false };
	for (const a of argv) {
		if (a === "--json") args.json = true;
		else if (a === "--strict") args.strict = true;
		else if (a === "-h" || a === "--help") args.help = true;
		else if (!a.startsWith("-")) args.dir = a;
	}
	return args;
}

/** Recursively collect .md files, skipping hidden/dot folders (e.g. .obsidian). */
async function walk(dir) {
	const out = [];
	let entries;
	try {
		entries = await readdir(dir, { withFileTypes: true });
	} catch (err) {
		throw new Error(`cannot read directory "${dir}": ${err.message}`);
	}
	for (const entry of entries) {
		if (entry.name.startsWith(".")) continue;
		const full = join(dir, entry.name);
		if (entry.isDirectory()) {
			out.push(...(await walk(full)));
		} else if (entry.isFile() && extname(entry.name).toLowerCase() === ".md") {
			out.push(full);
		}
	}
	return out;
}

/** Normalize a wikilink target to a bare note name for matching. */
function linkTargetName(raw) {
	// Drop alias ([[Note|Alias]]), heading ([[Note#H]]) and block ref ([[Note^id]]).
	let target = raw.split("|")[0].split("#")[0].split("^")[0].trim();
	// Links may include a folder path: [[folder/Note]] → "Note".
	const segments = target.split("/");
	return segments[segments.length - 1].trim();
}

function countWords(text) {
	const trimmed = text.trim();
	return trimmed ? trimmed.split(/\s+/).length : 0;
}

async function analyze(dir) {
	const files = await walk(dir);

	// Index every note by its basename so we can resolve links.
	const known = new Set(files.map((f) => basename(f, ".md")));

	const notes = [];
	let totalWords = 0;
	const brokenLinks = [];
	const missingFrontmatter = [];

	for (const file of files) {
		const text = await readFile(file, "utf8");
		const rel = relative(dir, file) || basename(file);

		const hasFrontmatter = FRONTMATTER_RE.test(text);
		const body = hasFrontmatter ? text.replace(FRONTMATTER_RE, "") : text;
		totalWords += countWords(body);

		const links = [];
		for (const match of text.matchAll(WIKILINK_RE)) {
			const name = linkTargetName(match[1]);
			if (name) links.push(name);
		}

		if (!hasFrontmatter) missingFrontmatter.push(rel);
		for (const link of links) {
			if (!known.has(link)) brokenLinks.push({ note: rel, link });
		}

		notes.push({ path: rel, links });
	}

	// Count incoming links so we can detect orphans (no links in or out).
	const incoming = new Map();
	for (const note of notes) {
		for (const link of note.links) {
			incoming.set(link, (incoming.get(link) ?? 0) + 1);
		}
	}
	const orphans = notes
		.filter(
			(n) =>
				n.links.length === 0 &&
				(incoming.get(basename(n.path, ".md")) ?? 0) === 0,
		)
		.map((n) => n.path);

	return {
		directory: dir,
		totalNotes: notes.length,
		totalWords,
		brokenLinks,
		missingFrontmatter,
		orphans,
	};
}

function printHuman(r) {
	const rule = "─".repeat(42);
	console.log(`\nnote-lint · ${r.directory}`);
	console.log(rule);
	console.log(`Notes:               ${r.totalNotes}`);
	console.log(`Total words:         ${r.totalWords}`);
	console.log(`Broken links:        ${r.brokenLinks.length}`);
	console.log(`Missing frontmatter: ${r.missingFrontmatter.length}`);
	console.log(`Orphan notes:        ${r.orphans.length}`);

	if (r.brokenLinks.length) {
		console.log(`\n⚠ Broken links`);
		for (const b of r.brokenLinks) console.log(`  ${b.note} → [[${b.link}]]`);
	}
	if (r.missingFrontmatter.length) {
		console.log(`\nℹ Notes without frontmatter`);
		for (const n of r.missingFrontmatter) console.log(`  ${n}`);
	}
	if (r.orphans.length) {
		console.log(`\nℹ Orphan notes (no links in or out)`);
		for (const n of r.orphans) console.log(`  ${n}`);
	}
	console.log("");
}

function printHelp() {
	console.log(`note-lint — scan Obsidian markdown notes

Usage:
  node note-lint.mjs [dir] [--json] [--strict]

Arguments:
  dir          Folder to scan (default: current directory)

Options:
  --json       Output a machine-readable JSON report
  --strict     Exit with code 1 if any broken links are found (useful in CI)
  -h, --help   Show this help
`);
}

async function main() {
	const args = parseArgs(process.argv.slice(2));
	if (args.help) {
		printHelp();
		return 0;
	}
	const report = await analyze(args.dir);
	if (args.json) {
		console.log(JSON.stringify(report, null, 2));
	} else {
		printHuman(report);
	}
	return args.strict && report.brokenLinks.length > 0 ? 1 : 0;
}

main()
	.then((code) => process.exit(code))
	.catch((err) => {
		console.error(`note-lint: ${err.message}`);
		process.exit(2);
	});

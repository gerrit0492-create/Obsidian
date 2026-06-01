import {
	App,
	Editor,
	MarkdownView,
	Notice,
	Plugin,
	PluginSettingTab,
	Setting,
	moment,
} from "obsidian";

interface CompanionSettings {
	showWordCount: boolean;
	dailyHeadingFormat: string;
	wordsPerMinute: number;
}

const DEFAULT_SETTINGS: CompanionSettings = {
	showWordCount: true,
	dailyHeadingFormat: "YYYY-MM-DD dddd",
	wordsPerMinute: 200,
};

export default class CompanionPlugin extends Plugin {
	settings: CompanionSettings = DEFAULT_SETTINGS;
	private statusBarEl: HTMLElement | null = null;

	async onload(): Promise<void> {
		await this.loadSettings();

		// Status bar: live word count + reading time of the active note.
		this.statusBarEl = this.addStatusBarItem();
		this.statusBarEl.addClass("obsidian-companion-statusbar");
		this.refreshStatusBar();

		// Ribbon icon → insert a daily heading at the cursor.
		this.addRibbonIcon("calendar-plus", "Insert daily heading", () => {
			this.insertDailyHeading();
		});

		this.addCommand({
			id: "insert-daily-heading",
			name: "Insert daily heading",
			editorCallback: (editor: Editor) => this.insertDailyHeading(editor),
		});

		this.addCommand({
			id: "show-word-count",
			name: "Show word count of current note",
			callback: () => {
				const words = this.activeNoteWordCount();
				new Notice(`Word count: ${words} (${this.readingTime(words)})`);
			},
		});

		// Keep the status bar in sync as the user types / switches notes.
		this.registerEvent(
			this.app.workspace.on("active-leaf-change", () => this.refreshStatusBar()),
		);
		this.registerEvent(
			this.app.workspace.on("editor-change", () => this.refreshStatusBar()),
		);

		this.addSettingTab(new CompanionSettingTab(this.app, this));
	}

	onunload(): void {
		// The status bar item is removed automatically by Obsidian on unload.
	}

	/** Count whitespace-delimited words in a string. */
	private countWords(text: string): number {
		const trimmed = text.trim();
		if (trimmed.length === 0) return 0;
		return trimmed.split(/\s+/).length;
	}

	/** Word count of the currently active markdown note (0 if none). */
	private activeNoteWordCount(): number {
		const view = this.app.workspace.getActiveViewOfType(MarkdownView);
		if (!view) return 0;
		return this.countWords(view.editor.getValue());
	}

	/** Human-readable reading-time estimate for a word count. */
	private readingTime(words: number): string {
		const minutes = Math.max(1, Math.round(words / this.settings.wordsPerMinute));
		return `~${minutes} min read`;
	}

	private refreshStatusBar(): void {
		if (!this.statusBarEl) return;
		const view = this.app.workspace.getActiveViewOfType(MarkdownView);
		if (!this.settings.showWordCount || !view) {
			this.statusBarEl.setText("");
			return;
		}
		const words = this.countWords(view.editor.getValue());
		this.statusBarEl.setText(`${words} words · ${this.readingTime(words)}`);
	}

	/** Insert a date heading at the cursor of the given (or active) editor. */
	private insertDailyHeading(editor?: Editor): void {
		const target =
			editor ?? this.app.workspace.getActiveViewOfType(MarkdownView)?.editor;
		if (!target) {
			new Notice("Open a note to insert a daily heading.");
			return;
		}
		const heading = `# ${moment().format(this.settings.dailyHeadingFormat)}\n\n`;
		target.replaceSelection(heading);
	}

	async loadSettings(): Promise<void> {
		this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
	}

	async saveSettings(): Promise<void> {
		await this.saveData(this.settings);
		this.refreshStatusBar();
	}
}

class CompanionSettingTab extends PluginSettingTab {
	plugin: CompanionPlugin;

	constructor(app: App, plugin: CompanionPlugin) {
		super(app, plugin);
		this.plugin = plugin;
	}

	display(): void {
		const { containerEl } = this;
		containerEl.empty();

		new Setting(containerEl)
			.setName("Show word count in status bar")
			.setDesc("Display a live word count and reading-time estimate for the active note.")
			.addToggle((toggle) =>
				toggle
					.setValue(this.plugin.settings.showWordCount)
					.onChange(async (value) => {
						this.plugin.settings.showWordCount = value;
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName("Daily heading format")
			.setDesc('Moment.js date format used by the "Insert daily heading" command.')
			.addText((text) =>
				text
					.setPlaceholder(DEFAULT_SETTINGS.dailyHeadingFormat)
					.setValue(this.plugin.settings.dailyHeadingFormat)
					.onChange(async (value) => {
						this.plugin.settings.dailyHeadingFormat =
							value.trim() || DEFAULT_SETTINGS.dailyHeadingFormat;
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName("Reading speed (words per minute)")
			.setDesc("Used to estimate reading time in the status bar.")
			.addText((text) =>
				text
					.setPlaceholder(String(DEFAULT_SETTINGS.wordsPerMinute))
					.setValue(String(this.plugin.settings.wordsPerMinute))
					.onChange(async (value) => {
						const parsed = Number.parseInt(value, 10);
						this.plugin.settings.wordsPerMinute =
							Number.isFinite(parsed) && parsed > 0
								? parsed
								: DEFAULT_SETTINGS.wordsPerMinute;
						await this.plugin.saveSettings();
					}),
			);
	}
}

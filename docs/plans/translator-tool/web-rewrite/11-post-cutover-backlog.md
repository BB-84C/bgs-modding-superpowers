# Post-Cutover Backlog

Date: 2026-06-09

Scope: these are follow-up design and feature items raised during manual user testing after the browser GUI cut-over. They are intentionally not implemented in the current stabilization pass.

## Manual Testing Findings To Preserve

- Fresh GUI must mean a fresh browser process, not a clean project state. The UI must not report old sqlite `running` rows as actively billing unless the current GUI/CLI process has real activity evidence.
- Project selection must be URL/stateful. Clicking a project in the sidebar must change the active project for all tabs, API calls, and top status copy.
- `打开导出目录` must not imply an SST exists. If no `.sst` files exist, the UI must tell the user to run `导出 xTranslator 文件` first.
- Desktop panes must be tested at browser zoom levels like 150%, not only by `documentElement.scrollWidth`. Validation must include actual scrollability and visual reachability of controls.
- Theme variants must recolor the entire terminal surface, not only foreground text. Green is intended as a Fallout NV-style green terminal theme; amber remains the existing Fallout/TK inheritance; mono is black/white.
- Historical prompt previews can show different glossary/DNT hits because the current mechanism matches vanilla/mod terms against each batch's source text, while player/DNT override entries are merged more broadly. This is confusing and needs explicit design.

## New Feature Backlog

### 1. Import Translation Project From Plugin File

Add a GUI flow to import a new translation project from `.esp`, `.esl`, or `.esm`.

Expected behavior:

- User picks a plugin file from disk.
- Tool detects the Bethesda game automatically from plugin/header/context where possible.
- Tool creates a translator project and extracts translatable records.
- UI explains that the original plugin file is not modified.

Open design questions:

- Which game-detection signal is canonical when plugin headers are ambiguous?
- Whether imports should copy the plugin into the project or reference the original path.
- How to handle MO2/VFS paths versus ordinary filesystem paths.

### 2. Glossary And Do-Not-Translate Hit Mechanism

The current hit behavior is not transparent enough for ordinary players.

Current rough behavior:

- Vanilla/mod knowledge terms are selected by matching source text or aliases in the current batch.
- Player preference and DNT overrides are treated more like global user rules and can appear even when not matched in the current batch.
- Historical batches therefore differ: some show no matched terms, while others show terms such as those hit in history batch 10.

Needed design:

- Show why a term was included: exact source hit, alias hit, player global preference, DNT global rule, or manually pinned.
- Expose this explanation in Prompt preview without dumping internal implementation names.
- Decide whether player/DNT global rules should always appear or be capped/ranked.
- Add tests using RYOS/adwryos batches where one batch hits known Starfield terms and another does not.

### 3. RAG-Style Vanilla Lore/Terminology Retrieval

Design a retrieval mechanism for detecting when a mod text references vanilla concepts and passing the right game-term context into the system prompt.

Goals:

- Detect vanilla factions, locations, people, items, quests, abbreviations, and lore concepts present in the source text.
- Retrieve canonical translations plus short explanatory context.
- Keep prompt size bounded and deterministic.
- Prefer transparent source/alias matching first, then consider embeddings or lexical retrieval if needed.

Open design questions:

- Whether the KB should store embeddings, token n-grams, aliases, or all three.
- Whether retrieval should happen per item, per batch, or per plan.
- How to prevent common words from pulling irrelevant lore.
- How to show ordinary players why a term was included.

### 4. Quick Translate For One Entry

Add an Entries-tab button to translate the currently selected entry using the active AI provider.

Expected behavior:

- Button label: `快速翻译当前条目`.
- Uses current active provider profile.
- Uses a concise fixed system prompt assembled from game name, mod/project name, target language, and the selected entry text.
- Does not require full batch planning.
- Writes only to project memory, not to the original plugin.
- Shows clear cost/error status.

Prompt direction:

- "You are translating a mod for {game}. Translate this one entry into {target_language}. Preserve placeholders, tags, names that should remain untranslated, and JSON-safe formatting."
- Reuse the existing placeholder and validation rules where possible.

### 5. Select Entries And Submit To Batch Translation Queue

Add bulk selection to Entries and a button `提交到批量翻译队列`.

Expected behavior:

- Player can select multiple entries from the Entries table.
- Button creates a queue/selection artifact for the AI agent or CLI.
- UI explains that the AI agent still needs to assemble the system prompt through the CLI and, when preview is enabled, ask the user to approve the generated prompt before dispatch.
- Selection must not directly send hidden work to the provider.

Open design questions:

- Queue file format and location under the project.
- How the CLI consumes selected rows.
- Whether selected rows should become a new plan source, a plan filter, or a separate queue table.
- How to show queued rows and remove them.


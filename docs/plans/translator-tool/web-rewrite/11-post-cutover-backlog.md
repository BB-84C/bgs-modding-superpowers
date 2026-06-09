# Post-Cutover Backlog

Date: 2026-06-09

Scope: these are follow-up design and feature items raised during manual user testing after the browser GUI cut-over.

## Manual Testing Findings To Preserve

- Fresh GUI must mean a fresh browser process, not a clean project state. The UI must not report old sqlite `running` rows as actively billing unless the current GUI/CLI process has real activity evidence.
- Project selection must be URL/stateful. Clicking a project in the sidebar must change the active project for all tabs, API calls, and top status copy.
- `打开导出目录` must not imply an SST exists. If no `.sst` files exist, the UI must tell the user to run `导出 xTranslator 文件` first.
- Desktop panes must be tested at browser zoom levels like 150%, not only by `documentElement.scrollWidth`. Validation must include actual scrollability and visual reachability of controls.
- Theme variants must recolor the entire terminal surface, not only foreground text. Green is intended as a Fallout NV-style green terminal theme; amber remains the existing Fallout/TK inheritance; mono is black/white.
- Historical prompt previews can show different glossary/DNT hits because the current mechanism matches vanilla/mod terms against each batch's source text, while player/DNT override entries are merged more broadly. This is confusing and needs explicit design.

## New Feature Backlog

### 1. Import Translation Project From Plugin File

Status 2026-06-09: implemented for loose `.esp/.esm/.esl` files that the parser can read directly.

Add a GUI flow to import a new translation project from `.esp`, `.esl`, or `.esm`.

Expected behavior:

- User picks a plugin file from disk.
- Tool detects the Bethesda game automatically from plugin/header/context where possible.
- Tool creates a translator project and extracts translatable records.
- UI explains that the original plugin file is not modified.

Open design questions:

- Creation Club Starfield plugins with localized text packed inside `.ba2` archives still need BA2 Strings extraction support. Current GUI correctly blocks and explains missing loose `STRINGS/DLSTRINGS/ILSTRINGS`.
- Game detection now prefers root master hints such as `Starfield.esm`, then falls back to TES4 header form-version ranges.
- Whether imports should copy the plugin into the project or reference the original path.
- How to handle MO2/VFS paths versus ordinary filesystem paths.

### 2. Glossary And Do-Not-Translate Hit Mechanism

Status 2026-06-09: implemented as visible glossary evidence for prompt previews and planned batches.

The current hit behavior is not transparent enough for ordinary players.

Current rough behavior:

- Vanilla/mod knowledge terms are selected by matching source text or aliases in the current batch.
- Player preference and DNT overrides are treated more like global user rules and can appear even when not matched in the current batch.
- Historical batches therefore differ: some show no matched terms, while others show terms such as those hit in history batch 10.

Needed design:

- Show why a term was included: exact source hit, alias hit, player global preference, DNT global rule, or RAG-like source match.
- Player and DNT scopes now use the same evidence/dedupe path as vanilla/mod terminology.
- Retrieval is bounded by term and prompt character budgets; excluded terms are marked with an evidence reason instead of silently overflowing prompt panels.
- Remaining UX work: make the explanation friendlier in long historical batches without exposing internal match labels.

### 3. RAG-Style Vanilla Lore/Terminology Retrieval

Status 2026-06-09: first lexical/RAG-style retrieval pass implemented with deterministic caps and dedupe.

Design a retrieval mechanism for detecting when a mod text references vanilla concepts and passing the right game-term context into the system prompt.

Goals:

- Detect vanilla factions, locations, people, items, quests, abbreviations, and lore concepts present in the source text.
- Retrieve canonical translations plus short explanatory context.
- Keep prompt size bounded and deterministic.
- Prefer transparent source/alias matching first, then consider embeddings or lexical retrieval if needed.

Open design questions:

- Whether the KB should store embeddings, token n-grams, aliases, or all three.
- Whether embeddings are worth adding after the lexical candidate path.
- How much short lore explanation should accompany canonical translations without bloating prompts.
- How to tune stop-word/noise filters after more real mod batches.

### 4. Quick Translate For One Entry

Status 2026-06-09: implemented in Entries with `快速翻译当前条目`.

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
- Real OpenRouter-Opus4.6 browser verification translated `Portable Landing Pad Trigger` to `便携式着陆平台触发器`.
- Empty provider responses are not written. For OpenRouter/Claude `json_schema` empty `items`, the quick path retries the same provider/model with `json_object` before failing.

### 5. Select Entries And Submit To Batch Translation Queue

Status 2026-06-09: implemented as GUI selection artifacts plus CLI queue consumption.

Add bulk selection to Entries and a button `提交到批量翻译队列`.

Expected behavior:

- Player can select multiple entries from the Entries table.
- Button creates a queue/selection artifact for the AI agent or CLI.
- UI explains that the AI agent still needs to assemble the system prompt through the CLI and, when preview is enabled, ask the user to approve the generated prompt before dispatch.
- Selection must not directly send hidden work to the provider.

Implemented behavior:

- Queue files live under `batches/selection-queue/<queue-id>.json`.
- `xtl batch plan <project> --queue <queue-id> ...` consumes selected row ids and builds a normal plan.json/system prompt.
- GUI submission does not call the provider. It shows the next CLI command and explains that prompt preview still applies.
- Remaining UX work: list old queue requests and allow deleting stale requests from the GUI.

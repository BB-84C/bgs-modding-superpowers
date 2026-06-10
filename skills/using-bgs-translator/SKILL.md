---
name: using-bgs-translator
description: Use when the user wants to translate a Bethesda Game Studios plugin (.esp/.esm/.esl) with bgs-translator/xtl, create or inspect a translation project, run LLM batch translation, generate prompt previews, or export SST/XML for xTranslator. Triggers - "translate this mod", "汉化这个 mod", "localize plugin", "build SST", "use xtl", "bgs-translator".
---

# Using bgs-translator

`bgs-translator` is the agent-driven translation pipeline for Bethesda plugin
text. It reads plugin strings, builds AI translation batches with glossary and
protected-span handling, writes a project memory database, and exports SST/XML
dictionaries for xTranslator or ESP-ESM Translator to finalize.

The browser GUI is the only GUI surface. The agent should prefer `xtl` for work
it can do directly; use the GUI for human review, provider/key setup when the
user wants it, prompt preview, progress monitoring, and manual cleanup.

Human manuals, read these files and explain them to users who need GUI help:

- Chinese: `tools/bgs-translator/USER-GUIDE.zh-cn.md`
- English: `tools/bgs-translator/USER-GUIDE.en.md`

## What xtl Does Better

Most translator tools focus on editing string tables. `xtl` builds a complete
LLM request for each batch:

1. It extracts only translatable plugin text into project memory.
2. It masks dangerous placeholders such as `{P0}` and `<Alias=...>`.
3. It deduplicates repeated text where safe.
4. It recalls relevant game/mod/player terminology.
5. It adds game context, mod context, signature explanations, style rules, and
   do-not-translate rules to a system prompt.
6. It sends compact JSON-shaped work items to the selected provider.
7. It validates the response before writing translations back to project memory.
8. It exports SST/XML for xTranslator instead of editing the original plugin.

This is why the output can be more context-aware than plain string-table machine
translation: the LLM receives the text plus the mod's purpose, game lore,
record-type meaning, glossary, and placeholder rules in one request.

## Help and Capability Discovery

Never assume a shown command is the only valid shape. Examples below are
templates. Before using an unfamiliar option, check the live CLI:

```powershell
# Show all top-level xtl command groups.
xtl --help

# Show provider commands and accepted provider options.
xtl profile --help
xtl profile add --help
xtl profile edit --help

# Show project import/export options.
xtl project --help
xtl project init --help
xtl project export --help

# Show inspect, planning, run, status, and cancellation options.
xtl inspect --help
xtl batch plan --help
xtl batch run --help
xtl batch status --help
```

Provider `--sdk-kind` is not always `openai-compat`. Check `xtl profile add
--help` for the currently supported values. At the time of this skill, the
code supports `openai`, `anthropic`, `gemini`, and `openai-compat`.

## Operating Rules

- Do not edit `.esp`, `.esm`, or `.esl` directly. `xtl` emits SST/XML only.
- Do not route translator work through xEdit or MO2 unless the user explicitly
  asks for an unrelated xEdit/MO2 task.
- Do not accept API keys in chat or command history. Use `xtl profile set-key`
  for hidden interactive input, or let the user enter the key in the browser GUI.
- Do not bypass prompt preview when the user has enabled it. If the user asks for
  a fully agent-run batch, set/confirm `behavior.prompt_preview_required=false`
  before dispatching.
- Always surface plan size, batch count, skipped placeholder-only count, and the
  output dictionary path.
- Treat `needs_review` as real work, not as success. Either fix it or report it.

## CLI End-to-End Flow

Use this flow when the user wants the agent to run the translation process.

1. Verify the local CLI.

   ```powershell
   # Confirm the installed/current xtl can start and report capabilities.
   xtl version
   ```

2. Inspect the plugin before creating a project.

   ```powershell
   # Example path only. Replace with the user's real ESP/ESM/ESL.
   xtl inspect plugin "D:\path\to\Mod.esm"
   ```

   If game detection is ambiguous, pass a real game value. Do not guess silently.
   Check available options with `xtl inspect plugin --help`.

3. Create or refresh a project.

   ```powershell
   # Create project memory from the source plugin. Example target language: zh-cn.
   xtl project init <project> --plugin "D:\path\to\Mod.esm" --target-lang zh-cn
   ```

4. Configure the provider if needed.

   ```powershell
   # Example: OpenAI-compatible provider. Check xtl profile add --help for all sdk kinds.
   xtl profile add <profile> --sdk-kind openai-compat --base-url <api-root> --model <model> --api-key-env <ENV_NAME> --json-mode json_object

   # Store the key with hidden input. Never put the real key in the command line.
   xtl profile set-key <profile>

   # Example advanced settings. Use xtl profile edit --help before changing these.
   xtl profile edit <profile> --max-concurrency 8 --rate-limit-rpm 120 --rate-limit-tpm 90000

   # Test the provider and then make it active.
   xtl profile probe <profile>
   xtl profile activate <profile>
   ```

   `set-key` prompts with hidden input and writes `translator/profiles/.env`.
   Never place a real key in a shell command, commit, log, or chat message.

5. Inspect project content.

   ```powershell
   # Get high-level counts by record signature.
   xtl inspect signatures <project>

   # Example: inspect 100 quest entries. Check xtl inspect entries --help for filters.
   xtl inspect entries <project> --sig QUST --limit 100
   ```

6. Research context before planning. For real mods, gather:

   - game-world context relevant to the mod;
   - mod context from the mod page/readme;
   - sampled entries by signature/field;
   - protected placeholders and recurring tags that must remain unchanged.

7. Plan the batch. For "all currently untranslated" use filters; for GUI
   queue/fanatic mode use `--queue <queue_id>` when the user submitted one.

   ```powershell
   # Example: plan untranslated QUST text in groups of 200.
   # This only writes plan.json and does not call the provider.
   xtl batch plan <project> --register dialogue --target-lang zh-cn --profile <profile> --batch-size 200 --sig QUST --game-lore-world "Starfield 2330 Settled Systems" --game-lore-summary "<detailed lore>" --mod-name "<mod name>" --mod-theme "<detailed mod context>" --style "Polished Simplified Chinese game localization."
   ```

   `--register`, `--sig`, `--field`, batch size, and context fields are examples.
   Check `xtl batch plan --help` and inspect project signatures before choosing.
   Report `plan_id`, `total_items`, `batch_count`, `skipped_reasons`, and the
   plan path.

8. Dispatch the run.

   ```powershell
   # Start a background worker and return immediately with run_id and log paths.
   xtl batch run <project> --plan <plan_id>
   ```

   `xtl batch run` returns immediately by default. Use `--wait` only for tests or
   deliberate foreground execution. Use `--dry-run` only for smoke tests. For
   no-human-preview agent runs, first confirm:

   ```powershell
   # Disable required browser prompt preview only when the user asked for agent-only execution.
   xtl config set behavior.prompt_preview_required false
   ```

9. Poll status and logs.

   ```powershell
   # Poll periodically after background launch.
   Start-Sleep -Seconds 10
   xtl batch status <run_id>

   # Inspect recent persisted run files/logs if progress looks stuck.
   xtl batch logs <run_id>

   # Request cancellation if the user asks to stop.
   xtl batch cancel <run_id>
   ```

10. Validate and export.

    ```powershell
    # Validate project state before export.
    xtl validate project <project>

    # Export xTranslator dictionary output.
    xtl project export <project> --format sst
    ```

    Tell the user which SST/XML files were emitted and that xTranslator/ESP-ESM
    Translator owns the final "Finalize" step.

## Browser GUI Flow

Use the GUI when a human needs to configure, inspect, approve, or manually fix:

```powershell
# Launch the local browser control panel.
xtl gui
```

If the GUI or its process state becomes inconsistent, restart it with the stable
helper:

```powershell
# From tools/bgs-translator, restart the web GUI on the usual local port.
powershell -ExecutionPolicy Bypass -File .\scripts\restart-web-gui.ps1 -Port 7847
```

The GUI is browser-only. There is no Tk fallback.

High-signal tabs:

- Project: import plugin projects, see project metadata, export SST, open export
  directory, and see record signature translation stats.
- Entries: filter, inspect source/destination, quick translate, multi-select,
  submit selected entries, or use fanatic mode for all filtered entries.
- Prompt: inspect current pending prompt and approve/approve-all/skip/discard.
- Batches: watch run progress, request stop, inspect historical audit records,
  and discard completed run translations when supported.
- Profiles: create/activate/probe providers and store API keys locally.
- Glossary: edit player terms and do-not-translate terms.
- Logs: inspect run files and technical logs.

For detailed player-facing guidance, point the user to the manuals listed at the
top of this skill.

For maintaining Starfield official terminology packs, mod-specific glossary
packs, or third-party Skyrim/Fallout localization KBs, switch to
`maintaining-modding-environments`. Translator runs consume those packs; they do
not own KB release or provenance policy.

## Prompt Context Requirements

Do not send generic prompts. For every real batch, build context with:

- the game, era, faction/setting, and localization style;
- the mod's purpose, systems, characters, places, terminology, and UI tone;
- signature explanations only for signatures present in the batch;
- player glossary and do-not-translate rules;
- protected placeholder rules such as `{P0}` and `<Alias=...>`.

If the user provides a mod URL, browse it and summarize relevant features. If
the mod page is unavailable, use local readmes/project entries and state the
gap.

## Status Semantics

Align user-facing status with xTranslator concepts:

- `untranslated`: no accepted translation exists.
- `translated`: validated/accepted translation.
- `needs_review`: partial or suspicious translation that requires human review.
- `locked`: should remain unchanged and should not be sent to AI.

Placeholder-only and number-only strings should not enter AI batches. Do not
hide a mismatch between GUI counts and exported SST; investigate before
claiming success.

## Anti-Patterns

- Do not copy examples blindly. Check `--help` for supported values first.
- Do not make up hard caps. Respect user batch size/budget settings; if a prompt
  may exceed context, report it and ask for smaller batches/settings.
- Do not mark English source copied to destination as translated unless it is a
  deliberate locked/no-translate entry.
- Do not rely on string-only SST matching as proof of correct export. FormID and
  record identity should match xTranslator where possible.
- Do not leave orphaned pending-preview state after a service restart. Historical
  plans are audit records unless a real resume command exists.
- Do not promise cancellation is free; already-started provider calls may bill.

---
name: using-bgs-translator
description: Use when the user wants to translate a Bethesda Game Studios plugin (.esp/.esm/.esl) with bgs-translator/xtl, create or inspect a translation project, run LLM batch translation, generate prompt previews, or export SST/XML for xTranslator. Triggers - "translate this mod", "汉化这个 mod", "localize plugin", "build SST", "use xtl", "bgs-translator".
---

# Using bgs-translator

`bgs-translator` is the agent-driven translation pipeline for Bethesda plugin
text. It reads plugin strings, builds AI translation batches with glossary and
protected-span handling, writes a project memory database, and exports SST/XML
dictionaries for xTranslator or ESP-ESM Translator to finalize.

The browser GUI is the only GUI surface. The agent should still prefer `xtl`
for work it can do directly; use the GUI only for human review, provider/key
setup when the user wants it, prompt preview, progress monitoring, and manual
cleanup.

Human manuals:

- Chinese: `tools/bgs-translator/USER-GUIDE.zh-cn.md`
- English: `tools/bgs-translator/USER-GUIDE.en.md`

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

1. Verify the local CLI:

   ```powershell
   xtl version
   ```

2. Inspect the plugin before creating a project:

   ```powershell
   xtl inspect plugin "D:\path\to\Mod.esm"
   ```

   If game detection is ambiguous, pass `--game Starfield`, `--game SkyrimSE`,
   etc. Do not guess silently.

3. Create or refresh a project:

   ```powershell
   xtl project init <project> --plugin "D:\path\to\Mod.esm" --target-lang zh-cn
   ```

4. Configure the provider if needed:

   ```powershell
   xtl profile add <profile> --sdk-kind openai-compat --base-url <api-root> --model <model> --api-key-env <ENV_NAME> --json-mode json_object
   xtl profile set-key <profile>
   xtl profile edit <profile> --max-concurrency 8 --rate-limit-rpm 120 --rate-limit-tpm 90000
   xtl profile probe <profile>
   xtl profile activate <profile>
   ```

   `set-key` prompts with hidden input and writes `translator/profiles/.env`.
   Never place a real key in a shell command, commit, log, or chat message.

5. Inspect project content:

   ```powershell
   xtl inspect signatures <project>
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
   xtl batch plan <project> --register dialogue --target-lang zh-cn --profile <profile> --batch-size 200 --sig QUST --game-lore-world "Starfield 2330 Settled Systems" --game-lore-summary "<detailed lore>" --mod-name "<mod name>" --mod-theme "<detailed mod context>" --style "Polished Simplified Chinese game localization."
   ```

   Read the returned JSON envelope. Report `plan_id`, `total_items`,
   `batch_count`, `skipped_reasons`, and the plan path.

8. Dispatch the run:

   ```powershell
   xtl batch run <project> --plan <plan_id>
   ```

   Use `--dry-run` only for smoke tests. For no-human-preview agent runs, first
   confirm `behavior.prompt_preview_required=false`.

9. Monitor and cancel if requested:

   ```powershell
   xtl batch status <run_id>
   xtl batch logs <run_id>
   xtl batch cancel <run_id>
   ```

10. Validate and export:

    ```powershell
    xtl validate project <project>
    xtl project export <project> --format sst
    ```

    Tell the user which SST/XML files were emitted and that xTranslator/ESP-ESM
    Translator owns the final "Finalize" step.

## Browser GUI Flow

Use the GUI when a human needs to configure, inspect, approve, or manually fix:

```powershell
xtl gui
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

- Do not make up hard caps. Respect user batch size/budget settings; if a prompt
  may exceed context, report it and ask for smaller batches/settings.
- Do not mark English source copied to destination as translated unless it is a
  deliberate locked/no-translate entry.
- Do not rely on string-only SST matching as proof of correct export. FormID and
  record identity should match xTranslator where possible.
- Do not leave orphaned pending-preview state after a service restart. Historical
  plans are audit records unless a real resume command exists.
- Do not promise cancellation is free; already-started provider calls may bill.

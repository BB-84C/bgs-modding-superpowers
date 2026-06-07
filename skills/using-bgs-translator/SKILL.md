---
name: using-bgs-translator
description: Use when the user wants to translate a Bethesda Game Studio mod's plugin text (.esp/.esm/.esl) to another language, especially via batch LLM translation. Routes through the bgs-translator CLI + Tk control panel. Emits SST files that the user finalizes in xTranslator or ESP-ESM Translator. Triggers - "translate this mod", "汉化这个 mod", "localize mod to chinese", "build SST for", "use my LLM to translate plugins".
---

# Using bgs-translator

`bgs-translator` is the agent-driven translation pipeline for Bethesda plugin
text. It reads plugin strings, plans or applies translations, validates project
state, and emits dictionaries for the user's existing translator GUI to finalize.

## When to use this skill

Use this skill when the user asks for any of these tasks:

- Translate a Bethesda plugin (`.esp`, `.esm`, `.esl`) to another language.
- Build `.sst` output for xTranslator or ESP-ESM Translator.
- Run an LLM batch translation pass over a mod.
- Do spot translation fixes after a batch run.
- Inspect translatable plugin entries before translation.
- Manage glossary terms for a plugin translation project.

Do not use this skill for MCM text files, VMAD/Pex strings, voice files, or
direct plugin binary edits. See "What this tool does not do" below.

## Tool surface

- **Agent operations use `xtl`.** The agent invokes the `xtl` CLI for project
  init, inspection, planning, batch execution, validation, and export.
- **Tk panel is for the user.** `xtl gui` opens configuration and monitoring:
  provider profiles, prompt preview, progress, cancellation, and cost display.
  The agent does not automate Tk clicks.
- **BGS KB tools are glossary reference only.** Use `bgs_kb_query` /
  `bgs_kb_get` to read curated terminology where available. The KB does not
  perform translation operations.
- **xEdit and MO2 are unrelated here.** Do not route translator work through the
  xEdit MCP or MO2 control plane. `bgs-translator` reads plugin text and emits
  dictionaries; it does not write plugins.

## Two operating modes

| Mode | Use when | Main commands |
|---|---|---|
| Mode A: LLM batch | First-pass or bulk translation | `xtl batch plan` -> preview -> `xtl batch run` -> `xtl batch status` |
| Mode B: atomic edits | Spot fixes, terminology corrections, post-batch cleanup | `xtl inspect entries` / `xtl inspect entry` -> `xtl edit entry` or `xtl edit bulk` |

Choose one mode deliberately. If a Mode A run is in flight, avoid Mode B edits
against queued entries unless you have confirmed the queued batch will not
overwrite the manual change.

## Required workflow steps

For any translation project:

1. Verify the CLI is installed:
   ```powershell
   xtl version
   ```
   If missing, tell the user to install it with `pipx install bgs-translator`
   or, in a source checkout, `pipx install -e .` from `tools/bgs-translator/`.
2. Confirm the essentials with the user: source mod path, game code, target
   language, and provider profile. If a project already exists, read its status
   before asking for repeated details.
3. Initialize the project:
   ```powershell
   xtl project init <name> --plugin <path> --game <code> --source-lang <src> --target-lang <tgt>
   ```
4. Surface parse status and counts:
   ```powershell
   xtl inspect signatures <name>
   ```
   If parsing fails, report the envelope error exactly and stop.
5. Run either Mode A or Mode B.
6. Validate the project:
   ```powershell
   xtl validate project <name>
   ```
   If validation returns findings or a manual-review queue, surface them; do not
   force them to translated.
7. Export the dictionary:
   ```powershell
   xtl project export <name> --format sst
   ```
8. Tell the user the output file path(s) and next step: open them in
   xTranslator or ESP-ESM Translator, click Finalize, and build the final mod.

## Mode A: LLM batch

Use Mode A for bulk translation.

1. Compose prompt slots before planning:
   - `--game-lore`: concise game-world context for the LLM.
   - `--mod-name`: display name of the mod.
   - `--mod-theme`: one or two sentences describing what the mod adds.
   - `--style`: target-language register and tone.
   - Extra project context when the command surface supports it.
2. Plan the batch for each signature / field selection:
   ```powershell
   xtl batch plan <project> --register <register> --target-lang <tgt> --profile <profile> --sig <SIG> --field <FIELD> --game-lore "..." --mod-name "..." --mod-theme "..." --style "..."
   ```
3. Read the returned plan envelope. Surface:
   - `plan_id`
   - `total_items`
   - `batch_count`
   - token estimates
   - estimated cost
   - sample system prompt when available in the plan artifact
4. If estimated cost is above the confirmation threshold, stop and ask the
   user before dispatching.
5. Run the plan:
   ```powershell
   xtl batch run <project> --plan <plan_id>
   ```
   Use `--dry-run` only for rehearsal or acceptance smoke.
6. Poll status by run id:
   ```powershell
   xtl batch status <run_id>
   ```
7. If items go to manual review, surface them and either handle with Mode B or
   leave them for the user.

Respect the user's Tk prompt-preview setting. Do not use command flags to bypass
the user's desire to preview prompts before dispatch.

## Mode B: atomic edits

Use Mode B for small, precise changes.

1. Find candidate entries:
   ```powershell
   xtl inspect entries <project> --sig <SIG> --field <FIELD> --limit 50
   ```
2. Inspect the full entry context:
   ```powershell
   xtl inspect entry <project> <row_id>
   ```
3. Decide the translation from context, glossary, and user preference. Ask only
   if the meaning is genuinely ambiguous.
4. Apply the edit:
   ```powershell
   xtl edit entry <project> <row_id> --dest "<translation>" --status translated --reason "agent spot fix"
   ```
5. For bulk corrections, write JSONL rows containing `row_id`, `dest`, `status`,
   and optional `reason`, then run:
   ```powershell
   xtl edit bulk <project> --input <edits.jsonl>
   ```

Validate after edits. Do not mark uncertain entries as translated just to clean
up the queue.

## Glossary management

For terminology that should be consistent:

1. Read existing glossary knowledge where available:
   ```text
   bgs_kb_query({ query: "<term>", domains: ["localization"], games: ["<game>"] })
   ```
2. Apply the glossary during planning by giving the LLM enough context and by
   relying on translator's built-in glossary composition.
3. For player overrides or do-not-translate entries, instruct the user to use
   the Tk Glossary tab, or write a user-pack override only when the user has
   explicitly permitted that filesystem change.
4. For routine custom pack registration or cache maintenance, route to
   `maintaining-modding-environments`.

The KB is reference material. The actual project state is the translator memory
database and the `xtl` command output.

## API key boundary (critical)

The agent must never read, write, request, or echo API key values.

Hard rules:

- Do **not** read `~/.bgs-modding-superpowers/translator/profiles/.env`.
- Do **not** accept API keys in chat.
- Do **not** write API keys into files.
- Do **not** echo API-like strings from error output.
- Use only environment-variable references via `--api-key-env`.

When registering a provider profile:

```powershell
xtl profile add <name> --sdk-kind <kind> --base-url <url> --model <model> --api-key-env <VARNAME>
```

After registration, tell the user:

> I've registered profile `<name>`. To activate it, please add your API key to
> `~/.bgs-modding-superpowers/translator/profiles/.env`:
>
> `<VARNAME>=<your-key>`
>
> Or open the Tk panel -> Profiles tab -> `<name>` -> Edit -> enter your key.
> Then run `xtl profile probe <name>` to verify the profile metadata.

If the user pastes a key into chat, refuse to handle it and direct them to the
`.env` or Tk workflow.

## Cost awareness

- Always surface the cost estimate from `xtl batch plan` before large batch runs.
- If `est_cost_usd` is greater than `$1.00`, get explicit user confirmation
  before `xtl batch run`.
- If the plan would exceed the profile's `cost_cap_usd`, do not dispatch. Tell
  the user the cap and ask them to switch profile, reduce scope, or raise the cap.
- Keep cancellation billing honest: provider-side billing for in-flight requests
  may still occur after client cancellation.

## Cancellation handling

When the user asks to cancel:

```powershell
xtl batch cancel <run_id>
```

If the CLI supports client-level cancellation for the active version, use the
specific client selector requested by the user. After cancellation, surface the
returned envelope's committed-cost estimate or billing note. Do not promise that
already-started provider calls were free.

## Starfield-specific behavior

- Starfield projects default to `starfield_dummy_fill = true`.
- Export normally produces nine SST files: one target-language translation and
  eight source-as-dummy files to protect non-target-language installs.
- Tell the user to Finalize each of the nine files separately in xTranslator.
- If the user disables dummy fill with `--no-starfield-dummy-fill`, explain the
  consequence first: non-target Starfield language players may see missing or
  source-language strings.

## What this tool does not do

- **MCM translation:** do not use `xtl` for MCM `.txt` or `config.json` files.
  Translate those by direct file read and agent reasoning, with user review.
- **VMAD / Pex translation:** not supported. Redirect to xTranslator workflows.
- **Plugin binary writing:** not supported. `xtl` reads plugins and emits
  dictionaries only.
- **Voice translation:** not supported. SST output covers text, not audio.
- **MO2 overlay emission:** the user's translator GUI Finalize step owns the
  final files and mod packaging.

## Anti-patterns (must not do)

1. Do not drive the Tk GUI from the agent. The GUI is for the user; the agent
   uses `xtl`.
2. Do not write, read, ask for, or echo API keys. Use `--api-key-env` only.
3. Do not bypass validation. Manual-review items stay manual until resolved.
4. Do not skip cost surfacing before large batches. Cost caps are safety rails.
5. Do not assume Starfield dummy-fill behavior. Check project settings or export
   output and explain consequences when disabled.
6. Do not modify `.esp`, `.esm`, or `.esl` files directly. `xtl` emits SST/XML;
   the user's translator GUI finalizes.
7. Do not bypass prompt preview when the user has enabled it.
8. Do not interleave Mode A and Mode B unsafely while a batch is in flight.
9. Do not route translator work through xEdit or MO2. Those are separate tools.

## Cross-references

- `using-bgs-modding-superpowers` — per-session bootstrap that routes mod
  translation requests here.
- `writing-modpack-devlog` — use when the user asks to log translation progress
  or decisions.
- `maintaining-modding-environments` — use for KB pack registration, glossary
  pack updates, or cache care.
- `setting-up-bgs-modding-environment` — first-run environment setup; may add
  optional `pipx install bgs-translator` guidance.

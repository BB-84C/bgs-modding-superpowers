# 13 — Agent Skill Outline

One skill: `using-bgs-translator`.

This document specifies what that skill needs to contain. The actual `SKILL.md` will be authored in chunk M.

---

## 1. Frontmatter

```yaml
---
name: using-bgs-translator
description: Use when the user wants to translate a Bethesda Game Studio mod's plugin text (.esp/.esm/.esl) to another language, especially via batch LLM translation. Routes through the bgs-translator CLI + Tk control panel. Emits SST files that the user finalizes in xTranslator or ESP-ESM Translator. Triggers - "translate this mod", "汉化这个 mod", "localize mod to chinese", "build SST for", "use my LLM to translate plugins".
---
```

---

## 2. What the skill must teach the agent

### 2.1 Tool surface

- The agent invokes the `xtl` CLI for all operations
- The Tk panel is configuration + monitoring; the user opens it; the agent does NOT automate Tk interactions
- The bundled `bgs_kb_*` MCP tools are for glossary management (read), not translation operation
- The `xedit` MCP and MO2 control plane are unrelated to this work

### 2.2 The two modes

| Mode | When to use | Commands |
|---|---|---|
| Mode A (LLM batch) | Bulk translation, especially first pass over a mod | `xtl batch plan` → preview → `xtl batch run` → poll `xtl batch status` |
| Mode B (atomic edits) | Spot fixes, precision corrections, post-batch cleanup | `xtl inspect entries` / `xtl inspect entry` → agent decides translation → `xtl edit entry` or `xtl edit bulk` |

### 2.3 Required steps for any translation project

1. Verify the user has `bgs-translator` installed: `xtl version`. If not present: `pipx install bgs-translator`.
2. Confirm with user: which mod? which target language? which provider profile?
3. `xtl project init <name> --source-plugin <path> --game <code> --source-lang <src> --target-lang <tgt> --profile <name>`
4. Surface project status: `xtl project status <name>` — confirms parse worked, shows signature counts
5. Mode A flow per §2.4 below, OR Mode B flow per §2.5
6. `xtl validate project <name>` — confirm no validation failures or surface manual-review queue to user
7. `xtl project export <name> --format sst` — get SST file(s)
8. Tell user where the SST file(s) are; explain next step (open in xTranslator/ESP-ESM Translator, hit Finalize, build mod)

### 2.4 Mode A flow (LLM batch driver)

For each signature × field combination the agent wants to translate:

1. Compose the system prompt slots:
   - `--game-lore`: agent's understanding of the game world (Skyrim/Starfield/etc.) phrased for the LLM
   - `--mod-name`: mod's display name
   - `--mod-theme`: 1-2 sentence description of what the mod adds
   - `--style`: target language register/tone preferences
   - `--extra-context`: anything project-specific
2. `xtl batch plan ... --register <register> --signature <sig> --field <field>` — review the returned plan
3. Show the sample_system_prompt to user (text only — the user might separately have the Tk preview enabled)
4. `xtl batch run <project> --plan <plan_id> --confirm` — dispatch
5. Poll `xtl batch status <run_id>` until status=complete
6. If items went to manual-review: surface to user, then either Mode B them or skip

### 2.5 Mode B flow (atomic edits)

For each spot fix:
1. `xtl inspect entries <project> --edid-contains <X>` to find the entry
2. `xtl inspect entry <project> --row-id <r_...>` for full context
3. Agent decides translation (from its own knowledge OR by consulting user)
4. `xtl edit entry <project> --row-id <r_...> --translation "..." --status translated`

For bulk corrections: agent assembles a JSONL of `{row_id, translation, status}` rows and `xtl edit bulk`.

### 2.6 Glossary management

For curated terminology that should be consistent:
- Read existing community glossaries: `bgs_kb_query --domain l10n --games <game>`
- Add player overrides or do-not-translate entries: instruct user to add via Tk Glossary tab, or write directly to `~/.bgs-modding-superpowers/kb/user-packs/translator-overrides-<src>-<tgt>/` (if user permits and the agent has the skill loaded)

### 2.7 The API key boundary (critical)

**The agent does NOT read `~/.bgs-modding-superpowers/translator/profiles/.env`.**

When registering a new profile:

```
xtl profile add <name> --sdk <kind> --base-url <url> --model <model> --api-key-env <VARNAME>
```

After the command succeeds, the agent's message to the user:

> "I've registered profile `<name>`. To activate it, please add your API key to `~/.bgs-modding-superpowers/translator/profiles/.env`:
>
> `<VARNAME>=<your-key>`
>
> Or open the Tk panel → Profiles tab → `<name>` → [Edit] → enter your key in the [Show]-able field. Once that's done, run `xtl profile probe <name>` to verify."

The agent must NEVER:
- Accept an API key in chat from the user and try to write it to `.env`
- Read `.env` to verify a key is set
- Echo any API key it might encounter in error output back to chat

### 2.8 Cost awareness

- Before running large batches, the agent must surface the estimated cost from `xtl batch plan`
- For batches estimated > $1.00, the agent must explicitly confirm with the user before running
- For batches that would exceed the profile's `cost_cap_usd`, the agent must NOT attempt to dispatch; instead surface the cap and ask user to lift or switch profile

### 2.9 Cancellation handling

When the user requests cancellation:
- `xtl batch cancel <run_id>` for whole run
- `xtl batch cancel <run_id> --client <n>` for one
- After cancellation, surface the returned envelope's `cost_committed_estimate_usd` and the "may have been billed" note to the user

### 2.10 Starfield special cases

- Starfield projects default to `starfield_dummy_fill = true`. Agent doesn't need to do anything; export produces 9 SSTs.
- User must Finalize each of the 9 in xTranslator separately. Agent reminds user of this on export completion.
- If user wants to ship only one language (don't care about non-target Starfield language players): `xtl project init --no-starfield-dummy-fill`, surface the consequence per `03-sst-output.md` §3.3.

### 2.11 What this tool does NOT do (defer to other workflows)

- MCM translation: do NOT use `xtl` for MCM `.txt` / `config.json` files. Use direct file reads + agent reasoning. (See sister skill `translating-mcm` if/when it ships.)
- VMAD/Pex translation: not supported. If user asks, redirect to xTranslator.
- Plugin binary writing: not supported. We only produce SST.
- Voice file translation: not supported. SST translates text only; voice files are independent assets.

---

## 3. Skill cross-references

- `using-bgs-modding-superpowers` (bootstrap) — will be updated to mention `using-bgs-translator` as the translation routing target
- `maintaining-modding-environments` — for KB pack registration of `bgs-kb-l10n-*` packs
- `xedit-automation` — completely unrelated; do not cross
- `setting-up-bgs-modding-environment` — adds optional `pipx install bgs-translator` step

---

## 4. Skill anti-patterns (must explicitly forbid)

The skill body must include an anti-patterns section:

1. **Do not invoke Tk GUI commands from agent**. The GUI is for the user. Agent uses CLI.
2. **Do not write API keys** anywhere. Period. The CLI's `--api-key-env` is the only valid surface.
3. **Do not bypass the validator**. If a batch's items go to manual-review, surface them to user; do NOT force-set status to `translated`.
4. **Do not skip cost surfacing** before running large batches. Cost cap is a safety rail; respecting it is mandatory.
5. **Do not assume Starfield dummy-fill behavior**. If user has it disabled, the agent must explain consequences before export.
6. **Do not modify plugin .esp/.esm/.esl files directly**. The tool reads them; the tool emits SST; the user's xTranslator + Finalize produces the final mod.
7. **Do not use `xtl batch run --confirm` to bypass GUI prompt preview if user has it enabled**. The `--confirm` flag suppresses the popup; respect the user's preview setting from `project.toml`.
8. **Do not interleave Mode A and Mode B unsafely**. If Mode A run is in-flight, do Mode B edits cautiously — entries in batch dispatch queue may not yet reflect Mode B writes.

---

## 5. Skill file estimated structure

```markdown
---
(frontmatter)
---

# Using bgs-translator

## When to use this skill
...

## Tool overview
...

## Two operating modes
...

## Standard workflow
(numbered list per §2.3)

## Mode A: LLM batch (detailed)
...

## Mode B: atomic edits (detailed)
...

## Glossary
...

## API key boundary (critical)
...

## Cost and rate limit awareness
...

## Cancellation
...

## Starfield-specific behavior
...

## What this tool does NOT do
...

## Anti-patterns (must not do)
...

## Cross-references
...
```

Estimated 200-300 lines of skill content. Authored per chunk M.

---

## 6. Skill testing

After skill is materialized:
- Agent given a translation task from scratch: it should follow the standard workflow without prompting
- Agent given a "just translate one weapon name" task: it should choose Mode B
- Agent given an API key in chat: it should refuse and explain the .env workflow
- Agent given an "estimate cost first" task: it should run `xtl batch plan` and surface estimates
- Agent given a partial-failure scenario: it should surface manual-review queue to user, not silently mark items translated

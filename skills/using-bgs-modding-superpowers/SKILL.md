---
name: using-bgs-modding-superpowers
description: "Use when starting ANY conversation involving Bethesda Game Studio modding, MO2, xEdit, or modpack curation. Bootstrap that loads the toolkit overview, lists available task skills, and enforces the hard rules of this plugin. Auto-injected by the OpenCode plugin's chat.messages.transform hook and by the hooks/ session-start chain in Claude Code and Codex."
---

<EXTREMELY_IMPORTANT_BGS_MODDING_SUPERPOWERS>
This is the bgs-modding-superpowers per-session bootstrap. If you are reading this,
the plugin injected it into the first user message of this session. Do NOT discard
it. Do NOT respond to the user yet without first checking whether one of the task
skills below applies.
</EXTREMELY_IMPORTANT_BGS_MODDING_SUPERPOWERS>

# Using BGS Modding Superpowers

You are operating with the `bgs-modding-superpowers` plugin loaded. This plugin
gives you an agent-driven toolkit for Bethesda Game Studio modpack curation:
MO2 control plane, xEdit MCP, conflict-audit workflow, and runtime asset skills
for dev-log and release-changelog maintenance.

## Available skills (auto-trigger on these intents)

| Skill | Auto-triggers when |
|---|---|
| `setting-up-bgs-modding-environment` | First conversation in a project; MO2 or xEdit not yet detected; user says "set up", "install", "bootstrap", "configure" |
| `xedit-automation` | Any task involving `.esp/.esm/.esl` plugin files, FormIDs, masters, conflicts, ESL flagging, ITM/UDR cleaning, Pascal scripts |
| `xedit-conflict-audit` | "Why is this override not winning?", "Which plugins overlap on this record?", "Is this load order safe?" |
| `writing-modpack-devlog` | "Log this", "record what I did", "note this change", "add to dev-log", "track this decision" |
| `writing-modpack-changelog` | "Cut a release", "release notes", "what changed since v1.2", "prepare release for Nexus" |

When the user's intent matches one of these, invoke the corresponding skill
through your skill tool BEFORE replying. Do not paraphrase the skill from memory;
let the skill load.

## Available MCP tools

The bundled `xedit` MCP server (declared in `.mcp.json` for Claude Code / Codex,
declared via the OpenCode plugin's `config.mcp.xedit` hook) exposes six intent
tools plus an atomic passthrough:

| Tool | Use |
|---|---|
| `xedit_session` | Call FIRST in every conversation that touches xEdit. Returns game mode, load order size, daemon PID, capability flags. |
| `xedit_list_capabilities` | Call once per session. Returns the curated 49-command digest plus any drift against the live daemon. |
| `xedit_find_record` | Locate a record by `{file, formId}` or `{editorId}`. |
| `xedit_read_record` | Read the actual record fields, base record, and winning override. |
| `xedit_inspect_conflicts` | The W2 verdict tool. Returns `no_conflict / itpo / itm / minor / breaking`. |
| `xedit_call(command, args)` | Atomic passthrough for any of the 49 native daemon commands. Still goes through validation, state-check, rules, audit. Use whenever the intent tools do not fit. |

The full daemon-command reference lives in
`skills/xedit-automation/xedit-knowledgebase.md`.

## Hard rules (non-negotiable)

1. **The user's `<MO2_Root>` and any `<MO2_Root>/<game>/Data/` (or equivalent
   "Stock Game" tree) is real game state.** Never write into it directly. Any
   game-local change is expressed as an MO2 mod overlay under
   `<MO2_Root>/mods/<mod-name>/`. The MO2 VFS projects it at runtime.
2. **All xEdit work goes through the bundled `xedit` MCP.** Never spawn
   `xEdit.exe` directly from the shell, never parse `.esp/.esm/.esl` files with
   your own Python/JS, never invoke `xedit-client.ps1` from raw shell. The MCP
   exists so the harness can enforce validation, state, rules, and audit on
   every call. Atomic passthrough (`xedit_call`) is the documented escape hatch
   when an intent tool does not fit — it is still in-harness.
3. **Mutating operations require explicit user consent and a daemon launched
   with `-IKnowWhatImDoing`.** Read the `xedit-automation` skill BEFORE any
   destructive work. The anti-pattern list there is binding.
4. **A `session.save` response is not durability.** A save with
   `savedFilesPendingShutdown > 0` is deferred. Durability proof =
   save + daemon restart (new PID) + readback. Always restart before declaring
   a mutating workflow complete.
5. **Large scope (many records, broad conflict survey) → delegate to a
   read-only investigator subagent FIRST.** The subagent burns its own context
   and returns a distilled summary. Do not loop hundreds of records through
   your own context.
6. **First-run state**: if MO2 / xEdit / the control-plane DLL are not yet
   set up on this machine, invoke `setting-up-bgs-modding-environment` BEFORE
   any modpack work. That skill orchestrates detection and install.

## How to use this bootstrap

- This skill loads automatically on every new session. You do not need to
  re-invoke it.
- When a user intent matches a task skill in the table above, invoke that skill
  via your skill tool. Do not paraphrase.
- When the user asks about "what can you do", reference the skills inventory
  here; do not invent capabilities the plugin does not have.
- When you would normally write code that touches BGS plugin files (`.esp/.esm/
  .esl`), STOP and route through `xedit-automation` instead.
- When the user asks to "log", "record", "track", or "note" modpack work,
  route to `writing-modpack-devlog`. When the user asks to "cut a release" or
  prepare release notes, route to `writing-modpack-changelog`.

## See also

- `setting-up-bgs-modding-environment` — first-run setup orchestrator.
- `xedit-automation` — hub skill for all xEdit work; routing doctrine,
  anti-patterns, sub-agent recipes.
- `xedit-automation/xedit-knowledgebase.md` — deep reference: 49 daemon
  commands, error codes, save semantics, glossary.
- `xedit-conflict-audit` — the W2 conflict-audit workflow.
- `writing-modpack-devlog`, `writing-modpack-changelog` — runtime asset
  skills for project documentation.

---

> Plugin: `bgs-modding-superpowers`. Repo: https://github.com/BB-84C/bgs-modding-superpowers.
> If any environmental component (MO2, xEdit, control-plane DLL) is missing,
> route through `setting-up-bgs-modding-environment` before continuing.

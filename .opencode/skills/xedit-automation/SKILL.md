---
name: xedit-automation
description: Use whenever the task involves inspecting, modifying, or building plugins for Bethesda games via the forked xEdit automation daemon. Loads first; routes to the right path (MCP intent tool, MCP atomic passthrough, or sub-agent delegation) and prevents the agent from bypassing the harness.
---

# xEdit Automation — Hub Skill

This skill is the always-loaded entry point for any xEdit work. It is the single source of truth for "which path do I use" and "what must I never do." Specialised task skills (e.g. `xedit-conflict-audit`) inherit its routing, anti-patterns, and verification discipline; they do not restate them.

## Toolbox at a glance (capability digest, Top-N)

The forked xEdit daemon exposes 49 commands across 7 groups (system, session, files, records, elements, jobs, scripts), all reachable through the MCP. The most common ones:

- **Discovery & session** — `xedit_session`, `xedit_list_capabilities`. Call `xedit_session` first every conversation. Then call `xedit_list_capabilities` once to see the toolbox and check for drift between the curated digest and the live daemon.
- **Reading records & conflicts** — `xedit_find_record`, `xedit_read_record`, `xedit_inspect_conflicts`. These are the W2 (conflict audit) backbone.
- **Atomic passthrough** — `xedit_call(command, args)`. For any native daemon command that does not have an intent tool yet. Still runs the full pipeline (validation → state → rules → audit). Use it whenever the intent tools do not fit.

For the deep reference (all 49 commands, error codes, save semantics, locator format, UESP CK wiki, glossary), see the companion file `xedit-knowledgebase.md` in this skill directory.

## Routing doctrine (which path to use)

| Task shape | Path |
|---|---|
| High-frequency known intent (audit a conflict, read a record, run a job, write a patch) | **MCP intent tool** |
| Novel / debugging / free composition of native commands | **MCP atomic passthrough**: `xedit_call(command, args)` — still in harness |
| Exploratory atomic-op storm (trial-and-error, repeated read-eval, hypothesis testing) | **Delegate to a read-only investigator sub-agent** with this skill loaded; the sub-agent burns its own context, returns a distilled summary |
| Large formalisable bulk mutation | **MCP `xedit_run_script`** (Batch 4+) with dry-run + snapshot |
| Daemon explicitly in default (non-MCP) mode, manual debug only | Direct `xedit-client.ps1` is acceptable — but ONLY when the user has explicitly accepted the risk and the daemon is not in `-automation-mcp-mode` |

**The agent should never have a reason to bypass the MCP.** Atomic passthrough exists for that.

## Anti-patterns (hard bans)

Never do any of the following. Each ban is encoded as an MCP rule or daemon-side refusal, but the skill states them so the agent does not even attempt:

1. **Do not write Python (or any other language) to parse `.esp/.esm/.esl` files directly.** The daemon is the only correct path. If you find yourself reaching for a binary plugin parser, stop and use `xedit_call` instead.
2. **Do not trust an `ok: true` response as durability.** A save with `pendingShutdown > 0` is deferred; durability requires a daemon restart and readback (see §10 of the design spec).
3. **Do not call mutating ops in mcp-mode without going through the MCP.** Direct pipe writes will be refused by the daemon with `mcp_mode_required`.
4. **Do not page `system.capabilities` every session.** The digest in `xedit_list_capabilities` already carries the curated map; only call live capabilities once to check drift.
5. **Do not delete or mark-deleted a record that is referenced by other plugins** without first calling `xedit_call records.referenced_by` and accepting the consequences. Snapshot does not cleanly recover deletions.

## Confidence + dry-run discipline (borrowed from skyrimvr-claude-toolkit)

Before any mutating action:

1. State your confidence (0-100%) and your top 3 assumptions.
2. If confidence < 90%, investigate first (read records, inspect conflicts, list references) until ≥ 90%.
3. For HIGH-RISK mutations, the MCP will return a preview envelope with `confirmToken`. Read the preview, decide, then commit with the token. Treat the preview as the contract.

## Sub-agent delegation recipes (role-agnostic)

When delegating, do not hard-code role names — the harness will map them. Use these recipes:

**Read-only investigator** — for exploratory storms, conflict surveys, and "what's in this plugin" reconnaissance:

> Dispatch a read-only investigator sub-agent with this skill loaded. Provide the question, the target files, and the budget (token / time / step count). The sub-agent should return a distilled summary (verdict + key evidence + open questions), not the raw daemon round-trips.

**Bounded mutation worker** — for well-defined batch edits (Batch 4+):

> Dispatch a bounded-execution sub-agent with this skill and the patch-authoring skill loaded. Provide the spec, the snapshot expectations, and the acceptance checks. The sub-agent should perform the mutations through the MCP and return the snapshot IDs + readback proof.

## Self-growing knowledgebase

After any session that produced a footgun (an unexpected refusal, a non-obvious recovery, a surprising daemon behavior):

1. Append a short note to `xedit-knowledgebase.md` under "Lessons" — file/record/element involved, what went wrong, what worked.
2. If the footgun is mechanically detectable, draft a rule at `tools/xedit-mcp/src/rules/candidates/<id>.ts` describing the check and the corrective hint. Candidates require human review before promotion.

## When this skill applies

- Any task involving Bethesda plugin files (`.esp/.esm/.esl`) for FO4, Skyrim, FO76, Starfield in this repo's MO2 harness.
- Any conflict / patching / cleaning / ESL / scripting task against xEdit.
- Whenever the task description names xEdit, plugin records, FormIDs, masters, conflicts, ITM/UDR, ESL flagging, or Pascal Edit Scripts.

When in doubt, load it.

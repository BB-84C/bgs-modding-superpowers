# xEdit Agent Skills + Harness MCP — Design

- **Date**: 2026-05-26
- **Status**: Draft — pending user review
- **Supersedes**: nothing (new); builds on `2026-05-13-xedit-native-adoption-design.md`
- **Scope**: This spec covers all 8 xEdit workflows end-to-end. Construction is batched in 4 stages (§12); the spec itself is whole-system.

---

## 1. Goal & Problem Statement

The fork at `D:\TES5Edit-contrib` already exposes a non-GUI-blocking JSON-over-named-pipe automation surface (47 commands across 8 groups, contract documented at `docs/notes/automation-contract/`). The fork is *capable*. The agents are not *competent*. Two failure modes have been observed and are explicitly the target of this design:

- **Problem A — wrong-path drift.** Weaker models, given a CLI/daemon, bypass it and write Python to hand-parse `.esp` files. The daemon is the right path but is not the obvious path.
- **Problem B — context decay.** Any model, when troubleshooting or exploring a solution, ends up in long back-and-forth atomic-op storms with the daemon. The orchestrator's context fills with raw JSON envelopes; token cost compounds; reasoning quality degrades.

This design fixes both by adding an **MCP server that functions as a safety harness**, a **skills layer that teaches the agent the toolbox and the doctrine**, and a **coordinated change in the xEdit fork** that makes the harness mandatory when production-grade safety is required.

The MCP is not a workflow-convenience wrapper. It is the chokepoint that turns the daemon from a powerful-but-dangerous surface into a powerful-and-defensive surface.

## 2. Substrate (what we are building on)

Confirmed by reconnaissance (preserved verbatim in conversation; key paths quoted here):

- **Daemon transport**: Windows named pipe `\\.\pipe\xedit-<PID>`, one request → one response per connection, JSON envelopes.
- **Request envelope**: `{ command, args:{...}, requestId?, id? }`. Args is an object (never an array).
- **Response envelopes**: `{ ok:true, command, requestId, result:{...} }` or `{ ok:false, command, requestId, error:{ code, message, details? } }`.
- **Error codes**: stable snake_case, source-of-truth in `xeAutomationErrors.pas` plus per-command tiers. **Clients branch on `error.code`, never on `error.message`.**
- **Contract version**: source emits `"0.10"`; contract docs pinned to `"0.9"`. Delta is additive only (`consent_required` code, `iKnowWhatImDoing` capability flag). Clients **must branch on field presence**, not on version string.
- **Launch modes (current)**: `-automation-serve` (long-lived daemon), `-automation-cli-request/response` (one-shot stateless), `-automation-call-pid` (thin relay).
- **Consent gate (current)**: `-IKnowWhatImDoing` at daemon launch enables mutating commands.
- **Existing harness layer**: `tools/mo2-vfs-launcher/xedit-client.ps1` is the mature PowerShell outer client; the MCP wraps this boundary rather than opening a parallel extraction path.
- **Note**: the `KYWD/MISC` whitelist on `records.create` has been removed in the fork. The MCP must read supported signatures from `system.capabilities` at runtime; no signature whitelist is hard-coded.
- **README drift**: `D:\TES5Edit-contrib\README.md` still documents `-AutomationPipe:<pipe-name>` which does not exist. Authoritative source is the `xeAutomation*.pas` units. The MCP follows source.

## 3. Architecture Overview

```
+-------------------------------------------------------------+
|  agent (any harness — OpenCode, Claude Code, future...)     |
+----------------------------+--------------------------------+
                             |
                             v
+-------------------------------------------------------------+
|  Skills layer (hub + KB + 8 task skills)                    |
|  - capability digest, routing doctrine, anti-patterns       |
|  - sub-agent delegation recipes (role-agnostic)             |
|  - dry-run / confidence discipline                          |
+----------------------------+--------------------------------+
                             |
                             v
+-------------------------------------------------------------+
|  xEdit MCP server (TypeScript, harness pipeline)            |
|  Tool surface:                                              |
|    Layer A — intent tools (~14, high-value workflows)       |
|    Layer B — atomic passthrough (xedit_call, ~47 commands)  |
|  Both layers share the same 7-stage pipeline (§4).          |
+----------------------------+--------------------------------+
                             |
                             v
+-------------------------------------------------------------+
|  tools/mo2-vfs-launcher/xedit-client.ps1 (existing outer)   |
|  Owns: launch, ensure-daemon, PID/state plumbing, automation|
|  call/serve plumbing. MCP does NOT re-implement this layer. |
+----------------------------+--------------------------------+
                             |
                             v
+-------------------------------------------------------------+
|  MO2-managed xEdit.exe -automation-serve [-mcp-mode]        |
|  Named pipe \\.\pipe\xedit-<PID>                            |
+-------------------------------------------------------------+
```

Two execution modes for the daemon, both supported (see §8 for the new flag):

- **Default mode**: any client that can reach the pipe may issue commands. This preserves the existing PowerShell client, manual debugging, and the contrib repo's standalone usefulness.
- **MCP-only mode** (new, opt-in via launch flag): daemon rejects any request lacking a valid `mcpToken`. This makes the MCP the single legitimate path during production modpack work, closing the bypass hole.

## 4. MCP as Harness — the 7-Stage Pipeline

Every MCP tool invocation traverses the same pipeline. Each stage may short-circuit with a structured refusal carrying an educational hint.

```
agent call
   v
[1] Schema/argument validator
       Type, required fields, enum/range checks against tool's declared schema.
       Fail -> { ok:false, code:"invalid_request", hint:"...", detail:{ field, expected, got } }
   v
[2] State precheck
       Is daemon up? Is target file in load order? Is -IKnowWhatImDoing active
       for mutating ops? Is mcp-mode active (if enforced)?
       Fail -> { ok:false, code:"state_violation", hint:"...", detail:{ ... } }
   v
[3] Rule registry scan
       Run all rules whose appliesTo matches the tool name.
       CRITICAL  -> hard refuse: { ok:false, code:"rule_<id>", hint, rationale, severity }
       HIGH      -> refuse if registry.blockHigh=true (default), else warn
       MEDIUM    -> add to envelope.warnings[]
   v
[4] Snapshot before mutate  (only for mutating tools)
       Read current state of affected records/elements/file headers.
       Persist to .opencode/artifacts/xedit-mcp/snapshots/<session>/<ts>/<file>/<formid>.json
       Returns snapshotId, included in final envelope.
   v
[5] Preview / consent gate  (only for HIGH-RISK mutating tools, see §7)
       First call: dryRun=true implicit; pipeline stops after this stage and returns
                   { ok:true, preview:{ from, to, affected:[...] }, confirmToken }
       Second call: caller passes confirmToken; pipeline proceeds.
       If preview path skipped (e.g. tool marked low-risk or explicit override),
       this stage is a no-op.
   v
[6] Forward to xedit-client.ps1 -> daemon
       Translate to the underlying native command. For atomic passthrough (xedit_call),
       this is direct; for intent tools, may involve N >= 1 native commands.
   v
[7] Envelope shape + audit
       Build standard envelope:
       {
         ok: boolean,
         tool: "<name>",
         summary: "<one-line human-readable>",
         data?: { ... shaped, paginated, projected ... },
         changed?: { files:[...], records:[...], counts:{ added, modified, deleted } },
         status?: "completed" | "pending_shutdown" | "partial" | ...,
         snapshotId?: "<id>",
         dirty?: { files:[...], unsavedChangeCount },
         warnings: [{ code, message, severity }],
         readback?: { ref:"<snapshotId>" or "<resource://...>" }
       }
       Append one line to .opencode/artifacts/xedit-mcp/audit/YYYY-MM-DD.jsonl:
       { ts, tool, args(hash or redacted), decision, ruleHits, snapshotId, ok, code }
       Raw daemon envelope NEVER leaks to the agent.
```

Each stage is individually toggleable for development, but **default is all-on**. The pipeline is the harness; stages are not optional in production.

## 5. Tool Surface

### Layer A — Intent tools (~14)

Ergonomic, well-typed, response-shaped tools for high-frequency or high-risk workflows. Each maps to one or more native commands and bundles the common case (e.g. polling, summarization, default flags).

| Tool | Purpose | Wraps |
|---|---|---|
| `xedit_session` | Ensure daemon, describe, dirty-state, save | `system.describe`, `session.get_dirty_state`, `session.save` |
| `xedit_list_capabilities` | Return curated digest + live cross-check | `system.capabilities` |
| `xedit_find_record` | Locator search, field-projected | `records.list`, `records.apply_filter`, `records.find_by_form_id`, `records.find_by_editor_id` |
| `xedit_read_record` | Record summary + winning override + conflict status + base | `records.get`, `records.winning_override`, `records.base_record`, `records.conflict_status` |
| `xedit_inspect_conflicts` | Conflict audit for a record or plugin | `records.conflict_status`, `records.winning_override`, `elements.conflict_status` |
| `xedit_references` | References / referenced_by, summarized | `records.references`, `records.referenced_by` |
| `xedit_read_element` | Element get + children, summarized | `elements.get`, `elements.children` |
| `xedit_set_element` | Element set_value with rule scan (ELEMENT001) and snapshot | `elements.set_value`, `elements.add_child`, `elements.remove_child`, `elements.copy_child_to` |
| `xedit_edit_record` | create/copy_into/delete/mark_deleted with full pipeline | `records.create`, `records.copy_into`, `records.delete`, `records.mark_deleted` |
| `xedit_create_plugin` | New plugin + add required masters | `files.create`, `files.add_required_masters` |
| `xedit_file_hygiene` | Header read/flag-set/sort/clean masters | `files.get_header`, `files.get_masters`, `files.set_header_flags`, `files.sort_masters`, `files.clean_masters` |
| `xedit_run_job` | Async job lifecycle wrapper (start→poll→findings) | All 10 `jobs.*` kinds: hygiene, validation, cleaning, esl, formid compact |
| `xedit_run_script` | Write `Agent/*.pas` + run with lint/timeout reporting | `scripts.write`, `scripts.run`, `scripts.read`, `scripts.list`, `scripts.delete` |
| `xedit_restore_snapshot` | Reapply a prior snapshot to undo field-level mutations | Composite over `elements.set_value` / `records.copy_into` |

### Layer B — Atomic passthrough

A single tool, `xedit_call(command, args)`, that accepts any of the 47 native commands by name and forwards them through the **same 7-stage pipeline**. This satisfies two needs:

- Agents have a legitimate path for novel/debugging/free-composition scenarios without bypassing the harness.
- The MCP surface stays small (one tool, not 47), preserving discoverability.

The tool's schema enumerates supported commands (read from `system.capabilities` at startup) and validates args per command. Rule registry scans `appliesTo` against the resolved `command`, so a passthrough call to `records.delete` still triggers `DEL001` exactly as `xedit_edit_record` would.

### Why both layers

Layer A is the obvious path for known intent. Layer B is the escape valve for everything else. Both run the harness. Skills (§9) teach the agent to prefer A when it fits and fall back to B otherwise — but never to "drop to direct CLI" because doing so loses the harness, and in mcp-mode the daemon will refuse anyway.

## 6. Rule Registry

### Shape

```ts
type Rule = {
  id: string;                    // e.g. "COPY001"
  appliesTo: string[];           // native command names or intent tool names
  riskLevel: "CRITICAL" | "HIGH" | "MEDIUM";
  check: (ctx: { args, state, capabilities }) => Finding | null;
  description: string;           // shown to agent in refusal
  suggestion: string;            // educational hint — the corrective path
  rationale?: string;            // human-facing why
};

type Finding = {
  ruleId: string;
  matched: Record<string, unknown>;   // what about the call tripped the rule
  message: string;
};
```

Rules live in `tools/xedit-mcp/src/rules/` as one TypeScript file per rule. Decoupled from pipeline code so rules can be added/edited/disabled without touching the harness core.

### Refusal envelope shape

```json
{
  "ok": false,
  "tool": "xedit_edit_record",
  "code": "rule_DEL001",
  "severity": "HIGH",
  "message": "Refusing: target record is referenced by 7 other plugins.",
  "hint": "Run xedit_references referenced_by first; review dependents; either pick a different target, or accept breakage and pass {acknowledgeBreakingRefs: true}.",
  "rationale": "Marking a referenced record as deleted leaves dangling references in dependents. xEdit will not auto-fix.",
  "matched": { "file": "MyPatch.esp", "formId": "0x00012345", "referencedByCount": 7 }
}
```

The dual surface (machine-readable `code` + agent-readable `hint`) borrows directly from instrMCP's `SecurityIssue.suggestion` pattern.

### Seed rules (v1 — 10 rules, intentionally small)

| ID | Trigger | Level | Hint |
|---|---|---|---|
| `MUTATE001` | Any mutating tool while daemon launched without `-IKnowWhatImDoing` | CRITICAL | "Relaunch daemon with consent flag; mutating ops blocked at daemon level otherwise." |
| `COPY001` | `copy_into` where target plugin lacks the source plugin as master | CRITICAL | "Call `xedit_file_hygiene` add-required-masters first, then retry copy." |
| `DEL001` | `delete`/`mark_deleted` on a record with at least one referencing plugin | HIGH | "Run `xedit_references referenced_by` first; review and either change target or pass `{acknowledgeBreakingRefs: true}`." |
| `CREATE001` | `records.create` signature not in current `system.capabilities` allowed set | CRITICAL | "Signature not currently supported by this fork build; check `xedit_list_capabilities`." |
| `ELEMENT001` | `set_element` without a prior read or without `expectedValue` (blind set) | MEDIUM | "Read first, then set; or pass `expectedValue` for optimistic concurrency." |
| `SAVE001` | Caller treats `session.save` response as durable while `pendingShutdown > 0` | HIGH | "Pending-shutdown saves are deferred. Restart daemon and readback before claiming durability." |
| `SCRIPT001` | `run_script` with `targets` exceeding threshold or `maxStatements` overrun anticipated | MEDIUM | "Split targets / page work; prefer a `xedit_run_job` kind if one applies." |
| `JOB001` | `run_job` invoked in apply mode without prior dryRun/analyze on same target | HIGH | "Run dryRun first, review findings, then apply." |
| `LOAD001` | Operation targets a file not present in the active load order | CRITICAL | "Target not loaded; add to plugins.txt and reload session first." |
| `STORE001` | `scripts.write` to a path outside `Agent/` namespace | CRITICAL | "Only `Agent/` is writable from the daemon. Relocate." |

### Growth model

Rules grow through dogfooding. Skills (see §9) instruct agents that after a session involving xEdit mutations, if a footgun was discovered or narrowly avoided, append a draft rule to `tools/xedit-mcp/src/rules/candidates/<id>.ts` for human review and promotion. This is the skyrimvr-claude-toolkit "self-growing knowledgebase" pattern adapted to executable rules.

### Honesty

Following instrMCP's example: **the rule registry is not a substitute for daemon-level enforcement**. It is a soft second layer over the daemon's own consent gate, signature whitelist (where applicable), and namespace restrictions. The registry catches the *common* mistakes; it does not pretend to be airtight.

## 7. Snapshot, Preview, Restore (Recovery Layer)

instrMCP explicitly lacks rollback; this is the gap we fill.

### Snapshot (pipeline stage [4])

Before any mutating tool runs, the MCP reads the current state of all records/elements/file-headers it is about to touch and serializes them to:

```
.opencode/artifacts/xedit-mcp/snapshots/
  <sessionId>/
    <isoTimestamp>-<tool>-<shortHash>/
      manifest.json          # tool, args, affected list, daemon-pid, contractVersion
      records/<file>/<formId>.json
      elements/<file>/<formId>/<path>.json   (for set_element)
      headers/<file>.json    (for file_hygiene mutations)
```

`snapshotId` = `<sessionId>/<isoTimestamp>-<tool>-<shortHash>`, returned in every mutating response envelope.

### Preview (pipeline stage [5])

For HIGH-RISK mutations (a registry attribute `previewRequired: true` per rule or per tool config), the first call is implicit-dry-run:

```jsonc
// Agent call:
{ "tool": "xedit_set_element", "args": { "file":"Patch.esp", "formId":"0x012345", "path":"FULL", "value":"New Name" } }

// MCP response:
{
  "ok": true,
  "preview": {
    "from": { "FULL": "Old Name" },
    "to":   { "FULL": "New Name" },
    "affected": [{ "file":"Patch.esp", "formId":"0x012345", "path":"FULL" }]
  },
  "confirmToken": "tok_a3f9...",
  "expiresAt": "2026-05-26T12:34:56Z"
}

// Agent commits:
{ "tool": "xedit_set_element", "args": { ..., "confirmToken": "tok_a3f9..." } }
```

Tokens are random, single-use, short-lived (default 5 min), bound to the args hash. Replay/tampering is rejected.

### Restore

`xedit_restore_snapshot(snapshotId)` reapplies the captured state via the appropriate native commands (`elements.set_value`, `records.copy_into`, etc.). Limits, stated up front:

- **Field-level edits, copy-overrides, and flag changes are restorable.** This covers the most common footguns.
- **`records.delete` and `mark_deleted` are NOT cleanly restorable.** Snapshot captures the pre-delete state, but the restore path may require manual `records.create` + `copy_into` and is not guaranteed transparent. `DEL001` is set to HIGH precisely because the recovery layer cannot fully cover it.
- **Cross-file ordering changes (sort_masters)** restore by reapplying the captured master list.

Snapshots are retained per session; cleanup policy is age-based (configurable, default 14 days).

## 8. xEdit-side Coordination Change (MCP-only mode)

To close the bypass hole, the fork ships a new daemon flag and a token mechanism. This change is **owned by the xEdit fork repo** (`D:\TES5Edit-contrib`); this spec documents the contract the MCP needs.

### Daemon flag

```
xEdit.exe -FO4 -automation-serve -IKnowWhatImDoing -automation-mcp-mode
```

When `-automation-mcp-mode` is set:

1. At startup, the daemon generates a 256-bit random token and writes it to a discoverable file. Proposed location (subject to fork-side review):
   ```
   %TEMP%\xedit-automation\<PID>.mcp-token
   ```
   File permissions: user-only (`O_RDONLY` for current user, denied otherwise on Windows ACL).
2. Every incoming request envelope must include a top-level `mcpToken` field whose value equals the daemon-generated token.
3. Missing or mismatched token → daemon rejects with new error code `mcp_mode_required`:
   ```json
   { "ok": false, "command": "<...>", "error": {
       "code": "mcp_mode_required",
       "message": "Daemon is in MCP-only mode; requests must include a valid mcpToken."
   }}
   ```
4. In default mode (no flag), behavior is unchanged. Existing PowerShell client, manual debugging, and the contrib repo's standalone use case all continue to work.

### MCP-side handling

- On `xedit_session` (ensure-daemon), MCP launches with `-automation-mcp-mode` and immediately reads the token file. Token is held in-process; not persisted, not logged, not surfaced to the agent.
- Every request the MCP sends to the daemon includes `mcpToken`.
- The agent never sees the token. The agent calls MCP tools; MCP injects the token transparently.

### Why this design

- **Capability-based, not network-based.** The token mechanism doesn't depend on process ancestry, port allocation, or OS-specific IPC ACL — it works through the existing pipe transport with a single envelope field.
- **Reversible.** The MCP-only mode is opt-in. Repos and tools that depend on direct CLI continue to work in default mode. This protects the `xedit-client.ps1` debug path and the standalone fork's general usefulness.
- **No new transport.** The contract addition is one envelope field and one error code. Minimal blast radius.

### Coordination

Implementing this change requires a small patch in the xEdit fork. That work is **out of scope** for this spec's implementation, but is a **prerequisite** for declaring the harness mandatory. The MCP implementation can ship before the fork change (in which case the token field is sent but currently ignored). Once the fork ships the flag, MCP can be configured to launch with `-automation-mcp-mode` and the bypass hole closes.

## 9. Skills Topology

Format: **global Superpowers YAML-frontmatter format** (`name`, `description: "Use when..."`), matching `~/.config/opencode/skills/`. The project's existing minimal-markdown skills are scaffolds and will be migrated separately; this design uses the richer format to support routing, anti-patterns, and confidence/dry-run discipline.

### File layout

```
.opencode/skills/
  xedit-automation/                              <- HUB (always-load candidate)
    SKILL.md
    xedit-knowledgebase.md                       <- Deep reference, 2-tier with hub
  xedit-conflict-audit/SKILL.md                  <- Batch 1
  xedit-validation/SKILL.md                      <- Batch 2
  xedit-file-hygiene/SKILL.md                    <- Batch 3
  xedit-cleaning/SKILL.md                        <- Batch 3
  xedit-esl-compact/SKILL.md                     <- Batch 3
  xedit-patch-authoring/SKILL.md                 <- Batch 4
  xedit-scripting/SKILL.md                       <- Batch 4
```

### Hub skill (`xedit-automation/SKILL.md`)

Contents, in order:

1. **Capability digest** — curated 47-command/8-group cheat sheet. ~1 screen. Agent has the toolbox at hand without calling `system.capabilities` every session.
2. **Routing doctrine** — when to use intent tool, when to use atomic passthrough, when to delegate to a sub-agent. Prose dispatch table (§10).
3. **Anti-pattern list (Top-N gotchas)** — distilled hard rules. "Don't write Python to parse ESPs." "Don't trust `ok` without snapshot/readback." "Don't bypass MCP." Etc.
4. **Confidence discipline** — borrowed from skyrimvr-claude-toolkit. Before any mutating call, state confidence 0-100% and assumptions; target ≥ 90%; investigate gaps first.
5. **Dry-run convention** — for mutating tools that gate on preview/confirm, present preview to user/self, review, then commit. The MCP enforces this for HIGH-RISK ops; the skill enforces it culturally for the rest.
6. **Sub-agent delegation recipes** — *role-agnostic*. Skill says "delegate to a read-only investigator sub-agent" or "delegate to a bounded-execution sub-agent." Each harness maps these to its local names (OpenCode `@explorer` / `@fixer`; Claude Code subagents; etc.). No hardcoded role names.
7. **Self-growing KB pointer** — at session end, if a footgun was discovered, append to `xedit-knowledgebase.md` and/or draft a new rule in `tools/xedit-mcp/src/rules/candidates/`.

### Knowledgebase (`xedit-knowledgebase.md`)

The deep reference. Two-tier per skyrimvr-claude-toolkit pattern: hub holds the Top-N distilled facts; KB holds the full reference.

Contents:

- Full 47-command digest with arg shapes and response shapes (synthesized from `docs/notes/automation-contract/`).
- Error code table.
- Save semantics: `pendingShutdown` ≠ saved; restart + readback to verify.
- File/record/element locator format (FormID conventions, master ordering).
- Mutation policy: consent gate, namespace restrictions, signature support.
- Job kinds reference: all 10, with dryRun semantics and findings shape.
- Pascal scripting reference: `Agent/` namespace, runtime policy, lint gate, statement budget, declared timeouts.
- **UESP Creation Kit wiki pointer**: https://ck.uesp.net/wiki — primary external reference for record schema, field meanings, engine quirks, and modding semantics. Agents should consult UESP for "what does this field mean" / "what does this signature represent" questions before guessing.
- Known drift: README switch names, contract version string, removed whitelists.
- Glossary: ITM, ESL, masters, override, winning override, conflict status.

### Task skills (8 workflows)

Each task skill follows the structure:

```yaml
---
name: xedit-<workflow>
description: Use when <concrete trigger phrasing>
---

## Purpose
## When To Use
## Tools (which MCP intent tools / passthrough commands; never raw CLI)
## Workflow (numbered, with embedded decision points)
## Verification (what to read back, what counts as semantic pass)
## Common Mistakes (with rule_id pointers where applicable)
## Delegation hints (when this workflow should be done by a sub-agent)
```

Workflows enumerated in §11.

## 10. Routing Doctrine

The hub skill ships this dispatch table:

| Task shape | Recommended path |
|---|---|
| High-frequency known intent (conflict audit, find/read record, run a job, author a patch) | **MCP intent tool** (Layer A) |
| Novel intent, debugging, free composition of native commands | **MCP atomic passthrough** `xedit_call(command, args)` (Layer B) — still in harness |
| Exploratory atomic-op storms (trial-and-error, hypothesis testing, many small read-eval cycles) | **Delegate to a read-only investigator sub-agent** with this skill loaded; the sub-agent burns its own context, returns a distilled summary |
| Large, formalizable bulk mutation | **MCP `xedit_run_script`** with dry-run + snapshot, or `xedit_run_job` if a kind applies |
| Daemon not in mcp-mode, manual debugging | Direct `xedit-client.ps1` is acceptable — but ONLY when explicitly out of mcp-mode and the user has accepted the risk; this is a debug path, not a production path |

**The key shift from v1**: there is no "direct CLI" path for novel scenarios. Atomic passthrough through the MCP covers that need while preserving the harness. The agent should never have a reason to bypass.

## 11. The 8 Workflows

### W1. Session & Capability Discovery (read-only, foundational)

- Purpose: Bootstrap a session, confirm game mode/data path, get capability digest, check dirty state.
- Tools: `xedit_session`, `xedit_list_capabilities`.
- Skill: folded into hub (no separate task skill).
- Verification: live response from daemon, contract version present, expected commands listed.

### W2. Conflict Audit (read-only) — **Batch 1 vertical slice**

- Purpose: For a record or plugin, determine override chain, winning override, conflict status, references.
- Tools: `xedit_find_record`, `xedit_read_record`, `xedit_inspect_conflicts`, `xedit_references`.
- Skill: `xedit-conflict-audit/SKILL.md`.
- Workflow: locate record(s) → read winning override → inspect conflict status → trace references → summarize.
- Verification: against live daemon with the project's MO2 harness, walk three representative records (one no-conflict, one minor, one breaking), confirm summary matches manual xEdit inspection.

### W3. Validation / Error Checking (read-only)

- Purpose: Check plugins for errors, ITM records, deleted references.
- Tools: `xedit_run_job` with kinds `validation.check_for_errors`, `validation.check_for_itm`, `validation.check_for_deleted_refs`. Default dryRun=true (which for validation is the only mode anyway).
- Skill: `xedit-validation/SKILL.md`.
- Verification: findings count matches xEdit GUI report for the same plugin set.

### W4. File Hygiene & Master Management (mutating)

- Purpose: Read headers, get masters, sort masters, clean masters, set ESM/ESL flags.
- Tools: `xedit_file_hygiene`, `xedit_run_job` with `files.hygiene.batch`.
- Skill: `xedit-file-hygiene/SKILL.md`.
- Pipeline: stages [4] snapshot + [5] preview enabled.
- Verification: post-save → restart daemon → readback confirms header changes; master list matches expected.

### W5. Plugin Cleaning (mutating)

- Purpose: Quick-clean and sort+clean-masters on official masters (LOOT/xEdit standard cleaning).
- Tools: `xedit_run_job` with kinds `cleaning.quick_clean`, `cleaning.quick_auto_clean`, `cleaning.sort_and_clean_masters`.
- Skill: `xedit-cleaning/SKILL.md`.
- Pipeline: stages [4] + [5] enabled; JOB001 enforces dryRun-first.
- Verification: findings match expected ITM/UDR removal; post-clean validation pass shows zero remaining issues.

### W6. ESL Flagging & FormID Compaction (mutating)

- Purpose: Analyze ESL eligibility, compact FormIDs, apply ESL flag — load-order slot economy for modpack assembly.
- Tools: `xedit_run_job` with kinds `plugin.esl.analyze`, `plugin.esl.apply`, `plugin.formids.compact_for_esl`.
- Skill: `xedit-esl-compact/SKILL.md`.
- Pipeline: stages [4] + [5]; JOB001 enforces analyze-first.
- Verification: post-apply readback confirms ESL flag set, FormID range within 0x800-0xFFF for compacted records, no broken references.

### W7. Patch Authoring & Record Editing (mutating, highest-risk)

- Purpose: Create a compatibility/merge patch: new plugin → add masters → copy overrides in → edit fields → save.
- Tools: `xedit_create_plugin`, `xedit_edit_record`, `xedit_set_element`.
- Skill: `xedit-patch-authoring/SKILL.md`.
- Pipeline: full stages [3][4][5] enabled; COPY001, DEL001, ELEMENT001 all active.
- Verification: save → restart daemon → load patch → readback confirms all intended records present, masters correct, no broken refs.

### W8. Custom Pascal Scripting (mutating, escape hatch)

- Purpose: When discrete commands cannot express the operation (bulk parametric transforms), write and run a headless Pascal Edit Script.
- Tools: `xedit_run_script`.
- Skill: `xedit-scripting/SKILL.md`.
- Pipeline: stages [1][2][3][4][7]; preview via dry-run mode within the script itself.
- Verification: script's own dirtyFiles report + post-save readback.

## 12. Construction Batches

The spec is whole-system; the build proceeds in 4 risk-graded batches.

### Batch 1 — Vertical slice (proves the pattern, becomes the template)

- MCP scaffold: TS project, pipeline stages [1][2][3][6][7], audit log, session lifecycle (launch + token + describe).
- Intent tools: `xedit_session`, `xedit_list_capabilities`, `xedit_find_record`, `xedit_read_record`, `xedit_inspect_conflicts`.
- Atomic passthrough: `xedit_call` shell with capability-driven command enumeration.
- Hub skill: `xedit-automation/SKILL.md` with capability digest, routing doctrine, anti-patterns, confidence/dry-run discipline, delegation recipes, KB pointer.
- KB skill: `xedit-knowledgebase.md` (draft, with UESP link).
- Task skill: `xedit-conflict-audit/SKILL.md`.
- Semantic verification harness: end-to-end run against live daemon in `.artifacts/mo2/`, exercising W2 with three representative records.

Acceptance: conflict audit workflow runs end-to-end through MCP; agent successfully completes a representative audit task with skill loaded; readback matches manual xEdit; all artifacts preserved under `.opencode/artifacts/xedit-mcp/...`; semantic review by @oracle passes.

### Batch 2 — Read-only completion

- Tools: `xedit_references`, `xedit_read_element`, `xedit_run_job` (read-only kinds: validation.*).
- Skill: `xedit-validation/SKILL.md`.
- Acceptance: all read-only paths covered; no harness gaps.

### Batch 3 — Mutating jobs

- Pipeline stages [4] snapshot and [5] preview now activated for these tools.
- Tools: `xedit_file_hygiene`, `xedit_run_job` (mutating kinds: hygiene/cleaning/esl/compact), `xedit_restore_snapshot`.
- Skills: `xedit-file-hygiene`, `xedit-cleaning`, `xedit-esl-compact`.
- Acceptance: save → restart → readback semantic verification passes for each mutating workflow; `restore_snapshot` demonstrably reverts a hygiene change.

### Batch 4 — Mutating records + scripting (highest risk)

- Tools: `xedit_edit_record`, `xedit_create_plugin`, `xedit_set_element`, `xedit_run_script`.
- Skills: `xedit-patch-authoring`, `xedit-scripting`.
- Acceptance: a small representative compatibility patch is authored end-to-end; save → restart → readback confirms patch integrity; `restore_snapshot` demonstrably reverts a field-level edit; `run_script` dry-run produces a faithful preview.
- Coordination prerequisite: by this batch, the xEdit fork should ship `-automation-mcp-mode` so the bypass hole is closed for production runs.

## 13. Semantic Verification & Acceptance

For every workflow, acceptance is **semantic, not surface**. Following project memory `10-semantic-proof-and-acceptance-design.md`:

- **Read-only workflows**: live daemon round-trip + manual or scripted readback comparison.
- **Mutating workflows**: `session.save` → **new daemon process restart** → readback of affected records/elements/headers → semantic match with intended state. `pendingShutdown` is treated as not-saved.
- **Restore**: snapshot taken, mutation applied, restore invoked, fresh readback confirms pre-mutation state.
- Per-batch acceptance artifacts preserved under `.opencode/artifacts/xedit-mcp/acceptance/<batch>/...` for audit and oracle review.
- Reviewer subagent (`@oracle`) judges semantic acceptance per batch before declaring complete. No batch closes on surface "ok" alone.

## 14. Risks & Open Items

- **Rule registry as operator-knowledge constitution**: starting with 10 seed rules is deliberate. Pad too early and we over-fit theoretical scenarios; grow through dogfooding. Risk: real footguns slip through Batch 1-2. Mitigation: aggressive rule-candidate capture during early runs.
- **Snapshot is not full undo**: delete/master-remove are not cleanly recoverable. `DEL001` blocks the worst case at HIGH; user education in the patch-authoring skill covers the rest.
- **Two-step preview/confirm UX**: adds a round-trip per HIGH-RISK mutation. Accepted cost — this is the only consistently-effective mechanism instrMCP and the toolkit's dry-run convention both validate.
- **MCP → PowerShell → daemon hop**: latency overhead. Batch 1 must measure end-to-end latency under load; provisional acceptance threshold is ≤ 50 ms per round-trip on a warm daemon. If exceeded, investigate whether the TS MCP should speak the named pipe directly and retire the PowerShell hop for hot paths.
- **Audit log volume**: one JSONL line per mutating call. Per-day rotation by default. Cleanup policy deferred to Batch 4.
- **xEdit-fork coordination**: `-automation-mcp-mode` is not implemented yet. MCP can ship without it (sends token, daemon ignores), but the bypass-closure benefit waits on the fork patch. Coordination timing is the main schedule risk.
- **Skills format migration**: the project's existing 7 minimal skills are not in YAML-frontmatter format. This spec uses the richer format for new xEdit skills; the existing skills are not touched. A separate cross-cutting migration is out of scope.

## 15. Non-goals / YAGNI

- **No new sub-agent type definitions.** Existing roles in any harness suffice; skills are role-agnostic.
- **No async `scripts.runAsync` work.** Reserved for fork 1.x; not in scope.
- **No live tail of audit log to the agent.** Audit is for human review and forensics.
- **No GUI-side integration.** The MCP serves the daemon only.
- **No multi-daemon orchestration in Batch 1-4.** One daemon per session.
- **No automatic rule-candidate promotion.** Candidates always require human review.
- **No persistent always-allow grants.** Each mutating call evaluates fresh; instrMCP's `persist_permissions` is intentionally not adopted.

## 16. Appendix

### Standard response envelope schema

```ts
type Envelope<T = unknown> = {
  ok: boolean;
  tool: string;
  summary: string;
  data?: T;
  changed?: { files: string[]; records: string[]; counts: { added: number; modified: number; deleted: number } };
  status?: "completed" | "pending_shutdown" | "partial" | "preview" | "refused";
  snapshotId?: string;
  dirty?: { files: string[]; unsavedChangeCount: number };
  warnings: Array<{ code: string; message: string; severity: "MEDIUM" | "HIGH" }>;
  readback?: { kind: "snapshot" | "resource"; ref: string };
  // refusal-only:
  code?: string;             // e.g. "rule_DEL001", "invalid_request", "state_violation"
  severity?: "MEDIUM" | "HIGH" | "CRITICAL";
  hint?: string;
  rationale?: string;
  matched?: Record<string, unknown>;
  // preview-only:
  preview?: { from: unknown; to: unknown; affected: unknown[] };
  confirmToken?: string;
  expiresAt?: string;
};
```

### Error code namespace (MCP layer)

- `invalid_request` — pipeline [1] failure
- `state_violation` — pipeline [2] failure
- `rule_<id>` — pipeline [3] failure (e.g. `rule_DEL001`)
- `snapshot_failed` — pipeline [4] failure
- `confirm_required`, `confirm_token_invalid`, `confirm_token_expired` — pipeline [5]
- `daemon_error` — pipeline [6] daemon-side error; wraps original `error.code` in `detail`
- `mcp_mode_required` — daemon refused due to missing/wrong token (when fork patch lands)

### Artifact layout

```
.opencode/artifacts/xedit-mcp/
  snapshots/<session>/<ts>-<tool>-<hash>/...
  audit/YYYY-MM-DD.jsonl
  acceptance/<batch>/...
  rule-candidates/                       (drafts before promotion to src/rules/)
```

### Repository placement

- MCP server: `tools/xedit-mcp/` (independent package; not inside `mo2-vfs-launcher`).
- Skills: `.opencode/skills/xedit-automation/`, `.opencode/skills/xedit-<workflow>/`.
- Spec: `docs/superpowers/specs/2026-05-26-xedit-skills-and-harness-mcp-design.md` (this file).
- Plan: to be created by `writing-plans` skill at `docs/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp.md`.
- Fork-side coordination: tracked separately in `D:\TES5Edit-contrib`; this spec documents the contract only.

---

End of design.

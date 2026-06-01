# xEdit Automation — Knowledgebase

This is the deep reference. Consult it when the hub skill's Top-N is not enough. When you discover a new gotcha, append to "Lessons" at the bottom.

## External references (consult first)

- **UESP Creation Kit Wiki** — https://ck.uesp.net/wiki — primary source for record schema, field meanings, signature reference (KYWD, WEAP, ARMA, NPC_, MISC, etc.), and engine semantics. When you ask "what does this field actually mean," go here before guessing.
- Forked xEdit automation contract: https://github.com/BB-84C/TES5Edit/tree/main/docs/notes/automation-contract — wire protocol, examples, COMPATIBILITY notes.

## Daemon protocol essentials

- Transport: Windows named pipe `\\.\pipe\xedit-<PID>`. One connection = one request → one response.
- Request envelope: `{ command, args: {...}, requestId?, id?, mcpToken? }`. `args` is always an object.
- Success envelope: `{ ok: true, command, requestId, result: {...} }`.
- Failure envelope: `{ ok: false, command, requestId, error: { code, message, details? } }`. **Branch on `error.code` only**, never on prose message.
- Contract version drift: source emits `"0.10"`, docs say `"0.9"`. Branch on field presence, not version string. The MCP digest expects `"0.10"`.

## All 49 commands (grouped)

### system.* — always available, no load required
- `system.ping` `{}` → liveness.
- `system.describe` `{}` → app/game-mode/data-path/sub-mode.
- `system.capabilities` `{}` → full live command list and `supports.*` tree. Compare against the digest via `xedit_list_capabilities` once per session.

### session.*
- `session.get_dirty_state` → which files have unsaved changes (`dirty: bool`, `dirtyFiles: []`, `unsavedChangeCount: int`).
- `session.get_gui_snapshot` → coarse modal-blocker probe; `hasBlockers: bool`.
- `session.save` `{ files: [...] }` → **mutating**, gated by `-IKnowWhatImDoing`. Response carries `savedFilesNow`, `savedFilesPendingShutdown`. Pending-shutdown saves are NOT durable until daemon restart and readback.
- `session.navigate_to_record` `{ file, formId, path? }` → drive the GUI JumpTo seam.

### files.*
- `files.list`, `files.get { name }` — read.
- `files.create { fileName, extension: ".esp"|".esm"|".esl", flags?: ["esm","esl"], template?: "empty", initialMasters? }` — mutating.
- `files.add_required_masters { targetFile, source: {...} }` — mutating. Note nested `source` shape.
- `files.get_header`, `files.get_masters` — read.
- `files.set_header_flags`, `files.sort_masters`, `files.clean_masters` — mutating. ESM/ESL/medium flag support. Persistence still needs explicit `session.save`.

### records.* (15)
Read/search: `records.list`, `records.apply_filter`, `records.base_record`, `records.find_by_form_id`, `records.find_by_editor_id`, `records.get`, `records.master_or_self`, `records.winning_override`, `records.conflict_status`, `records.references`, `records.referenced_by`.
Mutating: `records.create { targetFile, signature, editorId? }` (signature support is dynamic — read `system.capabilities`), `records.copy_into { source, target, mode }` (nested source/target), `records.delete`, `records.mark_deleted`.

Locator shape (used throughout): `{ file: "Fallout4.esm", formId: "0x0000003C", path: "" }`. Root locators use `path: ""`; nested element addressing extends with strings like `"[0]"`. FormIDs are load-order-resolved.

### elements.* (8)
Read: `elements.get`, `elements.children`, `elements.conflict_status`, `elements.required_masters`.
Mutating: `elements.set_value`, `elements.add_child`, `elements.remove_child`, `elements.copy_child_to`.

### jobs.* — async work (10 kinds, single-active-job bounded)
Lifecycle: `jobs.start`, `jobs.get`, `jobs.findings`, `jobs.cancel`, `jobs.discard`.
States: `queued | running | succeeded | failed | cancel_requested | canceled`.
Apply mode requires explicit `dryRun: false`; omitted `dryRun` defaults to `true` (non-mutating).

**Frozen kinds list** (order is stable):
1. `files.hygiene.batch`
2. `plugin.esl.analyze`
3. `plugin.esl.apply`
4. `plugin.formids.compact_for_esl`
5. `validation.check_for_errors`
6. `validation.check_for_itm`
7. `validation.check_for_deleted_refs`
8. `cleaning.quick_clean`
9. `cleaning.quick_auto_clean`
10. `cleaning.sort_and_clean_masters`

### scripts.* (5)
- `scripts.list { prefix?, limit? }`, `scripts.read { id }`, `scripts.write { id, source, overwrite? }`, `scripts.delete { id }`. Writable namespace is **only `Agent/`**.
- `scripts.run { id, targets?, timeoutMs?, maxStatements? }` — synchronous on GUI thread, single-process-single-runner, shared with GUI Apply Script via a runner token. Default timeout 30 s, default budget 1,000,000 statements.

## Save & durability semantics

- A `session.save` response with `savedFilesPendingShutdown` is **not** durable. The save is deferred until daemon shutdown.
- Durability proof = (a) save → (b) daemon restart (new PID) → (c) readback of the affected records/headers/masters confirms the intended state.
- Always restart before declaring a mutating workflow complete.

## Error code reference (stable snake_case)

- Transport / validation: `invalid_request`, `unknown_command`, `internal_error`, `unknown_job_kind`, `consent_required`, `file_not_found`, `record_not_found`, `invalid_target`, `save_failed`.
- Script lifecycle (frozen 7): `script_blocker_lint`, `script_busy`, `script_external_declaration_not_allowed`, `script_compile_error`, `script_timeout`, `script_statement_budget_exceeded`, `script_runtime_error`.
- MCP-layer additions: `mcp_mode_required`, `state_violation`, `daemon_error`, `internal_error`, `confirm_required`, `confirm_token_invalid`, `confirm_token_expired`, `snapshot_failed`, `rule_<ID>`.

## Mutation policy

- All mutating commands require the daemon to be launched with `-IKnowWhatImDoing`.
- `records.create` signature support is dynamic; the legacy `KYWD/MISC` whitelist has been removed in the fork. Always check `system.capabilities` for current allowed signatures.
- Pascal scripts run in a constrained runtime: `runtimeFsRead: true`, `runtimeFsWrite: false`, no UI / shell / clipboard / process-spawn. External declarations are denied.

## Known drift (do not be surprised by these)

- The forked xEdit README at https://github.com/BB-84C/TES5Edit may still reference `-AutomationPipe:<pipe-name>`. **That switch does not exist.** The real switches are `-automation-serve`, `-automation-cli-request/response`, `-automation-call-pid`, plus the new `-automation-mcp-mode` (when the fork patch lands).
- Contract version: source `"0.10"`, docs `"0.9"`. Treat as equivalent except for the `consent_required` code and `iKnowWhatImDoing` capability flag, which only exist in 0.10.
- Some daemon responses include emoji or formatted strings; the MCP envelope strips/normalises these. Trust `data` / `summary`; ignore prose flourishes.

## Glossary

- **ITM** — Identical To Master: an override record whose every field matches its master. Safe to remove (cleaning).
- **UDR / "deleted refs"** — Undeleted Reference: a reference flagged as deleted instead of disabled. Cleaning replaces with disable.
- **Master** — A plugin (`.esm` or any plugin tagged with the ESM flag) that other plugins depend on.
- **Override** — A record in plugin B that "shadows" the same FormID from plugin A (its master).
- **Winning override** — The last override in load order; whichever plugin xEdit considers "winning" for that record.
- **Conflict status** — xEdit's coloured-record label: no_conflict, ITM/ITPO, minor, critical, etc.
- **ESL** — Light plugin: limited to 0x800–0xFFF FormID range; shares its 254-slot space with other ESLs.

## Lessons (append as encountered)

> This section is the dogfood log. After any session that surfaced an unexpected behavior, append a short entry: date, summary, what worked, link to the rule candidate if one was drafted.

- (no entries yet)

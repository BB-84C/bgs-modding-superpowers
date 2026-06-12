# Batch 1 Status — xEdit Skills + Harness MCP (Vertical Slice)

- **Plan**: `docs/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.md`
- **Spec**: `docs/superpowers/specs/2026-05-26-xedit-skills-and-harness-mcp-design.md`
- **Branch**: `feat/xedit-skills-mcp`
- **Status**: **SHIPPED** (accept_with_followups per oracle re-review)
- **Date completed**: 2026-05-31
- **Oracle reviews**:
  - v1 (reject, then resolved): `.opencode/artifacts/xedit-mcp/acceptance/batch1/oracle-review.md`
  - v2 (accept_with_followups): `.opencode/artifacts/xedit-mcp/acceptance/batch1/oracle-review-v2.md`

## What Batch 1 actually delivered

- **TypeScript MCP package** at `tools/xedit-mcp/` with the 7-stage harness pipeline (stages [1][2][3][6][7] live; [4] snapshot and [5] preview deferred to Batch 3 per spec §12).
- **Six MCP intent tools**: `xedit_session`, `xedit_list_capabilities`, `xedit_find_record`, `xedit_read_record`, `xedit_inspect_conflicts`, `xedit_call` (atomic passthrough that closes the bypass hole).
- **`xedit_call` atomic passthrough** so agents never have to drop to direct CLI; capability-validated against the curated digest plus live `system.capabilities`.
- **Seed rule `LOAD001`** (CRITICAL): refuses operations against a file not in the active load order, with `appliesTo` covering the read-side tools and the atomic-passthrough escape valve.
- **Rule registry mechanism** decoupled from the pipeline (`tools/xedit-mcp/src/rules/`), one file per rule; ready to accept the remaining nine seed rules from spec §6 as later batches land their target tools.
- **Append-only JSONL audit logger** with a documented best-effort / never-throws contract (`audit.ts`).
- **Curated 49-command capabilities digest** matched against the live xEdit fork source; `keyArgs` independently verified against `D:\TES5Edit-contrib\xEdit\xeAutomationCommands*.pas` during Batch 1.
- **Skills layer** under `.opencode/skills/`:
  - `xedit-automation/SKILL.md` — hub: capability digest + routing doctrine (CLI vs MCP vs sub-agent) + anti-pattern bans + confidence/dry-run discipline + role-agnostic delegation recipes.
  - `xedit-automation/xedit-knowledgebase.md` — deep reference covering all 49 commands, error-code namespace, save semantics, locator format, UESP CK wiki pointer, glossary, lessons log.
  - `xedit-conflict-audit/SKILL.md` — W2 task skill template.
- **Live W2 semantic acceptance against the MO2-backed xEdit daemon**: 3/3 integration tests pass; preserved artifacts under `.opencode/artifacts/xedit-mcp/acceptance/batch1/` include `01-session.json`, `02-capabilities.json`, `03-audit-results.json`, the per-day audit JSONL, defect note (RESOLVED), and both oracle reviews.

## What was learned (now-known facts that we did not know at plan time)

- The xEdit automation daemon writes response files as **UTF-8 with BOM** on Windows; `JSON.parse` chokes on the leading `0xFEFF` unless stripped. The adapter now strips it.
- `system.describe` returns the friendly game label in `gameName` (`"Fallout4"`), not in `gameMode` (which is the internal token `"gmFO4"`). The session tool now prefers `gameName`.
- `files.list` returns an array of objects (`{ name, loadOrder, fileName, isESM, isLight, ... }`), not an array of strings. `session.ts` accepts both shapes and extracts the canonical name.
- The daemon rejects FormIDs with a `0x` prefix; it wants bare hex. MCP schemas accept both styles and the tools strip the prefix before forwarding to the daemon.
- `records.conflict_status` returns the conflict label under `result.conflict.all` using the xEdit `caXxx` enum (e.g. `caConflict`, `caITM`, `caITPO`, `caConflictCritical`, `caOnlyOne`), **not** under a top-level `result.status`. The verdict mapper now handles both the canonical enum and the legacy flat strings used by unit-test mocks.
- The verified subcommand shape of `tools/mo2-vfs-launcher/xedit-client.ps1`: `process launch/status/wait/stop` plus `automation call`. The `automation call` flags are `--xedit-pid <pid> --request-file <reqPath> --response-file <resPath> --timeout-seconds <n>` (Task 5 discovery). The `process launch` flags are `--launcher-path / --game-mode / --mo-profile` (Task 23 discovery). These are now codified in `AGENTS.md`.
- The canonical MO2 launch shape for live semantic testing is: pre-launch MO2 with `Start-Process` (no tool arg) so the Mo2AgentControl plugin loads and writes the bootstrap files; then `xedit-client.ps1 process launch` calls the broker's `launch.start` which runs xEdit-as-tool via `OpenCodeVfsLauncher`. The direct `ModOrganizer.exe -p <profile> run -e <tool>` invocation against an already-running MO2 does **not** dispatch the tool; the broker is the real launch path.
- `runRules` currently returns `EnvelopeRefusal | null` and silently drops MEDIUM-severity findings. This is acceptable for Batch 1 because LOAD001 is CRITICAL and is the only seed rule, but it is a structural gap once any MEDIUM rule lands.
- The state-precheck `targetFileFromArg: "file"` option exists in `state-precheck.ts` but is unused after Batch 1 — load-order checks are owned by LOAD001 in the rule layer, not by the precheck. Either keep `targetFileFromArg` for future tools that prefer pre-check ordering, or remove it.

## Implications for later batches

- **Batch 2 (read-only completion)** can rely on the `formId` normalization pattern and the `files.list` object-shape handling already in place; it should keep using those rather than re-deriving them per tool.
- **Batch 2** should also fold in the oracle v2 follow-ups (see below): finish audit uniformity, complete the W2 representative matrix, and add manual-parity evidence.
- **Batch 3 (mutating jobs with snapshot + preview)** lands pipeline stages [4] and [5]. The composer (`runTool`) is already structured to accept them — the top-level try/catch from commit `5f5cec7` guarantees the audit + envelope shape stays uniform even on unexpected throws, so stage [4]/[5] code only needs to slot in between stages [3] and [6].
- **Batch 3/4** is where save → fresh-daemon-restart → readback durability semantics become mandatory. Anchor that work on §13 of the design spec and rule `SAVE001` from §6.
- **xEdit fork coordination** (`-automation-mcp-mode` + per-request `mcpToken` enforcement) remains an explicit prerequisite for declaring the harness mandatory; documented in §8 of the spec and not blocking for Batch 1's read-only scope.

## Carry-forwards into Batch 2

| # | Source | Item | Action | Status |
|---|---|---|---|---|
| 1 | Oracle v2 follow-up 1 | W2 representative matrix is incomplete — current fixtures map to `minor/no_conflict/no_conflict`; spec calls for a `breaking` case too. | Add a fourth fixture or replace one of the existing ones with a known-breaking record; assert verdict against an `expectedVerdict` enum rather than `"any"`. | OPEN |
| 2 | Oracle v2 follow-up 2 + Task 13 review note | `xedit_session` and `xedit_list_capabilities` do not write audit lines despite stage [7]'s "one line per MCP tool call" contract. Inspect-audit entries lack `daemonPid` and `sessionId` (unlike read-record's). | Add `auditLine` calls to session and list-capabilities tools; align inspect's audit payload with read-record's by including `daemonPid` and `sessionId`. | **CLOSED 2026-06-01** — `src/audit-line.ts` shared helper; session + list_capabilities + inspect_conflicts all emit uniform audit lines via `emitAudit` including `daemonPid` + `sessionId`. Tests in `tests/unit/tool-session.test.ts`, `tool-list-capabilities.test.ts`, `tool-inspect-conflicts.test.ts`. |
| 3 | Oracle v2 follow-up 3 | Manual-parity evidence is not preserved — Batch 1 only has live-daemon envelopes, not a side-by-side with manual xEdit GUI. Spec §13 says readback should match manual xEdit. | For one representative fixture in Batch 2, capture a manual xEdit GUI screenshot or text export of the same record's conflict view and store it alongside the MCP envelope under `.opencode/artifacts/xedit-mcp/acceptance/<batch>/manual-parity/`. | **CLOSED 2026-06-11** — MCP envelopes + human screenshot saved under `.opencode/artifacts/xedit-mcp/acceptance/batch2/manual-parity/fo4-WRLD-0000003C/` (inspect.json, read.json, README.md, xedit-gui.png). @observer verified all 4 criteria PASS: 6-column plugin order, FULL row values, ICON row missing in DLCRobot/DLCCoast, no breaking-red cells. Critical anti-hallucination finding: GUI and MCP envelope **agree on identical mojibake** (`è"é‚¦`) for ArmorKeywords.esm's FULL override — proves the MCP faithfully transmits what xEdit reads, no fabrication. The mojibake itself is tracked separately (see Encoding Note below). |
| 4 | Task 9 review note | `runRules` silently discards MEDIUM-severity findings (returns `null`, drops the finding). | Before the first MEDIUM seed rule lands, change `runRules` to surface non-blocking findings as warnings on the success envelope rather than discarding them. | **CLOSED 2026-06-01** — `runRules` now returns `{ refusal, warnings, ruleHits }`. CRITICAL always blocks; HIGH blocks when `blockHigh=true` (default); MEDIUM always warns. Callers attach warnings to `EnvelopeOk.warnings`. Tests in `tests/unit/rules.test.ts` (6 cases) + `compose.test.ts` (MEDIUM-on-ok-envelope case). |
| 5 | Task 15 implementation finding | `precheck.targetFileFromArg` is unused after Batch 1 because LOAD001 owns load-order checks at the rule layer. | Decide intentionally: either remove `targetFileFromArg` from the `PrecheckNeeds` interface to reduce surface, or keep it and document in the spec when a tool should prefer hard-precheck over rule-layer enforcement. | **CLOSED 2026-06-01** — RETIRED. The Batch 1 STATUS claim "unused after Batch 1" was incorrect — `find-record.ts:62` was still using it. Migrated find-record to LOAD001-only load-order enforcement, then removed the field from `PrecheckNeeds`. Rationale documented in `src/pipeline/state-precheck.ts`. |
| 6 | Task 23 implementation finding | The `mapVerdict` mapping inside `inspect-conflicts.ts` is hard-coded to the xEdit `caXxx` enum. If the fork ever changes labels, every tool that consumes verdicts needs to be re-verified. | When more record-side tools land, lift the mapping into a shared `src/verdict.ts` module so all tools share one source of truth. | **CLOSED 2026-06-01** — Lifted to `src/verdict.ts` with `Verdict` type + `mapVerdict` function. `inspect-conflicts.ts` re-exports the type for back-compat with existing imports. Tests in `tests/unit/verdict.test.ts`. |
| 7 | Task 5 implementation note | The daemon adapter's PowerShell hop adds ~1-2 s per call (3 round-trips per inspect = ~6 s observed in `audits the three fixture records end-to-end`). Adequate for Batch 1; will not be adequate for snapshot/preview-heavy mutating flows. | Batch 3 must measure end-to-end latency under load and decide whether the TS MCP should speak the named pipe directly for hot paths. | **CLOSED-WITH-FINDING 2026-06-11** — measured 3.5-3.7 s floor (`system.ping` cold-cache), 2.4-3.8 s typical across `records.*` commands on FO4 Default profile with 13 plugins. Root cause: `xedit-client.ps1` `Invoke-XeditClientAutomationCall` spawns a fresh `xEdit.exe` child (45 MB binary cold-load) per call. Decision: **Batch 3 must implement a direct Node named-pipe client to the daemon endpoint** (`Mo2AgentControl/bootstrap/runtime/endpoint.json`) and use it for mutating hot paths; PowerShell adapter stays as fallback for non-mcp-mode safety on read-only tools. Detailed readback + recommendation at `.opencode/artifacts/xedit-mcp/acceptance/batch2/cf7-latency/SUMMARY.md` + `cf7-readback.json`. |
| 8 | Oracle v2 documentation cleanup | The resolved defect note's verification line still listed the removed `0x000003E9` fixture (stale prose). | RESOLVED in this Batch 1 closeout — defect note now references the live fixture set and the `ac81e50` commit. | CLOSED 2026-05-31 |

## What Batch 1 explicitly does NOT prove

- **Mutating workflows** (records.create / copy_into / delete / mark_deleted / elements.set_value / scripts.run / session.save). These are Batches 3 and 4. The pipeline is wired to accept their stages [4]/[5], but no mutating tool exists yet.
- **Snapshot / preview / restore**. Spec §7 reserves these for Batch 3.
- **`-automation-mcp-mode` bypass closure**. Requires a coordinated patch in the xEdit fork (spec §8). The MCP already passes `mcpToken` in every request; the daemon currently ignores it.
- **Async job lifecycle wrapping** (`xedit_run_job` for the 10 job kinds). Plan §5/§11 reserves this for Batches 3-4.
- **Pascal script execution** (`xedit_run_script`). Batch 4.
- **Manual GUI parity** for any record. See carry-forward #3 above.

## Acceptance evidence (preserved)

All under `.opencode/artifacts/xedit-mcp/acceptance/batch1/`:

- `01-session.json` — live `xedit_session` envelope: ok, gameMode Fallout4, contractVersion 0.10, loadOrderSize 13, consent off, dirty false.
- `02-capabilities.json` — live `xedit_list_capabilities` envelope: digest 49 / live 49 / drift 0.
- `03-audit-results.json` — three-fixture audit results showing real `conflict.all` values (`caConflict`, `caOnlyOne`, `caOnlyOne`), real `participants` chains, real `winningOverride`, real `referenced_by` (truncated to 100 for the Commonwealth WRLD), and full `read_record` composites including the conflicting child elements.
- `audit/2026-05-31.jsonl` — per-call audit log: 16 lines covering inspect + read calls across the green run (plus prior runs from the same day).
- `defects/plugin-loading-empty-load-order.md` — defect note (RESOLVED), with root-cause analysis archived.
- `oracle-review.md` (v1 reject) and `oracle-review-v2.md` (v2 accept_with_followups).

## Commit summary

The Batch 1 work is on `feat/xedit-skills-mcp`. Highlights:

- Spec + plan landed first: `82d6769` (spec), `6dbdd51` (plan).
- 25 plan-task commits implementing the package scaffold, types, audit logger, envelope shaper, daemon adapter, session lifecycle, the 5-stage pipeline, the 6 intent tools, the atomic passthrough, the server entry wiring, the 49-command digest, and the three skills (hub, KB, conflict-audit).
- Review-driven fixes interleaved with task commits, including (selected): `ae66eb0` (tsconfig hardening), `67becec` (audit logger never-throws), `634aad7` (daemon-adapter UUID filenames + stdout capture + temp-file cleanup), `5f5cec7` (runTool guarantees envelope + audit on unexpected throws), `7830100` (digest keyArgs verified against fork source), `a66dd6f` (UTF-8 BOM + gameName fallback), `aa766a2` (`files.list` object-shape handling), `da58318` (FormID normalization), `ac81e50` (inspect-conflicts verdict mapping + audit + tightened W2 assertions).

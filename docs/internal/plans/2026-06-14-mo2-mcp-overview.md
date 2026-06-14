# MO2 MCP — Overview Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement individual stage plans task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build a unified TypeScript MCP server that exposes 32 tools for safe, agent-driven Mod Organizer 2 control: read mod/plugin/profile state, mutate with plan→apply→lease safety, install mods (including FOMOD non-interactive), manage profile lifecycle, configure executables, and audit everything.

**Architecture:** Stateless TS MCP server (`tools/mo2-mcp/`) + long-lived Python sidecar (`tools/mo2-mcp-sidecar/`) wrapping `mo2_assets_engine` + `pyfomod`. Live-mode mutations proxy through extended `mo2_agent_control.py` named-pipe broker (new mobase mutator command set). Server-side rule engine (port from `xedit-mcp/src/pipeline/rules.ts`), JSONL audit, snapshot-before-write, lease-protected plan/apply. Per-instance permission ceiling via `<MO2_Root>/.mo2-mcp.json`.

**Tech Stack:** TypeScript (Node 22+, MCP SDK), Python 3.11+ (sidecar, pyfomod), C++/Qt6 (existing MO2 control-plane plugin, extended), Windows named pipes, JSON-RPC over stdio.

---

## Locked decisions (from brainstorming Phase 4)

| ID | Decision |
|---|---|
| Q1 | Default `permission_ceiling = "metadata-editable"` |
| Q2 | v1 install scope = `full` (includes FOMOD non-interactive Pattern A: `pyfomod` external parse → `IOrganizer.createMod` → populate folder → write `meta.ini`) |
| Q3 | `mo2_agent_control.py` extended with mobase mutator command set in lockstep with MCP |
| Q4 | `mo2_run_tool` ships in v1 |
| Scope | v1 ships all 32 tools (no v1.1 deferral) |
| Approach | A (5-stage substrate-first) |

## 32 v1 tools

### T1 reads (11) — always allowed under per-instance ceiling, audit only

| # | Tool | Source |
|---|---|---|
| 1 | `mo2_status` | New |
| 2 | `mo2_machine_contract` | Charrdge pattern adopted |
| 3 | `mo2_modlist` | New (TS native) |
| 4 | `mo2_pluginlist` | New (TS native) |
| 5 | `mo2_mod_info` | New |
| 6 | `mo2_assets_summary` | Subsume `mo2-assets summary` via sidecar |
| 7 | `mo2_assets_conflicts` | Subsume via sidecar |
| 8 | `mo2_assets_resolve` | Subsume via sidecar |
| 9 | `mo2_search_files` | New |
| 10 | `mo2_list_executables` | New |
| 11 | `mo2_audit_query` | New |

### T2 metadata writes (5) — snapshot-before-write + plan/apply + audit

| # | Tool | Notes |
|---|---|---|
| 12 | `mo2_set_mod_notes` | meta.ini `[General] notes="..."` |
| 13 | `mo2_edit_meta` | arbitrary meta.ini fields |
| 14 | `mo2_profile_ini_set` | profile-local `<game>.ini` etc. |
| 15 | `mo2_backup_mod` | filesystem copy to `<name>backupN` |
| 16 | `mo2_backup_profile` | explicit full-profile snapshot |

(Also exposes T1 read `mo2_profile_ini_get`.)

### T3 mutate mod state (15) — plan/apply mandatory + lease + snapshot + audit

| # | Tool | Notes |
|---|---|---|
| 17 | `mo2_toggle_mod` | live: `mods.set_active` via pipe; offline: modlist.txt |
| 18 | `mo2_toggle_plugin` | + optional `also_hide_file` for "Optional ESP" |
| 19 | `mo2_send_mod_to` | mode: top/bottom/priority/above_separator/above_first_conflict |
| 20 | `mo2_install` | Includes FOMOD Pattern A (Q2=full) |
| 21 | `mo2_rollback` | Restore from snapshot |
| 22 | `mo2_restore_profile` | From `mo2_backup_profile` snapshot |
| 23 | `mo2_run_tool` | Live: `organizer.start_application`; offline: CLI `exe <title>` |
| 24 | `mo2_configure_executable` | action: add/edit/remove |
| 25 | `mo2_switch_profile` | Cold-restart sequence |
| 26 | `mo2_create_mod` | Empty mod with optional `above` |
| 27 | `mo2_create_separator` | `_separator` suffix + optional color |
| 28 | `mo2_rename_mod` | Cross-profile sync |
| 29 | `mo2_reinstall_mod` | Requires meta.ini installationFile |
| 30 | `mo2_remove_mod` | Default `backup_first=true` |
| 31 | `mo2_set_file_hidden` | `.mohidden` rename, virtual_path → hidden:bool |

Plus the 3 profile lifecycle tools (Q5=v1 scope):

| # | Tool | Notes |
|---|---|---|
| 32 | `mo2_create_profile` | `initializeProfile` (online) or file-level (offline) |
| 33 | `mo2_clone_profile` | File-level recursive copy, MO2 closed |
| 34 | `mo2_rename_profile` | Rename dir + update `[General] selected_profile` |

(Final count: 11 T1 + 5 T2 + 18 T3 = 34 — slightly above the 32 sketch because `mo2_profile_ini_get`/`set` and `mo2_create_profile`/`clone_profile`/`rename_profile` decomposed into independent tools rather than one super-tool with mode args. Final spec confirms 34.)

---

## 5-stage execution

Each stage is a separate plan file. Each stage produces working, testable software on its own and lands a sequence of small commits. Per-stage code review gate via `requesting-code-review` skill before moving to next stage. Final integration via `finishing-a-development-branch`.

| Stage | Plan file | What lands | Tools added |
|---|---|---|---|
| **S1** | `2026-06-14-mo2-mcp-S1a-broker-extension.md` + `2026-06-14-mo2-mcp-S1b-broker-organizer-and-sidecar.md` | Extended `mo2_agent_control.py` broker (new mobase mutator commands + `system.shutdown`); new Python sidecar (`tools/mo2-mcp-sidecar/`) with JSON-RPC envelope, World cache, pyfomod integration | 0 (substrate) |
| **S2** | `2026-06-14-mo2-mcp-S2-mcp-server.md` | New `tools/mo2-mcp/` TS package: lifecycle state machine, rule engine port, JSONL audit, snapshot manager, lease verifier, 7-signal MO2 detection ladder, native profile reader, sidecar JSON-RPC client, broker pipe client, `.mo2-mcp.json` config loader, permission ceiling, hard-deny rules | 0 (framework) |
| **S3** | `2026-06-14-mo2-mcp-S3-t1-reads.md` | All 11 T1 read tools + `mo2_profile_ini_get` | 12 |
| **S4** | `2026-06-14-mo2-mcp-S4-t2-and-core-t3.md` | All 5 T2 metadata writes + core T3 mutations: `mo2_toggle_mod`, `mo2_toggle_plugin`, `mo2_send_mod_to`, `mo2_rollback`, `mo2_restore_profile` | +10 |
| **S5** | `2026-06-14-mo2-mcp-S5-complex-t3.md` | All remaining T3: `mo2_install` (with FOMOD Pattern A), `mo2_run_tool`, `mo2_switch_profile`, `mo2_configure_executable`, `mo2_create_mod`/`create_separator`/`rename_mod`/`reinstall_mod`/`remove_mod`/`set_file_hidden`, profile create/clone/rename | +12 |

After S5: 11 + 5 + 18 = 34 tools live, vendor clone refreshed, ready for end-user dispatch.

---

## Branch + worktree strategy

Per repo memory (2026-05-27): use a feature branch + parent for best-of-N if needed. Per repo memory (2026-06-03): push to main is routine integration; cut commits small; refresh vendor clone after main lands.

- Feature branch: `feat/mo2-mcp` off `main`.
- Each stage land as multiple small commits on `feat/mo2-mcp`.
- Per-stage gate: green tests + oracle review via `requesting-code-review`.
- Merge to main per stage OR at end (decide at end of S2 based on whether stages are independent enough). Default: merge per stage with `--no-ff` to preserve stage boundary.
- Vendor clone refresh after each merge to main.

---

## Acceptance matrix (end of S5)

Inherits the v2 INTEGRATION.md acceptance plan plus additions from oracle traps:

| Test | Method | Pass criterion |
|---|---|---|
| T1 11-tool coverage | All against `B:\WastelandBlues 2.0` (803 mods / 421k files) | Bounded output, <5s per call, no truncation crash, asset results match `mo2-assets` CLI |
| Live-detect ladder | MO2 closed → open → re-call `mo2_status` | First offline; second online + correct PID + all 3 tiers reported |
| Plan/apply (toggle) | `mo2_toggle_mod plan` → `apply` | Diff matches; snapshot present; audit logged with plan_id chain |
| Lease enforcement | Plan → manually touch modlist.txt → apply | Refused with `lease_violation` + drifted file details |
| Rollback | Apply → `mo2_rollback` | File contents byte-identical |
| Live mutation via pipe | MO2 running, `mo2_toggle_plugin apply` | GUI reflects without restart, mobase readback confirms |
| Read-only ceiling | `ceiling: "read-only"` → try T2/T3 | All refuse with `permission_ceiling_violation`; startup probe verifies write-impossible |
| Stock Game hard-deny | Mutate path under `Stock Game/Data/**` | Hard refuse |
| `base_directory` relative path deny | Try writing relative path | `relative_base_directory_forbidden` |
| Install simple .7z | `mo2_install` plan + apply | Stages, conflict-checks, applies, registers in modlist.txt |
| Install FOMOD | `mo2_install plan` returns FOMOD tree → apply with choices | Pyfomod resolves files, stages, conflict-checks, applies; meta.ini fields correct |
| Atomic write | Interrupt modlist.txt write mid-rename | Either full old or full new file; no half state |
| Audit completeness | After T2/T3 sequence + rollback | Every plan/apply/refuse/rollback in JSONL, full plan_id/snapshot_id chain |
| Cold-restart switch | `mo2_switch_profile plan` + `apply` | MO2 dies; relaunches with new profile; sidecar World invalidated; pipe reconnected; status correct |
| customExecutables roundtrip | Add → list → edit → list → remove → list | INI atomic rewrite; MO2 reads on relaunch; other sections preserved |
| Profile create (online) | MO2 running, `mo2_create_profile plan + apply` | New profile dir created, game-INI defaults populated via `initializeProfile` |
| Profile clone | `mo2_clone_profile plan + apply` (MO2 closed) | Source files copied, saves skipped by default, MO2 picks up on next launch |
| Profile rename | `mo2_rename_profile plan + apply` (MO2 closed) | Dir renamed, `selected_profile` updated if matched |
| Cross-MCP concurrent | mo2-mcp + xedit-mcp both running, concurrent commands | Pipe serializes on main thread; no race; both succeed within 30s timeout |

---

## See also

- `D:\awesome-bgs-mod-master\.opencode\artifacts\mo2-mcp-design\INTEGRATION.md` — full design synthesis (v3)
- `.opencode/artifacts/mo2-mcp-design/IMPLEMENTATION-TRAPS.md` — 41 oracle-identified traps
- `.opencode/artifacts/mo2-mcp-design/librarian-alpha-full.md` — 893-line mobase + charrdge recon
- `.opencode/artifacts/mo2-mcp-design/librarian-beta-source-pins.md` — MCP spec elicitation + filesystem-mcp + git source pins

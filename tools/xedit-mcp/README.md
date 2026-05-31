# xedit-mcp

Harness MCP server for the forked xEdit automation daemon at `D:\TES5Edit-contrib`.

The MCP is the chokepoint that turns the daemon from a powerful-but-bare CLI surface into an agentic, harness-enforced workflow surface for BGS modpack curation. Each tool call traverses a fixed pipeline (validate → state precheck → rule registry → snapshot → preview → forward → envelope+audit) so the agent gets predictable, auditable, hint-rich refusals when something is wrong and shaped, audited responses when something works.

- **Design spec**: `docs/superpowers/specs/2026-05-26-xedit-skills-and-harness-mcp-design.md`
- **Batch 1 plan**: `docs/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.md`
- **Batch 1 status**: `docs/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.STATUS.md`
- **Hub skill**: `.opencode/skills/xedit-automation/SKILL.md`
- **Deep reference**: `.opencode/skills/xedit-automation/xedit-knowledgebase.md`
- **W2 task skill**: `.opencode/skills/xedit-conflict-audit/SKILL.md`
- **Acceptance artifacts**: `.opencode/artifacts/xedit-mcp/acceptance/batch1/`

## Status

**Batch 1 SHIPPED** (2026-05-31). Live W2 conflict-audit verified end-to-end against the MO2-backed xEdit daemon, oracle review verdict `accept_with_followups`. See the STATUS file linked above for the full carry-forward list.

| Surface | Status |
|---|---|
| 7-stage pipeline stages [1][2][3][6][7] (validate / state precheck / rules / forward / audit) | shipped |
| 7-stage pipeline stages [4][5] (snapshot / preview) | Batch 3 |
| `xedit_session`, `xedit_list_capabilities`, `xedit_find_record`, `xedit_read_record`, `xedit_inspect_conflicts` | shipped |
| `xedit_call` atomic passthrough | shipped |
| Seed rule `LOAD001` (CRITICAL) + rule registry | shipped |
| Append-only JSONL audit logger (`.opencode/artifacts/xedit-mcp/audit/YYYY-MM-DD.jsonl`) | shipped |
| Curated 49-command capabilities digest with live drift report | shipped |
| Remaining seed rules (`COPY001`, `DEL001`, `MUTATE001`, `CREATE001`, `ELEMENT001`, `SAVE001`, `SCRIPT001`, `JOB001`, `STORE001`) | per-batch as their target tools land |
| Mutating record tools (create / copy_into / delete / mark_deleted / set_element) | Batch 3-4 |
| `xedit_run_job` async wrapper for the 10 job kinds | Batch 3 |
| `xedit_run_script` Pascal scripting | Batch 4 |
| `restore_snapshot` recovery tool | Batch 3 |
| `-automation-mcp-mode` token enforcement (fork-side coordination) | Batch 4 prerequisite |

## Architecture (7-stage pipeline)

Every tool call traverses:

1. **Schema/argument validation** — `zod`-based, refuses with `invalid_request` + structured `detail.issues`.
2. **State precheck** — daemon readiness, consent flag, load-order membership (where applicable). Refuses with `state_violation`.
3. **Rule registry scan** — operator-knowledge rules with `riskLevel` ∈ {CRITICAL, HIGH, MEDIUM}. CRITICAL always blocks; HIGH blocks by default; MEDIUM warns (Batch 1) and will surface as envelope warnings (Batch 2+). Refuses with `rule_<ID>` plus a `hint` that teaches the corrective path.
4. **Snapshot before mutate** — Batch 3. Persists affected state under `.opencode/artifacts/xedit-mcp/snapshots/` so `restore_snapshot` can revert field-level edits.
5. **Preview / consent gate** — Batch 3. HIGH-risk mutating tools return a preview envelope with `confirmToken`; the caller commits with the token.
6. **Forward to daemon** — invokes `tools/mo2-vfs-launcher/xedit-client.ps1 automation call` and parses the response. UTF-8 BOM stripped; daemon errors mapped to MCP refusals.
7. **Envelope shape + audit** — uniform `{ok, tool, summary, data?, status?, snapshotId?, warnings, …}` envelope. The raw daemon envelope never leaks. One JSONL audit line per mutating-tool invocation that goes through the composer.

The pipeline composer (`src/pipeline/compose.ts`) wraps the entire call in a try/catch so unexpected throws still produce an `internal_error` envelope and an audit line — no caller ever sees a bare rejection.

## Use

```bash
# install + build
npm install
npm run build

# unit suite (default; integration tests excluded)
npm test

# typecheck only
npm run typecheck

# live integration against the MO2-backed daemon. Prereqs:
#   1. .artifacts/mo2/ exists with the Mo2AgentControl plugin installed
#      and a populated profiles/Default/plugins.txt
#   2. xEdit binary at .artifacts/mo2/Stock Game/Fallout 4/Tools/OpenCodeXEdit/xEdit.exe
#   3. ModOrganizer.exe is pre-launched OR the test will spawn MO2 via Start-Process
#   4. fixtures.json points at records present in the live load order
XEDIT_MCP_INTEGRATION=1 npm run test:integration
```

Production wiring goes through `buildServerToolset()` exported from `src/index.ts`, fed by a `DaemonAdapter` produced by `launchDaemon()` from `src/launch.ts`. The integration test `tests/integration/live-conflict-audit.test.ts` is the canonical wiring example.

## Layout

```
src/
  index.ts                    MCP server toolset assembly; production stdio entry
  types.ts                    Envelope, Rule, Finding, ToolContext, MCP_ERROR_CODES
  audit.ts                    Append-only JSONL audit logger
  envelope.ts                 ok / refuse / fromRuleFinding helpers
  daemon-adapter.ts           PowerShell adapter over xedit-client.ps1
  session.ts                  buildContext: describe + capabilities + files.list -> ToolContext
  capabilities-digest.ts      Curated 49-command digest used by xedit_list_capabilities
  launch.ts                   Production launchDaemon: process launch + ready-poll + plugin-load wait
  pipeline/
    validate.ts               Stage [1] — zod schema validator
    state-precheck.ts         Stage [2] — daemon/consent/load-order checks
    rules.ts                  Stage [3] — registry runner with severity gating
    forward.ts                Stage [6] — daemon adapter forward + error mapping
    compose.ts                runTool: wires [1] → [2] → [3] → [6] → [7] with try/catch
  rules/
    registry.ts               createRegistry + defaultRegistry
    LOAD001.ts                Seed rule: target file in active load order
  tools/
    session.ts                xedit_session
    list-capabilities.ts      xedit_list_capabilities
    find-record.ts            xedit_find_record
    read-record.ts            xedit_read_record (composite read)
    inspect-conflicts.ts      xedit_inspect_conflicts (caXxx → verdict mapping)
    call.ts                   xedit_call atomic passthrough
tests/
  unit/                       per-module unit tests (vitest)
  integration/
    live-conflict-audit.test.ts  W2 acceptance against the live daemon (gated)
    diag-*                       gated diag tests for ad-hoc debugging
    fixtures.json                three known-good Fallout4.esm records for W2
```

## Known semantic facts (from Batch 1)

- Daemon response files are UTF-8 with BOM on Windows; adapter strips the leading `0xFEFF`.
- `system.describe`: friendly name is in `gameName` (`"Fallout4"`), internal token in `gameMode` (`"gmFO4"`).
- `files.list`: returns `Array<{ name, loadOrder, fileName, isESM, ... }>`, not `string[]`.
- FormIDs over the wire: daemon rejects the `0x` prefix; MCP schemas accept both styles and strip before forwarding.
- `records.conflict_status`: returns the conflict label under `result.conflict.all` using the xEdit `caXxx` enum (`caConflict`, `caITM`, `caITPO`, `caConflictCritical`, `caOnlyOne`, `caOverride`, `caConflictBenign`, `caUnknown`, `caNoConflict`).
- `xedit-client.ps1` verified surface: `process launch | status | wait | stop` + `automation call`. `automation call` flags: `--xedit-pid <pid> --request-file <reqPath> --response-file <resPath> --timeout-seconds <n>`.

These are codified in `AGENTS.md` and in `.opencode/skills/xedit-automation/xedit-knowledgebase.md`.

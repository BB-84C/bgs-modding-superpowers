# xedit-mcp

The bundled MCP server that the `bgs-modding-superpowers` plugin uses to drive xEdit programmatically. Ships as part of the plugin; end users do not invoke it directly.

This package wraps the agent-friendly xEdit fork at [BB-84C/TES5Edit](https://github.com/BB-84C/TES5Edit) with a 7-stage harness pipeline so every tool call goes through validate -> state-check -> rule registry -> forward -> envelope -> audit. The harness exists so the agent gets predictable, auditable, hint-rich refusals when something is wrong and shaped, audited responses when something works.

## What the agent gets

Six MCP intent tools plus an atomic passthrough:

| Tool | Purpose |
|---|---|
| `xedit_session` | First call every conversation. Returns game mode, load order size, daemon PID, capability flags. |
| `xedit_list_capabilities` | Curated 49-command digest + drift report against the live daemon. |
| `xedit_find_record` | Locate a record by `{file, formId}` or `{editorId}`. |
| `xedit_read_record` | Fields + base record + winning override. |
| `xedit_inspect_conflicts` | W2 verdict tool: `no_conflict / itpo / itm / minor / breaking`. |
| `xedit_call(command, args)` | Atomic passthrough for any of the 49 native daemon commands. Still goes through the full pipeline. |

The agent-facing skills are documented separately at `skills/xedit-automation/` and `skills/xedit-conflict-audit/` in the plugin root.

## Use from the plugin

This MCP is wired up automatically when `bgs-modding-superpowers` is installed:

- **OpenCode**: the plugin's `.opencode/plugins/bgs-modding-superpowers.js` writes `config.mcp.xedit = { type: "local", command: ["node", <dist/index.js>] }`.
- **Claude Code / Codex**: `.mcp.json` at the plugin root declares this server with `${CLAUDE_PLUGIN_ROOT}/tools/xedit-mcp/dist/index.js` alongside the sibling `bgs_kb` server.

End users never run `xedit-mcp` directly. The MCP receives stdio requests from the host agent's MCP client and forwards them to the xEdit daemon via the `xedit-client.ps1` outer client at `tools/mo2-vfs-launcher/`.

## Runtime requirements

- Node 22+ on the user's machine.
- MO2 with the `bgs-modding-superpowers` control plane installed (see the plugin's `setting-up-bgs-modding-environment` skill).
- xEdit binary co-located with `xEditHookBridge.dll` under the user's MO2 (also handled by `setting-up-bgs-modding-environment`).

## Architecture (7-stage pipeline)

Every tool call traverses:

1. **Schema/argument validation** — `zod`-based, refuses with `invalid_request` + structured `detail.issues`.
2. **State precheck** — daemon readiness, consent flag, load-order membership (where applicable). Refuses with `state_violation`.
3. **Rule registry scan** — operator-knowledge rules with `riskLevel` in `{CRITICAL, HIGH, MEDIUM}`. CRITICAL always blocks; HIGH blocks by default; MEDIUM warns.
4. **Snapshot before mutate** (Batch 3) — persists affected state under `.opencode/artifacts/xedit-mcp/snapshots/` so `restore_snapshot` can revert field-level edits.
5. **Preview / consent gate** (Batch 3) — HIGH-risk mutating tools return a preview envelope with `confirmToken`; the caller commits with the token.
6. **Forward to daemon** — invokes `tools/mo2-vfs-launcher/xedit-client.ps1 automation call` and parses the response.
7. **Envelope shape + audit** — uniform `{ok, tool, summary, data?, status?, snapshotId?, warnings, ...}` envelope. The raw daemon envelope never leaks. One JSONL audit line per mutating-tool invocation under `.opencode/artifacts/xedit-mcp/audit/YYYY-MM-DD.jsonl`.

## Status

- Shipped: pipeline stages [1][2][3][6][7], six intent tools, atomic passthrough, seed rule `LOAD001`, append-only JSONL audit logger, curated 49-command capabilities digest with live drift report.
- Deferred: pipeline stages [4][5] (snapshot/preview), mutating record tools, `xedit_run_job` async wrapper, `xedit_run_script` Pascal scripting, `restore_snapshot` recovery tool, `-automation-mcp-mode` token enforcement.

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
  pipeline/                   Stages [1][2][3][6][7]
  rules/
    registry.ts               createRegistry + defaultRegistry
    LOAD001.ts                Seed rule: target file in active load order
  tools/                      Six intent tools + atomic passthrough
tests/
  unit/                       per-module unit tests (vitest)
  integration/                live + diag tests; double-gated by env vars
dist/                         pre-built TypeScript output, committed for plugin shipping
```

## Development

```bash
npm install
npm run build      # rebuilds dist/; also runs via `prepare` on install
npm test           # unit suite (integration tests excluded)
npm run typecheck

# Live integration against the dedicated dev MO2 sandbox at .artifacts/mo2/:
#   Prereqs: control-plane DLL + py installed; xEdit at .artifacts/mo2/Stock Game/Fallout 4/Tools/OpenCodeXEdit/xEdit.exe;
#   fixtures.json records present in load order.
XEDIT_MCP_INTEGRATION=1 npm run test:integration

# Diagnostic tests (against a pre-launched xEdit PID):
XEDIT_MCP_INTEGRATION=1 BGS_MCP_DIAG=1 XEDIT_PID=<pid> npm run test:integration
```

Override env vars for non-default paths:
- `BGS_TEST_CLIENT_SCRIPT` — alternative xedit-client.ps1 location.
- `BGS_TEST_XEDIT_PATH` — alternative xEdit binary path.

## Known semantic facts

- Daemon response files are UTF-8 with BOM on Windows; the adapter strips the leading `0xFEFF`.
- `system.describe`: friendly name is in `gameName` (e.g. `"Fallout4"`), internal token in `gameMode` (e.g. `"gmFO4"`).
- `files.list`: returns `Array<{ name, loadOrder, fileName, isESM, ... }>`, not `string[]`.
- FormIDs over the wire: the daemon rejects the `0x` prefix; MCP schemas accept both styles and strip before forwarding.
- `records.conflict_status`: returns the conflict label under `result.conflict.all` using the xEdit `caXxx` enum (`caConflict`, `caITM`, `caITPO`, `caConflictCritical`, `caOnlyOne`, `caOverride`, `caConflictBenign`, `caUnknown`, `caNoConflict`).
- `xedit-client.ps1` verified subcommand surface: `process launch | status | wait | stop` + `automation call`. `automation call` flags: `--xedit-pid <pid> --request-file <reqPath> --response-file <resPath> --timeout-seconds <n>`.

Deeper internals, plans, and design specs live under [`docs/internal/`](../../docs/internal/) in the plugin root.

## License

MIT, inherited from the parent plugin.

# KB-5d xEdit MCP rule-candidate markers

This note reserves LOAD-style rule IDs for durable KB facts that could become
mechanically checkable `tools/xedit-mcp` rules in a later phase. The records
describe the facts; this planning note owns the proposed rule IDs.

## Marked records

- `xedit.session-save-deferred-when-pending-shutdown.v1` — reserve
  `RULE_SAVE_DURABILITY_001`: require save + daemon restart + readback before an
  agent can claim durability when `session.save` reports pending-shutdown files.
- `tooling-mo2.xedit-data-path-flag.v1` — reserve `RULE_DATA_PATH_001`: warn or
  refuse an MO2-backed xEdit launch whose `dataPath` is absent or does not match
  MO2 `gamePath\Data`.
- `debugging.dirty-state-before-stop-restart.v1` — reserve
  `RULE_DIRTY_STATE_001`: ensure stop/restart paths surface dirty state and do
  not silently abandon unsaved plugin edits.

## Considered but not marked

- 0x-prefixed FormID records: not marked because the MCP already normalizes at
  the edge; this is an adapter behavior, not a new rule requirement.
- Direct CLI bypass in MCP mode: not marked because it is already enforced by
  the architecture / daemon mode boundary.
- xEdit error-code mapping records: not marked because they are read-only
  triage guidance rather than preflight or mutation rules.

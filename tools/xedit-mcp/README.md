# xedit-mcp

Harness MCP server for the forked xEdit automation daemon. See the design spec at
`docs/superpowers/specs/2026-05-26-xedit-skills-and-harness-mcp-design.md`.

## Quick start

```bash
npm install
npm run build
npm test
```

## Architecture

Every MCP tool call traverses a fixed 7-stage pipeline:

1. Schema/argument validation
2. State precheck (daemon, load-order, consent)
3. Rule registry scan
4. Snapshot before mutate (Batch 3+)
5. Preview / consent gate (Batch 3+)
6. Forward to daemon via `tools/mo2-vfs-launcher/xedit-client.ps1`
7. Envelope shape + audit log

Batch 1 ships stages [1][2][3][6][7] and the read-only tools needed for the
conflict-audit (W2) workflow.

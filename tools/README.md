# Tools

This directory holds implementation code or automation invoked by commands or agents.

It now also hosts the MO2 control plane scaffold, split into a broker CLI and plugin kernel, plus the generic VFS launcher and xEdit outer client layer.

## Sub-packages

| Path | Purpose | Status |
|---|---|---|
| `mo2-control-plane/` | MO2-side broker CLI + agent-control plugin + Python live bridge. The broker owns `system.*` discovery and `launch.start/status/wait/stop` over a local named-pipe transport. | Foundation in place |
| `mo2-vfs-launcher/` | Generic, tool-agnostic launcher behind the MO2 `OpenCodeVfsLauncher` entrypoint, plus `xedit-client.ps1` — the canonical outer client (`process launch / status / wait / stop` + `automation call`). | Foundation in place |
| `xedit-mcp/` | TypeScript MCP server that wraps `xedit-client.ps1` and the forked xEdit automation daemon. Implements the 7-stage harness pipeline (validate → state → rules → snapshot → preview → forward → audit). Batch 1 (conflict-audit vertical slice) shipped 2026-05-31; see `tools/xedit-mcp/README.md`. | Batch 1 shipped |
| `xedit-hook-bridge/` | Legacy Delphi DLL for early MO2-hook experiments. Slated for removal under the native xEdit adoption design. | Marked for removal |

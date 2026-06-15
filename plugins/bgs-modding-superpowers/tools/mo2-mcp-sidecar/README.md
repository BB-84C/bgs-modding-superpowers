# mo2-mcp-sidecar

Long-lived Python JSON-RPC subprocess for the MO2 MCP TypeScript server.
Wraps `mo2_assets_engine` and `pyfomod` so the TS MCP can call asset enumeration,
conflict resolution, and FOMOD parsing without per-call Python startup cost.

Spawned by the MCP at startup with `--mods-root`, `--profile-dir`, `--game`.
Communicates over stdin/stdout in JSON-RPC 2.0 framing.

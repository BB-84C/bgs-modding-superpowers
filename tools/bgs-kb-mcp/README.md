# bgs-kb-mcp

Sibling MCP package for the BGS Modding agentic knowledge base.

This package will serve pack-based SQLite + FTS5 + BM25 retrieval across the
cross-game core pack and per-game packs for Skyrim, Fallout, and Starfield
modding workflows. It is independent of `xedit-mcp`: KB lookups do not start
xEdit, do not require MO2, and do not hold live plugin-file state.

## Status

KB-1c bootstrap only.

- Server tools (`bgs_kb_status`, `bgs_kb_query`, `bgs_kb_get`, etc.) land in
  KB-2.
- CLI subcommands land later: `build` in KB-1e, `validate` / `info` in KB-1f,
  and `render` in KB-5.
- For now, `src/index.ts` deliberately exits with a clear KB-2 pointer, and
  `src/cli.ts` only implements `--help`.

## SQLite library decision

Use `node:sqlite`.

KB-1d smoke verification on Node v24.16.0 confirmed:

- `node:sqlite` is available without `--experimental-sqlite`.
- FTS5 is enabled.
- BM25 ranking works.

This keeps the package at zero native dependencies and preserves the portable
plugin Target-1 invariant. Do not add `better-sqlite3`, `sql.js`, or another
SQLite alternative unless the plan is explicitly revised.

## Links

- Spec: `docs/internal/superpowers/specs/2026-06-02-agentic-cross-game-kb-design.md`
- Plan: `docs/internal/superpowers/plans/2026-06-02-agentic-cross-game-kb.md`
- Roadmap: `docs/internal/roadmap.md`

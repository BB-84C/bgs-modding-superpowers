# SQLite Schema

Phase 1 SQLite storage is the wrapper-owned artifact layer behind compact summaries and scoped inspection.

## Recommended Tables

- `runs`: one row per scan with scan metadata and artifact paths
- `files`: scanned file and plugin rows for a run
- `groups`: grouped summaries by top-level group and signature
- `records`: compact record and conflict index rows
- `overrides`: ordered override-chain rows
- `inspections`: cached or persisted scoped inspection results
- `refs`: optional dependency slices if Phase 1 includes reference views

## Index Vs Detail Storage

Store scan metadata, plugin rows, group summaries, record index rows, and override chains as indexed tables.

Keep expensive record-detail payloads out of the base index when possible. Persist them in `inspections` only when a specific drilldown is requested or when caching clearly improves repeated inspection flows.

## Wrapper Responsibilities

The wrapper owns schema evolution, ingestion, and query rendering. The Pascal script should emit stable report rows, while `xedit-cli` decides what becomes relational index data versus on-demand detail.

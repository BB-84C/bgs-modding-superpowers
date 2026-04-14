# Intermediate Report Contract

Phase 1 uses a wrapper-owned intermediate report emitted by a read-only xEdit Pascal script and ingested by `xedit-cli`.

The report should stay stable enough for automated ingestion while avoiding giant full-record dumps.

## Scan Metadata

Capture one run header with the scan ID, report version, generated timestamp, game mode, load-order source, and xEdit launch context needed for traceability.

## File And Plugin Rows

Emit one row per scanned file or plugin with stable plugin name, load-order position, and a simple role marker such as master, plugin, or light plugin.

## Group And Signature Summaries

Emit compact summary rows for major groups and signatures so the wrapper can surface hotspots before any deep drilldown.

## Record And Conflict Index Rows

Emit one compact row per indexed record with a stable record ID, signature, winning override context, conflict state, and a short summary suitable for list views.

## Override Chain Rows

Emit ordered override-chain rows that let the wrapper reconstruct which plugins participate in a record conflict and which one currently wins.

## Inspection Detail Strategy

Keep Phase 1 indexing lightweight. Store enough information for navigation and follow-up inspection, then let the wrapper materialize or cache record-level detail on demand instead of embedding every field comparison in the base report.

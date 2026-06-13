# Skill: Conflict Auditor

> **SUPERSEDED 2026-06-12.** This scaffold has been replaced by the shipped skill
> `skills/xedit-conflict-audit/` backed by the bundled xEdit MCP
> (`tools/xedit-mcp/`). Kept here as a historical design note; do not author new
> work against this stub. See `docs/internal/roadmap.md` "Capability Map"
> (`conflict auditor` row) for the shipped surface.

## Purpose

Separate file conflicts from plugin/data conflicts and guide the next inspection step.

Use the native xEdit outer client in `tools/mo2-vfs-launcher/xedit-client.ps1` as the execution boundary for read-only conflict inspection instead of building a separate extraction path inside the skill.

## When To Use

Use when two or more mods overlap in files, records, or load-order behavior.

## Workflow

1. Classify the overlap as file, archive, or plugin-data conflict.
2. Use the native xEdit outer client plus the planned read-only MCP boundary to gather conflict inspection data for the affected records.
3. Check loose files versus BSA or BA2 precedence.
4. Identify whether load order or a patch is required.
5. Record unresolved hotspots for later xEdit work.

## Outputs

- conflict classification
- likely resolution path
- unresolved follow-up list

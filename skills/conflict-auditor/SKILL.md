# Skill: Conflict Auditor

## Purpose

Separate file conflicts from plugin/data conflicts and guide the next inspection step.

Use `xedit-cli` as the tool layer for read-only conflict inspection instead of building a separate extraction path inside the skill.

## When To Use

Use when two or more mods overlap in files, records, or load-order behavior.

## Workflow

1. Classify the overlap as file, archive, or plugin-data conflict.
2. Use `xedit-cli` to gather read-only conflict inspection data for the affected records.
3. Check loose files versus BSA or BA2 precedence.
4. Identify whether load order or a patch is required.
5. Record unresolved hotspots for later xEdit work.

## Outputs

- conflict classification
- likely resolution path
- unresolved follow-up list

---
id: load-order.plugins-txt-legacy.v1
title: Legacy BGS plugins.txt is active-only; loadorder.txt holds the full order
domains: [load-order]
appliesTo:
  games: [SkyrimLE, Fallout3, FalloutNV]
  engineFamilies: [gamebryo, creation-engine]
canonical:
  answer: Legacy Bethesda load-order handling uses plugins.txt as the active-only list, while loadorder.txt carries the full active and inactive order.
  confidence: verified-project-doc
queryKeys: [legacy plugins.txt, loadorder.txt, active only, Skyrim LE, Fallout New Vegas]
severity: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Legacy format
related: [load-order.plugins-txt-modern-asterisk.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Legacy BGS plugins.txt is active-only; loadorder.txt holds the full order

Older Bethesda targets do not use the asterisk activation marker.
In this format, a plugin appears in `plugins.txt` only when it is active.

The sibling `loadorder.txt` is the full-order surface that can include inactive entries.
Agents must not copy modern `*` toggling rules into Skyrim LE, Fallout 3, or Fallout New Vegas workflows.

When editing order for these games, reason about both files together so activation and ordering do not drift.

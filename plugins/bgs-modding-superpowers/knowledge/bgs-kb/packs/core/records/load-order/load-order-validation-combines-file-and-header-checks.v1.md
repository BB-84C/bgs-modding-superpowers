---
id: load-order.load-order-validation-combines-file-and-header-checks.v1
title: Load-order validation combines plugins.txt presence with xEdit header checks
domains: [load-order, xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: A valid load-order check needs both file-surface validation and xEdit header/readback checks, because plugins.txt activation and plugin master consistency are different failure surfaces.
  confidence: verified-project-doc
queryKeys: [load order validation, missing master, duplicate plugin, files.get_masters, files.list]
severity: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Validation
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Load-order validation combines plugins.txt presence with xEdit header checks

Malformed load orders can fail before xEdit ever reaches a meaningful conflict audit.
A plugin line can duplicate another line, point at a missing file, exceed slot limits, or name a plugin whose masters are not resolvable.

Check the text file for syntax and presence, then use daemon readback such as `files.list` and `files.get_masters` for plugin-state confirmation.
Neither side alone proves the whole configuration is safe.

This record is useful before launching a custom `plugins.txt` into a long xEdit run.

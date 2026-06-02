---
id: load-order.loot-sort-vs-manual-order.v1
title: LOOT is the default sorter, but manual order is valid when plugin intent requires it
domains: [load-order, tooling.loot, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Use LOOT for normal metadata-driven sorting, then apply manual placement only when a mod author's instructions, a curated modlist rule, or verified conflict readback requires a specific override.
  confidence: verified-tooling
queryKeys: [LOOT sort, manual load order, sort plugins, metadata, modlist rule]
severity: high
sources:
  - kind: tooling-docs
    url: "https://loot.readthedocs.io/"
    ref: LOOT documentation
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Routing matrix
related: [load-order.xedit-cannot-change-load-order.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# LOOT is the default sorter, but manual order is valid when plugin intent requires it

LOOT is the normal first pass for plugin ordering because it applies shared metadata and known rules.
That does not make every sorted result final for every curated setup.

Manual order is appropriate when a mod author states an order requirement, a guide owns a deliberate placement, or xEdit conflict readback proves the desired winner is not in the LOOT result.
Document the reason for the manual override so later sorting does not erase it as noise.

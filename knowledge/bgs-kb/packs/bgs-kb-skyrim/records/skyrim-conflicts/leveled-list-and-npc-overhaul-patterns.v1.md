---
id: skyrim-conflicts.leveled-list-and-npc-overhaul-patterns.v1
title: Skyrim leveled-list and NPC overhaul conflict patterns
kind: rule
domains: [file-conflicts, xedit, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [gamebryo, creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Automated leveled-list merging can make Skyrim records structurally compatible, but NPC appearance and distribution coherence still require human review and often a hand-authored patch."
  confidence: high
queryKeys: [Skyrim leveled list, NPC overhaul, Bashed Patch, facegen, xEdit, asset conflicts]
severity: high
sources:
  - kind: tooling-docs
    url: "https://wrye-bash.github.io/docs/Wrye%20Bash%20General%20Readme.html"
    ref: "Wrye Bash documentation"
  - kind: tooling-docs
    url: "https://tes5edit.github.io/docs/6-themethod.html"
    ref: "xEdit The Method documentation"
  - kind: project-internal-doc
    ref: "BB84 corpus Q16 leveled-list coherence notes and WL2 / Starfield separator recon"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Skyrim leveled-list and NPC overhaul conflict patterns

## Perspective: OBJECTIVE

Skyrim leveled-list conflicts often fail silently. The game may not crash; items simply stop appearing, spawn rates drift, outfits become incoherent, or a faction's equipment no longer matches the intended world. Wrye Bash/Bashed Patch and similar merge tools can combine list entries and reduce structural overwrite loss, but they cannot decide whether bandits should carry a particular weapon tier, whether a new armor belongs in a region, or whether two distribution mods produce sensible scarcity.

NPC overhauls add a second conflict class. Record winners, facegen meshes/textures, race edits, voice types, outfits, perks, AI packages, and body/skin assets must agree. A plugin winner without matching facegen can cause dark face or visual mismatch; a visual overhaul that loses outfit or package edits can erase gameplay intent.

The practical check is two-plane: inspect record conflicts in xEdit, then confirm the winning loose files or archives provide the facegen and meshes the record winner expects. A “green” plugin conflict view does not prove the final actor is visually coherent in MO2’s asset order.

## Perspective: SUBJECTIVE — BB84 curator reference (not a universal rubric)

BB84 treats heavy leveled-list and NPC overhauls as “custom patch plus human review” territory, not a place to trust automation blindly. His WL2 practice includes many Complex Sorter / INNR-style rule mods, showing a preference for explicit classification and manual patch discipline. His Starfield separator split between NPC modification and NPC addition reflects the same axis discipline: separate changing existing actors from adding new population content. Another curator may choose a lighter approach, but should still verify the objective conflict surface.

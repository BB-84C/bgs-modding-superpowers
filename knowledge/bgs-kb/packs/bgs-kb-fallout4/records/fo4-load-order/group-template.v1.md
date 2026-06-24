---
id: fo4-load-order.group-template.v1
title: Fallout 4 load-order group template for curated modpacks
kind: workflow
domains: [load-order, install-planning, tooling.loot]
appliesTo:
  games: [Fallout4, Fallout4VR]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Fallout 4 load order should start from master and framework constraints, then group fixes, world edits, quests, NPCs, settlements, leveled lists, sorting, and final patches by conflict semantics rather than by download order.
  confidence: high
queryKeys: [Fallout 4 load order groups, LOOT, UFO4P, ESL, final patch]
severity: high
sources:
  - kind: tooling-docs
    url: "https://github.com/loot/fallout4"
    ref: LOOT Fallout 4 masterlist
  - kind: tooling-docs
    url: "https://loot.github.io/docs/help/LOOT-FAQs.html"
    ref: LOOT sorting guidance
  - kind: official
    url: "https://www.nexusmods.com/fallout4/mods/4598"
    ref: Unofficial Fallout 4 Patch Nexus page
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Fallout 4 load-order group template for curated modpacks

Use LOOT as a baseline sorter, then review by semantic groups. A practical Fallout 4 template is: official masters and DLC; UFO4P and foundational fixes; script extender and native framework dependencies; broad engine or UI frameworks; settlement/workshop frameworks; worldspace and previs/precombine-aware edits; quests and locations; NPC additions; NPC visual overhauls; weapons, armor, and object additions; leveled-list and injection mods; sorting/tagging rules; compatibility patches; final curator patch.

The group labels are not decoration. They encode the expected conflict surface. World edits need previs/precombine awareness, NPC overhauls need face/race/voice review, and leveled-list work needs a coherence patch rather than blind automated merging. ESL-flagged plugins can reduce slot pressure, but compacting or flag-flipping after a plugin has public dependents can break FormIDs and patches.

FO4VR can reuse the conceptual grouping but not every runtime dependency: F4SEVR, UI, and DLL-backed mods must be verified separately. Keep final patches late only when they intentionally win; do not use "bottom of load order" as a substitute for understanding why the record should win. The All-Clear siren sounds only after xEdit readback confirms the intended winners.

For large packs, keep separators named by function so later patch audits can find the responsible layer quickly.

---
id: fnv-load-order.group-template.v1
title: Practical load-order group template for Fallout 3, New Vegas, and TTW
kind: workflow
domains: [load-order, install-planning]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Use a conservative legacy Gamebryo group order: official masters first, framework masters and fixes next, large content and world edits in the middle, compatibility and generated patches last."
  confidence: high
queryKeys: [FNV load order groups, FO3 load order groups, TTW load order, Viva New Vegas, patch last]
severity: high
sources:
  - kind: community-forum
    ref: Viva New Vegas guide
    url: https://vivanewvegas.moddinglinked.com/
    sectionPath: Load order and final steps
  - kind: community-forum
    ref: Tale of Two Wastelands site
    url: https://taleoftwowastelands.com/
    sectionPath: Installation and load-order guidance
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Practical load-order group template for Fallout 3, New Vegas, and TTW

A stable Fallout 3, New Vegas, or TTW load order starts with conservative grouping. Place official masters and DLC first. For New Vegas, that means the base game and DLC masters before large framework or content mods. For TTW, Fallout 3 content is not a loose optional afterthought: the TTW-provided master structure defines how Fallout 3 is brought into the New Vegas runtime, so preserve the guide's master order exactly.

After official and TTW/framework masters, load engine and bug-fix plugins, UI and menu frameworks, settlement/worldspace/content expansions, quest and NPC edits, gameplay overhauls, item additions, leveled-list or distribution edits, visual/weather/audio plugins, then compatibility patches. Generated or hand-authored merge outputs, conflict-resolution ESPs, and final sorting/classification patches belong at the end because they intentionally decide winners after the inputs are visible.

Legacy Gamebryo titles have no ESL or medium-plugin tier. Do not import Skyrim SE, Fallout 4, or Starfield group rules that assume ESL compaction, light plugins, or master-tier variants. LOOT can provide a useful baseline, but it is not a curator. It cannot decide whether two item-distribution mods produce a coherent Mojave economy or whether an NPC overhaul should beat a quest mod's face/voice edits. Human review in xEdit remains the final authority for patch order and semantic winners.

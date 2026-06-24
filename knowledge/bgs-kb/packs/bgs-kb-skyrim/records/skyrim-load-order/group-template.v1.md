---
id: skyrim-load-order.group-template.v1
title: Skyrim load-order group template
kind: workflow
domains: [load-order, xedit, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [gamebryo, creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Use LOOT and guide groupings as the first Skyrim load-order pass, then hand-place compatibility patches after the records they patch and verify conflict winners in xEdit."
  confidence: high
queryKeys: [Skyrim load order, LOOT masterlist, compatibility patch, group template, xEdit winners]
severity: high
sources:
  - kind: tooling-docs
    url: "https://github.com/loot/skyrim/blob/master/masterlist.yaml"
    ref: "LOOT Skyrim masterlist"
  - kind: tooling-docs
    url: "https://github.com/loot/skyrimse/blob/master/masterlist.yaml"
    ref: "LOOT Skyrim Special Edition masterlist"
  - kind: tooling-docs
    url: "https://github.com/loot/skyrimvr/blob/master/masterlist.yaml"
    ref: "LOOT Skyrim VR masterlist"
  - kind: community-forum
    url: "https://stepmodifications.org/wiki/SkyrimSE:2.3"
    ref: "STEP Skyrim Special Edition guide"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Skyrim load-order group template

A safe Skyrim group template starts with immutable base content and ends with deliberate patches. Put official masters and DLC first; then large bug-fix and engine-fix plugins; worldspace, quest, location, and settlement-scale content; gameplay systems; NPC and leveled-list distribution; audio/weather/lighting; visual records; then compatibility, synthesis, bashed, and hand-authored patches. LOOT masterlists and STEP-style guides are the baseline ordering substrate, not a substitute for conflict review.

Examples: a perk overhaul belongs before its compatibility patches; a weather overhaul should load before lighting or image-space patches that intentionally adapt it; NPC visual overhauls need final facegen and record winners; leveled-list distribution may require a Bashed Patch plus a human coherence patch. Place a patch after every plugin it patches unless its documentation states an explicit exception.

Plugin type changes matter. LE has normal master/plugin semantics and no ESL layer. SE, AE, and VR can include ESL-flagged plugins and Creation Club light plugins, so FormID slot and compacting decisions affect load-order risk. Do not compact FormIDs or flip ESL flags on published plugins without checking downstream patches. Final acceptance is xEdit readback of intended winners, not a clean LOOT sort alone.

Keep separators aligned with this logic in MO2. If the left-pane asset order says one weather or NPC overhaul wins but the right-pane plugin order says another wins, the game can load mismatched records and loose assets. Resolve both planes together.

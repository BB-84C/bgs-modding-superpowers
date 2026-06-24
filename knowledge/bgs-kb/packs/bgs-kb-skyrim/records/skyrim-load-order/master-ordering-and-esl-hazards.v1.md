---
id: skyrim-load-order.master-ordering-and-esl-hazards.v1
title: Skyrim master ordering and ESL hazards
kind: rule
domains: [load-order, plugin-format, xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [gamebryo, creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Skyrim master order and light-plugin flags are structural contracts: sort masters correctly, never create cycles, and do not compact or ESL-flag a published plugin unless all downstream FormID references are controlled."
  confidence: high
queryKeys: [Skyrim masters, ESL flag, FormID compacting, master order, light plugin, LOOT]
severity: high
sources:
  - kind: official
    url: "https://en.uesp.net/wiki/Skyrim:Form_ID"
    ref: "UESP Skyrim Form ID reference"
  - kind: tooling-docs
    url: "https://tes5edit.github.io/docs/8-managing-mod-files.html"
    ref: "xEdit managing mod files documentation"
  - kind: tooling-docs
    url: "https://github.com/loot/skyrimse/blob/master/masterlist.yaml"
    ref: "LOOT Skyrim Special Edition masterlist"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Skyrim master ordering and ESL hazards

Skyrim masters are not just load-order decoration. Every plugin records its master list, and FormIDs resolve through that order. If a plugin depends on another file, the dependency must load earlier; master cycles are invalid; changing master order without understanding references can turn correct FormIDs into the wrong records. ESM-flagged ESPs can be legitimate, but they still behave as master-like files for dependency and ordering purposes. Treat “just move it lower” as a radiation leak when masters are involved.

Version scope matters. Skyrim LE has no ESL/light-plugin system. Skyrim SE, AE, and VR can load ESL-flagged plugins and Creation Club light plugins, and UESP documents the `FE xxx YYY` FormID shape for Creation Club/light content. Compacting FormIDs to fit ESL range changes record IDs; doing that after a plugin is published, translated, patched, or referenced by another plugin can break every dependent patch.

Safe discipline: sort with LOOT as a first pass, inspect declared masters in xEdit, add missing masters intentionally, and only compact/ESL-flag private or newly created patches before anything else references them. If a mod author ships a plugin as non-ESL, assume there may be a reason until you inspect record count, new-cell behavior, references, and downstream patches.

For public or shared packs, document every manual master-order override and every ESL conversion. The future curator needs to know whether the choice came from LOOT metadata, author instructions, or a local patch requirement; otherwise the next automated sort may undo the contract.

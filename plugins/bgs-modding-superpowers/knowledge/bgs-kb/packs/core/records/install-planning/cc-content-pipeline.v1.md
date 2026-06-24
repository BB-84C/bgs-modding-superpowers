---
id: install-planning.cc-content-pipeline.v1
title: Creation Club content pipeline — agent boundary at in-game download step
kind: rule
domains: [install-planning, file-conflicts]
appliesTo:
  games: [SkyrimSE, SkyrimAE, Fallout4, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
canonical:
  answer: "Bethesda's Creation Club / Creations content downloads occur INSIDE the game (Creations menu) and require user action — agent cannot complete the download step. After in-game download, files appear in MO2's `overwrite/` folder when MO2 launches the game; from there, scripts like `make_mods_from_cc.py` can materialize the scattered .esm/.ba2 set into individual `<stem>-cc/` mod folders for proper MO2 organization."
  confidence: high
queryKeys: [Creation Club, CC, Creations, in-game download, overwrite folder, make_mods_from_cc, materialize CC, SC localization]
severity: high
sources:
  - kind: official
    url: "https://creations.bethesda.net/"
    ref: "Bethesda Creations marketplace (downloads happen in-game)"
  - kind: community-forum
    url: "https://www.nexusmods.com/skyrimspecialedition/articles/3"
    ref: "Nexus discussion on CC + MO2 workflows"
  - kind: project-internal-doc
    url: "https://github.com/BB-84C/bgs-modding-superpowers/tree/main/scripts"
    ref: "make_mods_from_cc.py reference implementation"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Creation Club content pipeline — agent boundary at in-game download step

Creation Club / Creations content has a three-stage pipeline. First, the user downloads content inside the game's Creations menu. Second, after the game closes, MO2 sees the newly written files in `overwrite/` when the game was launched through MO2. Third, a materialization helper such as `make_mods_from_cc.py` can group the scattered files by prefix and copy them into individual MO2 mod folders such as `<prefix>-cc/`.

The agent boundary is stage 1. The in-game Creations UX involves authenticated Bethesda session state, button clicks, entitlement checks, and sometimes payment flows. Agents should not pretend they can safely complete that step. The correct handoff is: ask the user to perform the in-game download, close the game, then inspect and organize the files that appeared under MO2 `overwrite/`.

The files usually appear as prefix-grouped plugin and archive sets, for example `aseveil.esm`, `aseveil - main.ba2`, and `aseveil - textures.ba2`. The materialization script's `-cc` suffix is a curator naming convention, not a Bethesda primitive. Chinese localization or Simplified Chinese coverage may be represented as parallel folders such as `<prefix>-cc - SC`, depending on the curator's organization scheme.

The same operational shape applies across Skyrim SE/AE, Fallout 4, and Starfield, though the scale differs. Skyrim has roughly 80 official Creation Club creations, Fallout 4 roughly 50, and Starfield Creations has been larger and growing since its 2024-06 release. Empty `meta.ini` files in generated CC mod folders are expected if the helper only materializes files; curator notes and metadata must be authored separately if needed. Cleanup of `overwrite/` should remain a deliberate user-visible step, not an invisible purge.

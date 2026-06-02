---
id: ttw-interop.ttw-requires-both-games-and-dlcs.v1
title: TTW requires both games with DLCs as installer input
domains: [install-planning, version-differences]
appliesTo:
  games: [FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: Current TTW guide requirements call for English copies of both Fallout 3 and Fallout New Vegas with all DLCs before running the TTW installer.
  confidence: high
queryKeys: [TTW requirements, both games, all DLC, English copy, Fallout 3 GOTY]
severity: critical
sources:
  - kind: community-forum
    ref: The Best of Times Introduction
    url: https://thebestoftimes.moddinglinked.com/intro.html
    sectionPath: Game copy requirements
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# TTW requires both games with DLCs as installer input

TTW's guide treats Fallout 3 and Fallout: New Vegas as installer inputs, not optional content packs.
The requirement includes DLC coverage and language constraints.

If a TTW build is missing Capital Wasteland content, first verify the source-game installs and installer inputs before investigating load-order conflicts.

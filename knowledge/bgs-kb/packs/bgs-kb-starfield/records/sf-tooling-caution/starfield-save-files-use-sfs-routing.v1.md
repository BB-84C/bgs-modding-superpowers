---
id: sf-tooling-caution.starfield-save-files-use-sfs-routing.v1
title: Starfield save tooling routes to .sfs, not .ess or .fos
domains: [save-file, debugging]
appliesTo:
  games: [Starfield]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV]
canonical:
  answer: Starfield save analysis should route through `.sfs` assumptions rather than Skyrim `.ess` or Fallout `.fos` assumptions.
  confidence: high
queryKeys: [Starfield save, .sfs, save file extension]
severity: medium
sources:
  - kind: project-internal-doc
    ref: knowledge/bgs-kb/packs/core/records/engine/save-file-extension-per-game.v1.md
    sectionPath: Core save file extension record
related: [engine.save-file-extension-per-game.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Starfield save tooling routes to .sfs, not .ess or .fos

The core pack records Starfield's `.sfs` save-file routing.
This per-game record exists so Starfield queries do not drift into Skyrim `.ess` or Fallout `.fos` tooling.

The extension is only a routing signal, not a complete parser contract.
Use a Starfield-specific save tool before drawing conclusions from save internals.

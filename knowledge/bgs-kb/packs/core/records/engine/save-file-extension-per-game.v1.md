---
id: engine.save-file-extension-per-game.v1
title: Save-file extensions are game-specific and should not be mixed across tools
domains: [engine, save-file, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: Bethesda save files are not one universal format; Skyrim uses `.ess`, Fallout 3/New Vegas/Fallout 4 use `.fos`, and Starfield uses `.sfs`, so save tooling must be scoped to the target game.
  confidence: high
variants:
  SkyrimLE:
    additions:
      - Skyrim-family saves commonly use `.ess`.
  SkyrimSE:
    additions:
      - Skyrim-family saves commonly use `.ess`.
  Fallout4:
    additions:
      - Fallout 4 saves commonly use `.fos`.
  Starfield:
    additions:
      - Starfield saves commonly use `.sfs`.
queryKeys: [.ess, .fos, .sfs, save extension, Bethesda save format]
severity: medium
sources:
  - kind: wiki
    url: "https://en.uesp.net/wiki/Main_Page"
    ref: UESP main page
  - kind: wiki
    url: "https://fallout.wiki/wiki/Fallout_Wiki"
    ref: Independent Fallout Wiki
  - kind: wiki
    url: "https://starfieldwiki.net/wiki/Home"
    ref: Starfield Wiki home
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Save-file extensions are game-specific and should not be mixed across tools

Save analysis tools must identify the game before interpreting the file.
The extension is a useful first routing signal: Skyrim saves are usually `.ess`, Fallout saves are commonly `.fos`, and Starfield uses `.sfs`.

The extension alone does not prove the save is healthy or parseable.
It only prevents the first class of mistake: running the wrong game's save assumptions against the wrong file.

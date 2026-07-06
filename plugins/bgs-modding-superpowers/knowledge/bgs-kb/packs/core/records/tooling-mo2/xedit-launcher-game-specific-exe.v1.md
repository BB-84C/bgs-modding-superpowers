---
id: tooling-mo2.xedit-launcher-game-specific-exe.v1
title: Launch xEdit with the game-specific 64-bit executable
kind: gotcha
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
canonical:
  answer: For 64-bit Bethesda games, launch the game-specific xEdit executable such as SF1Edit64.exe, FO4Edit64.exe, or SSEEdit64.exe; a default xEdit.exe can select the wrong bitness or mode and fail before record loading.
  confidence: verified-project-doc
queryKeys: [xedit launcher, SF1Edit64, FO4Edit64, SSEEdit64, bitness, Starfield xEdit, wbImplementation assertion]
severity: high
sources:
  - kind: project-internal-doc
    ref: AGENTS.md
    sectionPath: Starfield xEdit Executable Specificity and Read-Only Artifact Boundaries
related: [tooling-mo2.xedit-data-path-flag.v1]
lastReviewed: "2026-06-29"
schemaVersion: 1
---

# Launch xEdit with the game-specific 64-bit executable

xEdit mode and bitness are not cosmetic. For 64-bit games, explicitly launch the game-specific 64-bit executable so xEdit selects the correct parser, game mode, and address space.

Use `SF1Edit64.exe` or `xEdit64.exe` for Starfield, `FO4Edit64.exe` for Fallout 4, and `SSEEdit64.exe` for Skyrim Special Edition / Anniversary Edition. Do not leave the executable unspecified in automation where a default `xEdit.exe` may resolve to a 32-bit fallback.

In MO2-backed workflows, this rule sits alongside the data-path rule: select the correct executable and pass the correct MO2-derived `Data` path. The executable answers “which game/mode/bitness,” while the data path answers “which installation tree.”

Reference case: a BB84 Lane 3 Starfield xEdit restart through the default `xEdit.exe` hit a `wbImplementation.pas:19240` assertion; relaunching with the Starfield 64-bit executable resolved the startup failure.

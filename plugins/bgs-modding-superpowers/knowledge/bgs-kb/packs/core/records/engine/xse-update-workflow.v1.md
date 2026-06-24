---
id: engine.xse-update-workflow.v1
title: Script Extender (xSE) update workflow — game-root drop, runtime-pinned dll
kind: rule
domains: [engine, install-planning]
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "Script Extenders (SKSE/F4SE/NVSE/SFSE) live in the game install root next to the .exe (NOT in MO2 mods/ overlay), and ship as a versioned .7z archive containing `<xse>_loader.exe` + `<xse>_<runtime_version>.dll` + readme + whatsnew + source archive. Updates must match the current Steam game runtime exactly; replace requires backup-before-replace + sha256 verify; the 7z extracts to a versioned SUBDIRECTORY (e.g. `sfse_0_2_21/`), not flat — always glob-find the actual files after extract."
  confidence: high
queryKeys: [SFSE, SKSE, F4SE, NVSE, script extender, xSE update, game root, sfse_loader, sfse dll, runtime version mismatch]
severity: high
sources:
  - kind: official
    url: "https://sfse.silverlock.org/"
    ref: "SFSE official site (silverlock points to Nexus mod #106 for distribution)"
  - kind: official
    url: "https://skse.silverlock.org/"
    ref: "SKSE official site"
  - kind: official
    url: "https://f4se.silverlock.org/"
    ref: "F4SE official site"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Script Extender (xSE) update workflow — game-root drop, runtime-pinned dll

Script Extenders such as SKSE, F4SE, NVSE, FOSE, and SFSE are game-root tools, not MO2 Data overlays. The loader must sit next to the game executable so it can start the real game process and inject the matching runtime DLL. MO2's VFS projects `Data/` content; it does not safely replace the game root executable neighborhood.

Runtime pinning is the containment seal. The extender DLL filename encodes the supported runtime, such as `sfse_1_16_244.dll` or an SKSE64 build tied to a specific Skyrim runtime. If Steam updates the game overnight, yesterday's matching extender can fail the next morning. The usual symptom is that launching through the extender loader no longer starts the game or exits immediately. Verify the current `<game>.exe` `FileVersion` against the extender's supported runtime before replacing files.

Official archives are usually versioned `.7z` files that extract into a versioned subdirectory, not a flat staging directory. Scripts must find the real files after extraction rather than assuming fixed relative paths:

```powershell
$dll = Get-ChildItem $stagingDir -Recurse -Filter "sfse_*.dll" | Select-Object -First 1
$loader = Get-ChildItem $stagingDir -Recurse -Filter "sfse_loader.exe" | Select-Object -First 1
```

The standard update workflow is: detect the current extender by the `<xse>_*.dll` file in the game root; check the official page or distribution page for the latest supported runtime; if the Steam runtime advanced, download the matching `.7z`; extract to staging; back up current game-root extender files (`<xse>_loader.exe`, `<xse>_<oldver>.dll`, `<xse>_readme.txt`, `<xse>_whatsnew.txt`); copy the new files; replace readme and whatsnew; optionally delete the old runtime DLL for cleanliness; then verify SHA256 for all copied files.

[CAUTION] This workflow writes directly to the real game install root. It requires explicit user confirmation in the current session, a backup-before-replace step, and a final readback. Vault-Tec is not responsible for unexpected Steam auto-updates, loader mismatch radiation leaks, or Chryslus-fueled file drift.

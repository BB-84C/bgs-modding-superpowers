---
id: fo4-next-gen.f4se-dlls-must-match-next-gen-branch.v1
title: F4SE DLL mods must be rebuilt or matched for the selected next-gen branch
domains: [version-differences, debugging]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: F4SE plugins are native DLLs, so next-gen branch changes require compatible builds rather than ordinary plugin sorting fixes.
  confidence: verified-official
queryKeys: [F4SE DLL, next-gen rebuild, native plugin, runtime 1.10.984]
severity: critical
sources:
  - kind: official
    url: "https://f4se.silverlock.org/"
    ref: F4SE home
related: [engine.xse-plugin-version-compatibility.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# F4SE DLL mods must be rebuilt or matched for the selected next-gen branch

Native F4SE plugins bind to runtime details that can change across Fallout 4 updates.
If the game was updated but a DLL was not, the failure can happen before any ESP conflict is evaluated.

Check each native plugin's supported runtime.
Do not solve native incompatibility by moving the plugin's ESP or editing `plugins.txt`.

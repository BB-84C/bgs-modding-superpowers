---
id: fo4-papyrus.f4se-papyrus-extensions-runtime-bound.v1
title: F4SE Papyrus extensions are tied to the F4SE runtime stack
domains: [papyrus, version-differences, debugging]
appliesTo:
  games: [Fallout4, Fallout4VR]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Papyrus functions supplied by F4SE or F4SEVR depend on the matching extender runtime and scripts, so missing extension functions often indicate loader or version mismatch.
  confidence: verified-official
queryKeys: [F4SE Papyrus, F4SE scripts, missing Papyrus function, F4SEVR]
severity: critical
sources:
  - kind: official
    url: "https://f4se.silverlock.org/"
    ref: F4SE home
related: [engine.xse-plugin-version-compatibility.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# F4SE Papyrus extensions are tied to the F4SE runtime stack

F4SE includes a native loader and script assets that expose additional scripting functionality.
If those files do not match the game runtime, Papyrus errors can appear even when the plugin load order is sane.

For missing extension calls, verify the executable, F4SE build, installed scripts, and VR-vs-flat branch.
Only then inspect the mod's own Papyrus code.

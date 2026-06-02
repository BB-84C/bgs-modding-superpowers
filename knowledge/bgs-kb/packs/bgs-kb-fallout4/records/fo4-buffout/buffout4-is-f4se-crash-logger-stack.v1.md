---
id: fo4-buffout.buffout4-is-f4se-crash-logger-stack.v1
title: Buffout 4 belongs to the F4SE crash-logger and runtime-support stack
domains: [debugging, version-differences]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Buffout 4 should be treated as native-code crash and runtime instrumentation in the F4SE ecosystem, so runtime and dependency compatibility come before reading the crash log.
  confidence: medium
queryKeys: [Buffout 4, crash logger, F4SE plugin, Address Library]
severity: critical
sources:
  - kind: official
    url: "https://f4se.silverlock.org/"
    ref: F4SE home
  - kind: tooling-docs
    url: "https://www.nexusmods.com/fallout4/mods/47359"
    ref: Buffout 4 Nexus page
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Buffout 4 belongs to the F4SE crash-logger and runtime-support stack

Buffout 4 is not an ordinary plugin record fix; it is native-code tooling loaded through the Fallout 4 script extender environment.
That makes runtime branch, F4SE build, and dependency state part of the crash diagnosis.

This record is medium confidence because the Nexus page title was reachable through Playwright, but simple HTTP returned 403.
Do not interpret a Buffout crash log until the native loader stack is known-good.

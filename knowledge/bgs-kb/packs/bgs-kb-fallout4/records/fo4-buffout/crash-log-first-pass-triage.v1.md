---
id: fo4-buffout.crash-log-first-pass-triage.v1
title: Fallout 4 crash-log triage starts with runtime, loader, and recent-change facts
domains: [debugging]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: First-pass crash triage should capture runtime version, F4SE version, native DLL stack, ENB/ReShade status, and the latest mod changes before assigning meaning to an address or module name.
  confidence: high
queryKeys: [crash log triage, Buffout log, module name, crash address]
severity: high
sources:
  - kind: official
    url: "https://f4se.silverlock.org/"
    ref: F4SE home
  - kind: community-forum
    url: "http://enbdev.com/"
    ref: ENBSeries site
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Fallout 4 crash-log triage starts with runtime, loader, and recent-change facts

Crash logs are evidence, but they are not self-interpreting.
The same address-like symptom can mean different things on different executable branches or native DLL stacks.

Capture runtime branch, F4SE build, native plugins, ENB/ReShade status, and the last changed mods first.
Then group crashes by reproducible action and module, not by a single scary-looking line.

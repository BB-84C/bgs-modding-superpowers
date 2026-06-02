---
id: fo4-quirks.native-stack-before-plugin-stack.v1
title: Diagnose Fallout 4 native startup layers before plugin conflict layers
domains: [debugging, install-planning]
appliesTo:
  games: [Fallout4, Fallout4VR]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Fallout 4 startup failures with ENB, F4SE, Buffout, or ReShade installed should first isolate native injection and runtime compatibility before ordinary ESP conflict work.
  confidence: high
queryKeys: [startup crash, ENB F4SE Buffout, ReShade, native stack]
severity: critical
sources:
  - kind: official
    url: "https://f4se.silverlock.org/"
    ref: F4SE home
  - kind: community-forum
    url: "http://enbdev.com/"
    ref: ENBSeries site
related: [fo4-buffout.enb-and-buffout-are-different-native-layers.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Diagnose Fallout 4 native startup layers before plugin conflict layers

FO4 modlists often include native layers: script extender, graphics wrapper, crash logger, and post-processing injector.
If the game fails before the main menu, those layers are earlier suspects than record-level conflicts.

Disable or verify native components one class at a time.
Once the executable reaches a stable menu, resume normal plugin and asset conflict diagnosis.

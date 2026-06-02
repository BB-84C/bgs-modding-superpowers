---
id: fo4-buffout.enb-and-buffout-are-different-native-layers.v1
title: ENB and Buffout operate at different native layers in Fallout 4
domains: [debugging, install-planning]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: ENB wraps rendering while Buffout participates in the F4SE/native crash-support stack, so startup failures need both graphics-injector and script-extender checks.
  confidence: high
queryKeys: [ENB Buffout, d3d11, crash on startup, native injector]
severity: high
sources:
  - kind: community-forum
    url: "http://enbdev.com/"
    ref: ENBSeries site
  - kind: official
    url: "https://f4se.silverlock.org/"
    ref: F4SE home
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# ENB and Buffout operate at different native layers in Fallout 4

ENBSeries is a rendering wrapper/injector layer, while Buffout-class tools rely on the F4SE native plugin environment.
Both can be present in a working setup, but they fail for different reasons.

When Fallout 4 crashes before the main menu, disable and restore one native layer at a time.
Do not blame plugin load order until binary injection and runtime compatibility are cleared.

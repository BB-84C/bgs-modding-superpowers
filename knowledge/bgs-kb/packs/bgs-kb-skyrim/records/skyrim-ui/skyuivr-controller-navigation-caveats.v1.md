---
id: skyrim-ui.skyuivr-controller-navigation-caveats.v1
title: SkyUI VR menus inherit VR controller navigation limits
domains: [game-specific.vr, engine, debugging]
appliesTo:
  games: [SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "SkyUI VR works around VR controller navigation, but complex menu operations still map through directional signals rather than mouse-and-keyboard assumptions."
  confidence: verified-tooling
queryKeys: [SkyUI VR controls, MCM VR, controller navigation, trackpad]
severity: medium
sources:
  - kind: tooling-docs
    ref: Odie skyui-vr GitHub
    url: https://github.com/Odie/skyui-vr
    sectionPath: Controls notes
related: [skyrim-vr.skyuivr-mcm-fork.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# SkyUI VR menus inherit VR controller navigation limits

SkyUI VR provides the VR MCM path, but the control model is still VR-specific.
The README documents directional inputs and trackpad gesture distinctions for inventory/menu actions.

If a menu works on flat-screen Skyrim but is hard to operate in VR, that can be a control-layout issue rather than a missing script.
Test critical MCM pages in headset, not only from a desktop capture.

Prefer VR-maintained UI forks for modlists that depend on MCM configuration.

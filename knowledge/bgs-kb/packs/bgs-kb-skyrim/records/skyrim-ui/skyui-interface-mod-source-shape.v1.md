---
id: skyrim-ui.skyui-interface-mod-source-shape.v1
title: SkyUI is a Skyrim interface mod with ActionScript and Papyrus components
domains: [engine, papyrus, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "SkyUI is a Skyrim interface mod whose source tree contains both ActionScript UI code and Papyrus scripts, so UI breakage can cross asset and script layers."
  confidence: verified-tooling
queryKeys: [SkyUI, interface mod, ActionScript, Papyrus, MCM]
severity: high
sources:
  - kind: tooling-docs
    ref: schlangster SkyUI GitHub
    url: https://github.com/schlangster/skyui
    sectionPath: Repository description; languages
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# SkyUI is a Skyrim interface mod with ActionScript and Papyrus components

SkyUI is not only a plugin or only a script package.
Its source distribution includes UI-side ActionScript and Papyrus-side code.

When SkyUI or MCM behavior breaks, inspect interface assets, scripts, SKSE status, and menu files together.
Do not diagnose it solely from ESP load order.

For Skyrim VR, use the SkyUI VR fork rather than assuming the flat-screen package is sufficient.

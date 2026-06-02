---
id: nvse-fose.root-extender-before-addon-plugins.v1
title: xNVSE must be installed before NVSE addon plugins can matter
domains: [engine, install-planning, debugging]
appliesTo:
  games: [FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: In modern New Vegas setups, xNVSE and the executable patcher live at the game-root/runtime layer, while JIP LN, JohnnyGuitar, ShowOff, and similar addons layer on top of that extender surface.
  confidence: high
queryKeys: [xNVSE install order, NVSE plugins, root folder, 4GB Patcher, utilities separator]
severity: critical
sources:
  - kind: community-forum
    ref: The Best of Times Essentials
    url: https://thebestoftimes.moddinglinked.com/essentials.html
    sectionPath: xNVSE and utility plugins
related: [nvse-fose.xnvse-is-new-vegas-extender.v1, nvse-fose.jip-ln-adds-functions-and-engine-fixes.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xNVSE must be installed before NVSE addon plugins can matter

The Best of Times separates the root-folder xNVSE/patcher steps from MO2-installed NVSE utility plugins.
That ordering reflects the runtime stack: addon DLLs cannot supply functions if the base extender is absent or the executable does not load it.

For agent troubleshooting, prove the root executable and xNVSE layer first, then inspect addon plugins and INI presets.

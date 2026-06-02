---
id: fo4-tooling.xedit-fo4-mode-targets-fallout4-records.v1
title: xEdit Fallout 4 mode must target the FO4 Data view and load order
domains: [xedit, debugging, install-planning]
appliesTo:
  games: [Fallout4, Fallout4VR]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Fallout 4 xEdit work must launch in the Fallout 4 game mode against the intended FO4 Data tree and plugin list, or readback may describe the wrong runtime.
  confidence: verified-project-doc
queryKeys: [FO4Edit, xEdit Fallout4, game mode Fallout4, -fo4, gmFO4]
severity: critical
sources:
  - kind: tooling-docs
    url: "https://tes5edit.github.io/docs/"
    ref: Tome of xEdit
  - kind: project-internal-doc
    ref: AGENTS.md
    sectionPath: Canonical runtime surfaces
related: [tooling-mo2.xedit-data-path-flag.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit Fallout 4 mode must target the FO4 Data view and load order

FO4Edit/xEdit can only provide useful Fallout 4 evidence when launched against the correct game mode, Data path, and load order.
In MO2-backed harnesses, that means the projected profile, not whatever Steam path the registry exposes.

If xEdit sees missing DLC, wrong masters, or absent test plugins, suspect launch context first.
Do not debug record logic until the session proves it is reading the intended FO4 runtime.

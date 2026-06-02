---
id: sf-asset-model.starfield-uses-ba2-archives-in-xedit-mode.v1
title: xEdit Starfield mode uses BA2 archive extension
domains: [archive-precedence, version-differences]
appliesTo:
  games: [Starfield]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV]
canonical:
  answer: The xEdit Starfield mode sets the archive extension to `.ba2`, so Starfield archive work should start from BA2 expectations rather than BSA expectations.
  confidence: verified-tooling
queryKeys: [Starfield BA2, SF1 archive extension, xEdit Starfield archives]
severity: high
sources:
  - kind: tooling-docs
    ref: D:/TES5Edit-contrib/xEdit/xeInit.pas
    sectionPath: SF1 mode initialization
related: [archive-precedence.bsa-vs-ba2-by-game.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit Starfield mode uses BA2 archive extension

The local xEdit fork's SF1 mode initialization sets Starfield's archive extension to `.ba2`.
That confirms Starfield belongs with the BA2 archive family for tooling expectations.

This does not prove every Fallout 4 BA2 tool is Starfield-safe.
Verify Starfield archive versions and material/asset paths before reusing FO4 packaging workflows.

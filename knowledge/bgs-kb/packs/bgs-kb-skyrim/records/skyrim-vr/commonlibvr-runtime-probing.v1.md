---
id: skyrim-vr.commonlibvr-runtime-probing.v1
title: CommonLibVR enables single-DLL Skyrim plugins with runtime probing
domains: [game-specific.vr, engine, version-differences]
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "CommonLibVR/CommonLibSSE NG can target SE, AE, and VR from one codebase, but end users still need the correct runtime libraries such as VR Address Library for SKSEVR."
  confidence: verified-tooling
queryKeys: [CommonLibVR, CommonLibSSE NG, runtime probing, VR Address Library]
severity: medium
sources:
  - kind: tooling-docs
    ref: alandtse CommonLibVR GitHub
    url: https://github.com/alandtse/CommonLibVR
    sectionPath: README
  - kind: tooling-docs
    ref: CommonLibSSE-NG GitHub
    url: https://github.com/CharmedBaryon/CommonLibSSE-NG
    sectionPath: README
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# CommonLibVR enables single-DLL Skyrim plugins with runtime probing

Some modern native plugins can ship one DLL that supports SE, AE, and VR through CommonLibSSE NG/CommonLibVR.
That does not mean every SKSE plugin is automatically VR-compatible.

Check the plugin's stated build target and runtime-probing support.
For VR users, VR Address Library for SKSEVR remains a separate dependency when required.

Use this record to distinguish modern multi-runtime DLLs from older one-runtime-only builds.

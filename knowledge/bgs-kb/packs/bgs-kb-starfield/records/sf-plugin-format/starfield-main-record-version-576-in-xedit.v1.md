---
id: sf-plugin-format.starfield-main-record-version-576-in-xedit.v1
title: xEdit creates Starfield main records with version 576
domains: [plugin-format, xedit]
appliesTo:
  games: [Starfield]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV]
canonical:
  answer: In the local xEdit fork, new Starfield main records use record version 576, which differs from FO4/FO4VR's 131 and Skyrim SE's 44.
  confidence: verified-tooling
queryKeys: [Starfield record version 576, main record version, xEdit record header]
severity: high
sources:
  - kind: tooling-docs
    ref: D:/TES5Edit-contrib/Core/wbImplementation.pas
    sectionPath: BasePtr.mrsVersion case by game mode
related: [plugin-format.create-record-header-side-effects.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit creates Starfield main records with version 576

xEdit's implementation assigns different main-record versions for different game modes.
For `gmSF1`, the local source sets the main record version to 576.

That is a concrete example of why Starfield plugin-format claims need Starfield tooling evidence.
Do not assume FO4 record-header defaults are valid in Starfield.

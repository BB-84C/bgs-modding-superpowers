---
id: sf-plugin-format.starfield-supports-light-medium-blueprint-update-flags.v1
title: xEdit marks Starfield as supporting light, medium, blueprint, and update plugin classes
domains: [plugin-format, xedit]
appliesTo:
  games: [Starfield]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV]
canonical:
  answer: In the local xEdit fork, Starfield mode is the condition for medium, blueprint, and update plugin support and is included in light plugin support.
  confidence: verified-tooling
queryKeys: [Starfield medium plugin, blueprint plugin, update plugin, light plugin]
severity: high
sources:
  - kind: tooling-docs
    ref: D:/TES5Edit-contrib/Core/wbInterface.pas
    sectionPath: wbIsLightSupported / wbIsMediumSupported / wbIsBlueprintSupported / wbIsUpdateSupported
related: [plugin-format.light-plugin-formid-range.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit marks Starfield as supporting light, medium, blueprint, and update plugin classes

The local xEdit fork exposes Starfield-specific support checks for plugin classes beyond older full-plugin assumptions.
In code, `gmSF1` participates in light support and directly gates medium, blueprint, and update support.

This is a tooling fact, not a blanket recommendation to convert plugins blindly.
Use Starfield-aware xEdit readback before changing a plugin's class.

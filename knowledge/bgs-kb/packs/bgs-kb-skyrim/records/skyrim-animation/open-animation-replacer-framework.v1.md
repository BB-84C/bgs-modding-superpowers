---
id: skyrim-animation.open-animation-replacer-framework.v1
title: Open Animation Replacer is a runtime conditional animation framework for SE AE VR
domains: [engine, version-differences]
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Open Animation Replacer is an SKSE framework plugin for conditionally replacing animations, with SE, AE, and VR support and Address Library requirements."
  confidence: verified-tooling
queryKeys: [Open Animation Replacer, OAR, DAR, Address Library, SKSEVR]
severity: high
sources:
  - kind: tooling-docs
    ref: OpenAnimationReplacer GitHub
    url: https://github.com/ersh1/OpenAnimationReplacer
    sectionPath: README
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Open Animation Replacer is a runtime conditional animation framework for SE AE VR

OAR is a runtime framework, not a generated-behavior patcher like FNIS or Nemesis.
Its source page describes an SKSE plugin that replaces animations based on configurable conditions and includes an in-game editor.

Because it is an SKSE plugin, runtime compatibility still matters.
SE/AE and VR dependency paths differ through Address Library and VR Address Library.

When migrating DAR-style setups, verify the individual mod's OAR support rather than assuming every folder layout transfers unchanged.

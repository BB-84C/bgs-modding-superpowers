---
id: skyrim-animation.nemesis-behavior-framework.v1
title: Nemesis is a Skyrim behavior patching framework
domains: [engine, install-planning]
appliesTo:
  games: [SkyrimSE, SkyrimAE]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Nemesis is a Skyrim behavior patching framework that automates behavior modification extraction and patching, so it must be run after animation-behavior mods change."
  confidence: high
queryKeys: [Nemesis, behavior engine, behavior patching, Project New Reign]
severity: high
sources:
  - kind: community-forum
    ref: Nexus Mods Project New Reign - Nemesis Unlimited Behavior Engine
    url: https://www.nexusmods.com/skyrimspecialedition/mods/60033
    sectionPath: About this mod
  - kind: tooling-docs
    ref: Nemesis GitHub repository
    url: https://github.com/ShikyoKira/Project-New-Reign---Nemesis-Main
    sectionPath: About
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Nemesis is a Skyrim behavior patching framework

Nemesis is a behavior patcher, not just a runtime dependency.
Changing animation-behavior mods without rerunning the generator leaves stale generated outputs.

In MO2, keep the generated output in a dedicated mod or a controlled overwrite handoff.
That makes generator reruns reviewable and keeps unrelated overwrite files from mixing with behavior output.

Do not stack a second behavior generator unless the modlist explicitly documents that combined workflow.

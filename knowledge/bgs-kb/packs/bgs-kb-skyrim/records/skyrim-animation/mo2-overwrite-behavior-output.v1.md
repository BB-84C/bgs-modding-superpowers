---
id: skyrim-animation.mo2-overwrite-behavior-output.v1
title: Skyrim behavior generator output should not live forever in MO2 Overwrite
domains: [engine, install-planning, file-conflicts]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "FNIS and Nemesis output should be promoted from MO2 Overwrite into a named generated-output mod so later reruns and file conflicts are auditable."
  confidence: verified-project-doc
queryKeys: [MO2 Overwrite, Nemesis output, FNIS output, generated behavior mod]
severity: high
sources:
  - kind: project-internal-doc
    ref: knowledge/bgs-kb/packs/core/records/archive-precedence/mo2-overwrite-generated-assets.v1.md
    sectionPath: Runtime-generated outputs are real mod assets
  - kind: community-forum
    ref: Nexus Mods Nemesis
    url: https://www.nexusmods.com/skyrimspecialedition/mods/60033
    sectionPath: About this mod
related: [archive-precedence.mo2-overwrite-generated-assets.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Skyrim behavior generator output should not live forever in MO2 Overwrite

Behavior generation creates real files that affect the game.
Leaving them in Overwrite makes ownership unclear and can hide stale files from older generator runs.

After running FNIS or Nemesis, move the generated files into a named output mod such as `Nemesis Output`.
Keep that mod near the end of the relevant asset order.

On rerun, replace the output mod deliberately instead of mixing new and old output.

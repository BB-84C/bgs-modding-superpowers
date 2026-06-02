---
id: skyrim-animation.one-behavior-generator-authority.v1
title: Pick one authoritative behavior generator output for a Skyrim profile
domains: [engine, file-conflicts, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "FNIS and Nemesis both generate behavior outputs; a profile needs one intentional final generated output set rather than competing stale outputs from multiple runs."
  confidence: high
queryKeys: [FNIS vs Nemesis, behavior output, overwrite, generated files]
severity: critical
sources:
  - kind: community-forum
    ref: Nexus Mods FNIS
    url: https://www.nexusmods.com/skyrim/mods/11811
    sectionPath: About this mod
  - kind: community-forum
    ref: Nexus Mods Nemesis
    url: https://www.nexusmods.com/skyrimspecialedition/mods/60033
    sectionPath: About this mod
related: [archive-precedence.mo2-overwrite-generated-assets.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Pick one authoritative behavior generator output for a Skyrim profile

FNIS and Nemesis solve the same broad class of behavior-generation problem.
The dangerous state is not merely having both tools installed; it is leaving multiple stale generated outputs active.

For a curated profile, document which generator owns the final behavior files.
Delete or disable old generated output before rerunning a different generator.

Treat behavior output like a generated patch with a clear owner.

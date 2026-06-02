---
id: load-order.custom-plugins-file-p-flag.v1
title: xEdit -P points a run at an agent-authored plugins.txt
domains: [load-order, xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: For isolated xEdit experiments, generate a custom plugins.txt under an agent-owned artifacts path and launch xEdit with pluginsFile, which maps to the -P flag.
  confidence: verified-project-doc
queryKeys: [pluginsFile, "-P:", custom plugins.txt, conflict isolation]
severity: medium
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Generating a custom plugins.txt for xEdit experiments
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit -P points a run at an agent-authored plugins.txt

When the task is to inspect a small subset of plugins, the correct unit of control is a generated `plugins.txt`.
Place that file in agent-owned artifacts and pass it as `pluginsFile` to xEdit startup.

This maps to xEdit's `-P:` launch flag and keeps the real MO2 profile from being silently mutated for one experiment.
Pair it with an explicit `dataPath` so the custom load order still resolves against the intended Data tree.

Use this for conflict isolation rather than editing the live profile as scratch space.

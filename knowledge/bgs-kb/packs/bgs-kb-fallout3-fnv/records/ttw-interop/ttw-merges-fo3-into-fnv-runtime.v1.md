---
id: ttw-interop.ttw-merges-fo3-into-fnv-runtime.v1
title: TTW runs Fallout 3 content inside the New Vegas runtime
domains: [engine, install-planning, version-differences]
appliesTo:
  games: [FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: Tale of Two Wastelands is a Fallout New Vegas total conversion that merges Fallout 3 and New Vegas into one New Vegas-runtime setup.
  confidence: high
queryKeys: [TTW, Tale of Two Wastelands, Fallout 3 in New Vegas, total conversion]
severity: critical
sources:
  - kind: community-forum
    ref: The Best of Times Introduction
    url: https://thebestoftimes.moddinglinked.com/intro.html
    sectionPath: Requirements and TTW description
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# TTW runs Fallout 3 content inside the New Vegas runtime

TTW is not a Fallout 3 mod manager profile and not a FOSE runtime.
It rebuilds a combined setup for Fallout: New Vegas, so runtime tooling follows the New Vegas stack: xNVSE, New Vegas patchers, and FNV-compatible native plugins.

When classifying a TTW issue, ask whether the target is standalone Fallout 3 or Fallout 3 content after conversion into the New Vegas engine.

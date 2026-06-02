---
id: tooling-mo2.profile-plugins-modlist-truth-surfaces.v1
title: MO2 profile plugins.txt and modlist.txt are the authoritative harness truth surfaces
domains: [load-order, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: In this harness, the Default profile's plugins.txt and modlist.txt are the first places to inspect when xEdit sees unexpected plugins, missing plugins, or the wrong runtime state.
  confidence: verified-project-doc
queryKeys: [MO2 profile, plugins.txt, modlist.txt, Default profile, harness drift]
severity: high
sources:
  - kind: project-internal-doc
    ref: .opencode/memory/30-mo2-harness-hygiene.md
    sectionPath: Rules
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# MO2 profile plugins.txt and modlist.txt are the authoritative harness truth surfaces

When runtime evidence disagrees with expectation, check the MO2 profile before blaming xEdit code.
The active plugin list and enabled mod folders define what the harness intended to project.

In the dedicated FO4 harness, the Default profile is intentionally low-noise, so drift is often easy to spot.
Leading activation markers, disabled entries, and mod folder enablement all matter.

This record should surface when a plugin appears missing or unexpectedly loaded.

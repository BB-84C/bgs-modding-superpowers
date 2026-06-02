---
id: nvse-fose.fose-is-fallout3-extender.v1
title: FOSE is the Fallout 3 script extender and has its own runtime limits
domains: [engine, install-planning, version-differences]
appliesTo:
  games: [Fallout3]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: FOSE extends Fallout 3 scripting and targets specific Fallout 3 executable and GECK versions; it is not the New Vegas xNVSE runtime.
  confidence: verified-official
queryKeys: [FOSE, Fallout Script Extender, Fallout3.exe, FO3 runtime, GFWL]
severity: critical
sources:
  - kind: official
    ref: FOSE silverlock page
    url: https://fose.silverlock.org/
    sectionPath: Compatibility and supported versions
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# FOSE is the Fallout 3 script extender and has its own runtime limits

FOSE is the Fallout 3 extender line and documents supported Fallout 3 and GECK builds on its own download page.
Its compatibility constraints include executable build and storefront details, so a modpack should record the exact FO3 runtime being targeted.

Do not route Fallout: New Vegas xNVSE advice into a Fallout 3-only setup unless TTW has intentionally moved the content into the New Vegas runtime.

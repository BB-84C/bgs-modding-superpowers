---
id: skyrim-vr.skyuivr-mcm-fork.v1
title: Skyrim VR uses the SkyUI VR fork for MCM support
domains: [game-specific.vr, install-planning]
appliesTo:
  games: [SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "SkyUI VR is a working port of SkyUI and MCM for Skyrim VR, and its page requires SKSE VR including the PEX files."
  confidence: verified-tooling
queryKeys: [SkyUI VR, SkyUIVR, MCM, SKSEVR pex]
severity: high
sources:
  - kind: tooling-docs
    ref: Odie skyui-vr GitHub
    url: https://github.com/Odie/skyui-vr
    sectionPath: README; Releases
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Skyrim VR uses the SkyUI VR fork for MCM support

Flat Skyrim SkyUI and Skyrim VR UI are not interchangeable assumptions.
SkyUI VR is a fork/port that carries SkyUI and MCM into the VR runtime.

Its README notes SKSE VR as a prerequisite, including the PEX files.
Missing those scripts can look like broken MCM registration rather than a UI asset conflict.

For VR, prefer the VR fork unless a mod explicitly documents another supported UI path.

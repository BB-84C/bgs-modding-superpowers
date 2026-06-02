---
id: skyrim-ui.enbseries-se-dx11-profile-layer.v1
title: Skyrim SE ENB is a DX11 post-process layer, not a SkyUI patch
domains: [engine, file-conflicts, install-planning]
appliesTo:
  games: [SkyrimSE, SkyrimAE]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "ENBSeries for Skyrim SE is a DX11 post-process layer with its own preset/config files, so ENB troubleshooting should be separated from SkyUI/MCM troubleshooting."
  confidence: high
queryKeys: [ENBSeries Skyrim SE, DX11, SkyUI compatibility, enbseries.ini]
severity: medium
sources:
  - kind: community-forum
    ref: ENBSeries Skyrim SE page
    url: http://enbdev.com/download_mod_tesskyrimse.html
    sectionPath: Description; version notes
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Skyrim SE ENB is a DX11 post-process layer, not a SkyUI patch

ENBSeries modifies rendering; SkyUI modifies interface menus.
They can both affect what the player sees, but they live in different layers.

The ENB page distinguishes Skyrim SE's DX11 shader path from old Skyrim's DX9 path and notes that presets/configuration are separate.
When UI menus fail, do not blame ENB first unless the symptom is rendering/overlay-specific.

When visuals fail, test with the ENB layer disabled before changing SkyUI or MCM scripts.

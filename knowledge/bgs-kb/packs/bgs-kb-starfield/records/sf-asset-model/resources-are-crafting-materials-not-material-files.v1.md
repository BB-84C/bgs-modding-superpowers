---
id: sf-asset-model.resources-are-crafting-materials-not-material-files.v1
title: Starfield resources are gameplay materials, not proof of material-file format
domains: [engine, install-planning]
appliesTo:
  games: [Starfield]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV]
canonical:
  answer: Starfield Wiki documents resources/materials as collected crafting and research items, but that is not the same thing as documenting Starfield's asset material-file format.
  confidence: high
queryKeys: [Starfield resources, materials, crafting materials, material file format]
severity: medium
sources:
  - kind: wiki
    url: "https://starfieldwiki.net/wiki/Starfield:Resources"
    ref: Starfield Wiki Resources
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Starfield resources are gameplay materials, not proof of material-file format

The Starfield Wiki page reached from “Materials” describes resources used for crafting, research, extraction, and manufacturing.
That is useful gameplay knowledge, but it does not document the engine's asset material-file schema.

For asset pipeline records, do not cite gameplay resources as material-file evidence.
If material-file details are needed, require a tool or CK2-specific source.

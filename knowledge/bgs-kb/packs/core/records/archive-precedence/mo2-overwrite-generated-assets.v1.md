---
id: archive-precedence.mo2-overwrite-generated-assets.v1
title: MO2 Overwrite generated assets can override normal mod files
domains: [archive-precedence, file-conflicts, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV]
  engineFamilies: [gamebryo, creation-engine]
canonical:
  answer: Generated files left in MO2 Overwrite participate in the virtual file system and can win file conflicts over normal mod folders, so generated outputs must be inspected during asset-precedence debugging.
  confidence: verified-tooling
queryKeys: [MO2 Overwrite, generated assets, Nemesis, FNIS, FaceGen, generated files]
severity: critical
sources:
  - kind: tooling-docs
    url: "https://github.com/ModOrganizer2/modorganizer/wiki"
    ref: Mod Organizer 2 wiki
  - kind: wiki
    url: "https://stepmodifications.org/wiki/Main_Page"
    ref: STEP Wiki
related: [archive-precedence.loose-over-archive.v1, load-order.mo2-left-pane-vs-right-pane.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# MO2 Overwrite generated assets can override normal mod files

Tools such as Nemesis, FNIS, xLODGen-style generators, and FaceGen workflows can emit files into MO2's Overwrite area.
Those files are still part of the virtualized file view and can beat assets from installed mods depending on placement.

When behavior, face, mesh, texture, or LOD output looks stale, inspect Overwrite before changing plugin order.
Move durable generated output into a named mod so the winning layer is visible and reviewable.

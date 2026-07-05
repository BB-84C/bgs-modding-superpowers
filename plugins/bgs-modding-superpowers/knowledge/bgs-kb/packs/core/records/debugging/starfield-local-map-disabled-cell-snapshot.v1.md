---
id: debugging.starfield-local-map-disabled-cell-snapshot.v1
title: Starfield greyed local-map buttons can indicate a stale winning CELL snapshot
kind: gotcha
domains: [debugging, plugin-format, file-conflicts]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: "If a Starfield city local/surface-map button is greyed out, opens only planet preview, or loses city-map structure after adding mods, inspect the winning CELL override for missing SFBGS008/BGSCityMapsUsage component data. A pre-1.11.36 stale CELL snapshot can win the conflict and erase the city-map header data; load-ordering a complete post-update participant to win may fix it without a patch."
  confidence: verified-project-doc
queryKeys:
  - local map greyed out
  - surface map disabled
  - city map button grey
  - BGSCityMapsUsage missing
  - SFBGS008 city map
  - stale CELL winner
  - Cydonia local map
severity: high
sources:
  - kind: github-issue
    ref: Starfield Community Patch issue #967, The Well local map disabled by CELL header conflict
    url: https://github.com/Starfield-Community-Patch/Starfield-Community-Patch/issues/967
  - kind: tooling-docs
    ref: Starfield Community Patch changelog v0.1.4/v0.1.6/v0.1.7
    url: https://www.starfieldpatch.dev/changelog
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/wave3-investigations/WAVE5-LANE-W-CELL-FIELDS-WEB-REPORT.md
    sectionPath: BB84 Cydonia local map field test
related:
  - plugin-format.starfield-cell-header-post-1-11-36-fields.v1
  - file-conflicts.starfield-cell-conflict-triage.v1
lastReviewed: "2026-07-05"
schemaVersion: 1
---

# Starfield greyed local-map buttons can indicate a stale winning CELL snapshot

## Symptom

After adding or reordering mods, a city local/surface map may fail in a narrow way: the local map button is greyed out, pressing the map key shows only the planet preview, or the expected 3D city map structure does not load. This is not necessarily a UI mod or keybind problem.

## Likely root-cause class

For Starfield city cells, treat this as a CELL header conflict until disproved. The May 2024 city-map update added SFBGS008 city map data. A mod made before that update can carry an older CELL header snapshot. If that stale snapshot wins, the CELL may lose `BGSCityMapsUsage_Component` data and the local-map system has no city map component to load.

Public SFCP issue #967 shows the same class for The Well: a CELL header edit interacted with Bethesda's newly-added local-map data and broke the local map.

## Diagnosis

1. Identify the city or CELL FormID behind the failing local map.
2. In xEdit, inspect the winning CELL override and compare it with the latest official/post-update participant.
3. Look specifically for SFBGS008/city-map component data and other post-update header fields.
4. Check whether the winner also has suspiciously low traversal count compared with vanilla/post-update data; that strengthens the stale-snapshot diagnosis.
5. Prefer moving the most complete post-update participant to win before authoring a patch.

## BB84 Cydonia example

In BB84's Cydonia test, `CityCydoniaMainLevel [CELL:002B3DA2]` had a dense multi-ESM conflict. With a stale snapshot winning, the surface map failed and map input fell back to planet preview. Letting a post-update participant with complete city-map/traversal data win restored the 3D local map display.

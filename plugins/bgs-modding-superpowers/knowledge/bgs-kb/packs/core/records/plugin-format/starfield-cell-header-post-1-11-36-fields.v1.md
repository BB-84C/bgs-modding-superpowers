---
id: plugin-format.starfield-cell-header-post-1-11-36-fields.v1
title: Starfield post-1.11.36 CELL headers carry city-map, traversal, gravity, IS-volume, and global-layer fields
kind: rule
domains: [plugin-format, xedit, debugging]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: "Starfield's May 2024 update and SFBGS008 city-map data added or activated load-bearing CELL header fields. A pre-update CELL override is a stale snapshot: if it wins, it can erase city-map components, traversal data, gravity inheritance, image-space volume criteria, or global-layer visuals even when the mod never meant to touch those systems."
  confidence: verified-project-doc
queryKeys:
  - Starfield CELL header
  - SFBGS008 city maps
  - BGSCityMapsUsage_Component
  - XTV2 Traversals
  - Use Planet Gravity
  - Use IS Volumes Interior Criteria
  - XCGD Global Dirt Layer
  - stale cell snapshot
severity: critical
sources:
  - kind: github-issue
    ref: Starfield Community Patch issue #967
    url: https://github.com/Starfield-Community-Patch/Starfield-Community-Patch/issues/967
  - kind: official
    ref: Steam Starfield Creation Kit Guide, Draw Traversal / Post Effect Volume sections
    url: https://steamcommunity.com/sharedfiles/filedetails/?id=3385012985
  - kind: github-issue
    ref: Spriggit issue #95, Starfield navmesh serialization limitations
    url: https://github.com/Mutagen-Modding/Spriggit/issues/95
  - kind: tooling-docs
    ref: SFSE and CommonLibSF public headers for BGSTraversal, BGSCityMapsUsageComponent, and ExtraCellGlobalDirtLayer identifiers
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/wave3-investigations/WAVE5-LANE-W-CELL-FIELDS-WEB-REPORT.md
    sectionPath: public-source synthesis and BB84 Cydonia readback
related:
  - file-conflicts.starfield-cell-conflict-triage.v1
  - debugging.starfield-local-map-disabled-cell-snapshot.v1
lastReviewed: "2026-07-05"
schemaVersion: 1
---

# Starfield post-1.11.36 CELL header fields

## Why stale CELL overrides are dangerous

The 2024-05 Starfield update line (`1.11.33` / `1.11.36`) introduced official surface and city map data through `SFBGS008.esm`. Public SFCP issue and changelog history show that old CELL header edits could break The Well's local map even when the patch tried to forward the new map data manually. That makes pre-update CELL overrides a special conflict class: they are not simply older values, they are stale snapshots of a header shape that Bethesda later extended.

When a stale CELL override wins, it can roll back systems the mod author never intended to touch.

## Five fields to recognize

| Field / concept | Meaning | Loss symptom | Merge posture |
|---|---|---|---|
| `XTV2` Traversals | Off-mesh / animated pathing connections over navmesh for jumps, jetpack, climbing, ladders, doorways, buttons, and similar special routes. CK public docs expose `Draw Traversal`; SFSE/CommonLibSF expose traversal runtime types. | NPCs lose special pathing, get stuck near edges, route around, fail to follow, or become stranded without a direct error. | Do not xEdit-union blobs. Prefer the most complete participant or CK regeneration. |
| `BGSCityMapsUsage_Component` | SFBGS008 city-map component telling the local-map system which city map data to use for a CELL. | Local/surface map button greyed out or opens only planet preview; city vendor/ship markers may not render in that local map. | Must be carried by winner; CK-resaved cell is safer than manual component stitching. |
| `Use IS Volumes Interior Criteria` | ImageSpace volume / interior-criteria behavior for post-effect and reflection-volume boundaries; public CK docs describe ImageSpace volumes and interior criteria. | Post-process or reflection boundaries can leak, fade incorrectly, or treat interior spaces wrongly; community editor testing also treats this as potentially relevant to cloth-wind/interior classification. | Usually preserve winner or lighting-authoritative participant; observe in-game. |
| `XCLL` Gravity Scale + `DATA` bit 17 | Cell gravity scale plus planet-gravity inheritance; SFCP issue #967 identifies the unknown flag as planet-gravity inheritance. | Jump/fall/physics feel wrong for the planet or interior; not usually a CTD or quest breaker. | Evaluate with city-map component because SFCP saw gravity fixes interfere with city-map data. |
| `XCGD` Global Dirt Layer | Cell/interior global-layer material for biome dust, sand, dirt, snow, or similar coverage; SFSE public headers expose `ExtraCellGlobalDirtLayer`, and public CK material docs describe Global Layer concepts. | Visual biome layer wrong or missing: e.g. Cydonia/Mars surfaces look too clean or wrong. | Low-risk visual auto-forward candidate. |

## Count-based traversal sanity check

Traversal counts are a useful triage signal. A post-update or geometry-aware participant that has roughly vanilla traversal count plus a small delta is likely preserving the base navigation graph and adding its own edges. A participant with a count far below vanilla is a dangerous stale snapshot unless the mod intentionally rebuilt the cell geometry.

BB84's Cydonia case showed the pattern on `CityCydoniaMainLevel [CELL:002B3DA2]`: vanilla carried about 20,874 traversals, a post-update participant carried about 21,100, while a stale conflict participant carried about 1,264. Letting the stale snapshot win would discard most traversal data.

## Field validation example

In BB84's Cydonia 12-ESM conflict, a stale winning CELL snapshot made the surface/local-map button grey or fall back to planet preview. Moving the participant that carried the complete post-update fields to the winner restored the three-dimensional local city map. That is the expected symptom and recovery shape for missing city-map component data.

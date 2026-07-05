---
id: file-conflicts.starfield-cell-conflict-triage.v1
title: Triage Starfield CELL conflicts by field class before building patches
kind: workflow
domains: [file-conflicts, plugin-format, xedit, load-order]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: "Do not build a full load-order-wide Starfield CELL/world patch by default. Triage each affected city or CELL by acceptance symptoms, prefer load-order-first selection of the most complete post-update participant, auto-forward only low-risk scalar/visual fields, and reserve CK-resaved patches for XTV2/city-map component cases that load order cannot solve."
  confidence: verified-project-doc
queryKeys:
  - Starfield CELL conflict triage
  - city map component forward
  - XTV2 traversal merge
  - CK resave cell
  - full cell patch
  - load order first
  - local map acceptance
severity: high
sources:
  - kind: github-issue
    ref: Starfield Community Patch issue #967
    url: https://github.com/Starfield-Community-Patch/Starfield-Community-Patch/issues/967
  - kind: tooling-docs
    ref: Starfield Community Patch changelog v0.1.4/v0.1.6/v0.1.7
    url: https://www.starfieldpatch.dev/changelog
  - kind: github-issue
    ref: Spriggit issue #95, malformed Starfield navmesh serialization
    url: https://github.com/Mutagen-Modding/Spriggit/issues/95
  - kind: official
    ref: Steam Starfield Creation Kit Guide, Draw Traversal and Post Effect Volume sections
    url: https://steamcommunity.com/sharedfiles/filedetails/?id=3385012985
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/wave3-investigations/WAVE5-LANE-W-CELL-FIELDS-WEB-REPORT.md
    sectionPath: targeted patch strategy and Cydonia field readback
related:
  - plugin-format.starfield-cell-header-post-1-11-36-fields.v1
  - debugging.starfield-local-map-disabled-cell-snapshot.v1
lastReviewed: "2026-07-05"
schemaVersion: 1
---

# Triage Starfield CELL conflicts by field class

## Default stance

Starfield CELL/world conflicts are common in large modpacks, but that does not make a universal compatibility patch the right first move. SFCP's public history around The Well is the warning: manual xEdit forwarding of newly-added CELL header data was not enough, a later CK remake was needed, and a gravity fix was later reverted because it interfered with city maps.

Use targeted acceptance and load-order selection before authoring patches.

## Three field classes

### 1. Auto-forward candidates

Forward low-risk scalar or visual data when a real conflict needs it:

- `XCGD` / global dirt layer and similar visual material fields;
- classic scalar or simple subrecords where xEdit already displays stable structure;
- ImageSpace/interior-criteria flags only when the chosen lighting/cell winner is otherwise correct.

These are not reasons to create a full world patch by themselves.

### 2. Whole-record / CK-resave candidates

Do not hand-stitch these field families in xEdit as if they were independent rows:

- `XTV2` traversal blobs and related navmesh-derived data;
- `BGSCityMapsUsage_Component` / SFBGS008 city-map component data.

For these, prefer the participant that already carries the complete post-update snapshot. If no single participant has all required edits and fields, use the Creation Kit to load the selected inputs and resave the affected cell into a dedicated patch. Public tooling history supports this caution: Spriggit has had trouble serializing malformed Starfield navmesh data, and SFCP's manual city-map forward was not reliable enough.

### 3. Manual + in-game validation

Gravity inheritance and gravity scale need both record readback and feel testing. They can be coupled with the city-map component in the header, so a seemingly isolated gravity correction can break local maps. Validate local map and movement feel together.

## Load-order-first resolution

Many CELL conflicts can be solved without a patch by making the most complete participant win. In BB84's Cydonia case, moving the post-update participant with complete city-map/traversal fields to the winner restored the local map at zero patch cost. That is preferable to manufacturing a brittle merged CELL override.

Patch only when load order cannot satisfy both sides of the conflict.

## Targeted acceptance checklist

For a city or important CELL, use a three-item in-game acceptance gate:

1. Can the local/surface map open and show the expected 3D city structure?
2. Does gravity/jump/fall feel match the location and planet expectation?
3. Do NPCs path through expected jumps, ledges, doorways, ladders, and routes without getting stranded?

If all three pass, do not patch that CELL just because xEdit shows many participants. If one fails, inspect the current winning CELL for stale post-1.11.36 header fields and choose either load-order-first winner selection or a targeted CK-resaved patch.

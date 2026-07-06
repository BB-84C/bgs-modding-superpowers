---
id: debugging.navmesh-conflict-signature.v1
title: NPCs missing or stuck in one area are a navmesh conflict signature
kind: gotcha
domains: [debugging, xedit, load-order]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
canonical:
  answer: "If NPCs disappear, stand still, or cannot walk inside a specific edited area, audit NAVM conflicts: the winning navmesh override fully replaces loser navigation data for that cell or area."
  confidence: verified-project-doc
queryKeys: [navmesh, NAVM, NPC missing, NPC stuck, pathing conflict, Bethesda nav]
severity: high
sources:
  - kind: project-internal-doc
    ref: BB84 Lane 3 audit synthesis
    sectionPath: navmesh conflict signature
related: [load-order.cross-cutting-record-audit.v1]
lastReviewed: "2026-06-29"
schemaVersion: 1
---

# NPCs missing or stuck in one area are a navmesh conflict signature

Area-local NPC disappearance, frozen AI movement, or actors unable to enter a building is a classic `NAVM` conflict signal. The problem may not be a missing script or disabled quest: the winning navmesh can completely hide loser navigation changes in the same cell or area.

Diagnose by listing `NAVM` records, grouping by location/cell and FormID, then inspecting conflicts on the overlapping records. If one mod adds or adjusts navigation that loses to another complete override, NPCs controlled by the loser-side content may have no valid pathing data.

Resolution options are load-order reordering after side-effect review, a hand-merged xEdit navmesh patch, or an existing community compatibility patch. Do not blindly move one plugin later without checking what the other plugin's navmesh edits lose.

Reference case: Stroud Premium and Settled Systems Shuttle Service-style conflicts can make whichever building's navmesh loses appear unwalkable; similar signatures were later identified in other city/POI overlaps.

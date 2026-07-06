---
id: load-order.cross-cutting-record-audit.v1
title: Cross-cutting silent-loser record types need dedicated audits
kind: workflow
domains: [load-order, xedit, file-conflicts]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
canonical:
  answer: "Some record classes are silent losers: the losing override hides added content or behavior without an obvious broken master warning, so scan PNDT, NAVM, hidden PERK, GLOB, and similar shared classes across the whole load order instead of only inside feature clusters."
  confidence: verified-project-doc
queryKeys: [silent loser, cross-cutting audit, PNDT, NAVM, PERK, GLOB, hidden conflict]
severity: high
sources:
  - kind: project-internal-doc
    ref: BB84 Lane 3 audit synthesis
    sectionPath: cross-cutting record audits
related: [debugging.navmesh-conflict-signature.v1]
lastReviewed: "2026-06-29"
schemaVersion: 1
---

# Cross-cutting silent-loser record types need dedicated audits

Cluster-by-cluster conflict review can miss record classes that many unrelated mods touch. These classes become silent losers: the game still loads, but losing overrides hide newly added content, values, or navigation from the winning record.

Typical classes include `PNDT` / planet records where loser POIs vanish from the UI, `NAVM` where NPC pathing fails, hidden/script-effect `PERK` records that change behavior without visible perks, and `GLOB` values that quietly set shared numerical state.

Audit the class directly across the load order: list records by signature, group by FormID, filter groups with multiple override providers, then inspect conflicts deeply enough to identify whether the loser added meaningful content or only repeated inherited data.

Example xEdit MCP shape: `xedit_call('records.list', { signature: '<TYPE>' })`, followed by conflict inspection on multi-provider FormIDs.

Reference case: Starfield planet records such as JaffaII, Mars, and Akila showed high-risk loser behavior where POI additions could be hidden by a later winner.

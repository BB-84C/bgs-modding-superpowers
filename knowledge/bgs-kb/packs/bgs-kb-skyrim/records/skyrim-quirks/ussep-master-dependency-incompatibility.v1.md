---
id: skyrim-quirks.ussep-master-dependency-incompatibility.v1
title: USSEP can be both a baseline fix pack and a compatibility boundary
domains: [install-planning, load-order]
appliesTo:
  games: [SkyrimSE, SkyrimAE]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Many Skyrim SE mods assume USSEP, but USSEP also changes records and runtime expectations, so non-USSEP modlists need explicit compatibility review."
  confidence: high
queryKeys: [USSEP requirement, unofficial patch incompatibility, Skyrim baseline]
severity: medium
sources:
  - kind: community-forum
    ref: AFK Mods USSEP page
    url: https://www.afkmods.com/index.php?/files/file/1888-unofficial-skyrim-special-edition-patch/
    sectionPath: Description
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# USSEP can be both a baseline fix pack and a compatibility boundary

USSEP's broad bugfix scope makes it a common baseline dependency.
That same scope means it can change records other mods touch.

When a mod requires USSEP, removing it is not just removing a patch; it can break masters and assumptions.
When a modlist intentionally avoids USSEP, every USSEP-dependent plugin needs replacement or patching.

Treat USSEP policy as a top-level modlist decision.

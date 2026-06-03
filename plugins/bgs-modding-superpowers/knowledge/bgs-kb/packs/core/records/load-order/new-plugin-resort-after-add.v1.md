---
id: load-order.new-plugin-resort-after-add.v1
title: Adding a new plugin often requires a sort or deliberate placement review
domains: [load-order, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: A newly added plugin should not be left at the bottom by accident; run LOOT or deliberately place it based on masters, author guidance, and conflict readback.
  confidence: verified-project-doc
queryKeys: [new plugin added, append plugin, resort load order, bottom wins, install new mod]
severity: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Six operations the agent does most often
  - kind: tooling-docs
    url: "https://loot.readthedocs.io/"
    ref: LOOT documentation
seeAlso: [load-order.loot-sort-vs-manual-order.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Adding a new plugin often requires a sort or deliberate placement review

Appending a new active plugin at the bottom makes it load late, which can make it win conflicts unintentionally.
That is safe only when late placement is actually desired.

After adding a plugin, check its required masters, run a normal sorter when appropriate, and inspect important conflicts if the mod changes shared records.
If a curated guide or mod author requires a manual position, preserve that placement with a note instead of treating LOOT as the only authority.

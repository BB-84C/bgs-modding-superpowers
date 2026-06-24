---
id: fnv-conflicts.leveled-list-and-npc-overhaul-patterns.v1
title: Leveled-list and NPC-overhaul conflict patterns in Fallout 3 and New Vegas
kind: explanation
domains: [file-conflicts, load-order, install-planning]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: Automated merges can combine Fallout 3 and New Vegas leveled-list edits structurally, but human review is still required for item-distribution coherence and NPC face/race/voice winners.
  confidence: high
queryKeys: [FNV leveled list conflicts, FO3 NPC overhaul conflicts, Bashed Patch, smashed patch, NPC face conflict]
severity: high
sources:
  - kind: community-forum
    ref: Viva New Vegas guide
    url: https://vivanewvegas.moddinglinked.com/
    sectionPath: Conflict resolution and final steps
  - kind: community-forum
    ref: Tale of Two Wastelands site
    url: https://taleoftwowastelands.com/
    sectionPath: Mod compatibility guidance
  - kind: project-internal-doc
    ref: BB84 corpus Q16 leveled-list manual-review note
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Leveled-list and NPC-overhaul conflict patterns in Fallout 3 and New Vegas

## Perspective: OBJECTIVE

Leveled-list conflicts are a silent failure mode. A bad merge usually does not crash Fallout 3, New Vegas, or TTW; it simply makes weapons, outfits, loot, or creatures fail to appear as intended. Automated merge tools can resolve structural conflicts such as two plugins editing the same list, but they do not understand the intended economy, faction equipment language, or region balance. NPC overhaul conflicts have the same shape: the winning record may combine face, race, voice, outfit, AI package, or quest edits in a way no author intended.

The safe workflow is to inspect all LL and NPC edits in xEdit, generate any automated merge only as a starting point, then hand-author final winners where semantics matter. TTW increases the stakes because Fallout 3 content is running inside the New Vegas ecosystem; a Mojave overhaul can accidentally contaminate Capital Wasteland distribution if patches are lazy.

## Perspective: SUBJECTIVE — BB84 curator reference (not a universal rubric)

BB84's curator reference treats heavy leveled-list overhauls as "custom patch plus human review required." His WL2 practice of maintaining many Complex Sorter/INNR rule mods illustrates the discipline: classification, naming, item distribution, and final list winners are part of curation, not afterthought cleanup. Another curator may choose a lighter stack, but once the pack includes many distribution edits, BB84's view is that semantic coherence cannot be outsourced to an automatic patcher.

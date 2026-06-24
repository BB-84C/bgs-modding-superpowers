---
id: pack-curation.leveled-list-overhaul-coherence-discipline.v1
title: Heavy LL-modification packs require a hand-authored coherence patch
kind: rule
domains: [install-planning, file-conflicts, xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "Leveled-list merging tools resolve structural conflicts, not semantic coherence; heavy LL-modification packs must ship a curator-authored patch deciding actual equipment, loot, and spawn logic."
  confidence: high
queryKeys: [leveled list, coherence patch, Bashed Patch, Smashed Patch, xEdit, loot distribution]
severity: high
sources:
  - kind: project-internal-doc
    ref: "BB84 corpus Q16 verbatim point 3, explicit 不能完全机械化 manual-review requirement"
  - kind: project-internal-doc
    ref: "BB84 WL2 recon: Complex Sorter rule mods and 4estGimp INNR series"
  - kind: tooling-docs
    url: "https://wrye-bash.github.io/docs/Wrye%20Bash%20General%20Readme.html"
    ref: "Wrye Bash documentation"
  - kind: tooling-docs
    url: "https://tes5edit.github.io/docs/"
    ref: "xEdit documentation"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Heavy LL-modification packs require a hand-authored coherence patch

Leveled-list failures are dangerous because they are silent. The game usually does not crash when the wrong items disappear, a faction spawns with incoherent equipment, or rare loot floods the economy. The world simply becomes wrong. Automated tools such as Bashed Patch or Smashed Patch are useful, but they answer a structural question: how can entries from multiple plugins be combined without losing rows? They do not answer the semantic question: what should this world distribute, to whom, at what rate, and why?

BB84 Q16 point 3 is quoted in the spec as "不能完全机械化". That is the core rule. Curators can use automation to surface and merge data, but a heavy leveled-list pack still needs human review. The curator must decide whether a raider should carry pipe weapons, modern tactical rifles, faction-specific gear, regional variants, or no injected gear at all. The same applies to creature spawns, vendor lists, loot tiers, ammunition economy, and outfit distribution.

The discipline is straightforward. Identify all mods touching LL records in xEdit. Generate any automated merge as a starting substrate, not as final truth. Decide the intended distribution semantics for the pack. Then author a coherence patch ESP that overrides the generated output where world logic matters. Test in real sessions, because short smoke tests rarely reveal missing loot or bad spawn balance.

BB84's WL2 evidence illustrates the practice: Complex Sorter rule mods and 4estGimp INNR-series classification work encode human decisions about item identity and distribution. The point is not to copy those exact rules; the point is that a serious LL overhaul needs an authored coherence layer.

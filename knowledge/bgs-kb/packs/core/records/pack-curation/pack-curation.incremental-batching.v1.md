---
id: install-planning.pack-curation.incremental-batching.v1
title: Build BGS modpacks in named, reversible batches after declaring 风格
domains: [install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: Declare the pack's 风格 first, then add mods in coherent named batches with rollback boundaries, attribution, and devlog notes; stability is the floor, not the finish line.
  confidence: high
queryKeys: [pack curation, incremental batching, rollback boundary, modpack 风格, separator naming, devlog discipline, modpack planning]
severity: medium
sources:
  - kind: project-internal-doc
    ref: BB84 E12 整合搭建 transcript + 废土蓝调 intro/devlog source extraction
related: [mod-evaluation.systemic-design-fit.v1, mod-evaluation.quality-and-risk-signals.v1]
lastReviewed: "2026-06-23"
schemaVersion: 1
---

# Build BGS modpacks in named, reversible batches after declaring 风格

A BGS modpack is curated around a declared 风格, not around a raw count of impressive mods. Stability is required, but a stable pack is only at the floor; the pack still needs a coherent world style that explains why each layer exists.

Add mods in batches that express one role at a time: framework, world/content, mechanics, visuals, translation, optimization, compatibility patches, or testing/proof. Each batch should be named so future-you can recognize its purpose and small enough that the rollback boundary is real.

For diagnosis, a recent coherent batch can be disabled or split before resorting to broader binary search. This does not mean every mod can be casually removed: script-heavy or save-touching mods may not disable cleanly, so their rollback boundary should be planned before they enter a real playthrough.

Naming and separator discipline are part of the technical system. Patch names should preserve parent relationships, local archive names should match mod-manager names, and attribution should preserve author/source/translator information. The devlog should record why a batch exists, what risks it carries, and what later batches must now do differently.

Game-specific scale facts — archive ceilings, animation/behavior ecosystems, precombine/previs, Starfield toolchain drift — belong in per-game KB records and should be queried before sizing risky batches.

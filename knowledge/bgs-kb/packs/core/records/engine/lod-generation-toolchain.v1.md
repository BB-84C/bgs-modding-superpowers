---
id: engine.lod-generation-toolchain.v1
title: LOD generation is a toolchain output, not a plugin-order side effect
domains: [engine, file-conflicts, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR]
  engineFamilies: [creation-engine]
canonical:
  answer: Distant terrain, object, tree, texture, and occlusion output comes from LOD generation tools such as xLODGen, TexGen, and DynDOLOD; sorting plugins alone does not regenerate those assets.
  confidence: verified-tooling
queryKeys: [DynDOLOD, xLODGen, TexGen, LOD generation, occlusion]
severity: high
sources:
  - kind: tooling-docs
    url: "https://dyndolod.info/"
    ref: DynDOLOD documentation
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# LOD generation is a toolchain output, not a plugin-order side effect

LOD output is generated from the finalized mod and load-order state.
DynDOLOD documentation describes a pipeline that includes terrain LOD with xLODGen, texture/object assets with TexGen, and final LOD patch generation with DynDOLOD.

If distant objects, trees, terrain, or occlusion are wrong, check whether generated output is stale or missing.
Changing plugin order may be a prerequisite, but it is not itself LOD regeneration.

---
id: engine.persistent-vs-temporary-references.v1
title: Persistent and temporary references have different runtime loading responsibilities
domains: [engine, plugin-format, xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: Bethesda plugins distinguish references that must remain addressable across runtime state from temporary references that are loaded with cells, so reference persistence affects FormID planning and cell behavior.
  confidence: high
queryKeys: [persistent reference, temporary reference, REFR, cell loading, FormID]
severity: high
sources:
  - kind: tooling-docs
    url: "https://tes5edit.github.io/docs/"
    ref: Tome of xEdit
  - kind: wiki
    url: "https://ck.uesp.net/wiki/Main_Page"
    ref: Creation Kit Wiki UESP mirror
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Persistent and temporary references have different runtime loading responsibilities

References are not all equal just because they appear as placed objects.
Persistent references need stable addressability outside normal cell streaming; temporary references are generally tied to cell loading.

That distinction matters when moving objects, compacting plugins, or diagnosing scripts and quests that hold references.
Agents should inspect persistence flags and cell placement before assuming a reference can be treated as disposable geometry.

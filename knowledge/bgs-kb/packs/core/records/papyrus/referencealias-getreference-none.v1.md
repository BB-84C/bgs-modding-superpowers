---
id: papyrus.referencealias-getreference-none.v1
title: ReferenceAlias.GetReference can return None
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: ReferenceAlias.GetReference returns the alias target or None if the alias has not resolved to a reference, so alias scripts need defensive None checks before using the result.
  confidence: verified-tooling
queryKeys: [GetReference, ReferenceAlias, None check, unloaded alias, GetRef]
severity: high
sources:
  - kind: wiki
    ref: Creation Kit Wiki GetReference - ReferenceAlias
    url: https://ck.uesp.net/wiki/GetReference_-_ReferenceAlias
    sectionPath: Return Value
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# ReferenceAlias.GetReference can return None

Alias scripts should treat `GetReference()` as a nullable lookup.
The CK page says it returns `None` when the alias has not resolved to a reference.

This is a common failure pattern when quest aliases are optional, conditional, or not yet filled.
Cast only after checking the result.

If the reference is expected but absent, debug alias fill conditions before blaming the script body.

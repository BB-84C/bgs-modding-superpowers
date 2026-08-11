---
id: xedit.foreign-formid-local-space-resolution.v1
title: Resolve foreign FormIDs from their owner before walking to a target override
kind: gotcha
domains: [xedit, plugin-format, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "Legacy RecordByFormID(file, formId) resolves in the supplied file's local master space and can return a wrong-but-valid record for a foreign load-order FormID. On automation contract 0.23, prefer RecordByFormIDStrict(file, formId, allowInjected): it resolves through the FormID owner and returns nil unless that owner is the target file or one of its masters. Still verify file and signature before mutation."
  confidence: verified-project-doc
queryKeys: [RecordByFormIDStrict, RecordByFormID foreign FormID, local FormID space, WinningOverride, wrong record, FormID master index]
severity: critical
sources:
  - kind: github-issue
    url: "https://github.com/BB-84C/bgs-modding-superpowers/issues/29"
    ref: "Issue #29: xEdit local FormID-space investigation"
    sectionPath: "2. RecordByFormID(file, formID) resolves in the target file local FormID space"
  - kind: github-issue
    url: "https://github.com/BB-84C/TES5Edit/issues/7"
    ref: "Upstream strict FormID resolver acceptance"
related:
  - xedit.formid-prefix-stripping.v1
  - xedit.find-by-formid-vs-editorid.v1
  - xedit.safe-linked-record-and-nonascii-inspection.v1
lastReviewed: "2026-08-11"
schemaVersion: 1
---

# Resolve foreign FormIDs from their owner before walking to a target override

`RecordByFormID(file, formId, True)` does not treat `formId` as a globally absolute lookup. It resolves the ID in the `file` argument's local master space. In the verified incident, using a FormID whose high byte belonged to a different plugin with the target patch file returned a same-low-bytes record owned by the target file, not `nil`.

On automation contract 0.23, use
`RecordByFormIDStrict(file, formId, allowInjected)` when the input FormID is in
load-order space. It resolves through the owning file and returns `nil` when the
owner is neither the supplied target nor one of its masters. Legacy
`RecordByFormID` remains unchanged.

The safe sequence is:

1. Identify the plugin that owns the source FormID.
2. Prefer `RecordByFormIDStrict` when contract 0.23 is available; otherwise call
   legacy `RecordByFormID` with the owning file rather than the target patch.
3. Walk to `WinningOverride` if the operation needs the load-order winner.
4. Confirm both `GetFileName(GetFile(record))` and the expected signature before reading or mutating a child path.

An empty child path after a seemingly valid lookup is not proof the target data is absent. Check record identity first; a foreign-ID local-space collision can turn an intended outfit lookup into an unrelated `ARMO` or other record without raising an error.

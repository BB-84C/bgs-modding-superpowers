---
id: xedit.foreign-formid-local-space-resolution.v1
title: Resolve foreign FormIDs from their owner before walking to a target override
kind: gotcha
domains: [xedit, plugin-format, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: RecordByFormID(file, formId) resolves form IDs in the supplied file's local master space. Passing a foreign load-order FormID with the target patch file can silently recombine its low bytes into a different target-file record; resolve from the owning master first, then use WinningOverride and verify the resulting file and signature.
  confidence: verified-project-doc
queryKeys: [RecordByFormID foreign FormID, local FormID space, WinningOverride, wrong record, FormID master index]
severity: critical
sources:
  - kind: github-issue
    url: "https://github.com/BB-84C/bgs-modding-superpowers/issues/29"
    ref: "Issue #29: xEdit local FormID-space investigation"
    sectionPath: "2. RecordByFormID(file, formID) resolves in the target file local FormID space"
related:
  - xedit.formid-prefix-stripping.v1
  - xedit.find-by-formid-vs-editorid.v1
  - xedit.safe-linked-record-and-nonascii-inspection.v1
lastReviewed: "2026-08-02"
schemaVersion: 1
---

# Resolve foreign FormIDs from their owner before walking to a target override

`RecordByFormID(file, formId, True)` does not treat `formId` as a globally absolute lookup. It resolves the ID in the `file` argument's local master space. In the verified incident, using a FormID whose high byte belonged to a different plugin with the target patch file returned a same-low-bytes record owned by the target file, not `nil`.

The safe sequence is:

1. Identify the plugin that owns the source FormID.
2. Call `RecordByFormID` with that owning file and the source ID.
3. Walk to `WinningOverride` if the operation needs the load-order winner.
4. Confirm both `GetFileName(GetFile(record))` and the expected signature before reading or mutating a child path.

An empty child path after a seemingly valid lookup is not proof the target data is absent. Check record identity first; a foreign-ID local-space collision can turn an intended outfit lookup into an unrelated `ARMO` or other record without raising an error.

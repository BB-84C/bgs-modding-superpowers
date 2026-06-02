---
id: xedit.find-by-formid-vs-editorid.v1
title: FormID and EditorID lookups are different xEdit search paths
domains: [xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Use records.find_by_form_id when the caller has a plugin file plus FormID, and records.find_by_editor_id when the caller only has an EditorID-style identifier.
  confidence: verified-project-doc
queryKeys: [find_by_form_id, find_by_editor_id, EditorID, FormID lookup]
severity: low
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: records.* commands
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# FormID and EditorID lookups are different xEdit search paths

FormIDs are numeric, load-order-aware identifiers; EditorIDs are author-facing names when a record has one.
The daemon exposes separate lookup commands because those identifiers are not interchangeable.

Agents should choose the lookup path from the evidence in the user's request.
If a plugin file and FormID are known, use FormID lookup; if only a symbolic name is known, use EditorID lookup.

Do not guess a FormID from an EditorID without a real lookup result.

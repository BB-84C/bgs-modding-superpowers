---
id: xedit.override-vs-new-record-decision.v1
title: Choose xEdit override vs new record by whether the game object already exists
kind: rule
domains: [xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "Use copy-as-override when changing an existing game record and copy-as-new-record only when creating a distinct new object; replacing vanilla content still means overriding the vanilla record, not deleting it and adding an orphan duplicate."
  confidence: high
queryKeys: [copy as override, copy as new record, override record, new record, orphan duplicate]
severity: high
sources:
  - kind: tooling-docs
    ref: "xEdit Docs / Tome of xEdit"
    url: "https://tes5edit.github.io/docs/"
  - kind: tooling-docs
    ref: "xEdit Docs — Conflict detection and resolution"
    url: "https://tes5edit.github.io/docs/5-conflict-detection-and-resolution.html"
  - kind: tooling-docs
    ref: "STEP Guide — xEdit"
    url: "https://stepmodifications.org/wiki/Guide:XEdit"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Choose xEdit override vs new record by whether the game object already exists

## Decision tree

1. **Changing a field on an existing vanilla or mod record:** copy as override into your patch and edit the fields that must win. The FormID identity stays the same, so references keep pointing at the intended object.
2. **Creating an entirely new object:** copy as new record or create a new record when the game should contain an additional NPC, item, quest, constructible object, cell object, or form. Give it its own EditorID and references.
3. **Replacing a vanilla record's behavior entirely:** still override the original record. If the goal is "this vanilla weapon/NPC/quest/object now behaves differently," keep the original FormID and overwrite the needed fields in a patch. Do not delete the original and add a lookalike new record.
4. **Intermediate placement cases:** reason by record type. Adding a placed object to a cell usually means creating a new child REFR/ACHR in the cell context. Changing an existing placed object means overriding that placed reference. Editing the base object behind many placed references means overriding the base form.

## Common misuse and consequence

The common mistake is choosing "copy as new record" when the desired operation was an override. That creates an orphan duplicate while the original vanilla record remains present and referenced. The result can be double effects, duplicate NPCs/items, untouched vanilla behavior, missing references, or a patch that appears to contain the intended data but never wins in game because nothing points to it.

## Recovery from misuse

Find every reference to the accidental new record and decide whether those references should point to the original overridden record or to a genuinely new object. If the intent was modification, move the changes into an override of the original record, repoint or remove accidental references, then delete or mark-delete the orphan only after `Referenced By` is clean. If the intent was additive content, keep the new record but rename it clearly and make its placement/reference path explicit.

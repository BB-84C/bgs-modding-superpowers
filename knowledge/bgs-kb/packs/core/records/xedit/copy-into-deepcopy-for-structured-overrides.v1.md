---
id: xedit.copy-into-deepcopy-for-structured-overrides.v1
title: Use deepCopy when copy_into creates structured override records
kind: gotcha
domains: [xedit, plugin-format, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "xEdit daemon `records.copy_into` can produce a shallow override if `deepCopy: true` is omitted. For structured records such as LVLI, CONT, FLST, NPC_, QUST, or records with entries/VMAD/child elements, copy with `deepCopy: true`, then read back child-element counts before editing; a shallow winning override can effectively empty the record."
  confidence: verified-project-doc
queryKeys:
  - records.copy_into
  - deepCopy true
  - shallow override
  - structured record override
  - LVLI entries missing
  - copy into mode override
  - scripts.run targets path
  - JvI IntToStr
severity: critical
sources:
  - kind: project-internal-doc
    ref: BB84 Starfield P10 Wave 3.5-4 field notes
    sectionPath: xEdit daemon records.copy_into shallow LVLI override incident
related:
  - plugin-format.qust-override-shells-are-group-parents.v1
  - xedit.xedit-childgroup-navigation.v1
lastReviewed: "2026-07-05"
schemaVersion: 1
---

# Use deepCopy when copy_into creates structured override records

## The trap

An override record is only safe if it carries the payload that the winning override is supposed to preserve. With the xEdit daemon, `records.copy_into` in override mode can create a shallow override when `deepCopy: true` is omitted. For records with meaningful child structures, a shallow winner is worse than no patch: it can erase the visible winning payload while looking like a valid override record exists.

High-risk structured record classes include:

- `LVLI` / leveled lists, where entries, counts, levels, and entry conditions are the payload;
- `CONT`, where item entries and ownership/container data matter;
- `FLST`, where the form array is the point of the record;
- `NPC_`, `ARMO`, `WEAP`, and other records with subrecord groups or VMAD;
- `QUST`, `SCEN`, dialogue, and any record with child groups or script fragments.

## Required pattern

When creating an override for a structured record through the daemon:

1. Call `records.copy_into` with `mode: "override"` and `deepCopy: true`.
2. Immediately read back the new override.
3. Compare the relevant child-element counts against the source or previous winner: e.g. LVLI entry count, CONT item count, FLST length, VMAD/script-fragment presence.
4. Only after the readback matches should you edit the targeted child element or condition.
5. If the count is zero or missing, discard/recreate the override before saving; do not patch on top of an empty winner.

## Starvival LVLI example

During BB84's Starfield P10 vendor-stock patching, `records.copy_into` without `deepCopy: true` created an `LVLI` override that lost `EDID`, `LLCT`, and all leveled-list entries. As the winning override, that would have cleared the vendor stock path entirely. Re-copying with `deepCopy: true` and verifying the entry structure before editing avoided shipping a destructive empty list.

## Daemon scripting gotchas from the same incident

- The daemon's JvI scripting ledger does not expose every Delphi helper symbol; avoid relying on helpers such as `IntToStr` inside uploaded scripts unless already verified in that daemon context.
- `scripts.run` targets should include an explicit `path: ""` when the script expects the root record target. Do not rely on an omitted path being interpreted the same way across wrappers.

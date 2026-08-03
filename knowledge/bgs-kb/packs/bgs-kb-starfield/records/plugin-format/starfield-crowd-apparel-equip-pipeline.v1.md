---
id: plugin-format.starfield-crowd-apparel-equip-pipeline.v1
title: Crowd apparel is not a drop-in Starfield actor-equipment record
kind: gotcha
domains: [plugin-format, debugging]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: "Starfield crowd ARMO records can be display-oriented CrowdManager assets rather than actor-equipment records. Do not add one to a normal NPC outfit unchanged: copy the source as-new, compare its full ARMO and ARMA structure with a known-good equippable garment of the same slot, and verify in-game before treating it as wearable."
  confidence: verified-project-doc
queryKeys: [Starfield crowd apparel, CrowdManager clothing, crowd ARMO CTD, HumanCrowdRace, equippable clothing, outfit pipeline]
severity: critical
sources:
  - kind: github-issue
    url: "https://github.com/BB-84C/bgs-modding-superpowers/issues/27"
    ref: "Issue #27: verified Starfield crowd apparel investigation"
    sectionPath: "Part 1 — Crowd apparel is not equippable; The structural difference; Gotcha worth its own record"
related:
  - starfield-conflicts.leveled-list-and-npc-overhaul-patterns.v1
  - xedit.copy-into-deepcopy-for-structured-overrides.v1
  - xedit.safe-linked-record-and-nonascii-inspection.v1
lastReviewed: "2026-08-02"
schemaVersion: 1
---

# Starfield crowd apparel is not a drop-in actor-equipment record

## The boundary

The verified incident behind this record crashed on city cell load after a crowd garment was placed in an ordinary actor outfit. The affected crowd `ARMO` was authored for the crowd system, not proven safe for the normal actor equip path. The observed crash was an access violation while the engine resolved a `BGSOutfit` item array; that symptom is a stop signal, not evidence that the list itself is malformed.

## What was actually different

The investigated ordinary garment used `HumanRace`, real object bounds, transforms, resistances, attach-parent slots, and a matching `ARMA` with additional-race and morph links. The crowd body garment used `HumanCrowdRace`, zero bounds, and omitted several of those fields. A tested conversion added the required equipment-path fields to a source-as-new copy and added `HumanRace` to the source `ARMA` additional races; the converted body garment then equipped, rendered, and skinned on a `HumanRace` actor without reproducing the crash.

This is evidence for a **record-family mismatch**, not a proof that one named subrecord is the universal root cause. `APPR` was the strongest observed suspect, but the fields were not isolated one at a time. Do not publish an `APPR`-only fix as established fact.

## Required workflow

1. Start with the actual crowd source record, copied as-new with native content retained; do not create a new record from an unrelated vanilla template and transplant the crowd content into it.
2. Pick a known-good equippable vanilla garment in the same slot and compare the complete `ARMO` and linked `ARMA` structure, including race, bounds, transforms, slots, models, additional races, and morph links.
3. Treat every absent field as a finding until it has been justified. Verify the resulting record in a populated runtime scene, not only through xEdit readback.
4. Audit each item class independently. The investigated crowd hat lacked world models and an object template that the investigated crowd body garment already had; one crowd-item diff is not a schema for all crowd apparel.

`FLLD` is a zero-length marker that xEdit did not add through the observed script path. Its absence did not prevent the tested body garment from rendering, but inability to reach exact parity remains part of the risk assessment.

See `xedit.copy-into-deepcopy-for-structured-overrides.v1` for the deep-copy requirement when working with structured records, and `starfield-conflicts.leveled-list-and-npc-overhaul-patterns.v1` for semantic review of NPC/outfit distribution changes.

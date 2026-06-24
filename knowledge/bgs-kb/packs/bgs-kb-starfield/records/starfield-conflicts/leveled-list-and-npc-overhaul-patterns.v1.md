---
id: starfield-conflicts.leveled-list-and-npc-overhaul-patterns.v1
title: Starfield leveled-list and NPC overhauls need semantic review
kind: rule
domains: [file-conflicts, load-order]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: Starfield leveled-list and NPC conflicts are silent semantic failures; automated merging can help structure, but curator review decides whether the resulting world distribution and NPC presentation make sense.
  confidence: medium
queryKeys: [Starfield leveled list conflicts, NPC overhaul conflicts, outfit incoherence]
severity: high
sources:
  - kind: tooling-docs
    url: "https://www.nexusmods.com/starfield/mods/1"
    ref: Starfield Community Patch scope and load-order notes
  - kind: tooling-docs
    url: "https://raw.githubusercontent.com/loot/starfield/master/masterlist.yaml"
    ref: LOOT Starfield masterlist YAML
  - kind: project-internal-doc
    ref: BB84 Starfield MO2 mods recon, NPC修改 / NPC新增 separator observation
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Starfield leveled-list and NPC overhauls need semantic review

## Perspective: OBJECTIVE

Leveled-list conflicts rarely announce themselves with a crash. The failure mode is silent: equipment never appears, a vendor pool is skewed, a faction outfit becomes incoherent, or two NPC edits combine face, voice, race, inventory, and package data in a way no author intended. Automated sorting and patch generation can identify and merge structural edits, but they cannot decide what a settled Starfield world should distribute to pirates, guards, settlers, ship vendors, or new NPC populations.

For Starfield, review the axis of each conflict: list injection, outfit assignment, NPC visual edit, voice/race edit, package/AI data, or quest alias use. If two mods touch different axes, a patch may preserve both. If they touch the same semantic axis, the curator must choose.

## Perspective: SUBJECTIVE — BB84 curator reference (not a universal rubric)

BB84's reference take is stricter than a generic automated-merge posture: heavy leveled-list or NPC overhaul stacks are "must do custom patch + human review." His Fallout 4 WL2 pack uses many Complex Sorter / INNR rule mods as evidence of manual coherence discipline, and his Starfield layout separates `NPC修改` from `NPC新增`, preserving the distinction between editing existing characters and adding new population. Another curator can choose a lighter approach, but should still name the intended semantic axis before trusting an automated patch.

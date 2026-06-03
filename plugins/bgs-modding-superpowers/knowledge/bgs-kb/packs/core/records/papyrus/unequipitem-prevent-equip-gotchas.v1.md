---
id: papyrus.unequipitem-prevent-equip-gotchas.v1
title: UnequipItem force flags have inventory and NPC gotchas
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: Actor.UnequipItem can force unequip and optionally prevent re-equip, but CK notes warn about charge depletion and unreliable prevent-equip behavior on NPCs.
  confidence: verified-tooling
queryKeys: [UnequipItem, abPreventEquip, abSilent, equipment script, NPC re-equip]
severity: medium
sources:
  - kind: wiki
    ref: Creation Kit Wiki UnequipItem - Actor
    url: https://ck.uesp.net/wiki/UnequipItem_-_Actor
    sectionPath: Notes
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# UnequipItem force flags have inventory and NPC gotchas

`UnequipItem` can remove an item and takes flags for preventing re-equip and suppressing messages.
Those flags are not a complete equipment-control system.

The CK notes call out weapon enchantment-charge side effects and questionable NPC behavior for prevent-equip.
If a mod depends on forced equipment state, verify the actor type and inventory result after the call.

Prefer explicit follow-up checks over assuming the flag enforced policy permanently.

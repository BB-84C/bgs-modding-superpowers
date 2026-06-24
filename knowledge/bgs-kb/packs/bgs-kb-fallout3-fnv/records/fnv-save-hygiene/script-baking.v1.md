---
id: fnv-save-hygiene.script-baking.v1
title: Script state and upgrade hygiene in Fallout 3, New Vegas, and TTW saves
kind: rule
domains: [save-file, install-planning]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: Fallout 3, New Vegas, and TTW mods can bake quest, script, and reference state into saves, so risky installs and upgrades need pre-change saves plus deprecate-not-delete rollback discipline.
  confidence: high
queryKeys: [FNV save baked scripts, FO3 save hygiene, TTW upgrade rollback, script state, deprecated mods]
severity: high
sources:
  - kind: wiki
    ref: UESP Fallout New Vegas reference
    url: https://en.uesp.net/wiki/Fallout:New_Vegas
    sectionPath: Quests, scripts, and gameplay systems
  - kind: community-forum
    ref: Viva New Vegas guide
    url: https://vivanewvegas.moddinglinked.com/
    sectionPath: Save and testing guidance
  - kind: project-internal-doc
    ref: BB84 corpus Q5 and Q16 save-baking discipline notes
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Script state and upgrade hygiene in Fallout 3, New Vegas, and TTW saves

Fallout 3, New Vegas, and TTW do not use Papyrus, but they still persist state. Quests, scripts, aliases or reference-like state, globals, placed references, inventory changes, and started quest stages can all become part of a save's ongoing world. A mod that looks safe because it has only a small plugin can still leave durable state once the player loads, travels, triggers a quest, or picks up a scripted item.

The practical rule is simple: create a clean rollback save before installing or upgrading risky mods. Risky classes include quest mods, companion mods, major scripted gameplay systems, leveled-list injectors that run scripts, worldspace edits with persistent references, and TTW conversion patches. Test on a copied save first. If the upgrade misbehaves, you need both the old mod files and the pre-change save to recover.

Do not delete old versions on upgrade day. Disable the old mod, move it to a deprecated separator, install the new version, then compare records and behavior before removing the old copy. This is not hoarding; it is rollback insurance and diff substrate. TTW raises the cost of a bad upgrade because two game worlds can share a single New Vegas save/runtime. When in doubt, preserve the previous state until several real play sessions confirm the new stack is stable.

---
id: fo4-save-hygiene.script-baking.v1
title: Fallout 4 script-heavy mods bake state into saves
kind: rule
domains: [save-file, papyrus, install-planning]
appliesTo:
  games: [Fallout4, Fallout4VR]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Fallout 4 Papyrus-heavy mods can persist quests, aliases, globals, and script instances in saves, so upgrades need pre-install saves, disabled old versions, and rollback insurance rather than immediate deletion.
  confidence: high
queryKeys: [Fallout 4 save baking, Papyrus, script persistence, Sim Settlements 2, rollback]
severity: critical
sources:
  - kind: wiki
    url: "https://falloutck.uesp.net/wiki/Papyrus"
    ref: UESP Fallout 4 Papyrus reference
  - kind: tooling-docs
    url: "https://wiki.simsettlements2.com/"
    ref: Sim Settlements 2 documentation wiki
  - kind: project-internal-doc
    ref: BB84 WL2 recon, SS2 active plus deprecated version retention pattern
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Fallout 4 script-heavy mods bake state into saves

Fallout 4 saves can retain Papyrus script instances, quest stages, aliases, global variables, timers, workshop state, and mod-maintained registries. Removing or replacing the plugin files does not necessarily remove the state already serialized into the save. That is why quest, settlement, workshop, and large framework mods are not safe to churn like texture replacers.

The discipline is operational: make a named save before installing or upgrading a script-heavy mod; install in an isolated batch; test the touched systems; and when upgrading, disable the old version rather than deleting it immediately. Keep the old folder in a deprecated section until the new version survives real play and any curator patches are updated. If the new version fails, rollback needs both the old files and the pre-upgrade save.

BB84's WL2 provides objective evidence for this pattern: the Sim Settlements 2 stack retained eight active SS2-related entries plus five deprecated SS2 versions as rollback insurance, not as museum clutter. FO4VR shares the save-persistence concept but has different framework availability and must be tested separately. Vault-Tec recommends treating every Papyrus-heavy upgrade as a sealed-vault experiment with a planned evacuation route.

Never convert this rollback staging area into a silent junk drawer; document why each deprecated entry remains.

---
id: pack-curation.deprecate-not-delete-on-upgrade.v1
title: Do not delete the old version when you upgrade
kind: rule
domains: [install-planning, save-file]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "When upgrading a mod, disable and move the old version to a deprecated section for rollback and diff; delete only after migration confidence is established."
  confidence: high
queryKeys: [mod upgrade, deprecated section, rollback, old version, save state, diff strategy]
severity: high
sources:
  - kind: project-internal-doc
    ref: "BB84 WL2 recon lane 5: 不再使用_separator with deprecated upgrade entries"
  - kind: project-internal-doc
    ref: "BB84 Starfield recon lane 4: 版本已过期 / 等待作者更新 / 观望 status separators"
  - kind: official
    url: "https://ck.uesp.net/wiki/Save_File_Notes_(Papyrus)"
    ref: "Creation Kit Wiki save file notes for Papyrus"
  - kind: tooling-docs
    url: "https://tes5edit.github.io/docs/"
    ref: "xEdit documentation"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Do not delete the old version when you upgrade

Upgrade-time deletion is a rollback breach. When a mod is replaced by a newer version, the old version should usually be disabled and moved to a deprecated or no-longer-used section first, not deleted immediately. This is not a museum policy and not permanent retention. It is a temporary safety layer while the new version proves itself.

The first reason is save state. Papyrus-heavy mods, quest mods, LL injectors, workshop frameworks, and content frameworks may bake aliases, globals, scripts, or distribution state into a save. If the new version misbehaves, an old disabled copy plus a pre-upgrade save gives the curator a realistic path back. Without it, the only rollback may be reconstructing an archive from downloads or abandoning the save.

The second reason is diff and patch strategy. A curator-maintained coherence patch may depend on records, scripts, assets, or installer choices from the old version. Keeping both versions temporarily lets the curator compare changes, inspect new records in xEdit, and update patches deliberately rather than guessing.

The workflow is simple: before upgrade, checkpoint the profile/save; install the new version separately; disable the old version; move it under a deprecated separator; inspect differences and patch impact; then play several sessions before deleting. BB84's WL2 provides the concrete pattern with `不再使用_separator`, including deprecated Sim Settlements 2-era entries. The Starfield pack uses three status separators — `版本已过期`, `等待作者更新`, and `观望` — to preserve operational state instead of flattening everything into installed/deleted. Delete later, after confidence; not on upgrade day.

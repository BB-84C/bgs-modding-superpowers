---
id: pack-curation.localization-layer-discipline.v1
title: Non-English locale modpacks treat localization as a structural layer
kind: rule
domains: [install-planning, plugin-format]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "In non-English locale packs, localization patches are peer dependencies of content mods; preserve translator attribution, order them deliberately, and budget localization conflict resolution as real curation work."
  confidence: high
queryKeys: [localization layer, translation companion, 汉化, xTranslator, bgs-translator, Simplified Chinese]
severity: high
sources:
  - kind: project-internal-doc
    ref: "BB84 WL2 recon: 250+ separate - 汉化 companion mod folders"
  - kind: project-internal-doc
    ref: "BB84 Starfield recon: - SC Simplified Chinese suffix pattern and localization separator"
  - kind: community-forum
    url: "https://www.nexusmods.com/skyrimspecialedition/mods/134"
    ref: "xTranslator Nexus page"
  - kind: community-forum
    url: "https://www.nexusmods.com/starfield/mods/313"
    ref: "Starfield localization-related Nexus page"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Non-English locale modpacks treat localization as a structural layer

For a non-English modpack, localization is not optional polish. A content mod that leaves key strings in English inside an otherwise localized game is a broken user experience, and sometimes a functional break when quests, clues, passwords, or item names depend on readable text. Treat localization patches as first-class peer dependencies of their parent content mods.

The dependency graph should make that relationship visible. In MO2, a translation companion usually needs to load after the parent mod's assets and plugin strings. If two translations target the same parent, choose one and record why. If the parent updates, the translation becomes version-sensitive and must be audited; a stale translation can overwrite new strings with old text or fail to cover new records. Empty or orphan localization companions should be surfaced during install review because they indicate a parent mismatch or removed dependency.

Naming is part of the technical discipline. Preserve translator attribution in folder names and notes, not just the original content author. BB84's WL2 demonstrates the pattern with more than 250 `- 汉化` companion folders and names such as `by Melon`, `by 饺子皮`, `by Cx3`, or `by 废土沙狐`. The Starfield pack uses `- SC` as a Simplified Chinese suffix pattern with a dedicated localization separator; here SC means Simplified Chinese, not Starfield Community Patch.

Budget localization alongside record conflicts. A public pack needs an installation flow that includes translation dependencies, translator attribution, string conflict choices, and retranslation work for missing spans. Tools such as xTranslator or bgs-translator can help create artifacts, but the curation decision remains human: which translation belongs in this world, which parent version it matches, and how conflicts are resolved.

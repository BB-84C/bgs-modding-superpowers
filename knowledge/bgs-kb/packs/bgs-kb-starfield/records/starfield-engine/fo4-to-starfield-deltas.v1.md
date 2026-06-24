---
id: starfield-engine.fo4-to-starfield-deltas.v1
title: Fallout 4 assumptions must be revalidated before porting to Starfield
kind: rule
domains: [engine, version-differences]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: Starfield shares Bethesda lineage with Fallout 4, but CE2 world structure, plugin tiers, archive compression, activation flow, and CK tools are different enough that FO4 modpack habits must be revalidated.
  confidence: medium
queryKeys: [FO4 to Starfield differences, CE2 deltas, BA2 v3, plugins.txt Starfield, CK differences]
severity: high
sources:
  - kind: project-internal-doc
    ref: .artifacts/starfield wiki html/Differences from Fallout 4 to Starfield - WIP - XWiki.html
    sectionPath: Creation Kit differences from Fallout 4
  - kind: github-issue
    url: "https://github.com/wrye-bash/wrye-bash/issues/667"
    ref: Wrye Bash initial Starfield support issue
  - kind: official
    url: "https://store.steampowered.com/app/2722710/"
    ref: Starfield Creation Kit Steam page
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Fallout 4 assumptions must be revalidated before porting to Starfield

Starfield still belongs to Bethesda's plugin-and-record lineage: Papyrus exists, master/plugin data still drives world state, BA2 archives remain central, and load order matters. That similarity is useful, but dangerous when it becomes copy-paste curation.

Creation Engine 2 changes several pack-facing assumptions. Worldspaces no longer map neatly to the FO4-style single exterior world; planets, space cells, instanceable interiors, PackIns, and the Planet Content Manager create new placement and conflict surfaces. Quest and dialogue tooling changed, including scene/greeting integration and stage-based reward handling. CK tools such as OPALs, Inspector/Properties, ImGUI, spaceship editor, snap templates, and AssetWatcher also change author workflows and the kinds of assets curators will see.

Plugin and asset handling are the biggest hazards. Starfield uses Full, Medium, and Small master concepts rather than a direct FO4 ESL mental model. Plugin activation moved toward the Creations/load-order interface and current plugins.txt behavior, while older `sTestFile` habits are only a dev/test shortcut. Starfield BA2 v3 texture archives use DX10/LZ4 block compression; FO4-era archive tools that do not understand that format can corrupt or misread assets.

Confidence is medium because the CK wiki page is a 2025 snapshot and marked WIP. Treat each FO4-derived rule as a hypothesis until current Starfield CK, xEdit, or runtime readback confirms it.

> Source note: portions paraphrased from a community-archived Bethesda Creation Kit
> wiki snapshot (circa 2025-05-14). The information surfaced here represents
> community reverse-engineering of behavior visible in the live Creation Kit, not
> Bethesda's official documentation.

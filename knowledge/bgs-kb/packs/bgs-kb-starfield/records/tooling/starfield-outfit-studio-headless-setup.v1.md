---
id: tooling.starfield-outfit-studio-headless-setup.v1
title: Outfit Studio 5.8.2 needs explicit noninteractive Starfield configuration
kind: workflow
domains: [install-planning, debugging]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: "Outfit Studio 5.8.2 can launch --automation without interaction only after its Starfield configuration is explicit: target game, game-data path, output overlay, default skeleton reference, and skeleton root. The upstream setup path selects res/skeleton_female_sf.nif for Starfield; do not document the male skeleton as the default."
  confidence: verified-tooling
queryKeys: [Outfit Studio 5.8.2 headless, --automation, Starfield Config.xml, skeleton_female_sf.nif, GameDataPath, OutputDataPath]
severity: high
sources:
  - kind: github-issue
    url: "https://github.com/BB-84C/bgs-modding-superpowers/issues/27"
    ref: "Issue #27: verified Outfit Studio 5.8.2 Starfield setup"
    sectionPath: "Part 4 — Driving Outfit Studio 5.8.2 fully headless"
  - kind: tooling-docs
    url: "https://github.com/ousnius/BodySlide-and-Outfit-Studio/blob/v5.8.2/Config.xml"
    ref: "BodySlide and Outfit Studio v5.8.2 Config.xml"
    sectionPath: "Config; TargetGame; GameDataPath; OutputDataPath; Anim"
  - kind: tooling-docs
    url: "https://github.com/ousnius/BodySlide-and-Outfit-Studio/blob/v5.8.2/src/program/OutfitStudio.cpp#L1088-L1148"
    ref: "BodySlide and Outfit Studio v5.8.2 OutfitStudio.cpp"
    sectionPath: "OutfitStudioFrame::SettingsLoad; Starfield target selection"
related:
  - engine.starfield-morph-dat-observed-contract.v1
  - tooling-mo2.stock-game-data-read-only.v1
lastReviewed: "2026-08-02"
schemaVersion: 1
---

# Outfit Studio 5.8.2 Starfield automation needs explicit noninteractive configuration

The verified 5.8.2 startup path used `OutfitStudio.exe --automation <name>` and exited without interaction only after `CalienteTools/BodySlide/Config.xml` had all five Starfield-relevant settings:

| Config key | Starfield setting | Why it matters |
| --- | --- | --- |
| `TargetGame` | `9` | selects Starfield rather than leaving first-run setup unresolved |
| `GameDataPath` | game `Data` path with a trailing separator | a missing separator can concatenate the archive name directly to the directory and silently load no archives |
| `OutputDataPath` | dedicated MO2 overlay `Data` directory | prevents generated output from targeting the real game `Data` tree |
| `Anim/DefaultSkeletonReference` | `res/skeleton_female_sf.nif` | this is the upstream Starfield default selected by Outfit Studio |
| `Anim/SkeletonRootName` | `Root` | pairs with the skeleton reference |

The BodySlide v5.8.2 source bundles both Starfield skeletons, but its Starfield setup branch explicitly selects `res/skeleton_female_sf.nif`. `res/skeleton_male_sf.nif` exists as a bundled asset; it is not the default to document for this workflow.

Read the tool log before deciding whether automation failed. A first-run setup wizard or a missing-skeleton dialog can block the process, while a missing trailing separator can leave archive loading silently wrong. Put `OutputDataPath` in an MO2 overlay, never in the game install.

Automation XML vocabulary, XML tree shape, generated `morph.dat` validity, and in-game acceptance are intentionally outside this record. This setup evidence proves launch configuration, not a complete generation pipeline.

---
id: starfield-load-order.master-ordering-and-esl-hazards.v1
title: Starfield master ordering and medium-plugin hazards
kind: rule
domains: [load-order, plugin-format]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: Starfield plugins are not just FO4-style ESP/ESM files; Full, Medium, and Small masters have different capacity expectations, and changing tier or loading both ESP and converted ESM copies can break tests and saves.
  confidence: high
queryKeys: [Starfield Full Master, Medium Master, Small Master, ESL hazards, plugin tier]
severity: critical
sources:
  - kind: project-internal-doc
    ref: .artifacts/starfield wiki html/Understanding and Creating Data Files - XWiki.html
    sectionPath: Understanding Master Files and their Sizes
  - kind: official
    url: "https://store.steampowered.com/app/2722710/"
    ref: Starfield Creation Kit Steam page
  - kind: tooling-docs
    url: "https://raw.githubusercontent.com/loot/starfield/master/masterlist.yaml"
    ref: LOOT Starfield masterlist YAML
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Starfield master ordering and medium-plugin hazards

Starfield's Creation Kit workflow treats shareable Creations as master files, and the game distinguishes Full, Medium, and Small masters. In the archived CK page, Full masters are for large frameworks and overhauls, Medium masters for mid-sized creations such as quests or planets, and Small masters for small items or reskins. The listed capacity tiers differ sharply, so a plugin that outgrows its tier is not a harmless metadata issue.

The curation hazard is twofold. First, parent masters are real dependencies: if a plugin edits or references DLC or another master, users need that parent. Second, conversion testing can create duplicate activation mistakes. If a development `.esp` is converted to an `.esm`, load only the converted master for in-game testing; loading both copies means two files affect the same data and can mask the real failure.

Do not port Skyrim or FO4 ESL instincts directly. Starfield's tier model and Creation storefront behavior create different pressure than classic ESL-flag flipping. Treat tier changes after release as high risk because FormID range, dependency expectations, and downstream patches may have encoded the old shape. Use LOOT's evolving Starfield groups as scaffolding, then verify parent masters and winning overrides in xEdit or another Starfield-aware reader.

> Source note: portions paraphrased from a community-archived Bethesda Creation Kit
> wiki snapshot (circa 2025-05-14). The information surfaced here represents
> community reverse-engineering of behavior visible in the live Creation Kit, not
> Bethesda's official documentation.

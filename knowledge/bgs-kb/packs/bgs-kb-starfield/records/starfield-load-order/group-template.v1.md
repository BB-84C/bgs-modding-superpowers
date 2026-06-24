---
id: starfield-load-order.group-template.v1
title: Starfield LOOT group template is useful but still evolving
kind: workflow
domains: [load-order, tooling.loot]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: Use the current LOOT Starfield groups as a starting scaffold, but treat the template as evolving and verify plugin class, master tier, and patch semantics before locking a pack order.
  confidence: high
queryKeys: [Starfield LOOT groups, Starfield load order, masterlist.yaml, Dynamic Patches]
severity: high
sources:
  - kind: tooling-docs
    url: "https://raw.githubusercontent.com/loot/starfield/master/masterlist.yaml"
    ref: LOOT Starfield masterlist YAML
  - kind: tooling-docs
    url: "https://github.com/loot/starfield"
    ref: LOOT Starfield masterlist repository
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Starfield LOOT group template is useful but still evolving

As of 2026-06, Starfield's community load-order grouping is still younger than Skyrim or Fallout 4. Use LOOT's Starfield masterlist as a scaffold, not as a substitute for curator review.

The current group chain is: Main Plugins, Bethesda Game Studios Creations, BGS Creations - Trackers Alliance, BGS Creations - Late, Fixes & Resources, Early Loaders, Verified Creations, default, Low Priority Overrides, Core Mods, High Priority Overrides, Late Loaders, Dynamic Patches, and Late Fixes & Changes. In practice, official Bethesda and Creation marketplace masters belong before ordinary mod overrides; frameworks and resources should load early enough for dependents; ordinary content sits near default/Core Mods; intentional overrides and compatibility patches move late.

Starfield adds extra review pressure because plugins may be Full, Medium, or Small masters, and marketplace Creations can sit outside an MO2 user's normal visual workflow. Do not sort only by filename extension. Check the plugin's master tier, dependency chain, whether it is an official/BGS Creation, and whether it is a dynamic patch meant to win conflicts.

The safe template is therefore: official game and BGS Creation masters first, frameworks/resources next, content and overhauls in declared pack sections, then high-priority overrides, generated patches, and late fixes. Re-run xEdit or equivalent readback for conflicts that LOOT cannot semantically judge.

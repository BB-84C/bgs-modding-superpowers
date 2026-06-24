---
id: starfield-frameworks.taxonomy.v1
title: Starfield framework taxonomy and BB84 reference stack
kind: explanation
domains: [install-planning]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: Classify Starfield frameworks by runtime layer, address/version layer, Papyrus/API extension layer, gameplay framework, and community patch layer; then reject abandoned or version-locked frameworks before building dependencies on them.
  confidence: medium
queryKeys: [Starfield frameworks, SFSE, Address Library, Cassiopeia, Halmod, Trainwreck]
severity: medium
sources:
  - kind: tooling-docs
    url: "https://sfse.silverlock.org/"
    ref: Starfield Script Extender
  - kind: tooling-docs
    url: "https://www.nexusmods.com/starfield/mods/3256"
    ref: Address Library for SFSE Plugins
  - kind: tooling-docs
    url: "https://www.nexusmods.com/starfield/mods/1"
    ref: Starfield Community Patch
  - kind: project-internal-doc
    ref: D:/Starfield MO2/mods recon, BB84 reference take current as of 2026-08
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Starfield framework taxonomy and BB84 reference stack

## Perspective: OBJECTIVE

Starfield frameworks should be sorted by what layer they stabilize. Runtime frameworks include SFSE and native DLL plugins; these are sensitive to game version and platform. Address-layer frameworks such as Address Library reduce offset churn for SFSE plugins but still require compatible data files. Papyrus/API extenders expose new script functions and can bake assumptions into saves. Gameplay frameworks provide shared rules for systems such as non-lethal combat, ships, vendors, or UI behavior. Community patches are not frameworks in the code sense, but they become a baseline dependency layer for many packs.

Trap signs are objective: no changelog, hardcoded old game build, broken dependency chain, no source or maintainer signal for a native plugin, and comments showing unresolved load failures after recent game updates.

## Perspective: SUBJECTIVE — BB84 curator reference (not a universal rubric)

BB84's Starfield reference stack, current as of 2026-08, includes SFSE 1-15-222, Address Library v19, Cassiopeia Papyrus Extender, Trainwreck SFSE, Halmod, Baka Achievement Enabler, Non-Lethal Framework, Ship Vendor Framework, and Starfield Community Patch. This is a reference take, not a universal mandate. A smaller pack may avoid several gameplay frameworks; a systems-heavy pack may add more. The BB84-style lesson is to name each framework's layer before adopting it, so version churn and save impact are visible.

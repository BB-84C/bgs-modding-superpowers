---
id: fo4-frameworks.taxonomy.v1
title: Fallout 4 framework taxonomy and curator adoption reference
kind: explanation
domains: [install-planning, version-differences, debugging]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Fallout 4 frameworks should be classified by runtime layer, UI layer, settlement layer, sorting/content layer, and animation layer, then screened for maintenance and runtime compatibility before adoption.
  confidence: high
queryKeys: [F4SE, Address Library, MCM, HUDFramework, AWKCR, Workshop Framework, framework taxonomy]
severity: high
sources:
  - kind: official
    url: "https://f4se.silverlock.org/"
    ref: F4SE official downloads
  - kind: tooling-docs
    url: "https://www.nexusmods.com/fallout4/mods/47327"
    ref: Address Library for F4SE Plugins
  - kind: tooling-docs
    url: "https://www.nexusmods.com/fallout4/mods/21497"
    ref: Mod Configuration Menu
  - kind: project-internal-doc
    ref: BB84 WL2 recon, framework adoption inventory
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Fallout 4 framework taxonomy and curator adoption reference

## Perspective: OBJECTIVE

Classify Fallout 4 frameworks by the layer they own. Runtime frameworks include F4SE, Address Library, crash loggers, and native DLL dependencies. UI/config frameworks include MCM, MCM Booster, HUDFramework, DEF_UI-like stacks, and menu patchers. Settlement frameworks include Workshop Framework and Sim Settlements dependencies. Content/sorting frameworks include AWKCR, Armorsmith Extended, ECO/NEO-style replacements, and tag/classification systems. Animation frameworks are a separate risk class because behavior files are binary and not visible to xEdit.

Trap signals are objective: abandoned runtime dependency, no changelog across game updates, hardcoded executable version, broken prerequisite chain, or comments/bug reports showing unresolved loader failures. Frameworks amplify every dependent mod; stale foundations create pack-wide radiation leaks.

## Perspective: SUBJECTIVE — BB84 curator reference (not a universal rubric)

BB84's WL2 reference stack includes F4SE, Buffout4, Address Library, MCM, MCM Booster, HUDFramework, AWKCR plus Armorsmith Extended, Workshop Framework, and Take a Bite with compatibility patches. This is a historical adoption reference from one FO4 curator, not a universal recommendation that every new pack must choose the same older frameworks.

For new packs, preserve the taxonomy but re-evaluate each framework against current maintenance, next-gen runtime support, and the declared pack style.

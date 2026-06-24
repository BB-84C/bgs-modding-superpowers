---
id: skyrim-frameworks.taxonomy.v1
title: Skyrim framework taxonomy
kind: explanation
domains: [install-planning, engine, papyrus]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [gamebryo, creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Classify Skyrim frameworks by runtime dependency, UI/MCM service, Papyrus extension, and content integration role before trusting a mod that depends on them."
  confidence: high
queryKeys: [Skyrim framework, SKSE, SkyUI, Address Library, PapyrusUtil, MCM]
severity: medium
sources:
  - kind: tooling-docs
    url: "https://skse.silverlock.org/"
    ref: "SKSE official download and runtime matrix"
  - kind: community-forum
    url: "https://www.nexusmods.com/skyrimspecialedition/mods/12604"
    ref: "SkyUI Nexus page"
  - kind: community-forum
    url: "https://www.nexusmods.com/skyrimspecialedition/mods/32444"
    ref: "Address Library for SKSE Plugins Nexus page"
  - kind: community-forum
    url: "https://www.nexusmods.com/skyrimspecialedition/mods/13048"
    ref: "PapyrusUtil SE Nexus page"
  - kind: project-internal-doc
    ref: "BB84 corpus Skyrim framework adoption notes"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Skyrim framework taxonomy

## Perspective: OBJECTIVE

Skyrim frameworks fall into several operational classes. Runtime frameworks include SKSE/SKSE64 and native DLL ecosystems; they are executable-version sensitive and must match LE, SE 1.5.97, AE/GOG, or VR. Address Library-style indirection reduces some AE/SE churn but does not make a DLL universally compatible. UI frameworks include SkyUI and MCM-related systems; if they fail, configuration and menus fail even when plugins load. Papyrus extension frameworks such as PapyrusUtil expand scripting APIs and can become hard dependencies for quests, widgets, or storage. Content frameworks provide shared systems that other mods plug into.

Trap signals: no changelog across game updates, hardcoded runtime support, abandoned bug reports after a breaking AE update, contradictory dependency requirements, or a framework whose dependents have moved on while the original remains pinned to old binaries.

Adoption order matters. Install and verify the foundational runtime layer before adding content that depends on it, then confirm MCM registration, Papyrus storage, and DLL loading in game. A missing framework can masquerade as a broken quest, invisible widget, or unexplained crash later.

## Perspective: SUBJECTIVE — BB84 curator reference (not a universal rubric)

BB84’s Skyrim baseline is conservative: SKSE/SkyUI/Address Library/PapyrusUtil/MCM are treated as the core utility layer, not as style choices. That reflects one curator’s preference for mature infrastructure before adding content. A pure visual showcase or tightly scoped vanilla-plus list may use fewer frameworks; a heavy gameplay overhaul may need more. The transferable rule is to understand the framework’s maintenance and runtime contract before adopting it.

His bias is toward boring, widely adopted dependencies whose failure modes are well known.

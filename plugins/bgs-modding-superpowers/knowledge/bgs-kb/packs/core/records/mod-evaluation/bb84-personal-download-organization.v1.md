---
id: mod-evaluation.bb84-personal-download-organization.v1
title: BB84 curator's personal mod download organization (REFERENCE ONLY — not universal)
kind: explanation
domains: [install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: 'BB84 (this plugin''s primary curator) downloads all non-CC Starfield mods to `F:\Starfield Mods\<37-category-tree>\` (e.g. `Utilities/`, `Ship Build/`, `Animation-Character/`, `Quests/`). This is a curator''s PERSONAL organization preference and SHOULD NOT be imposed on other users — agent must respect each user''s chosen download location.'
  confidence: high
queryKeys: [BB84 personal rule, 'F:\Starfield Mods', download organization, curator convention, subjective]
severity: low
sources:
  - kind: project-internal-doc
    url: "https://github.com/BB-84C/bgs-modding-superpowers"
    ref: "bgs-modding-superpowers plugin AGENTS.md — BB84 personal rules section"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# BB84 curator's personal mod download organization (REFERENCE ONLY — not universal)

## Perspective: OBJECTIVE

Mod downloads should land in a predictable user-chosen location, not scattered across temp directories or browser defaults. A stable download root makes provenance, reinstall, and rollback easier to audit. Beyond that, the specific folder tree is curator preference, not a universal modding rule.

## Perspective: SUBJECTIVE — BB84 curator reference (not a universal rubric)

BB84 organizes non-CC Starfield mods under `F:\Starfield Mods\<category>\` with 37 categories: Animation-Character, Animation-Ship, Armors, Audio-Replacement, Bug Fix, Character Beauty, Clothing, Companions, Enviorment [sic], Game Play, Immersion, INI Tweaks, Interface and HUD, Meshes-Weapons, My Mods, My Plugins, New Ship Parts, NPCs, Performance, Photo Mode, POI - New, POI - Tweaks, Quests, Reshade and ENB, Settlement, Ship Build, Sound FX, Textures, Tools, Utilities, Vanilla Planets Tweaks, Visual, Weapon - Vanilla Tweaks, Worldspace, WorldSpace - Main Quest, xEdit Scripts.

When an agent is operating in BB84's environment and downloads a new mod, prefer placing it in the matching category subdirectory. When the agent is operating in a different user's environment, ask where downloads go; do not assume `F:\` or any specific path exists.

CC mods follow a different path entirely (see `install-planning.cc-content-pipeline.v1`): downloads happen in-game, then files appear in MO2 `overwrite/` for later materialization into organized mod folders.

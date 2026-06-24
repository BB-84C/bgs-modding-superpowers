---
id: install-planning.script-extender-version-matrix.v1
title: Script extender version matrix and Address Library discipline
kind: rule
domains: [install-planning, engine]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "Every script-extender DLL must match the game runtime family and version; Address Library reduces per-update churn for compatible plugins but does not make wrong-runtime plugins load."
  confidence: high
queryKeys: [script extender, SKSE, F4SE, SFSE, xNVSE, Address Library, runtime version]
severity: high
sources:
  - kind: tooling-docs
    url: "https://skse.silverlock.org/"
    ref: "SKSE official runtime downloads"
  - kind: tooling-docs
    url: "https://f4se.silverlock.org/"
    ref: "F4SE official runtime downloads"
  - kind: tooling-docs
    url: "https://sfse.silverlock.org/"
    ref: "SFSE official runtime downloads"
  - kind: tooling-docs
    url: "https://github.com/xNVSE/NVSE"
    ref: "xNVSE project"
  - kind: community-forum
    url: "https://www.nexusmods.com/skyrimspecialedition/mods/32444"
    ref: "Address Library for SKSE Plugins Nexus page"
  - kind: community-forum
    url: "https://www.nexusmods.com/fallout4/mods/47327"
    ref: "Address Library for F4SE Plugins Nexus page"
  - kind: community-forum
    url: "https://www.nexusmods.com/starfield/mods/3256"
    ref: "Address Library for SFSE Plugins Nexus page"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Script extender version matrix and Address Library discipline

Script extender failures are version-matrix failures before they are mysterious mod conflicts. Skyrim LE uses the original SKSE line, Skyrim SE/AE/VR use SKSE64 branches tied to their executable families, Fallout 4 uses F4SE, Starfield uses SFSE, and Fallout New Vegas uses modern xNVSE. Fallout 3 has no equivalent modern universal script-extender ecosystem and must be handled with game-specific assumptions.

The first check is always the runtime executable version, not the mod page headline. Skyrim AE versus SE and Fallout 4 pre-next-gen versus next-gen are split points because Creation Kit/runtime updates changed addresses and plugin ABI expectations. A mod built against one runtime may hard-fail or silently skip its DLL entry point on another. Starfield has the same discipline: SFSE, Address Library, and SFSE plugins must align with the current Starfield build.

Address Library is a compatibility layer, not a force field from Big MT. When a plugin was built to use it correctly, the author can target stable address IDs instead of recompiling for every executable update. When a plugin embeds raw offsets, depends on removed engine behavior, or targets the wrong script extender branch, Address Library cannot save it.

Troubleshooting "script extender plugin will not load" should follow a fixed order: confirm the game runtime version, confirm the correct script extender executable launches through the mod manager, confirm the DLL architecture and game family, confirm Address Library is installed where required, read the extender loader log, then check whether the plugin page names the current runtime. Do not patch around a loader mismatch with load order changes; load order cannot fix a wrong binary contract.

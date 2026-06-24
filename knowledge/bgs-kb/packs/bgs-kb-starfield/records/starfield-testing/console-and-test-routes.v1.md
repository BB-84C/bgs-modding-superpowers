---
id: starfield-testing.console-and-test-routes.v1
title: Starfield console and safe test routes
kind: workflow
domains: [install-planning]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: Use Starfield console tests as short, disposable route checks only; verify real behavior through targeted cells, staged saves, and SFSE/Trainwreck readback rather than treating console success as pack stability.
  confidence: high
queryKeys: [Starfield console testing, QASmoke, coc, tcl, tgm, Trainwreck]
severity: medium
sources:
  - kind: tooling-docs
    url: "https://www.nexusmods.com/starfield/mods/5068"
    ref: Trainwreck - A Crash Logger
  - kind: official
    url: "https://store.steampowered.com/app/2722710/"
    ref: Starfield Creation Kit Steam page
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Starfield console and safe test routes

Starfield console testing is best used to shorten travel and isolate a route, not to prove a modpack is stable. Keep a throwaway save before testing, then use `coc` to jump into known interiors or test cells, `tcl` for collision/navigation checks, `tgm` for hostile-space traversal, `player.additem` for item-spawn verification, and `setstage` only when intentionally probing one quest stage. `saq` and broad stage forcing are destructive test hammers: they can advance unrelated quest state and should not be used on a real playthrough save.

For quick character setup, use a clean test profile, a fresh save, and only the minimum console state needed for the route. If a mod affects ships, outposts, planets, or dialogue, walk the real production path after the jump: land, enter the cell, talk to the NPC, open the workbench, or trigger the space encounter.

Crash tooling does not replace this route discipline. Trainwreck can provide crash logs under the SFSE crashlog path, but a no-crash result after one teleported route is only a smoke result. The pass condition is: console shortcut gets you to the scenario, then normal gameplay behavior matches the mod intent without corrupting the saved state.

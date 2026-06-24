---
id: fnv-testing.console-and-test-routes.v1
title: Console and safe test routes for Fallout 3, New Vegas, and TTW
kind: workflow
domains: [install-planning, debugging]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: Use console-driven test routes for quick smoke checks, but treat them as setup helpers rather than proof that quests, scripts, and leveled lists behave correctly in long play.
  confidence: high
queryKeys: [FNV console test, Fallout 3 console test, QASmoke, coc, tcl, tgm, TTW testing]
severity: high
sources:
  - kind: wiki
    ref: UESP Fallout New Vegas console commands
    url: https://en.uesp.net/wiki/Fallout:New_Vegas
    sectionPath: Console commands and gameplay reference
  - kind: community-forum
    ref: Viva New Vegas guide
    url: https://vivanewvegas.moddinglinked.com/
    sectionPath: Testing and final steps
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Console and safe test routes for Fallout 3, New Vegas, and TTW

Console testing is the fast route for Fallout 3, Fallout: New Vegas, and TTW setup verification. Use `coc` to move to a test cell or known exterior, `tcl` to cross blocked geometry, `tgm` to remove survival pressure, `player.additem` to give required gear, `setstage` only for narrow quest-state probes, and `saq` only as a destructive stress test on a disposable save. For character setup, make a fresh profile save after leaving character generation, then clone it for each batch check.

Useful checks are deliberately small: launch the game through the intended runtime, load the test save, verify menus and NVSE/JIP-dependent MCM-like features, visit one interior and one exterior, spawn or visit a recently touched NPC type, and inspect inventory/drop behavior for new leveled-list content. `QASmoke`-style cells are useful for item and menu access, but they do not prove world integration.

The traps are also objective. Console shortcuts can mask load-order errors, skipped quest preconditions, or scripts that only fail after real travel and save/load cycles. Mods that disable console access or alter start sequences must be documented before testing, not discovered mid-run. TTW adds a second worldspace and stricter assumptions about both games being present, so include at least one Capital Wasteland and one Mojave travel/readback path before calling a TTW batch healthy.

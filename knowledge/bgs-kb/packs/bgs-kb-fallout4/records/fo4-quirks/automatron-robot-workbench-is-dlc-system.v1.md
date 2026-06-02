---
id: fo4-quirks.automatron-robot-workbench-is-dlc-system.v1
title: Automatron Robot Workbench issues involve DLC quest and settlement systems
domains: [engine, debugging]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Robot Workbench problems are not just crafting-menu issues; Automatron adds a DLC questline, settlement object, and robot companion customization system.
  confidence: high
queryKeys: [Automatron, Robot Workbench, DLCRobot.esm, robot mods]
severity: high
sources:
  - kind: wiki
    url: "https://fallout.wiki/wiki/Automatron_(add-on)"
    ref: Fallout Wiki Automatron add-on
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Automatron Robot Workbench issues involve DLC quest and settlement systems

Automatron adds `DLCRobot.esm`, its questline, and the Robot Workbench settlement object.
That means crashes or missing menus can involve DLC load state, quest progression, workshop placement, and robot mod data.

Check whether Automatron is present and active before diagnosing robot workbench failures.
If the issue appears after a robot overhaul, inspect both plugin conflicts and workshop/script state.

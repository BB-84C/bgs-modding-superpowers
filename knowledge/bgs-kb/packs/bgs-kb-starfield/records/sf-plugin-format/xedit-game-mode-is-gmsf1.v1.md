---
id: sf-plugin-format.xedit-game-mode-is-gmsf1.v1
title: xEdit uses gmSF1 as the Starfield game mode
domains: [xedit, plugin-format, debugging]
appliesTo:
  games: [Starfield]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV]
canonical:
  answer: The xEdit fork's game-mode enum and startup logic identify Starfield as `gmSF1`, so Starfield xEdit work should use the SF1/Starfield mode rather than a Fallout 4 mode.
  confidence: verified-tooling
queryKeys: [gmSF1, SF1Edit, xEdit Starfield mode, Starfield xEdit]
severity: critical
sources:
  - kind: tooling-docs
    ref: D:/TES5Edit-contrib/Core/wbInterface.pas
    sectionPath: TwbGameMode enum
  - kind: tooling-docs
    ref: D:/TES5Edit-contrib/xEdit/xeInit.pas
    sectionPath: isMode('SF1')
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit uses gmSF1 as the Starfield game mode

The local xEdit fork includes `gmSF1` in the game-mode enum and assigns it when `SF1` mode is selected.
That is the canonical xEdit-side mode name for Starfield in this tooling track.

Agents should not launch Starfield plugin checks under FO4 or generic Creation Engine assumptions.
The first readback question is whether the session is actually in Starfield mode.

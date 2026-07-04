---
id: plugin-format.scene-dialogue-option-hiding.v1
title: Scene-driven player dialogue options cannot be hidden by INFO conditions alone
kind: gotcha
domains: [plugin-format, xedit]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: In Starfield scene-driven dialogue, hiding only the INFO response with impossible conditions can leave the SCEN player-dialogue action alive and make the engine render a placeholder such as "No Dialogue Action on Player in First Phase". First determine whether the dialogue option is topic-driven or SCEN-driven; for dedicated scenes, hide at the SCEN/action visibility layer, while shared vendor scenes should not be globally disabled just to hide one option.
  confidence: verified-project-doc
queryKeys: [SCEN dialogue option, INFO condition hide, No Dialogue Action on Player in First Phase, scene-driven dialogue, Starfield vendor scene]
severity: high
sources:
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/E2E-FIELD-FINDINGS.md
    sectionPath: §7 Round-2 反馈与 Wave 2.7 修复
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/lane-b/FUEL-RECORDS-CONSTRUCTION-REPORT.md
    sectionPath: Wave 2.7 修复轮 — scene 占位串与 rover 解伤
related: [plugin-format.qust-override-shells-are-group-parents.v1]
lastReviewed: "2026-07-04"
schemaVersion: 1
---

# Scene-driven player dialogue options cannot be hidden by INFO conditions alone

Do not assume every visible player dialogue option is controlled only by its `INFO` conditions. In Starfield scene-driven dialogue, the player-facing action is owned by a `SCEN` tree. If a patch makes the `INFO` response impossible while leaving the scene action alive, the engine may still try to render the player action and display a placeholder string instead of cleanly removing the option.

The first diagnostic step is to classify the surface:

1. If the option is normal topic dialogue, `INFO` conditions may be the correct layer.
2. If the option is driven by a dedicated `SCEN`, inspect the scene actions and apply visibility control at the scene/action layer without deleting or reordering fragments.
3. If the option is embedded in a shared vendor or quest scene, do not put an impossible condition on the whole `SCEN` unless suppressing the entire scene is intended. Prefer leaving the shared scene intact or redesigning the surviving prompt text.

Reference case: hiding Starvival ship-service top-up `INFO` records produced `No Dialogue Action on Player in First Phase` placeholders for ship and vehicle service dialogue. The safe repair removed the `INFO` overrides, hid only the two dedicated ship-refuel `SCEN` records with a top-level impossible condition, and deliberately left the shared Key vendor scene alone.

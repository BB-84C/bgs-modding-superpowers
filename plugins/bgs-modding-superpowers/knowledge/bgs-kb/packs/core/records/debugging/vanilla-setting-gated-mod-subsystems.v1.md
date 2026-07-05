---
id: debugging.vanilla-setting-gated-mod-subsystems.v1
title: Mod subsystems can be gated by vanilla difficulty or gameplay settings
kind: rule
domains: [debugging, engine, plugin-format]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: When a mod mechanic does not trigger, read the full record condition chain before blaming the script. Mods often reuse vanilla CNDF/MGEF primitives that inherit vanilla difficulty or game-setting GLOB gates, so the player setting can make a mod subsystem look broken while another UI meter still moves normally.
  confidence: verified-project-doc
queryKeys:
  - vanilla difficulty gate
  - game setting GLOB
  - PEO_EnvironmentalDamage_GV
  - AtRisk condition
  - ENV_Damage_Soak
  - actor value meter mismatch
  - mod mechanic not triggering
severity: high
sources:
  - kind: project-internal-doc
    ref: BB84 Starfield P10 Wave 3.5-4 field notes
    sectionPath: Starvival ESPS environment protection reserve drain diagnosis
related:
  - debugging.shared-actor-value-ground-truth.v1
  - load-order.cross-cutting-record-audit.v1
lastReviewed: "2026-07-05"
schemaVersion: 1
---

# Mod subsystems can be gated by vanilla difficulty or gameplay settings

## The trap

A mod subsystem can be correctly installed, correctly scripted, and still appear inert because a vanilla condition primitive gates the whole effect. Bethesda records are composable: a mod can attach its own AVs, effects, and scripts behind vanilla CNDF/MGEF condition functions. If those vanilla primitives reference game-setting globals, the mod inherits the player's difficulty setting even when the mod UI never says so.

This is especially misleading when two meters that sound related read different actor values. One meter can move because it is vanilla-facing; another can stay flat because the mod's reserve drain is behind a difficulty gate.

## Diagnostic discipline

When a mod mechanic does not trigger:

1. Read the full MGEF/SPEL/PERK/QUST condition chain, not just the mod script.
2. Expand named CNDF-style helper records and follow any vanilla GLOB they reference.
3. Check the player's relevant gameplay and difficulty settings before blaming Papyrus.
4. Distinguish script property names from real `AVIF` EditorIDs when using console `getvalue` or xEdit readback.
5. Separate UI meters by actual AVIF source; two gauges can look semantically adjacent while reading unrelated values.

## Starvival ESPS example

Starvival's ESPS environment-protection decay looked broken: the spacesuit radiation reserve did not drain while the vanilla SOAK meter collapsed instantly. The condition chain showed the cause. The Starvival reserve drain was gated through vanilla `PEO_ENV_CND_ExtremeEnvironment_AtRisk [CNDF:002EDFF5]`, whose semantics included either missing a complete spacesuit or `PEO_EnvironmentalDamage_GV [GLOB:0020E61D] == 3` (highest environmental-damage difficulty). At difficulty 1 or 2, wearing a complete suit made `AtRisk` false, so the reserve never drained.

At the same time, vanilla SOAK (`ENV_Damage_Soak [AVIF:00000313]`) behaved normally because its own suppression path is active at difficulty 1 or 2. That produced the confusing observation: one environmental meter moved, the other did not. Raising environmental damage to the highest setting made the Starvival reserve drain behave normally, including solar hiding behavior.

## Practical rule

If a mod subsystem appears dead only under some player settings, treat vanilla difficulty/gameplay GLOBs as first-class suspects. The fix may be documentation, config guidance, or a deliberate patch to replace the inherited gate; it is not automatically a script bug.

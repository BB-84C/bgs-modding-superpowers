---
id: debugging.shared-actor-value-ground-truth.v1
title: Shared actor values require dual-UI field validation before assigning mechanic ownership
kind: rule
domains: [debugging, papyrus, plugin-format]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
canonical:
  answer: When two mods appear to expose the same gameplay meter, do not assign ownership from one AVIF name, VMAD property label, or recon document alone. Validate the shared ground truth in game through independent UI/readback surfaces; if both mods read or write the same actor value, one mod's view-only UI may be honest while its action surfaces and AV event registrations still need removal.
  confidence: verified-project-doc
queryKeys: [shared actor value, AVIF ownership, AVLessThan, dual UI validation, ground truth meter, view-only UI]
severity: high
sources:
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/E2E-FIELD-FINDINGS.md
    sectionPath: §5 BB84 第二轮实测修正; §6 Wave 2.6 定稿范围
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/lane-a/LANE-A-CONSTRUCTION-REPORT.md
    sectionPath: Wave 2.6 修补 — 残留交互面清理
related: [papyrus.actor-value-mod-damage-force.v1, install-planning.partial-disable-requires-author-toggle.v1]
lastReviewed: "2026-07-04"
schemaVersion: 1
---

# Shared actor values require dual-UI field validation before assigning mechanic ownership

Actor-value names and script property names can mislead subsystem-ownership analysis. A mod may expose a meter under its own property label while another mod also reads or writes the same underlying actor value. Static recon should therefore classify AV ownership claims as hypotheses until field readback compares independent surfaces.

Validation pattern:

1. Identify every UI, console, or log surface that reports the meter.
2. Change the value through one candidate owner and observe whether the other surface moves in lockstep.
3. If both surfaces track the same number, preserve honest read-only mirrors when they help the user.
4. Remove or short-circuit mutation paths, tutorial text, procurement loops, and `RegisterForActorValueLessThanEvent` handlers that imply the retired subsystem still owns the mechanic.
5. Re-audit AVLessThan registrations: writes from the replacement mod can trigger the legacy mod's low-value handler if it remains registered.

Reference case: field testing showed Real Fuel and Starvival's `SpaceshipFuelTank` property reflected the same fuel value. The Starview Analyzer fuel percentage became an acceptable read-only mirror, while Starvival refuel buttons, low-fuel warnings, and AVLessThan auto-injector paths remained removal targets.

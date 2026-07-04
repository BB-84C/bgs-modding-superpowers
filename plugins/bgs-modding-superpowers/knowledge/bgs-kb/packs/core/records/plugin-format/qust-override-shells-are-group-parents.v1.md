---
id: plugin-format.qust-override-shells-are-group-parents.v1
title: QUST override shells can be required parent groups for nested SCEN, DIAL, and INFO overrides
kind: gotcha
domains: [plugin-format, xedit]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: In Starfield nested dialogue trees, a QUST override that looks like an empty shell may be the required parent group for child SCEN, DIAL, or INFO overrides. xEdit copy_into may create that shell automatically; deleting it as a suspected ITM can cascade-delete the child override payload, so inspect the child tree before shell cleanup.
  confidence: verified-project-doc
queryKeys: [QUST shell, SCEN child, nested dialogue tree, child group parent, copy_into, cascade delete]
severity: high
sources:
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/E2E-FIELD-FINDINGS.md
    sectionPath: §8 Analyzer 卡死事件结案
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/lane-b/FUEL-RECORDS-CONSTRUCTION-REPORT.md
    sectionPath: Wave 2.7b 重建 — SCEN override 恢复
related: [xedit.xedit-childgroup-navigation.v1, xedit.xedit-records-create-parent-spec.v1, plugin-format.scene-dialogue-option-hiding.v1]
lastReviewed: "2026-07-04"
schemaVersion: 1
---

# QUST override shells can be required parent groups for nested SCEN, DIAL, and INFO overrides

In Starfield's nested dialogue record trees, an apparently empty `QUST` override can be structural, not dirty. It may exist only because a child `SCEN`, `DIAL`, or `INFO` override needs its parent group present in the target file.

Before cleaning a suspected ITM-like `QUST` shell:

1. List the target file's child records under that quest.
2. Check whether any child `SCEN`, `DIAL`, or `INFO` override is the real patch payload.
3. If the child override is needed, keep the parent `QUST` shell even if the quest record itself carries no meaningful field edits.
4. Only delete the shell when the entire child subtree is intentionally being removed.

`records.copy_into` can create these parent shells automatically. That is expected behavior; the shell is part of the group topology required to store the child override. Deleting the parent shell is not a harmless cleanup operation.

Reference case: a cleanup pass deleted “vanilla shell” `QUST` overrides and accidentally removed the child `SCEN` conditions that hid Starvival ship top-up scenes. The fix was to rebuild the two `SCEN` overrides and accept the required parent shells for `DialogueShipServices` and `DialogueRedMile`.

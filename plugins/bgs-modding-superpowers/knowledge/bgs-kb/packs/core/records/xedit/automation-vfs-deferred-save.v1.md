---
id: xedit.automation-vfs-deferred-save.v1
title: xEdit automation saves through MO2 VFS may flush plugin files only on daemon shutdown
kind: gotcha
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "When xEdit automation edits a plugin projected through MO2 VFS from a mods folder, session.save may return savedFilesPendingShutdown and savePendingShutdownCount, deferring the physical write until daemon shutdown. The MCP must fail closed: retain the pending state, surface it through xedit_dirty, and refuse normal stop/restart. force:true is auditable abandonment, not a way to flush or prove durability."
  confidence: verified-project-doc
queryKeys: [xEdit automation, MO2 VFS save, savedFilesPendingShutdown, overwrite esm.save, TES4 magic, Small flag, flags.esl]
severity: critical
sources:
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/E2E-FIELD-FINDINGS.md
    sectionPath: §7 Round-2 反馈与 Wave 2.7 修复
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/lane-b/FUEL-RECORDS-CONSTRUCTION-REPORT.md
    sectionPath: Wave 2.7 修复轮; Wave 2.7b 重建
  - kind: project-internal-doc
    ref: .opencode/artifacts/bb84-starfield-lane3-audit/lane-3.5-p10-wave2/lane-b/LANE-B-CONSTRUCTION-REPORT.md
    sectionPath: xEdit record 层证据与风险; Orchestrator 勘误
related: [xedit.session-save-deferred-when-pending-shutdown.v1, plugin-format.light-plugin-formid-range.v1, load-order.esl-flag-lives-in-header.v1]
lastReviewed: "2026-08-02"
schemaVersion: 1
---

# xEdit automation saves through MO2 VFS may flush plugin files only on daemon shutdown

`session.save` is a state transition, not always an immediate physical file write. Under MO2 VFS, a plugin that xEdit sees through a projected mod folder can be held for deferred save and only flushed when the automation daemon exits. The resulting file may appear in `overwrite` with a name like `<plugin>.esm.save.<timestamp>` rather than replacing the projected mod file directly.

Safe workflow:

1. Inspect `session.save` for `savedFilesPendingShutdown`.
2. If pending, do not copy a stale plugin from the mod folder or assume the overwrite path is empty.
3. Keep the daemon alive while the MCP reports pending state. `dirty:false` does
   not clear the guard.
4. Do not use normal stop/restart to make or prove the flush. The current
   automation surface has no authoritative pending-queue inspection or flush
   operation.
5. `force:true` is explicit, auditable abandonment, not a successful save path.

Light-plugin shape is a separate guardrail. Starfield automation refused `files.create(... flags.esm=true, flags.esl=true ...)` with `Automation .esm files must not set flags.esl true`, and xEdit refused adding or removing the `Small` light flag on an already-saved file. If a patch must become light, rebuild it through an accepted creation route; do not flip the flag on an existing full ESM during the same save path.

Reference case: P10 Wave 2.7 saved `BB84_Starvival_Fuel_Off_Patch.esm` with
`savedFilesPendingShutdown`; the shutdown-time output demonstrated the deferred
path, but it does not make lifecycle restart a safe generic durability recipe.

---
id: xedit.automation-vfs-deferred-save.v1
title: xEdit automation saves through MO2 VFS may flush plugin files only on daemon shutdown
kind: gotcha
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "When xEdit automation edits a plugin projected through MO2 VFS, session.save may defer the final rename. On contract 0.23, surface the authoritative queue through xedit_dirty and resolve it with xedit_flush; require a complete zero-remaining result, confirmed daemon self-exit, and fresh-daemon readback. force:true on stop/restart is abandonment, not durability."
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
lastReviewed: "2026-08-11"
schemaVersion: 1
---

# xEdit automation saves through MO2 VFS may flush plugin files only on daemon shutdown

`session.save` is a state transition, not always an immediate physical file write. Under MO2 VFS, a plugin that xEdit sees through a projected mod folder can be held for deferred save and only flushed when the automation daemon exits. The resulting file may appear in `overwrite` with a name like `<plugin>.esm.save.<timestamp>` rather than replacing the projected mod file directly.

Safe workflow:

1. Inspect `session.save` for `savedFilesPendingShutdown`.
2. If pending, do not copy a stale plugin from the mod folder or assume the overwrite path is empty.
3. `dirty:false` does not clear the guard. On contract 0.23, use the daemon's
   authoritative pending readback rather than assuming local tracker state is complete.
4. Call `xedit_flush`. Require a validated `completed` response with zero
   `pendingRemaining`, then relaunch and read the plugin from a fresh daemon.
5. A partial flush means failed in-band renames remain queued for one final
   process-exit retry. Relaunch and read the plugin back before deciding the
   result. An unknown outcome is likewise residue to investigate, not a pass.
6. `force:true` on stop/restart is explicit, auditable abandonment, not a
   successful save path.

Light-plugin shape is a separate guardrail. Starfield automation refused `files.create(... flags.esm=true, flags.esl=true ...)` with `Automation .esm files must not set flags.esl true`, and xEdit refused adding or removing the `Small` light flag on an already-saved file. If a patch must become light, rebuild it through an accepted creation route; do not flip the flag on an existing full ESM during the same save path.

Reference case: P10 Wave 2.7 saved `BB84_Starvival_Fuel_Off_Patch.esm` with
`savedFilesPendingShutdown`; the shutdown-time output demonstrated the deferred
path. Contract 0.23 supplies a deliberate flush-and-exit boundary, but ordinary
restart still is not a durability recipe.

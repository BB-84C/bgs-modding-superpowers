---
id: xedit.automation-vfs-deferred-save.v1
title: xEdit automation saves through MO2 VFS may flush plugin files only on daemon shutdown
kind: gotcha
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "When xEdit automation edits a plugin projected through MO2 VFS from a mods folder, session.save may return savedFilesPendingShutdown and defer the physical write until daemon shutdown, often as a <plugin>.save.<timestamp> file in overwrite. Treat that as a handoff artifact: after shutdown, verify TES4 magic and expected records before replacing the MO2 mod's plugin file; do not claim durability from the save response alone."
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
lastReviewed: "2026-07-04"
schemaVersion: 1
---

# xEdit automation saves through MO2 VFS may flush plugin files only on daemon shutdown

`session.save` is a state transition, not always an immediate physical file write. Under MO2 VFS, a plugin that xEdit sees through a projected mod folder can be held for deferred save and only flushed when the automation daemon exits. The resulting file may appear in `overwrite` with a name like `<plugin>.esm.save.<timestamp>` rather than replacing the projected mod file directly.

Safe workflow:

1. Inspect `session.save` for `savedFilesPendingShutdown`.
2. If pending, do not copy a stale plugin from the mod folder or assume the overwrite path is empty.
3. After the daemon is shut down by the authorized controller, find the flushed `.save.<timestamp>` artifact.
4. Verify the file starts with `TES4` magic and read back the expected records or header flags before installing it over the MO2 mod's plugin file.
5. Clear only the known handoff artifact from `overwrite` after the replacement is verified.

Light-plugin shape is a separate guardrail. Starfield automation refused `files.create(... flags.esm=true, flags.esl=true ...)` with `Automation .esm files must not set flags.esl true`, and xEdit refused adding or removing the `Small` light flag on an already-saved file. If a patch must become light, rebuild it through an accepted creation route; do not flip the flag on an existing full ESM during the same save path.

Reference case: P10 Wave 2.7 saved `BB84_Starvival_Fuel_Off_Patch.esm` with `savedFilesPendingShutdown`; daemon shutdown later produced an `.esm.save.<timestamp>` file in `overwrite`, which was validated by TES4 magic before being swapped into the MO2 overlay.

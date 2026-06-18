# Release Notes

## v0.1.0 (unreleased)

Initial release as `bgs-modding-superpowers` — agent plugin for Bethesda Game Studio modpack curation. Installs on OpenCode, Claude Code, and Codex.

### Added

- `xedit` MCP server with nine intent tools and atomic passthrough over the native daemon command set discovered at runtime via `system.capabilities`. 7-stage harness pipeline (validate / state-check / rules / forward / envelope / audit).
- TES5Edit-contrib release alignment line documented for `v4.1.6-automation.r3` / `r4` / `r5` / `r6`; this branch expects capability contract `0.20` after the r6 alignment.
- Aligned to TES5Edit-contrib `v4.1.6-automation.r6` (contract `0.20`): four new intent tools (`xedit_inspect_conflicts_deep`, `xedit_find_records_by_pattern`, `xedit_create_child_record`, `xedit_navigate_ancestry`); eight new capability blocks surfaced in `capabilities-digest`; eight new KB records under `bgs-kb-core/records/xedit`; skills taught r6 progressive-disclosure patterns.
- `xedit_start` and `xedit_restart` now accept an optional `iKnowWhatImDoing: boolean` to launch the xEdit daemon with the `-IKnowWhatImDoing` startup flag. Without it, mutating intent tools (`xedit_create_child_record`, future `records.delete` wrappers, etc.) fast-fail with `mutation_requires_iknowwhatimdoing`. Verify via `xedit_session.data.consentEnabled === true` after launch. Closes the architectural gap where consent could not be enabled through the MCP wire (#8).

### Fixed (post-r6 real-daemon E2E audit, 2026-06-18)

The following bugs were invisible to mock-tier unit tests and only surfaced during end-to-end wire verification against the FO4Edit 4.1.6r6 daemon:

- `xedit_find_records_by_pattern` now wraps the singular `file` arg into `files: [file]` before forwarding to `records.apply_filter`. The daemon requires the array form; without the wrap, every call returned `invalid_request: 'files' must contain at least one plugin name`. Regression guard test asserts `forwarded.files === [file]` and `forwarded.file === undefined`.
- `xedit_session.data.consentEnabled` now reads from the daemon's nested `supports.elementsMutation.iKnowWhatImDoing` (and `supports.scripts.execution.iKnowWhatImDoing` as fallback), not the non-existent top-level `supports.iKnowWhatImDoing`. The old code path was undetectable until consent forwarding (#8) wired the flag end-to-end. Regression guards pin the nested-only resolution.
- `xedit_create_child_record` intent-tool schema realigned with the daemon and the KB record (both use `parent: { file, formId, subGroup?, coords? }`). Previous schema used `parent: { parentFile, parentFormId, ... }` which never produced a successful daemon call. Replaced the inter-shape translator with a transparent 0x-prefix strip; documentation is now single-source-of-truth across MCP / KB / daemon.
- `bgs_kb_query` now gracefully skips packs whose schema lacks the `records` / `records_fts` tables (e.g. the glossary-schema pack `bgs-l10n-starfield-zhhans`). Previously the whole cross-pack query aborted on `no such table: records_fts` from the first glossary session encountered. Skipped packs are surfaced in `stats.skippedPacks` so the agent can see why they were excluded.
- MO2 control-plane installer: C++ plugin DLL + Python loader + broker, deployable into any MO2 install via `scripts/install-mo2-control-plane.ps1`.
- xEdit hook bridge: owned `xEditHookBridge.dll`, shipped from `tools/xedit-hook-bridge/dist/`.
- Skills:
  - `using-bgs-modding-superpowers` — per-session bootstrap.
  - `setting-up-bgs-modding-environment` — first-run setup orchestrator.
  - `xedit-automation` — hub skill for all xEdit work.
  - `xedit-conflict-audit` — W2 conflict-audit workflow.
  - `writing-modpack-devlog` — runtime dev-log creator/appender.
  - `writing-modpack-changelog` — runtime release-changelog creator/appender.
- Per-harness manifests: `.claude-plugin/{plugin,marketplace}.json`, `.codex-plugin/plugin.json`, `.opencode/plugins/bgs-modding-superpowers.js`, shared `.mcp.json`.
- `scripts/fetch-xedit-release.ps1` — download the agent-friendly xEdit fork from [BB-84C/TES5Edit](https://github.com/BB-84C/TES5Edit) into `<MO2>/tools/xEdit/`.
- Version sync via `.version-bump.json` + `scripts/bump-version.sh`.

### Reshaped (internal)

- Repo restructured from `awesome-bgs-mod-master` dev harness into Superpowers-shaped multi-harness plugin. See `docs/internal/superpowers/plans/2026-05-31-reshape-to-superpowers-plugin-shape.md`.
- Working skills moved out of `.opencode/skills/` (gitignored) into tracked top-level `skills/`.
- Phase-0 stub skills relocated to `docs/internal/future-skills/` as design notes.

### Known limitations

- Windows-only. The MO2 control plane and xEdit hook bridge depend on the Windows MO2 runtime.
- Codex `.mcp.json` `${CLAUDE_PLUGIN_ROOT}` substitution is observed to work for Claude Code; Codex behavior is verified during acceptance smoke tests.
- Cursor and Gemini CLI support not yet shipped — deferred to v0.2.
- `nexus-metadata`, `loot-metadata`, `translation-memory` MCPs are designed (see `docs/internal/mcp-specs/`) but not implemented yet.

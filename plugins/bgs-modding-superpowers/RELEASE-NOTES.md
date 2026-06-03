# Release Notes

## v0.1.0 (unreleased)

Initial release as `bgs-modding-superpowers` — agent plugin for Bethesda Game Studio modpack curation. Installs on OpenCode, Claude Code, and Codex.

### Added

- `xedit` MCP server with six intent tools and atomic passthrough. 7-stage harness pipeline (validate / state-check / rules / forward / envelope / audit).
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

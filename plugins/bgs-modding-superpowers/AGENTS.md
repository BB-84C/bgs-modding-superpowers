---
title: bgs-modding-superpowers - materialized plugin tree
status: generated
scope: distribution-mirror
---

# This directory is a generated mirror - do not hand-edit

This plugins/bgs-modding-superpowers/ tree is **rematerialized** from the
repo-root source layout by scripts/build-portable-plugin.ps1. End users
install the plugin by cloning this directory only (via OpenCode / Claude Code
vendor cache or Codex marketplace). Edits made here will be overwritten the
next time the build script runs.

## What is canonical (source of truth)

Edit these instead:

| You want to change ... | Edit here |
|---|---|
| Skill content (.md files under skills/<name>/) | repo-root `skills/<name>/` |
| MCP server code (gs-kb-mcp / xedit-mcp) | `tools/<mcp>/src/` - then `npm run build` in that dir |
| `bgs-translator` (Python `xtl`) docs / helper scripts | `tools/bgs-translator/` - Python runtime is PyPI-published; only docs + scripts are mirrored here |
| `xEditHookBridge.dll` | Rebuild from the sister xEdit fork (`D:\TES5Edit-contrib`), then drop into `tools/xedit-hook-bridge/dist/` |
| MO2 control plane (Python plugin + broker) | `tools/mo2-control-plane/` |
| MO2 VFS launcher (PowerShell + xedit-client) | `tools/mo2-vfs-launcher/` |
| Hooks (session-start chain) | `hooks/` |
| Top-level scripts (installers, fetchers, build) | `scripts/` |
| Plugin manifests (`.claude-plugin`, `.codex-plugin`, `.mcp.json`, OpenCode entrypoint) | repo root |
| Bundled core KB pack (`knowledge/bgs-kb/packs/core/`) | repo root `knowledge/bgs-kb/packs/core/` |
| `RELEASE-NOTES.md`, `README.md`, `LICENSE`, `package.json` | repo root |

## Rebuild command (canonical)

```powershell
# 1. Rebuild MCP server bundles if any `tools/<mcp>/src/` changed.
pwsh -Command "Set-Location <repo>\tools\xedit-mcp; npm run build"
pwsh -Command "Set-Location <repo>\tools\bgs-kb-mcp; npm run build"

# 2. Rematerialize the plugin tree from sources.
pwsh <repo>\scripts\build-portable-plugin.ps1 `
  -OutputDir plugins `
  -PluginName bgs-modding-superpowers `
  -McpPathStrategy relative `
  -Force
```

`-Force` removes and recreates this directory tree wholesale; do not skip it
on a re-materialize. `-OutputDir plugins -PluginName bgs-modding-superpowers`
overwrites THIS tree (relative to repo root). `-McpPathStrategy relative` is
the portable form that resolves on Codex marketplace caches and Claude Code
vendor caches alike.

The build script uses `robocopy /XD` for `tools/bgs-translator/` so Python
dev caches (`__pycache__`, `.mypy_cache`, `.pytest_cache`,
`.ruff_cache`, `*.egg-info`, `build/`, `dist/`, `.venv/`) are
excluded at any depth. `.gitignore` mirrors the same excludes.

## Two-commit shape for source changes

Per repo-root `AGENTS.md` (the operational truth for this project):

> Prefer two-commit shape when the change touches both the source tree and the
> materialized plugin tree: commit 1 = source / tests / regenerated `dist/`;
> commit 2 = mirrored `plugins/bgs-modding-superpowers/...` payload. This keeps
> the materializer-rebuild diff isolated and easy to revert.

So the standard flow is:

1. Edit sources under `skills/`, `tools/<mcp>/src/`,
   `tools/bgs-translator/`, `scripts/`, `hooks/`, etc.
2. Rebuild MCP `dist/` if any TypeScript changed.
3. Commit the source changes only.
4. Re-run `scripts/build-portable-plugin.ps1`.
5. Commit the regenerated `plugins/bgs-modding-superpowers/` payload as a
   separate commit titled e.g.
   `chore(plugin-dist): rematerialize after <source-change-title>`.
6. `git push`; vendor clones pull both commits in one
   `git pull --ff-only origin <branch>` and pick up the new functionality on
   next session bootstrap.

## What lives in this tree but NOT in source

Nothing intentionally. If something here has no source counterpart, that is a
sync bug. Open an issue or fix the build script.

## What lives in source but NOT in this tree (by design)

- `tools/bgs-translator/.venv/`, `__pycache__/`, `*.egg-info/`,
  `build/`, `dist/` - Python build artifacts; excluded by `robocopy /XD`.
- `knowledge/bgs-kb/packs/<per-game-or-l10n-pack>/` (everything other than
  `core/`) - large KB packs are GitHub-Release-distributed and installed via
  `bgs_kb_install_pack` at runtime; bundling them would balloon vendor clone
  size from tens of MB to >1 GB.
- `docs/`, `tests/`, `.opencode/`, `.git/` - development surfaces.
- `dist/portable-plugin/` - the build script's alternate output target.

## Sentinel rule

If you find yourself about to `Edit` or `Write` a file inside this
directory, **stop**. Find the canonical source per the table above, edit there,
and re-run the build script. The two-commit shape preserves the audit trail of
what was edited vs what was regenerated.
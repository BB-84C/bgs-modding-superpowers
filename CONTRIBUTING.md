# Contributing to `bgs-modding-superpowers`

Thanks for the interest. This doc is for contributors opening pull requests against this repo. End users should read [README.md](README.md) and [`.opencode/INSTALL.md`](.opencode/INSTALL.md) instead.

## Clone + bootstrap

```powershell
git clone https://github.com/BB-84C/bgs-modding-superpowers.git
cd bgs-modding-superpowers
# Build the xEdit MCP
cd tools/xedit-mcp
npm install
npm run build
cd ..\..
```

The repo carries a dedicated MO2 sandbox under `.artifacts/mo2/` (gitignored — bring your own for now). The development plan and roadmap live in `docs/internal/`.

## Branch conventions

- Work on feature branches: `feat/<topic>`, `fix/<topic>`, `chore/<topic>`, `reshape/<topic>`.
- Target `main` via pull request. Do not push directly to `main` (especially do not force-push).
- Prefer multiple small commits per logical step over one large monolithic commit.
- For ambiguous or high-risk implementation work, prefer best-of-N candidate generation over single-shotting.

## Test commands

- `tools/xedit-mcp/` — `npm test` (vitest unit tests). Integration tests live in `tools/xedit-mcp/tests/integration/` and require a running MO2 + xEdit; gate diagnostic-only tests behind `BGS_MCP_DIAG=1`.
- `tests/` (top-level) — PowerShell tests for the MO2 control plane and VFS launcher. Run with `pwsh -File tests/<suite>/...`.

## Where things live

| Path | Purpose |
|---|---|
| `skills/` | Shippable agent skills (Superpowers convention). Each dir has a `SKILL.md` with YAML frontmatter. |
| `tools/xedit-mcp/` | TypeScript MCP server. Pre-built `dist/` is tracked; `prepare` rebuilds on install. |
| `tools/mo2-vfs-launcher/` | PowerShell outer client for the xEdit MCP. Runtime dependency. |
| `tools/mo2-control-plane/` | C++ MO2 plugin DLL source, Python loader, broker. |
| `tools/xedit-hook-bridge/dist/` | Pre-built Delphi DLL (`xEditHookBridge.dll`). `.pas` source lives in the sister xEdit fork [BB-84C/TES5Edit](https://github.com/BB-84C/TES5Edit). |
| `.claude-plugin/`, `.codex-plugin/`, `.opencode/plugins/` | Per-harness manifests + OpenCode plugin wiring. All four manifests share `.mcp.json` for the MCP declaration. |
| `hooks/` | Claude Code / Codex session-start hook chain. |
| `scripts/` | Version bumping + (P6+) installer scripts. |
| `docs/internal/` | Roadmap, plans, design specs, hook + MCP specs, future-skills design notes. |
| `tests/`, `.artifacts/` | Dev-only verification scaffolding (gitignored as appropriate). |

## Pull request expectations

- Reference the issue or design doc the PR implements. Plans live under `docs/internal/superpowers/plans/`.
- Run the relevant test suite locally and report what passed.
- If the change touches shippable surfaces (skills, MCP, manifests, scripts), confirm it still installs cleanly into a fresh OpenCode profile against the dev MO2 sandbox.
- Don't commit `node_modules/`, `.artifacts/` content, or other gitignored material.

## Version bumping

Versions across `package.json`, `.claude-plugin/{plugin,marketplace}.json`, and `.codex-plugin/plugin.json` are kept in lockstep by `scripts/bump-version.sh` driven by `.version-bump.json`:

```powershell
bash scripts/bump-version.sh 0.2.0
```

(Requires `jq` available on PATH.)

## Code of conduct

Be civil. Don't ship code that you wouldn't be comfortable explaining to another maintainer in person.

## License

By contributing, you agree your contributions are licensed under the MIT license. See [LICENSE](LICENSE).

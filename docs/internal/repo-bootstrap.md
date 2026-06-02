# Repo Bootstrap (internal)

Notes for setting up the local dev environment for `bgs-modding-superpowers`.

## What this doc replaces

The pre-reshape `agents/repo-bootstrap/AGENT.md` (deleted) described a "repo-bootstrap agent" persona that maintained scaffold structure. That persona is no longer maintained as a separate agent role; its concerns are now covered by this doc plus the existing memory routers under `.opencode/memory/` and `AGENTS.md`.

## Local dev directory tree

| Path | Purpose | Tracked? |
|---|---|---|
| `.artifacts/mo2/` | Dedicated dev MO2 instance used for end-to-end verification of the plugin's MCP + control plane against real game state. | No (gitignored). Bring your own MO2 setup; the path is canonical for this repo. |
| `.artifacts/bgs-mod-plugins/` | Sample `.esp/.esm` fixtures across multiple games for parser/conflict experiments. | No |
| `.external-resource/` | MO2 installer + xEdit upstream mirror, for local convenience. | No |
| `.opencode/memory/` | Local agent memory routers (hygiene, harness, launcher architecture, Stock Game protection). | No |
| `.opencode/artifacts/` | Acceptance and brainstorm artifacts from prior implementation rounds. | No |
| `.worktrees/` | Worktree convention — when a feature branch needs a separate working tree. | No |
| `tests/` | PowerShell test suites for the MO2 control plane and VFS launcher. | Yes |
| `docs/internal/` | Plans, specs, design notes, future-skills design notes, hook + MCP specs. | Yes |
| `tools/` | All shippable runtime code (xedit-mcp, mo2-vfs-launcher, mo2-control-plane, xedit-hook-bridge). | Yes |
| `skills/` | Shippable Superpowers-shaped skills. | Yes |
| `hooks/`, `scripts/`, `.{claude,codex}-plugin/`, `.opencode/plugins/`, `.mcp.json`, `package.json`, `.version-bump.json` | Multi-harness plugin scaffolding. | Yes |

## Initial setup

```powershell
# Clone
git clone https://github.com/BB-84C/bgs-modding-superpowers.git
cd bgs-modding-superpowers

# Build the xEdit MCP (committed dist/ exists, but rebuilding is cheap)
cd tools/xedit-mcp
npm install
npm run build
cd ..\..

# Optional: set up the dev MO2 sandbox under .artifacts/mo2/
# (Manual today; see docs/internal/superpowers/plans/ for the install path.)
```

## Repo standards (durable)

- Tracked files should contain durable knowledge, workflow definitions, project docs, or tested tooling.
- Raw investigation output belongs in `.artifacts/` and must not be committed.
- Do not leave temporary files, dumps, screenshots, or local machine state in the repository root.
- Do not write into `.artifacts/mo2/Stock Game/Fallout 4/Data/` (or equivalent game-data root). Game-local changes are expressed as MO2 mod overlays under `.artifacts/mo2/mods/<mod-name>/`. See `.opencode/memory/70-stock-game-protection.md`.

## Stop conditions for the bootstrap dance

- GitHub owner / repo name / visibility / auth state required and unavailable.
- Cleanup would delete material without explicit approval.

## See also

- `docs/internal/roadmap.md` — phase ladder + capability map for the plugin.
- `docs/internal/standards/repo-hygiene.md` — durable repo cleanliness rules.
- `docs/internal/superpowers/plans/` — Superpowers-shape plans, including the reshape plan that produced this layout.
- `.opencode/memory/30-mo2-harness-hygiene.md`, `.opencode/memory/40-mo2-launcher-architecture.md`, `.opencode/memory/70-stock-game-protection.md` — the in-repo project-local memory router.

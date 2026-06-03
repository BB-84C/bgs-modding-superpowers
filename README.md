# bgs-modding-superpowers

An agent plugin for Bethesda Game Studio modpack curation. Installs on OpenCode, Claude Code, and Codex. Ships xEdit and knowledge-base MCP servers, an MO2 control-plane installer, and skills that walk the agent through first-run setup, conflict audit, and project documentation.

## What's in v0.2

- **`xedit` MCP server** — six intent tools (`xedit_session`, `xedit_list_capabilities`, `xedit_find_record`, `xedit_read_record`, `xedit_inspect_conflicts`) plus the atomic `xedit_call` passthrough for any of 49 native xEdit daemon commands. Goes through a 7-stage harness pipeline (validate → state-check → rules → forward → envelope → audit).
- **`bgs_kb` MCP server** — local SQLite + FTS5 knowledge-base lookup (`bgs_kb_status`, `bgs_kb_query`, `bgs_kb_get`) over the bundled core BGS modding KB. Works without MO2 or xEdit running.
- **MO2 control plane** — C++ MO2 plugin DLL + Python loader + broker that lets the agent drive your MO2 instance (read profile state, run launchers, capture child PIDs). Deployed by `scripts/install-mo2-control-plane.ps1` into your own MO2.
- **xEdit hook bridge** — owned-by-this-repo Delphi DLL that unblocks unattended xEdit launches under MO2. Ships from `tools/xedit-hook-bridge/dist/`.
- **Skills**:
  - `using-bgs-modding-superpowers` — per-session bootstrap.
  - `setting-up-bgs-modding-environment` — first-run install orchestrator (MO2 detect → control plane → optional xEdit download → dev-log / changelog init → semantic smoke test).
  - `xedit-automation` + `xedit-conflict-audit` — the hub skill and the W2 conflict-audit workflow.
  - `writing-modpack-devlog`, `writing-modpack-changelog` — create and maintain your modpack project's documentation at runtime.

## Install

### OpenCode

Add to the `plugin` array of your `opencode.json`:

```json
{
  "plugin": ["bgs-modding-superpowers@git+https://github.com/BB-84C/bgs-modding-superpowers.git"]
}
```

Full instructions: [`.opencode/INSTALL.md`](.opencode/INSTALL.md).

### Claude Code

```text
/plugin marketplace add BB-84C/bgs-modding-superpowers
/plugin install bgs-modding-superpowers@bgs-modding-superpowers
```

The bundled `xedit` and `bgs_kb` MCP servers are declared in [`.mcp.json`](./.mcp.json) and resolve via `${CLAUDE_PLUGIN_ROOT}`.

### Codex

Start a Codex session and paste this prompt. Your Codex agent does the install for you:

> Install the bgs-modding-superpowers plugin from `https://github.com/BB-84C/bgs-modding-superpowers`. Run these two commands and report back what `codex mcp list` shows afterwards:
>
> ```
> codex plugin marketplace add BB-84C/bgs-modding-superpowers
> codex plugin add bgs-modding-superpowers@bgs-modding-superpowers
> ```
>
> Both `xedit` and `bgs_kb` MCP servers should appear in `codex mcp list` after install — Codex auto-imports them from the plugin's `.mcp.json`. If either is missing or any step fails, surface the exact error rather than working around it.

That's it. After install, restart any open Codex session so the new skills and MCP servers load.

**Manual install** (same two commands, run yourself):

```text
codex plugin marketplace add BB-84C/bgs-modding-superpowers
codex plugin add bgs-modding-superpowers@bgs-modding-superpowers
```

**Update later** with:

```text
codex plugin marketplace upgrade bgs-modding-superpowers
```

The repo carries the materialized plugin tree at `plugins/bgs-modding-superpowers/` (Codex's marketplace schema requires the subdirectory layout). Source-of-truth files at the repo root are mirrored there by `scripts/build-portable-plugin.ps1` on every release.

## First run

Start any session in your modpack project directory and ask:

> Set up the BGS modding environment.

The `setting-up-bgs-modding-environment` skill will detect MO2, install the control plane, optionally fetch xEdit from [BB-84C/TES5Edit](https://github.com/BB-84C/TES5Edit), and initialize your dev-log + release-changelog.

You can install MO2 yourself, ask the agent to install it (explicit consent), or run in "no MO2" mode for documentation-only work.

## Requirements

- Windows. The MO2 control plane and xEdit hook bridge are Windows-only by design (modpack work is Windows-anchored).
- A target game: Skyrim SE/AE, Fallout 4, Fallout 76, or Starfield. Skyrim LE and Oblivion can work but are untested.
- Node 22+ (the bundled MCP servers run on Node).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Internal design docs and plans live under [`docs/internal/`](docs/internal/).

## License

MIT. See [LICENSE](LICENSE).

# Installing `bgs-modding-superpowers` in OpenCode

Add the plugin to the `plugin` array in your `opencode.json` (global or project-level):

```json
{
  "plugin": ["bgs-modding-superpowers@git+https://github.com/BB-84C/bgs-modding-superpowers.git"]
}
```

Restart OpenCode. OpenCode reads the package's `main` entry
(`plugins/bgs-modding-superpowers/.opencode/plugins/bgs-modding-superpowers.js`),
which loads the self-contained materialized plugin tree under
`plugins/bgs-modding-superpowers/` and registers:

- All skills under `skills/` (including the per-session bootstrap and first-run setup skills)
- Three MCP servers wired by the plugin's `config.mcp` hook, each resolved relative
  to the materialized tree (so the bundled `node_modules/` next to each `dist/` is used):
  - `xedit`  (`plugins/bgs-modding-superpowers/tools/xedit-mcp/dist/index.js`)
  - `bgs_kb` (`plugins/bgs-modding-superpowers/tools/bgs-kb-mcp/dist/index.js`)
  - `mo2`    (`plugins/bgs-modding-superpowers/tools/mo2-mcp/dist/index.js`)

The materialized plugin tree under `plugins/bgs-modding-superpowers/` ships with
each MCP package's `node_modules/` and the bundled `bgs-kb-core` SQLite database
already populated, so the MCP stdio servers start on a fresh clone with no
`npm install` step.

> Why `main` points into `plugins/bgs-modding-superpowers/`: a `git+https` install
> exposes the **repo root** as the package, but only the materialized subtree carries
> the bundled `node_modules/`. Pointing `main` at the subtree's entry makes OpenCode
> resolve `PLUGIN_ROOT` onto the self-contained tree. The root-level `.mcp.json`
> performs the equivalent wiring for Claude Code / Codex via `${CLAUDE_PLUGIN_ROOT}`;
> OpenCode does not read `.mcp.json`.

## Verify

Start a new OpenCode session and ask:

> Tell me about your BGS modding superpowers.

The agent should reference the `using-bgs-modding-superpowers` skill and offer to run `setting-up-bgs-modding-environment` if MO2 / xEdit haven't been detected yet.

## Version pinning

```json
{
  "plugin": ["bgs-modding-superpowers@git+https://github.com/BB-84C/bgs-modding-superpowers.git#v0.1.0"]
}
```

## Windows fallback (npm-managed local install)

If the direct git install path is slow or unreliable on Windows, install into your global OpenCode tree first:

```powershell
npm install bgs-modding-superpowers@git+https://github.com/BB-84C/bgs-modding-superpowers.git --prefix "$HOME\.config\opencode"
```

Then point `opencode.json` at the local path:

```json
{
  "plugin": ["~/.config/opencode/node_modules/bgs-modding-superpowers"]
}
```

## Local development checkout

If you cloned this repo and want to run the plugin from your local checkout, point `opencode.json` at the absolute path of the clone (forward slashes work on Windows):

```json
{
  "plugin": ["file:/path/to/your/bgs-modding-superpowers/checkout"]
}
```

The committed `plugins/bgs-modding-superpowers/` tree is what `.mcp.json` resolves against, so a plain clone is enough to run both MCPs. You only need a per-MCP `npm install && npm run build` if you are actively editing the TypeScript sources under `tools/xedit-mcp/src/` or `tools/bgs-kb-mcp/src/`; in that case re-materialize the plugin tree afterward with:

```powershell
pwsh scripts/build-portable-plugin.ps1 -OutputDir plugins -PluginName bgs-modding-superpowers -McpPathStrategy relative -Force
```

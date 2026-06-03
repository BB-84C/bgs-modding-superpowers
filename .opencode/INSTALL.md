# Installing `bgs-modding-superpowers` in OpenCode

Add the plugin to the `plugin` array in your `opencode.json` (global or project-level):

```json
{
  "plugin": ["bgs-modding-superpowers@git+https://github.com/BB-84C/bgs-modding-superpowers.git"]
}
```

Restart OpenCode. The plugin installs through OpenCode's plugin manager and registers:

- All skills under `skills/` (including the per-session bootstrap and first-run setup skills)
- Two MCP servers wired by the root-level `.mcp.json`:
  - `xedit` (`plugins/bgs-modding-superpowers/tools/xedit-mcp/dist/index.js`)
  - `bgs_kb` (`plugins/bgs-modding-superpowers/tools/bgs-kb-mcp/dist/index.js`)

The materialized plugin tree under `plugins/bgs-modding-superpowers/` ships with both MCP packages' `node_modules/` and the bundled `bgs-kb-core` SQLite database already populated, so `node <entry>.js` works on a fresh clone with no `npm install` step.

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

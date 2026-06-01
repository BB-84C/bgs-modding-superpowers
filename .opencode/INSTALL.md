# Installing `bgs-modding-superpowers` in OpenCode

Add the plugin to the `plugin` array in your `opencode.json` (global or project-level):

```json
{
  "plugin": ["bgs-modding-superpowers@git+https://github.com/BB-84C/bgs-modding-superpowers.git"]
}
```

Restart OpenCode. The plugin installs through OpenCode's plugin manager and registers:

- All skills under `skills/` (including the per-session bootstrap and first-run setup skills)
- The bundled `xedit` MCP server (`tools/xedit-mcp/dist/index.js`)

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

If you cloned this repo and want to run the plugin from your local checkout:

```json
{
  "plugin": ["file:D:/awesome-bgs-mod-master"]
}
```

The plugin's `prepare` script will build `tools/xedit-mcp/dist/` on install. You can also rebuild manually:

```powershell
cd tools\xedit-mcp
npm install
npm run build
```

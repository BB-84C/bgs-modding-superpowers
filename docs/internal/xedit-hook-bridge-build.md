# xEditHookBridge — build path (dev-only)

`xEditHookBridge.dll` is owned by this repo: it ships from
`tools/xedit-hook-bridge/dist/xEditHookBridge.dll` and is deployed by
`scripts/install-xedit-hook-bridge.ps1` into `<MO2Root>/tools/xEdit/`
alongside `xEdit.exe`.

The `.pas` source for the DLL lives in the sister xEdit fork at
`D:\TES5Edit-contrib` (public at
[BB-84C/TES5Edit](https://github.com/BB-84C/TES5Edit)). This repo does
**not** vendor the source; the `.gitignore` actively keeps any local
`tools/xedit-hook-bridge/src/` copy out of git.

## Why the split

- End users only need the DLL. They run the installer, the DLL lands next
  to xEdit.exe, the agent works.
- Developers maintaining the bridge work on the `.pas` source inside the
  sister Delphi project (where the rest of xEdit lives).
- Coupling the .pas source to this repo would force every bridge change
  to ripple across two checkouts, two build environments, and two
  release cycles.

## Rebuilding the DLL

1. In the sister xEdit-contrib checkout, open the Delphi project that owns
   `xEditHookBridge.dproj`.
2. Build target = `LiteDebug` (the per-machine convention here; do not use
   `Release` on the dev machine without verifying the build pipeline).
3. Confirm the produced `xEditHookBridge.dll` is bit-identical to the
   expected ABI (xEdit ImpDLL / Delphi-runtime requirements).
4. Copy the DLL into this repo:

   ```powershell
   Copy-Item D:\TES5Edit-contrib\Build\xEditHookBridge.dll `
             D:\awesome-bgs-mod-master\tools\xedit-hook-bridge\dist\xEditHookBridge.dll
   ```

5. Commit the updated `tools/xedit-hook-bridge/dist/xEditHookBridge.dll` here
   with the sister-repo commit hash referenced in the commit message.

## What ships, what does not

| Path | Status |
|---|---|
| `tools/xedit-hook-bridge/dist/xEditHookBridge.dll` | **Ships.** Tracked. Deployed by `scripts/install-xedit-hook-bridge.ps1`. |
| `tools/xedit-hook-bridge/src/*.pas` | Never lives here. Lives in sister `D:\TES5Edit-contrib`. Gitignored if it appears locally. |
| `tools/xedit-hook-bridge/src/*.dcu` | Delphi compile units. Gitignored. |
| `tools/xedit-hook-bridge/*.dproj.local` | Delphi project local config. Gitignored. |
| `tools/xedit-hook-bridge/*.identcache` | Delphi identifier cache. Gitignored. |
| `tools/xedit-hook-bridge/*.res` | Resource file. Gitignored. |

## See also

- `scripts/install-xedit-hook-bridge.ps1` — the runtime deployer.
- `skills/xedit-automation/xedit-knowledgebase.md` — agent-facing reference;
  notes that the hook bridge is owned here and the xEdit binary is owned at
  BB-84C/TES5Edit.
- `skills/setting-up-bgs-modding-environment/SKILL.md` — first-run skill
  that invokes the install script as step 6 of the setup workflow.

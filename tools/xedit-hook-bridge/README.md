# xedit-hook-bridge

This directory holds the minimal native hook bridge used by the current worktree's no-fork load path.

## Current Contract

The bridge contract is intentionally narrow for this slice:

- the DLL exports `Init(logLevel: Integer; profileName: LPCWSTR): BOOL; cdecl`
- `Init` reads only:
  - `XEDIT_CLI_HOOK_SESSION_ID`
  - `XEDIT_CLI_HOOK_SESSION_PATH`
- `Init` writes `hook-status.txt` under `XEDIT_CLI_HOOK_SESSION_PATH`
- the bridge does not own plugin-subset semantics
- the bridge only auto-confirms `Module Selection` and writes diagnostics

The wrapper is now responsible for deciding the load set by materializing a session-scoped `plugins.txt` and launching xEdit with `-P:<session plugins.txt>`.

## Status File Surface

The reduced load-only status surface is:

- `status=`
- `session_id=`
- `selection_detected=`
- `selection_confirmed=`
- `selected_modules=`
- `detail=`
- diagnostic snapshot lines

The bridge no longer writes subset-era fields such as:

- `load_mode=`
- `plugins=`
- `selection_method=`
- `forced_dependencies=`
- `blocked_exclusions=`

## Automation Behavior

The bridge now does only three automation jobs:

1. detect the `Module Selection` dialog when it appears
2. dismiss startup interstitials that would otherwise block it, such as:
   - `What's New?`
   - `A message from the developer`
3. confirm the current selection without mutating it

For selected-module evidence, the bridge prefers:

1. visible tree capture when available
2. fallback to the session `plugins.txt` file when tree capture is unavailable

That fallback is acceptable in this slice because the session `plugins.txt` is the wrapper-owned canonical input to the launch.

## Real xEdit Wiring

For real MO-backed launches, `xedit-cli process launch --mo-profile <name>`:

- copies `tools/xedit-hook-bridge/src/xEditHookBridge.dll` to xEdit's expected `..\Mod Organizer\hook.dll` path
- appends `-moprofile:"<name>"` to xEdit launch arguments
- appends `-P:<session plugins.txt>` so xEdit reads the session-scoped load set

The bridge stays no-fork and hook-based in this repository.

## Non-Interactive RAD Build Discovery

This machine has one reliable non-interactive Delphi build path for the hook bridge:

```powershell
$p = Start-Process -FilePath "C:\Program Files (x86)\Embarcadero\Studio\23.0\bin\bds.exe" `
    -ArgumentList @('-b', 'D:\awesome-bgs-mod-master\.worktrees\xedit-step1-hooks\tools\xedit-hook-bridge\src\xEditHookBridge.dproj') `
    -Wait -PassThru

$p.ExitCode
Get-Item "D:\awesome-bgs-mod-master\.worktrees\xedit-step1-hooks\tools\xedit-hook-bridge\src\xEditHookBridge.dll" |
  Select-Object FullName, Length, LastWriteTime
```

Why this matters:

- direct `dcc32.exe` is license-blocked on this machine and reports `This version of the product does not support command line compiling.`
- `msbuild` can still produce false-green output even when `dcc32` did not really refresh the DLL
- `bds.exe -b <project.dproj>` is the path that has produced fresh `xEditHookBridge.dll` updates during this slice

Use this as the preferred rebuild command before asking the user to open RAD manually.

## Manual RAD Fallback

If `bds.exe -b` is unavailable or does not refresh the DLL, use this manual loop:

1. Open `tools/xedit-hook-bridge/src/xEditHookBridge.dpr` in RAD Studio / Delphi.
2. Choose `Win32` and `Release`.
3. Make sure the editor has reloaded any externally modified `HookMain.pas`, `HookStatus.pas`, and `HookSession.pas` source before building.
4. Build `xEditHookBridge`.
5. Confirm the built DLL appears at `tools/xedit-hook-bridge/src/xEditHookBridge.dll` with a fresh timestamp.

## Repo-Side Verification Commands

The synthetic load-only verification path is:

```powershell
pwsh -NoProfile -File tests/xedit-cli/module-selection-contract.test.ps1
pwsh -NoProfile -File tests/xedit-cli/module-selection-all.integration.ps1
```

The real MO2 sandbox verification path is:

```powershell
pwsh -NoProfile -File tests/xedit-cli/mo2-sandbox-model-selection-real.test.ps1 -AllowLiveSandbox -EnsureBridge -RestartMo2
```

## Fallback Note

If `XEDIT_CLI_HOOK_SESSION_PATH` is missing, the bridge does not silently fail. It writes a blocker artifact under `%TEMP%\xedit-hook-bridge-blockers\` using one of these filenames:

- `<sanitized-session-id>-hook-status.txt`
- `missing-session-hook-status.txt`

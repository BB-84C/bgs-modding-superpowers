# xedit-hook-bridge

This directory holds the minimal native hook bridge skeleton for the xEdit step-1 Module Selection handshake.

## Handshake Contract

The bridge handshake is intentionally small for this slice:

- the DLL exports `Init(logLevel: Integer; profileName: LPCWSTR): BOOL; cdecl`
- `Init` reads `XEDIT_CLI_HOOK_SESSION_ID`, `XEDIT_CLI_HOOK_SESSION_PATH`, `XEDIT_CLI_HOOK_LOAD_MODE`, and optional `XEDIT_CLI_HOOK_PLUGINS`
- `Init` writes `hook-status.txt` under `XEDIT_CLI_HOOK_SESSION_PATH`
- a successful load writes `status=loaded`
- if `XEDIT_CLI_HOOK_SESSION_PATH` is missing, the bridge writes a blocker status file under `%TEMP%\xedit-hook-bridge-blockers\` using either a sanitized session-id-derived filename ending in `-hook-status.txt` or `missing-session-hook-status.txt`

## Module Selection `all` Contract

The first Module Selection automation slice is intentionally narrow:

- detect a top-level `Module Selection` dialog
- if `XEDIT_CLI_HOOK_LOAD_MODE=all`, confirm the current selection without changing it
- write explicit status markers showing whether Module Selection was detected and confirmed

Successful `all` confirmation updates `hook-status.txt` with:

- `status=module-selection-confirmed`
- `selection_detected=true`
- `selection_confirmed=true`
- `selection_method=button-click`

Failures keep writing `hook-status.txt` under the same hook session path with explicit `detail=` diagnostics.

## Module Selection `only` / `exclude` Contract

The subset slice keeps the same in-process dialog automation path and adds two policy modes:

- `XEDIT_CLI_HOOK_LOAD_MODE=only` checks the requested plugin roots from `XEDIT_CLI_HOOK_PLUGINS` and lets dialog dependency rules force required masters back on
- `XEDIT_CLI_HOOK_LOAD_MODE=exclude` unchecks the requested plugin roots when the dialog allows it
- the bridge matches requested filenames against the visible module tree and confirms the dialog after applying the policy
- the bridge records `selected_modules=` in visible tree order after the dialog has enforced dependency rules
- `only` reports dependency-added modules through `forced_dependencies=`
- `exclude` reports exclusions that stayed selected through `blocked_exclusions=`

## Manual Delphi CE Build Checkpoint

Because Delphi Community Edition cannot be driven from the command line on this machine, stop here after code changes and use this manual build loop:

1. Open `tools/xedit-hook-bridge/src/xEditHookBridge.dpr` in Delphi Community Edition.
2. In the IDE target selector, choose `Win32` and `Release`.
3. Click `Project -> Build xEditHookBridge` or the toolbar `Build` button.
4. Confirm the built DLL appears at `tools/xedit-hook-bridge/src/xEditHookBridge.dll`.
5. Make sure `%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe` exists on the machine before running the repo-side verification step, because the verification harness builds a small x86 WinForms fixture locally.

If Delphi writes the DLL somewhere else, tell the assistant the actual output path before running the repo-side verification command below.

## Real xEdit Hook Wiring

The real xEdit seam expects the built bridge DLL at `..\Mod Organizer\hook.dll` relative to the launched xEdit executable, and calls `Init(logLevel, profileName)` after `-moprofile:"<name>"` is present on the xEdit command line.

`xedit-cli process launch --mo-profile <name>` is the minimal real-launch contract for this slice:

- copy `tools/xedit-hook-bridge/src/xEditHookBridge.dll` to the real xEdit hook path `..\Mod Organizer\hook.dll` before launch
- append `-moprofile:"<name>"` to the xEdit launch arguments
- keep the existing synthetic fixture tests and manual Delphi CE rebuild flow

## Repo-Side Verification Command

After the user clicks `Build` and the DLL exists at the expected path, run:

```powershell
pwsh -File tests/xedit-cli/module-selection-subset.integration.ps1
```

For the earlier `all` smoke check, run:

```powershell
pwsh -File tests/xedit-cli/module-selection-all.integration.ps1
```

The subset verification builds a temporary `FO4Edit.exe` WinForms fixture with a checkbox tree, launches it through `xedit-cli process launch --load-mode only|exclude`, loads the compiled bridge DLL, opens a live `Module Selection` dialog, and expects the hook session status file to report `module-selection-confirmed` plus `selected_modules=` and either `forced_dependencies=` or `blocked_exclusions=`.

## Verification

When a command-line Delphi compiler is available, the following PowerShell command can still verify the handshake success path without Delphi CE:

```powershell
$repoRoot = (Resolve-Path .).Path
$bridgeRoot = Join-Path $repoRoot 'tools/xedit-hook-bridge'
$sourceRoot = Join-Path $bridgeRoot 'src'
$compiler = @('dcc64', 'dcc32') | ForEach-Object { Get-Command $_ -ErrorAction SilentlyContinue } | Select-Object -First 1
if (-not $compiler) {
    throw 'Tooling blocker: no Delphi DLL compiler (dcc32/dcc64) is available on PATH.'
}

$buildRoot = Join-Path $env:TEMP ('xedit-hook-bridge-build-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $buildRoot -Force
$compileOutput = & $compiler.Source (Join-Path $sourceRoot 'xEditHookBridge.dpr') ('-E' + $buildRoot) ('-N0' + $buildRoot) 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Compilation failed.`n$($compileOutput -join [Environment]::NewLine)"
}

$dllPath = Join-Path $buildRoot 'xEditHookBridge.dll'
if (-not (Test-Path $dllPath -PathType Leaf)) {
    throw 'Compilation did not produce xEditHookBridge.dll.'
}

$sessionPath = Join-Path $env:TEMP ('xedit-hook-session-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $sessionPath -Force
$env:XEDIT_CLI_HOOK_SESSION_ID = 'handshaketest'
$env:XEDIT_CLI_HOOK_SESSION_PATH = $sessionPath
$env:XEDIT_CLI_HOOK_LOAD_MODE = 'only'
$env:XEDIT_CLI_HOOK_PLUGINS = 'Example.esm|Another.esp'

$kernel32 = @"
using System;
using System.Runtime.InteropServices;
public static class NativeMethods {
    [DllImport("kernel32", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern IntPtr LoadLibrary(string lpFileName);

    [DllImport("kernel32", SetLastError = true)]
    public static extern IntPtr GetProcAddress(IntPtr hModule, string lpProcName);

    [DllImport("kernel32", SetLastError = true)]
    public static extern bool FreeLibrary(IntPtr hModule);
}

[UnmanagedFunctionPointer(CallingConvention.Cdecl, CharSet = CharSet.Unicode)]
public delegate bool InitDelegate(int logLevel, string profileName);
"@

Add-Type -TypeDefinition $kernel32
$module = [NativeMethods]::LoadLibrary($dllPath)
if ($module -eq [IntPtr]::Zero) {
    throw 'Failed to load compiled hook DLL.'
}

try {
    $proc = [NativeMethods]::GetProcAddress($module, 'Init')
    if ($proc -eq [IntPtr]::Zero) {
        throw 'Compiled hook DLL does not export Init.'
    }

    $init = [Runtime.InteropServices.Marshal]::GetDelegateForFunctionPointer($proc, [InitDelegate])
    if (-not ($init.Invoke(0, "handshaketest"))) {
        throw 'Init returned failure.'
    }

    $statusPath = Join-Path $sessionPath 'hook-status.txt'
    if (-not (Test-Path $statusPath -PathType Leaf)) {
        throw 'Init did not write hook-status.txt.'
    }

    $status = Get-Content $statusPath -Raw
    foreach ($expected in @('status=loaded', 'session_id=handshaketest', 'load_mode=only', 'plugins=Example.esm|Another.esp')) {
        if ($status -notmatch [regex]::Escape($expected)) {
            throw "Missing status marker: $expected"
        }
    }

    Write-Host 'xedit hook bridge handshake passed.'
}
finally {
    [NativeMethods]::FreeLibrary($module) | Out-Null
}
```

If no Delphi DLL compiler is available, treat that as the expected tooling blocker for this slice and stop before deeper native implementation work.

## Fallback Note

If `XEDIT_CLI_HOOK_SESSION_PATH` is missing, the bridge does not silently fail. It writes a blocker artifact under `%TEMP%\xedit-hook-bridge-blockers\` using one of these filenames:

- `<sanitized-session-id>-hook-status.txt`
- `missing-session-hook-status.txt`

The main verification command above only proves the success path. When a Delphi compiler is available, do a separate fallback spot-check by omitting `XEDIT_CLI_HOOK_SESSION_PATH` or forcing it to an unwritable location, then inspect `%TEMP%\xedit-hook-bridge-blockers\` for the expected blocker file.

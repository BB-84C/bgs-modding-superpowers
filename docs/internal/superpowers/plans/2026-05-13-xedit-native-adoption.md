# Native xEdit Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the legacy hook/wrapper xEdit control path, move the surviving MO2-facing xEdit client responsibilities next to `mo2-vfs-launcher`, and make native xEdit automation from `D:\TES5Edit-contrib` the only owner of xEdit business semantics.

**Architecture:** Keep `tools/mo2-vfs-launcher` generic, add an xEdit-specific outer client beside it, and route all real xEdit work through native `-automation-serve` / `-automation-call` instead of wrapper-owned conflict/index/hook behavior. The external client continues to own session-scoped `plugins.txt`, launcher normalization, MO2/control-plane launch, PID lifecycle, and artifact preservation.

**Tech Stack:** PowerShell 7, MO2 control plane, `OpenCodeVfsLauncher`, native xEdit automation serve/call protocol, repo bootstrap verification scripts.

---

## File Structure and Responsibilities

### Create

- `tools/mo2-vfs-launcher/xedit-client.ps1`
  - Entry point for the xEdit outer client.
  - Public commands: `process launch`, `process status`, `process wait`, `process stop`, `automation call`.

- `tools/mo2-vfs-launcher/lib/xedit-client.common.ps1`
  - Shared option parsing, game-mode mapping, xEdit identity checks, PID parsing.

- `tools/mo2-vfs-launcher/lib/xedit-client.session.ps1`
  - Session directory creation, plugins-file normalization, run-scoped `plugins.txt`, launch/call artifact paths.

- `tools/mo2-vfs-launcher/lib/xedit-client.launch.ps1`
  - Launcher normalization, MO2 launch request shaping, native serve launch args, PID lifecycle, readiness wait.

- `tools/mo2-vfs-launcher/lib/xedit-client.call.ps1`
  - Native `-automation-call-*` request execution and JSON response handling.

- `tools/mo2-vfs-launcher/xedit-client.md`
  - xEdit outer-client contract and ownership boundary.

- `tests/mo2-vfs-launcher/xedit-client.session-plugins.test.ps1`
  - Unit tests for plugin-list normalization and session `plugins.txt` writing.

- `tests/mo2-vfs-launcher/xedit-client.launch-adapter.test.ps1`
  - Unit tests for launch request shaping and MO2 transport metadata.

- `tests/mo2-vfs-launcher/xedit-client.process-lifecycle.test.ps1`
  - Process launch/status/wait/stop tests against local fixture executables.

- `tests/mo2-vfs-launcher/xedit-client.call.test.ps1`
  - Unit tests for native `automation-call` argument shaping and response-file handling.

- `tests/mo2-vfs-launcher/xedit-client.mo2-sandbox-real.test.ps1`
  - Opt-in real MO2 sandbox verification using native serve/call instead of hook status.

- `tests/mo2-vfs-launcher/layout.test.ps1`
  - Asserts new client files exist and legacy xEdit wrapper trees are gone.

### Modify

- `tools/mo2-vfs-launcher/README.md`
  - Keep generic launcher contract, add a short pointer to the neighboring xEdit outer client.

- `tools/mo2-control-plane/live-integration.md`
  - Replace `xedit-cli` example entrypoint with `tools/mo2-vfs-launcher/xedit-client.ps1`.

- `tools/README.md`
  - Reflect that xEdit outer-client code now lives beside `mo2-vfs-launcher`.

- `docs/roadmap.md`
  - Replace `xedit-cli` capability language with native xEdit + outer-client language.

- `AGENTS.md`
  - Remove `tools/xedit-hook-bridge/` from canonical runtime surfaces and routing hints.

- `tests/bootstrap/verify-specs.ps1`
  - Stop asserting `tools/xedit-cli/*`; start asserting `tools/mo2-vfs-launcher/xedit-client.ps1` and `xedit-client.md`.

- `tests/bootstrap/verify-foundation.ps1`
  - Replace roadmap signals that hardcode `xedit-cli` / `tools/xedit-cli/CONTRACT.md`.

- `.gitignore`
  - Remove obsolete hook-bridge binary ignore rules.

### Delete

- `tools/xedit-hook-bridge/**`
- `tools/xedit-cli/**`
- `tests/xedit-cli/**`

Historical design and plan documents under `docs/plans/` stay in place as historical artifacts; do not rewrite them as part of this implementation plan.

---

### Task 1: Create the new xEdit outer-client skeleton and migrate pure session/plugin helpers

**Files:**
- Create: `tools/mo2-vfs-launcher/xedit-client.ps1`
- Create: `tools/mo2-vfs-launcher/lib/xedit-client.common.ps1`
- Create: `tools/mo2-vfs-launcher/lib/xedit-client.session.ps1`
- Test: `tests/mo2-vfs-launcher/xedit-client.session-plugins.test.ps1`

- [ ] **Step 1: Write the failing session/plugins test**

Create `tests/mo2-vfs-launcher/xedit-client.session-plugins.test.ps1` by porting the old `tests/xedit-cli/session-plugins.test.ps1` to the new paths and function names.

Use this content:

```powershell
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
. (Join-Path $repoRoot "tools/mo2-vfs-launcher/lib/xedit-client.session.ps1")

function Assert-Equal {
    param($Actual, $Expected, [string]$Message)
    if ($Actual -is [System.Array] -or $Expected -is [System.Array]) {
        $actualText = [string]::Join("`n", @($Actual))
        $expectedText = [string]::Join("`n", @($Expected))
        if ($actualText -ne $expectedText) {
            throw "$Message`nExpected: $expectedText`nActual: $actualText"
        }
        return
    }
    if ($Actual -ne $Expected) {
        throw "$Message`nExpected: $Expected`nActual: $Actual"
    }
}

function Assert-Throws {
    param([scriptblock]$Action, [string]$ExpectedMessage, [string]$Message)
    try { & $Action } catch {
        if ($_.Exception.Message -ne $ExpectedMessage) {
            throw "$Message`nExpected error: $ExpectedMessage`nActual error: $($_.Exception.Message)"
        }
        return
    }
    throw "$Message`nExpected error: $ExpectedMessage`nActual error: <no error>"
}

$plugins = Resolve-XeditClientPluginLinesFromValues -PluginLines @(
    "  *ArmorKeywords.esm  ",
    "",
    "# comment",
    "*RaiderOverhaul.esp",
    "*RaiderOverhaul.esp"
)

Assert-Equal -Actual $plugins -Expected @("*ArmorKeywords.esm", "*RaiderOverhaul.esp") -Message "plugin lines should normalize and dedupe"

Assert-Throws -Action {
    Resolve-XeditClientPluginLinesFromValues -PluginLines @("", "   ")
} -ExpectedMessage "Plugin list must contain at least one non-empty entry." -Message "empty plugin lists should fail"

$session = New-XeditClientSessionContext -PluginLines @("*Fallout4.esm", "*ExamplePatch.esp")
Assert-Equal -Actual (Split-Path $session.SessionPluginsFilePath -Leaf) -Expected "plugins.txt" -Message "session should materialize plugins.txt"
Assert-Equal -Actual (Get-Content $session.SessionPluginsFilePath) -Expected @("*Fallout4.esm", "*ExamplePatch.esp") -Message "session plugins file should persist normalized lines"

Write-Host "xedit-client session/plugins checks passed."
```

- [ ] **Step 2: Run the new session/plugins test and verify it fails**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-vfs-launcher/xedit-client.session-plugins.test.ps1
```

Expected: FAIL with a file-not-found or function-not-defined error because the new library files do not exist yet.

- [ ] **Step 3: Implement the session/plugin helpers and entrypoint skeleton**

Create `tools/mo2-vfs-launcher/lib/xedit-client.common.ps1` with the shared parser and game-mode map ported from `tools/xedit-cli/lib/common.ps1`:

```powershell
function ConvertTo-XeditClientOptionMap {
    param([string[]]$Arguments, [string[]]$RepeatableNames = @())
    $options = @{}
    $repeatableLookup = @{}
    foreach ($name in $RepeatableNames) { $repeatableLookup[$name] = $true }
    for ($index = 0; $index -lt $Arguments.Count; $index++) {
        $token = $Arguments[$index]
        if (-not $token.StartsWith("--")) { throw "Unexpected argument: $token" }
        if ($index + 1 -ge $Arguments.Count) { throw "Missing value for option: $token" }
        $value = $Arguments[$index + 1]
        if ($value.StartsWith("--")) { throw "Missing value for option: $token" }
        if ($repeatableLookup.ContainsKey($token)) {
            if (-not $options.ContainsKey($token)) { $options[$token] = @() }
            $options[$token] += $value
        } else {
            $options[$token] = $value
        }
        $index++
    }
    return $options
}

function Get-XeditClientGameModeMap {
    return [ordered]@{
        Fallout4  = '-FO4'
        Skyrim    = '-TES5'
        SkyrimSE  = '-SSE'
        Starfield = '-SF1'
    }
}
```

Create `tools/mo2-vfs-launcher/lib/xedit-client.session.ps1` with the migrated plugin/session helpers:

```powershell
function Resolve-XeditClientPluginLinesFromValues {
    param([string[]]$PluginLines)
    $normalized = @()
    $seen = @{}
    foreach ($pluginLine in @($PluginLines)) {
        $trimmed = ([string]$pluginLine).Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith('#')) { continue }
        if ($seen.ContainsKey($trimmed)) { continue }
        $seen[$trimmed] = $true
        $normalized += $trimmed
    }
    if ($normalized.Count -eq 0) { throw "Plugin list must contain at least one non-empty entry." }
    return $normalized
}

function New-XeditClientSessionPluginsFile {
    param([string]$SessionPath, [string[]]$PluginLines)
    $null = New-Item -ItemType Directory -Path $SessionPath -Force
    $normalizedSessionPath = (Get-Item -Path $SessionPath).FullName
    $normalizedPluginLines = Resolve-XeditClientPluginLinesFromValues -PluginLines $PluginLines
    $pluginsFilePath = Join-Path $normalizedSessionPath 'plugins.txt'
    $temporaryPath = Join-Path $normalizedSessionPath 'plugins.txt.tmp'
    Set-Content -Path $temporaryPath -Value $normalizedPluginLines
    Move-Item -Path $temporaryPath -Destination $pluginsFilePath -Force
    [pscustomobject]@{
        SessionPath = $normalizedSessionPath
        PluginsFilePath = $pluginsFilePath
        PluginLines = $normalizedPluginLines
    }
}

function New-XeditClientSessionContext {
    param([string[]]$PluginLines)
    $sessionId = [guid]::NewGuid().ToString('N')
    $sessionPath = Join-Path (Join-Path $env:TEMP 'xedit-client-sessions') $sessionId
    $sessionPlugins = New-XeditClientSessionPluginsFile -SessionPath $sessionPath -PluginLines $PluginLines
    [pscustomobject]@{
        SessionId = $sessionId
        SessionPath = $sessionPlugins.SessionPath
        SessionPluginsFilePath = $sessionPlugins.PluginsFilePath
        PluginLines = $sessionPlugins.PluginLines
    }
}
```

Create `tools/mo2-vfs-launcher/xedit-client.ps1` as a minimal skeleton:

```powershell
$ErrorActionPreference = 'Stop'
$toolRoot = (Resolve-Path $PSScriptRoot).Path
. (Join-Path $toolRoot 'lib/xedit-client.common.ps1')
. (Join-Path $toolRoot 'lib/xedit-client.session.ps1')

try {
    if ($args.Count -lt 2) {
        Write-Host 'Usage: xedit-client.ps1 <group> <command> [options]'
        exit 1
    }
    Write-Host 'xedit-client skeleton ready'
    exit 0
} catch {
    Write-Host $_.Exception.Message
    exit 1
}
```

- [ ] **Step 4: Run the session/plugins test and verify it passes**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-vfs-launcher/xedit-client.session-plugins.test.ps1
```

Expected: PASS with `xedit-client session/plugins checks passed.`

- [ ] **Step 5: Commit this task boundary if commit authority has been explicitly granted during execution**

Run only if the execution round has explicit commit permission:

```bash
git add tools/mo2-vfs-launcher/xedit-client.ps1 tools/mo2-vfs-launcher/lib/xedit-client.common.ps1 tools/mo2-vfs-launcher/lib/xedit-client.session.ps1 tests/mo2-vfs-launcher/xedit-client.session-plugins.test.ps1
git commit -m "refactor: start xedit outer client migration"
```

Expected: one commit containing only the new skeleton and session/plugin helpers.

### Task 2: Implement native serve launch shaping and process lifecycle

**Files:**
- Create: `tools/mo2-vfs-launcher/lib/xedit-client.launch.ps1`
- Modify: `tools/mo2-vfs-launcher/xedit-client.ps1`
- Test: `tests/mo2-vfs-launcher/xedit-client.launch-adapter.test.ps1`
- Test: `tests/mo2-vfs-launcher/xedit-client.process-lifecycle.test.ps1`

- [ ] **Step 1: Write the failing launch/lifecycle tests**

Create `tests/mo2-vfs-launcher/xedit-client.launch-adapter.test.ps1` by porting the old `tests/xedit-cli/mo2-launch-adapter.test.ps1`, but change the assertions to the new boundary:

- it loads `tools/mo2-vfs-launcher/lib/xedit-client.common.ps1`, `xedit-client.session.ps1`, and `xedit-client.launch.ps1`
- it expects the target args to include `-automation-serve`
- it expects the target args to include the session `-P:` argument
- it expects the target args **not** to include `-moprofile:`
- it expects no `hook-session-id`, `hook-session-path`, or `hook-dll-path` outputs

Add these key assertions:

```powershell
Assert-True -Condition ($request.target.args -contains '-automation-serve') -Message 'launch args should always enable native automation serve mode'
Assert-True -Condition ($request.target.args[-1] -eq ('-P:' + $session.SessionPluginsFilePath)) -Message 'launch args should end with the session plugins file'
Assert-True -Condition (-not (@($request.target.args) | Where-Object { $_ -match '^-moprofile:' })) -Message 'the new client should not forward -moprofile into native xEdit args'
Assert-True -Condition (-not $launchOutput.Contains('hook-session-id:')) -Message 'launch output should not expose removed hook-session fields'
```

Create `tests/mo2-vfs-launcher/xedit-client.process-lifecycle.test.ps1` by porting the old `tests/xedit-cli/process-lifecycle.test.ps1` to the new CLI path:

```powershell
$cliPath = Join-Path $repoRoot 'tools/mo2-vfs-launcher/xedit-client.ps1'
```

Keep the existing fixture executable builder, but change the launch assertions to require `-automation-serve` in the logged xEdit arguments.

- [ ] **Step 2: Run the launch/lifecycle tests and verify they fail**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-vfs-launcher/xedit-client.launch-adapter.test.ps1
pwsh -NoProfile -File tests/mo2-vfs-launcher/xedit-client.process-lifecycle.test.ps1
```

Expected: FAIL because `xedit-client.launch.ps1` does not exist and `xedit-client.ps1` does not dispatch process commands yet.

- [ ] **Step 3: Implement launch shaping and process commands**

Create `tools/mo2-vfs-launcher/lib/xedit-client.launch.ps1` by porting the reusable pieces from `tools/xedit-cli/lib/process.ps1` and `tools/xedit-cli/lib/mo2-launch.ps1`, but strip hook-specific behavior.

Key implementation code:

```powershell
function Invoke-XeditClientProcessLaunch {
    param([string[]]$Arguments)

    $options = ConvertTo-XeditClientOptionMap -Arguments $Arguments
    $launcherPath = $options['--launcher-path']
    $gameModeArgument = Get-XeditClientValidatedGameModeArgument -GameMode $options['--game-mode']
    $moProfile = Get-XeditClientValidatedMoProfile -Options $options
    $pluginSource = Get-XeditClientResolvedPluginSource -Options $options -GameMode $options['--game-mode'] -MoProfile $moProfile -SandboxRoot $null
    $normalizedLauncherCommand = Get-XeditClientNormalizedLauncherCommand -LauncherPath $launcherPath -GameModeArgument $gameModeArgument
    $session = New-XeditClientSessionContext -PluginLines $pluginSource.PluginLines

    $normalizedLauncherCommand.ArgumentList = @(
        $normalizedLauncherCommand.ArgumentList + @(
            '-automation-serve',
            ('-P:' + $session.SessionPluginsFilePath)
        )
    )

    $launchRequest = New-XeditClientMo2LaunchRequest -Profile $moProfile -SandboxRoot $null -TargetPath $normalizedLauncherCommand.DetectionPath -TargetArguments $normalizedLauncherCommand.ArgumentList -TargetWorkingDirectory $normalizedLauncherCommand.WorkingDirectory -Session $session
    Write-XeditClientMo2LaunchRequestArtifact -LaunchRequest $launchRequest
    $launchResult = Invoke-XeditClientMo2LaunchStart -LaunchRequest $launchRequest
    Write-XeditClientMo2LaunchResponseArtifact -LaunchRequest $launchRequest -LaunchResponse $launchResult.Response

    $processId = [int]$launchResult.State.pid
    Write-Host 'process launch'
    Write-Host 'status: ok'
    Write-Host ('session-id: ' + $session.SessionId)
    Write-Host ('session-path: ' + $session.SessionPath)
    Write-Host ('session-plugins-file: ' + $session.SessionPluginsFilePath)
    Write-Host ('mo2-launch-request-file: ' + $launchRequest.artifacts.request_file)
    Write-Host ('mo2-launch-response-file: ' + $launchRequest.artifacts.response_file)
    Write-Host ('mo2-launch-state-file: ' + $launchRequest.artifacts.state_file)
    Write-Host ('xedit-pid: ' + $processId)
    return 0
}
```

Port the current `process status`, `process wait`, and `process stop` functions with renamed helpers:

```powershell
function Invoke-XeditClientProcessStatus {
    param([string[]]$Arguments)
    $options = ConvertTo-XeditClientOptionMap -Arguments $Arguments
    $validated = Get-XeditClientValidatedLiveProcess -ProcessId $options['--xedit-pid']
    Write-Host 'process status'
    Write-Host 'status: running'
    Write-Host ('xedit-pid: ' + $validated.ProcessId)
    return 0
}

function Invoke-XeditClientProcessWait {
    param([string[]]$Arguments)
    $options = ConvertTo-XeditClientOptionMap -Arguments $Arguments
    $validated = Get-XeditClientValidatedLiveProcess -ProcessId $options['--xedit-pid']
    $timeoutSeconds = ConvertTo-XeditClientPositiveIntValue -Value $options['--timeout-seconds']
    if ($validated.LiveProcess.WaitForExit($timeoutSeconds * 1000)) {
        Write-Host 'process wait'
        Write-Host 'status: exited'
        Write-Host ('xedit-pid: ' + $validated.ProcessId)
        return 0
    }
    Write-Host 'process wait'
    Write-Host 'status: timeout'
    Write-Host ('xedit-pid: ' + $validated.ProcessId)
    return 0
}

function Invoke-XeditClientProcessStop {
    param([string[]]$Arguments)
    $options = ConvertTo-XeditClientOptionMap -Arguments $Arguments
    $validated = Get-XeditClientValidatedLiveProcess -ProcessId $options['--xedit-pid']
    Stop-Process -Id $validated.ProcessId -Force
    $validated.LiveProcess.WaitForExit()
    Write-Host 'process stop'
    Write-Host 'status: stopped'
    Write-Host ('xedit-pid: ' + $validated.ProcessId)
    return 0
}
```

Update `tools/mo2-vfs-launcher/xedit-client.ps1` to dispatch:

```powershell
. (Join-Path $toolRoot 'lib/xedit-client.launch.ps1')

switch ("$group $command") {
    'process launch' { exit (Invoke-XeditClientProcessLaunch -Arguments $remaining) }
    'process status' { exit (Invoke-XeditClientProcessStatus -Arguments $remaining) }
    'process wait'   { exit (Invoke-XeditClientProcessWait -Arguments $remaining) }
    'process stop'   { exit (Invoke-XeditClientProcessStop -Arguments $remaining) }
    default {
        Write-Host "Unknown command: $group $command"
        exit 1
    }
}
```

- [ ] **Step 4: Run the launch/lifecycle tests and verify they pass**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-vfs-launcher/xedit-client.launch-adapter.test.ps1
pwsh -NoProfile -File tests/mo2-vfs-launcher/xedit-client.process-lifecycle.test.ps1
```

Expected: PASS, and the lifecycle log lines should show `-automation-serve` in the spawned xEdit arguments.

- [ ] **Step 5: Commit this task boundary if commit authority has been explicitly granted during execution**

Run only if the execution round has explicit commit permission:

```bash
git add tools/mo2-vfs-launcher/xedit-client.ps1 tools/mo2-vfs-launcher/lib/xedit-client.launch.ps1 tests/mo2-vfs-launcher/xedit-client.launch-adapter.test.ps1 tests/mo2-vfs-launcher/xedit-client.process-lifecycle.test.ps1
git commit -m "refactor: move xedit launch lifecycle beside vfs launcher"
```

Expected: one commit containing only launch/lifecycle behavior.

### Task 3: Implement native automation-call support and replace the live sandbox test

**Files:**
- Create: `tools/mo2-vfs-launcher/lib/xedit-client.call.ps1`
- Modify: `tools/mo2-vfs-launcher/lib/xedit-client.launch.ps1`
- Modify: `tools/mo2-vfs-launcher/xedit-client.ps1`
- Test: `tests/mo2-vfs-launcher/xedit-client.call.test.ps1`
- Test: `tests/mo2-vfs-launcher/xedit-client.mo2-sandbox-real.test.ps1`

- [ ] **Step 1: Write the failing call-mode unit test**

Create `tests/mo2-vfs-launcher/xedit-client.call.test.ps1` with a stubbed process and a real temporary request file.

Use this core assertion shape:

```powershell
$requestPath = Join-Path $tempRoot 'request.json'
$responsePath = Join-Path $tempRoot 'response.json'
Set-Content -Path $requestPath -Value '{"command":"system.describe","args":{}}'

$call = Invoke-XeditClientAutomationCall -XeditExecutablePath 'D:\xedit\xEdit.exe' -XeditPid 54321 -RequestPath $requestPath -ResponsePath $responsePath -TimeoutSeconds 5

Assert-Equal -Actual $script:CapturedStartInfo.FilePath -Expected 'D:\xedit\xEdit.exe' -Message 'call mode should launch the xEdit executable directly'
Assert-Equal -Actual $script:CapturedStartInfo.ArgumentList[0] -Expected '-automation-call-pid:54321' -Message 'call mode should target the live daemon PID'
Assert-Equal -Actual $script:CapturedStartInfo.ArgumentList[1] -Expected ('-automation-call-request:' + $requestPath) -Message 'call mode should forward the request file path'
Assert-Equal -Actual $script:CapturedStartInfo.ArgumentList[2] -Expected ('-automation-call-response:' + $responsePath) -Message 'call mode should forward the response file path'
```

- [ ] **Step 2: Run the call-mode test and verify it fails**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-vfs-launcher/xedit-client.call.test.ps1
```

Expected: FAIL because `xedit-client.call.ps1` and the call command do not exist yet.

- [ ] **Step 3: Implement the call command and readiness probe**

Create `tools/mo2-vfs-launcher/lib/xedit-client.call.ps1` with the native call-mode executor:

```powershell
function Invoke-XeditClientAutomationCall {
    param(
        [string]$XeditExecutablePath,
        [int]$XeditPid,
        [string]$RequestPath,
        [string]$ResponsePath,
        [int]$TimeoutSeconds = 30
    )

    $startInfo = @{
        FilePath = $XeditExecutablePath
        ArgumentList = @(
            ('-automation-call-pid:' + $XeditPid),
            ('-automation-call-request:' + $RequestPath),
            ('-automation-call-response:' + $ResponsePath)
        )
        PassThru = $true
        WindowStyle = 'Hidden'
    }

    $process = Start-Process @startInfo
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        throw "Timed out waiting for automation-call response after $TimeoutSeconds seconds"
    }
    if (-not (Test-Path $ResponsePath -PathType Leaf)) {
        throw "Automation call response was not created: $ResponsePath"
    }
    return Get-Content -Path $ResponsePath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
}

function Wait-XeditClientAutomationReady {
    param([string]$XeditExecutablePath, [int]$XeditPid, [string]$SessionPath, [int]$TimeoutSeconds = 30)
    $requestPath = Join-Path $SessionPath 'ready.request.json'
    $responsePath = Join-Path $SessionPath 'ready.response.json'
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Set-Content -Path $requestPath -Value '{"command":"system.describe","args":{}}'
        try {
            $response = Invoke-XeditClientAutomationCall -XeditExecutablePath $XeditExecutablePath -XeditPid $XeditPid -RequestPath $requestPath -ResponsePath $responsePath -TimeoutSeconds 5
            if ($response.ok -eq $true) { return $response }
        } catch {
        }
        Start-Sleep -Milliseconds 500
    }
    throw 'Timed out waiting for native xEdit automation readiness'
}
```

Update `tools/mo2-vfs-launcher/lib/xedit-client.launch.ps1` so `Invoke-XeditClientProcessLaunch` calls `Wait-XeditClientAutomationReady` before printing `status: ok`.

Update `tools/mo2-vfs-launcher/xedit-client.ps1` to dispatch the new command:

```powershell
. (Join-Path $toolRoot 'lib/xedit-client.call.ps1')

'automation call' { exit (Invoke-XeditClientAutomationCallCommand -Arguments $remaining) }
```

Implement `Invoke-XeditClientAutomationCallCommand` so it:

- requires `--xedit-pid`, `--request-file`, `--response-file`, and `--timeout-seconds`,
- resolves the live xEdit executable path from the running PID,
- executes `Invoke-XeditClientAutomationCall`,
- preserves the response file as the canonical output artifact.

- [ ] **Step 4: Replace the old live sandbox test with a native serve/call real test**

Create `tests/mo2-vfs-launcher/xedit-client.mo2-sandbox-real.test.ps1` by porting `tests/xedit-cli/mo2-sandbox-launch-real.test.ps1` with these changes:

- delete the `EnsureBridge` and `XeditLoadAll` parameters,
- point `$cliPath` at `tools/mo2-vfs-launcher/xedit-client.ps1`,
- point the real xEdit target at the MO2-managed OpenCodeXEdit tool path,
- remove `Wait-ForHookStatusSuccess`,
- after `process launch`, write a request file containing `{"command":"system.describe","args":{}}`,
- call `automation call` and assert the response JSON has `ok = true` and a `result` object.

Use this request/response section:

```powershell
$requestPath = Join-Path $tempRoot 'system-describe.request.json'
$responsePath = Join-Path $tempRoot 'system-describe.response.json'
Set-Content -Path $requestPath -Value '{"command":"system.describe","args":{}}'

$call = Invoke-Cli -Arguments @(
    'automation', 'call',
    '--xedit-pid', $xeditPid,
    '--request-file', $requestPath,
    '--response-file', $responsePath,
    '--timeout-seconds', '30'
)

Assert-Equal -Actual $call.ExitCode -Expected 0 -Message 'native automation call should succeed against the launched daemon'
$response = Get-Content -Path $responsePath -Raw | ConvertFrom-Json -AsHashtable
Assert-True -Condition ($response.ok -eq $true) -Message 'system.describe response should be ok'
Assert-True -Condition ($response.ContainsKey('result')) -Message 'system.describe response should include result'
```

- [ ] **Step 5: Run the call test and the opt-in real sandbox test**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-vfs-launcher/xedit-client.call.test.ps1
pwsh -NoProfile -File tests/mo2-vfs-launcher/xedit-client.mo2-sandbox-real.test.ps1 -AllowLiveSandbox -RestartMo2
```

Expected:

- the unit call test passes,
- the real test passes without any hook status file,
- the real test proves native `automation-serve` + `automation-call` are reachable through MO2.

- [ ] **Step 6: Commit this task boundary if commit authority has been explicitly granted during execution**

Run only if the execution round has explicit commit permission:

```bash
git add tools/mo2-vfs-launcher/lib/xedit-client.call.ps1 tools/mo2-vfs-launcher/lib/xedit-client.launch.ps1 tools/mo2-vfs-launcher/xedit-client.ps1 tests/mo2-vfs-launcher/xedit-client.call.test.ps1 tests/mo2-vfs-launcher/xedit-client.mo2-sandbox-real.test.ps1
git commit -m "feat: call native xedit automation through outer client"
```

Expected: one commit containing native call-mode support and the real test migration.

### Task 4: Rewrite docs, roadmap, and bootstrap verifiers to the new boundary

**Files:**
- Create: `tools/mo2-vfs-launcher/xedit-client.md`
- Create: `tests/mo2-vfs-launcher/layout.test.ps1`
- Modify: `tools/mo2-vfs-launcher/README.md`
- Modify: `tools/mo2-control-plane/live-integration.md`
- Modify: `tools/README.md`
- Modify: `docs/roadmap.md`
- Modify: `AGENTS.md`
- Modify: `tests/bootstrap/verify-specs.ps1`
- Modify: `tests/bootstrap/verify-foundation.ps1`

- [ ] **Step 1: Write the failing doc/layout/bootstrap tests first**

Create `tests/mo2-vfs-launcher/layout.test.ps1` with explicit absence/presence checks:

```powershell
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

foreach ($path in @(
    'tools/mo2-vfs-launcher/xedit-client.ps1',
    'tools/mo2-vfs-launcher/xedit-client.md',
    'tools/mo2-vfs-launcher/lib/xedit-client.common.ps1',
    'tools/mo2-vfs-launcher/lib/xedit-client.session.ps1',
    'tools/mo2-vfs-launcher/lib/xedit-client.launch.ps1',
    'tools/mo2-vfs-launcher/lib/xedit-client.call.ps1'
)) {
    if (-not (Test-Path (Join-Path $repoRoot $path))) { throw "Missing expected xedit outer-client path: $path" }
}

foreach ($path in @('tools/xedit-cli', 'tools/xedit-hook-bridge', 'tests/xedit-cli')) {
    if (Test-Path (Join-Path $repoRoot $path)) { throw "Legacy path should be removed: $path" }
}

Write-Host 'mo2-vfs-launcher layout checks passed.'
```

Update `tests/bootstrap/verify-specs.ps1` so `requiredPaths` includes:

```powershell
'tools/mo2-vfs-launcher/xedit-client.ps1',
'tools/mo2-vfs-launcher/xedit-client.md',
```

and remove all required-path and phrase assertions for:

```powershell
'tools/xedit-cli/README.md'
'tools/xedit-cli/CONTRACT.md'
'tools/xedit-cli/live-integration.md'
```

Update `tests/bootstrap/verify-foundation.ps1` so the roadmap assertions no longer require the literal capability signal `xedit-cli` or `tools/xedit-cli/CONTRACT.md`. Replace them with:

```powershell
'native xEdit outer client'
'tools/mo2-vfs-launcher/xedit-client.md'
```

- [ ] **Step 2: Run the layout/bootstrap tests and verify they fail**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-vfs-launcher/layout.test.ps1
pwsh -NoProfile -File tests/bootstrap/verify-specs.ps1
pwsh -NoProfile -File tests/bootstrap/verify-foundation.ps1
```

Expected: FAIL because the new xEdit client docs are not written yet and the legacy directories still exist.

- [ ] **Step 3: Write the replacement docs and roadmap language**

Create `tools/mo2-vfs-launcher/xedit-client.md` with this core content:

```markdown
# xedit-client

`xedit-client.ps1` is the MO2-facing outer client for native xEdit automation.

It does not own records, conflicts, jobs, scripts, or patch semantics. Those belong to native xEdit in `D:\TES5Edit-contrib`.

It owns only:

- session-scoped `plugins.txt` generation,
- game-mode and launcher normalization,
- MO2/control-plane launch,
- native serve readiness detection,
- native automation-call request/response artifact handling,
- PID lifecycle.
```

Update `tools/mo2-vfs-launcher/README.md` by appending a short section:

```markdown
## xEdit outer client

`xedit-client.ps1` lives beside the generic launcher and provides the MO2-facing client for native xEdit automation. The generic launcher remains tool-agnostic; xEdit-specific process and request logic belongs in the neighboring outer-client layer.
```

Update `tools/mo2-control-plane/live-integration.md` so its preferred xEdit entrypoint example uses:

```text
pwsh -NoProfile -File tools/mo2-vfs-launcher/xedit-client.ps1 process launch --launcher-path <xedit.exe> --game-mode Fallout4 --mo-profile Default
```

Update `tools/README.md` to mention that the tools tree now hosts the MO2 control plane, generic VFS launcher, and the xEdit outer client layer.

Update `docs/roadmap.md` with these exact signal changes:

- Capability map row: `native xEdit outer client | Foundation in place | tools/mo2-vfs-launcher/xedit-client.ps1 launches native xEdit automation under MO2 and preserves session/plugin-file/launch artifacts.`
- Completed foundations bullet: replace `tools/xedit-cli/CONTRACT.md` with `tools/mo2-vfs-launcher/xedit-client.md`.
- Supporting docs bullet: replace the xedit-cli contract mention with `tools/mo2-vfs-launcher/xedit-client.md`.

Update `AGENTS.md` by removing the `tools/xedit-hook-bridge/` row and replacing it with a note under the `tools/mo2-vfs-launcher/` row that this directory now includes the xEdit outer client.

- [ ] **Step 4: Run the layout/bootstrap tests and verify they pass**

Run:

```powershell
pwsh -NoProfile -File tests/bootstrap/verify-specs.ps1
pwsh -NoProfile -File tests/bootstrap/verify-foundation.ps1
```

Expected: PASS. The bootstrap verifiers should be fully updated to the new documentation boundary before the legacy trees are deleted.

- [ ] **Step 5: Commit this task boundary if commit authority has been explicitly granted during execution**

Run only if the execution round has explicit commit permission:

```bash
git add tools/mo2-vfs-launcher/xedit-client.md tools/mo2-vfs-launcher/README.md tools/mo2-control-plane/live-integration.md tools/README.md docs/roadmap.md AGENTS.md tests/mo2-vfs-launcher/layout.test.ps1 tests/bootstrap/verify-specs.ps1 tests/bootstrap/verify-foundation.ps1
git commit -m "docs: adopt native xedit outer-client boundary"
```

Expected: one commit containing doc and bootstrap-verifier migration only.

### Task 5: Delete the legacy trees and run the full verification sweep

**Files:**
- Delete: `tools/xedit-hook-bridge/**`
- Delete: `tools/xedit-cli/**`
- Delete: `tests/xedit-cli/**`
- Modify: `.gitignore`

- [ ] **Step 1: Remove the old trees and obsolete ignore rules**

Delete these directories completely:

```text
tools/xedit-hook-bridge/
tools/xedit-cli/
tests/xedit-cli/
```

Then remove the obsolete hook-bridge ignore block from `.gitignore`:

```gitignore
-tools/xedit-hook-bridge/src/__recovery/
-tools/xedit-hook-bridge/src/*.dcu
-tools/xedit-hook-bridge/src/*.dll
-tools/xedit-hook-bridge/src/*.dproj.local
-tools/xedit-hook-bridge/src/*.identcache
-tools/xedit-hook-bridge/src/*.res
```

- [ ] **Step 2: Run the new layout test and verify legacy paths are gone**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-vfs-launcher/layout.test.ps1
```

Expected: PASS with `mo2-vfs-launcher layout checks passed.`

- [ ] **Step 3: Run the targeted verification suite**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-vfs-launcher/xedit-client.session-plugins.test.ps1
pwsh -NoProfile -File tests/mo2-vfs-launcher/xedit-client.launch-adapter.test.ps1
pwsh -NoProfile -File tests/mo2-vfs-launcher/xedit-client.process-lifecycle.test.ps1
pwsh -NoProfile -File tests/mo2-vfs-launcher/xedit-client.call.test.ps1
pwsh -NoProfile -File tests/bootstrap/verify-specs.ps1
pwsh -NoProfile -File tests/bootstrap/verify-foundation.ps1
```

Expected: all targeted local tests pass.

- [ ] **Step 4: Run the real MO2 sandbox verification and the bootstrap aggregate**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-vfs-launcher/xedit-client.mo2-sandbox-real.test.ps1 -AllowLiveSandbox -RestartMo2
pwsh -NoProfile -File tests/bootstrap/verify-all.ps1
```

Expected:

- the live sandbox test proves launch + native serve + native call through the MO2 harness,
- `verify-all.ps1` passes with the repo in its new steady state.

- [ ] **Step 5: Commit this task boundary if commit authority has been explicitly granted during execution**

Run only if the execution round has explicit commit permission:

```bash
git add .gitignore tools/mo2-vfs-launcher tests/mo2-vfs-launcher tests/bootstrap tools/README.md tools/mo2-control-plane/live-integration.md docs/roadmap.md AGENTS.md
git rm -r tools/xedit-cli tools/xedit-hook-bridge tests/xedit-cli
git commit -m "refactor: remove legacy xedit wrapper and hook bridge"
```

Expected: one final cleanup commit removing the legacy trees after the new outer client passes verification.

## Self-Review Checklist

- Spec coverage:
  - hook removal is covered by Tasks 4-5,
  - xedit-cli semantic retirement is covered by Tasks 2-5,
  - outer-client re-home beside `mo2-vfs-launcher` is covered by Tasks 1-3,
  - `plugins.txt` ownership split is covered by Tasks 1-3,
  - docs/bootstrap/roadmap boundary updates are covered by Task 4,
  - real verification under MO2 is covered by Tasks 3 and 5.
- Placeholder scan: no unfinished-marker language remains.
- Type consistency: the plan uses one public entrypoint name (`xedit-client.ps1`) and one command family (`process launch/status/wait/stop`, `automation call`) throughout.

param(
    [switch]$AllowLiveSandbox,
    [switch]$DeployBridge,
    [switch]$RestartMo2,
    [int]$TimeoutSeconds = 15,
    [int]$PollIntervalMilliseconds = 500
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$liveMo2Root = "D:\awesome-bgs-mod-master\.artifacts\mo2"
$liveRepoRoot = (Split-Path (Split-Path $liveMo2Root -Parent) -Parent)
$mo2ExecutablePath = Join-Path $liveMo2Root "ModOrganizer.exe"
$modOrganizerIniPath = Join-Path $liveMo2Root "ModOrganizer.ini"
$pluginsRoot = Join-Path $liveMo2Root "plugins"
$moInterfaceLogPath = Join-Path $liveMo2Root "logs\mo_interface.log"
$bridgePath = Join-Path $pluginsRoot "mo2_agent_control.py"
$pluginSupportRoot = Join-Path $pluginsRoot "Mo2AgentControl"
$bootstrapRoot = Join-Path $pluginSupportRoot "bootstrap"
$runtimeRoot = Join-Path $bootstrapRoot "runtime"
$deployScriptPath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1"
$runtimeFilePaths = @(
    (Join-Path $runtimeRoot "status.json"),
    (Join-Path $runtimeRoot "capabilities.json"),
    (Join-Path $runtimeRoot "endpoint.json")
)

. (Join-Path $PSScriptRoot "live-sandbox.ps1")

function Get-PluginPayloadEntries {
    if (-not (Test-Path $pluginSupportRoot -PathType Container)) {
        return @()
    }

    @(Get-ChildItem -Path $pluginSupportRoot -Force | Where-Object {
        $_.Name -ne "bootstrap"
    })
}

function Test-RuntimeFilesPresent {
    foreach ($path in $runtimeFilePaths) {
        if (-not (Test-Path $path -PathType Leaf)) {
            return $false
        }
    }

    return $true
}

function Get-FreshMoInterfaceLogEntries {
    param(
        [int]$BaselineLineCount
    )

    if (-not (Test-Path $moInterfaceLogPath -PathType Leaf)) {
        return @()
    }

    $allLines = @(Get-Content -Path $moInterfaceLogPath)
    if ($BaselineLineCount -ge $allLines.Count) {
        return @()
    }

    $startIndex = [Math]::Max($BaselineLineCount, 0)
    return @($allLines[$startIndex..($allLines.Count - 1)])
}

if (-not $AllowLiveSandbox) {
    throw "This real harness touches D:\awesome-bgs-mod-master\.artifacts\mo2. Re-run with -AllowLiveSandbox to opt in."
}

if (-not (Test-Path $liveMo2Root -PathType Container)) {
    throw "Missing live MO2 sandbox root: $liveMo2Root"
}

if (-not (Test-Path $mo2ExecutablePath -PathType Leaf)) {
    throw "Missing live MO2 executable: $mo2ExecutablePath"
}

if ($DeployBridge -and -not (Test-Path $deployScriptPath -PathType Leaf)) {
    throw "Missing live bridge deploy helper: $deployScriptPath"
}

$sandboxHarnessMutex = Enter-SandboxHarnessLock -Path $mo2ExecutablePath -TimeoutSeconds $TimeoutSeconds

try {
    if (Test-Path $runtimeRoot) {
        Remove-Item -Path $runtimeRoot -Recurse -Force
    }

    if (Test-Path $runtimeRoot) {
        throw "Failed to clear live bootstrap runtime directory: $runtimeRoot"
    }

    foreach ($path in $runtimeFilePaths) {
        if (Test-Path $path) {
            throw "Runtime file should be missing before MO2 starts: $path"
        }
    }

    Write-Host "Cleared live bootstrap runtime directory: $runtimeRoot"
    Write-Host "Verified bootstrap runtime files are absent before MO2 starts."

    if ($DeployBridge) {
        & pwsh -NoProfile -File $deployScriptPath -Mo2Root $liveRepoRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Deploying the live bridge into the real sandbox should succeed."
        }
    }

    if (-not (Test-Path $modOrganizerIniPath -PathType Leaf)) {
        throw "Missing live sandbox MO2 configuration: $modOrganizerIniPath"
    }

    $modOrganizerIni = Get-Content -Path $modOrganizerIniPath -Raw
    if ($modOrganizerIni -notmatch '(?m)^lock_gui=false$') {
        throw "Live sandbox should keep lock_gui=false in ModOrganizer.ini"
    }

    if ($modOrganizerIni -match '(?m)^lock_gui=true$') {
        throw "Live sandbox should not regress to lock_gui=true in ModOrganizer.ini"
    }

    $moInterfaceLogBaseline = if (Test-Path $moInterfaceLogPath -PathType Leaf) {
        @(Get-Content -Path $moInterfaceLogPath).Count
    }
    else {
        0
    }

    $freshnessThreshold = [DateTime]::UtcNow

    if ($RestartMo2) {
        Stop-SandboxMo2FromPath -Path $mo2ExecutablePath -TimeoutSeconds $TimeoutSeconds -PollIntervalMilliseconds $PollIntervalMilliseconds
        $null = Start-Process -FilePath $mo2ExecutablePath -PassThru
        Write-Host "Started live MO2 sandbox: $mo2ExecutablePath"
    }
    else {
        Write-Host "Waiting for the operator to start or restart MO2: $mo2ExecutablePath"
    }

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-RuntimeFilesPresent) {
            break
        }

        Start-Sleep -Milliseconds $PollIntervalMilliseconds
    }

    if (-not (Test-RuntimeFilesPresent)) {
        $payloadEntries = Get-PluginPayloadEntries
        $payloadHint = if ($payloadEntries.Count -eq 0) {
            " No additional plugin payload is installed under $pluginSupportRoot yet; the Python bridge at $bridgePath may now be in the correct scan path, but MO2 still has not recreated the runtime files in this sandbox."
        }
        else {
            " Detected plugin payload entries: $($payloadEntries.Name -join ', ')."
        }

        throw "Expected live bootstrap runtime files to be recreated under $runtimeRoot after MO2 startup/restart. The bridge is likely not deployed or MO2 has not loaded it yet.$payloadHint"
    }

    foreach ($path in $runtimeFilePaths) {
        if ((Get-Item $path).LastWriteTimeUtc -lt $freshnessThreshold) {
            throw "Runtime file should be freshly recreated after MO2 startup/restart: $path"
        }
    }

    $status = Get-Content -Path (Join-Path $runtimeRoot "status.json") -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    if ($status.schemaVersion -ne 1) {
        throw "status.json should publish schemaVersion 1 in the real sandbox"
    }

    if ($status.state -ne "ok") {
        throw "status.json should publish state 'ok' in the real sandbox"
    }

    $liveMo2Processes = @(Get-ProcessFromPath -Path $mo2ExecutablePath)
    if ($liveMo2Processes.Count -eq 0) {
        throw "Expected a live sandbox MO2 process before validating status.json mo2Pid"
    }

    if ($status.mo2Pid -isnot [int] -and $status.mo2Pid -isnot [long]) {
        throw "status.json should publish an integer mo2Pid in the real sandbox"
    }

    if (($liveMo2Processes.Id) -notcontains ([int]$status.mo2Pid)) {
        throw "status.json mo2Pid should reference a currently running sandbox MO2 process"
    }

    $freshMoInterfaceLogEntries = Get-FreshMoInterfaceLogEntries -BaselineLineCount $moInterfaceLogBaseline
    $createPluginFailures = @($freshMoInterfaceLogEntries | Where-Object {
        $_ -match [regex]::Escape('missing a createPlugin(s) function')
    })
    if ($createPluginFailures.Count -gt 0) {
        throw "Fresh mo_interface.log entries still show MO2 rejecting the Python bridge as a plugin entrypoint: missing a createPlugin(s) function"
    }

    Write-Host "MO2 live bootstrap real-environment checks passed."
}
finally {
    if ($null -ne $sandboxHarnessMutex) {
        $sandboxHarnessMutex.ReleaseMutex()
        $sandboxHarnessMutex.Dispose()
    }
}

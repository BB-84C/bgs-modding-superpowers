param(
    [switch]$AllowLiveSandbox,
    [switch]$EnsureBridge,
    [switch]$RestartMo2,
    [int]$TimeoutSeconds = 15,
    [int]$PollIntervalMilliseconds = 500
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$liveMo2Root = "D:\awesome-bgs-mod-master\.artifacts\mo2"
$liveRepoRoot = (Split-Path (Split-Path $liveMo2Root -Parent) -Parent)
$mo2ExecutablePath = Join-Path $liveMo2Root "ModOrganizer.exe"
$runtimeRoot = Join-Path $liveMo2Root "plugins\Mo2AgentControl\bootstrap\runtime"
$cliPath = Join-Path $repoRoot "tools/mo2-control-plane/broker/bin/mo2-cli.ps1"
$deployScriptPath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1"
$runtimeFilePaths = @(
    (Join-Path $runtimeRoot "status.json"),
    (Join-Path $runtimeRoot "capabilities.json"),
    (Join-Path $runtimeRoot "endpoint.json")
)

. (Join-Path $PSScriptRoot "live-sandbox.ps1")

function Test-RuntimeFilesPresent {
    foreach ($path in $runtimeFilePaths) {
        if (-not (Test-Path $path -PathType Leaf)) {
            return $false
        }
    }

    return $true
}

function Wait-ForRuntimeFiles {
    param(
        [datetime]$FreshnessThreshold = $null
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-RuntimeFilesPresent) {
            $isFresh = $true
            if ($null -ne $FreshnessThreshold) {
                foreach ($path in $runtimeFilePaths) {
                    if ((Get-Item $path).LastWriteTimeUtc -lt $FreshnessThreshold) {
                        $isFresh = $false
                        break
                    }
                }
            }

            if ($isFresh) {
                return
            }
        }

        Start-Sleep -Milliseconds $PollIntervalMilliseconds
    }

    if (-not (Test-RuntimeFilesPresent)) {
        throw "Expected live bootstrap runtime files under $runtimeRoot"
    }

    throw "Expected live bootstrap runtime files under $runtimeRoot to be freshly recreated after bridge ensure/restart"
}

function Invoke-Cli {
    param(
        [string[]]$Arguments
    )

    $output = & pwsh -NoProfile -File $cliPath @Arguments 2>&1

    return [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = ($output | ForEach-Object { $_.ToString() }) -join "`n"
    }
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

if (-not (Test-Path $cliPath -PathType Leaf)) {
    throw "Missing broker CLI: $cliPath"
}

if ($EnsureBridge -and -not (Test-Path $deployScriptPath -PathType Leaf)) {
    throw "Missing live bridge deploy helper: $deployScriptPath"
}

$sandboxHarnessMutex = Enter-SandboxHarnessLock -Path $mo2ExecutablePath -TimeoutSeconds $TimeoutSeconds

try {
    $freshnessThreshold = $null
    if ($EnsureBridge) {
        $freshnessThreshold = [DateTime]::UtcNow
        & pwsh -NoProfile -File $deployScriptPath -Mo2Root $liveRepoRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Deploying the live bridge into the real sandbox should succeed."
        }
    }

    if ($RestartMo2) {
        if ($null -eq $freshnessThreshold) {
            $freshnessThreshold = [DateTime]::UtcNow
        }

        Stop-SandboxMo2FromPath -Path $mo2ExecutablePath -TimeoutSeconds $TimeoutSeconds -PollIntervalMilliseconds $PollIntervalMilliseconds
        $null = Start-Process -FilePath $mo2ExecutablePath -PassThru
        Write-Host "Started live MO2 sandbox: $mo2ExecutablePath"
    }

    Wait-ForRuntimeFiles -FreshnessThreshold $freshnessThreshold

    $livePing = Invoke-Cli -Arguments @("system", "ping", "--live-root", $runtimeRoot)
    if ($livePing.ExitCode -ne 0) {
        throw "system ping from the real runtime should succeed: $($livePing.Output)"
    }

    $livePingJson = $livePing.Output | ConvertFrom-Json -ErrorAction Stop
    if (-not $livePingJson.ok) {
        throw "system ping from the real runtime should return ok=true"
    }

    if ($livePingJson.result.status -ne "ok") {
        throw "system ping from the real runtime should surface state 'ok'"
    }

    $liveCapabilities = Invoke-Cli -Arguments @("system", "capabilities", "--live-root", $runtimeRoot)
    if ($liveCapabilities.ExitCode -ne 0) {
        throw "system capabilities from the real runtime should succeed: $($liveCapabilities.Output)"
    }

    $liveCapabilitiesJson = $liveCapabilities.Output | ConvertFrom-Json -ErrorAction Stop
    if (-not $liveCapabilitiesJson.ok) {
        throw "system capabilities from the real runtime should return ok=true"
    }

    foreach ($commandName in @("system.ping", "system.capabilities")) {
        if ($liveCapabilitiesJson.result.commands -notcontains $commandName) {
            throw "system capabilities from the real runtime should advertise $commandName"
        }
    }

    Write-Host "MO2 real live ping/capabilities checks passed."
}
finally {
    if ($null -ne $sandboxHarnessMutex) {
        $sandboxHarnessMutex.ReleaseMutex()
        $sandboxHarnessMutex.Dispose()
    }
}

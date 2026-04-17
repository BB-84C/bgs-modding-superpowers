param(
    [switch]$AllowLiveSandbox,
    [switch]$DeployBridge,
    [switch]$RestartMo2,
    [int]$TimeoutSeconds = 30,
    [int]$PollIntervalMilliseconds = 500
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$liveMo2Root = "D:\awesome-bgs-mod-master\.artifacts\mo2"
$liveRepoRoot = (Split-Path (Split-Path $liveMo2Root -Parent) -Parent)
$mo2ExecutablePath = Join-Path $liveMo2Root "ModOrganizer.exe"
$pluginSupportRoot = Join-Path $liveMo2Root "plugins\Mo2AgentControl"
$runtimeRoot = Join-Path $liveMo2Root "plugins\Mo2AgentControl\bootstrap\runtime"
$cliPath = Join-Path $repoRoot "tools/mo2-control-plane/broker/bin/mo2-cli.ps1"
$deployScriptPath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1"
$runtimeFilePaths = @(
    (Join-Path $runtimeRoot "status.json"),
    (Join-Path $runtimeRoot "capabilities.json"),
    (Join-Path $runtimeRoot "endpoint.json")
)

. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/common.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/protocol.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/session.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/launch.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/ipc-client.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/live-bootstrap.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/client.ps1")

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

    throw "Expected live bootstrap runtime files under $runtimeRoot to be freshly recreated after bridge deployment or restart"
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

function New-LiveLaunchRequest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SessionId,
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [Parameter(Mandatory = $true)]
        [string]$TargetPath,
        [string[]]$Arguments = @(),
        [string]$WorkingDirectory = $null
    )

    return New-Mo2ControlPlaneRequest -SessionId $SessionId -Command $Command -Payload ([ordered]@{
        transport = [ordered]@{
            target_path = $TargetPath
            args = $Arguments
            cwd = $WorkingDirectory
            env = [ordered]@{}
        }
    })
}

function Wait-ForLaunchStatus {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LiveRoot,
        [Parameter(Mandatory = $true)]
        [string]$SessionId,
        [Parameter(Mandatory = $true)]
        [string]$LaunchId,
        [Parameter(Mandatory = $true)]
        [string[]]$AcceptedStatuses
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $statusResponse = Invoke-Mo2ControlPlaneClientRequest -LiveRoot $LiveRoot -Request (New-Mo2ControlPlaneRequest -SessionId $SessionId -Command "launch.status" -Payload @{ launch_id = $LaunchId })
        if ($statusResponse.ok -and $AcceptedStatuses -contains ([string]$statusResponse.result.status)) {
            return $statusResponse
        }

        Start-Sleep -Milliseconds $PollIntervalMilliseconds
    }

    throw "Timed out waiting for launch $LaunchId to reach one of: $($AcceptedStatuses -join ', ')"
}

function Wait-ForPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $Path -PathType Leaf) {
            return
        }

        Start-Sleep -Milliseconds $PollIntervalMilliseconds
    }

    throw "Timed out waiting for file creation: $Path"
}

function Remove-ItemIfPresent {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (Test-Path $Path) {
        Remove-Item -Path $Path -Force -ErrorAction Stop
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

if ($DeployBridge -and -not (Test-Path $deployScriptPath -PathType Leaf)) {
    throw "Missing live bridge deploy helper: $deployScriptPath"
}

$sandboxHarnessMutex = Enter-SandboxHarnessLock -Path $mo2ExecutablePath -TimeoutSeconds $TimeoutSeconds

try {
    $freshnessThreshold = $null
    if ($DeployBridge) {
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

    $endpoint = Get-Content -Path (Join-Path $runtimeRoot "endpoint.json") -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    if ($endpoint.transport -ne "named-pipe") {
        throw "The real sandbox should publish named-pipe transport in endpoint.json"
    }
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

    foreach ($commandName in @("system.ping", "system.capabilities", "launch.start", "launch.status", "launch.wait", "launch.stop")) {
        if ($liveCapabilitiesJson.result.commands -notcontains $commandName) {
            throw "system capabilities from the real runtime should advertise $commandName"
        }
    }

    $cmdPath = if (-not [string]::IsNullOrWhiteSpace($env:ComSpec)) { $env:ComSpec } else { Join-Path $env:WINDIR "System32\cmd.exe" }
    $sessionId = "sess-live-ipc-real-" + [guid]::NewGuid().ToString("N")
    $pluginHarnessRoot = Join-Path $pluginSupportRoot "harness"
    $shortMarkerPath = Join-Path $pluginHarnessRoot "harmless-short.ok"
    $shortScriptPath = Join-Path $pluginHarnessRoot "harmless-short.cmd"
    $longMarkerPath = Join-Path $pluginHarnessRoot "harmless-long.ok"
    $longScriptPath = Join-Path $pluginHarnessRoot "harmless-long.cmd"

    $null = New-Item -ItemType Directory -Path $pluginHarnessRoot -Force
    Remove-ItemIfPresent -Path $shortMarkerPath
    Remove-ItemIfPresent -Path $longMarkerPath

    Set-Content -Path $shortScriptPath -Encoding ASCII -Value @"
@echo off
> "$shortMarkerPath" echo ok
exit /b 0
"@

    Set-Content -Path $longScriptPath -Encoding ASCII -Value @"
@echo off
> "$longMarkerPath" echo started
ping -n 30 127.0.0.1 >nul
exit /b 0
"@

    $shortStart = Invoke-Mo2ControlPlaneClientRequest -LiveRoot $runtimeRoot -Request (New-LiveLaunchRequest -SessionId $sessionId -Command "launch.start" -TargetPath $cmdPath -Arguments @("/c", $shortScriptPath) -WorkingDirectory $pluginHarnessRoot)
    if (-not $shortStart.ok) {
        throw "launch.start from the real runtime should succeed: $($shortStart.error.message)"
    }

    if ([string]::IsNullOrWhiteSpace([string]$shortStart.result.launch_id)) {
        throw "launch.start from the real runtime should return launch_id"
    }

    if ($shortStart.result.pid -le 0) {
        throw "launch.start from the real runtime should return a real pid"
    }

    if ([string]$shortStart.result.artifacts.backend -ne "organizer") {
        throw "launch.start from the real runtime should report artifacts.backend=organizer for sandbox launches"
    }

    Wait-ForPath -Path $shortMarkerPath

    $shortStatus = Wait-ForLaunchStatus -LiveRoot $runtimeRoot -SessionId $sessionId -LaunchId $shortStart.result.launch_id -AcceptedStatuses @("running", "completed")
    if ($shortStatus.result.launch_id -ne $shortStart.result.launch_id) {
        throw "launch.status from the real runtime should keep launch_id stable"
    }

    $longStart = Invoke-Mo2ControlPlaneClientRequest -LiveRoot $runtimeRoot -Request (New-LiveLaunchRequest -SessionId $sessionId -Command "launch.start" -TargetPath $cmdPath -Arguments @("/c", $longScriptPath) -WorkingDirectory $pluginHarnessRoot)
    if (-not $longStart.ok) {
        throw "long-lived launch.start from the real runtime should succeed: $($longStart.error.message)"
    }

    Wait-ForPath -Path $longMarkerPath

    $longStatus = Wait-ForLaunchStatus -LiveRoot $runtimeRoot -SessionId $sessionId -LaunchId $longStart.result.launch_id -AcceptedStatuses @("running")
    if ($longStatus.result.status -ne "running") {
        throw "launch.status from the real runtime should report the long-lived sandbox script as running before stop"
    }

    if ([string]$longStatus.result.artifacts.backend -ne "organizer") {
        throw "launch.status from the real runtime should preserve artifacts.backend=organizer for sandbox launches"
    }

    $longStop = Invoke-Mo2ControlPlaneClientRequest -LiveRoot $runtimeRoot -Request (New-Mo2ControlPlaneRequest -SessionId $sessionId -Command "launch.stop" -Payload @{ launch_id = $longStart.result.launch_id })
    if (-not $longStop.ok) {
        throw "launch.stop from the real runtime should succeed: $($longStop.error.message)"
    }

    if ($longStop.result.status -ne "stopped") {
        throw "launch.stop from the real runtime should report stopped for the long-lived sandbox script"
    }

    $longWait = Invoke-Mo2ControlPlaneClientRequest -LiveRoot $runtimeRoot -Request (New-Mo2ControlPlaneRequest -SessionId $sessionId -Command "launch.wait" -Payload @{ launch_id = $longStart.result.launch_id })
    if (-not $longWait.ok) {
        throw "launch.wait from the real runtime should succeed after stop: $($longWait.error.message)"
    }

    if ($longWait.result.status -ne "stopped") {
        throw "launch.wait from the real runtime should preserve stopped state after stop"
    }

    Write-Host "MO2 real IPC sandbox checks passed."
}
finally {
    if ($null -ne $sandboxHarnessMutex) {
        $sandboxHarnessMutex.ReleaseMutex()
        $sandboxHarnessMutex.Dispose()
    }
}

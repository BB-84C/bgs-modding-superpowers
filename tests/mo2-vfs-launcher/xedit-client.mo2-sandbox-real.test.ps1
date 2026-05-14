param(
    [switch]$AllowLiveSandbox,
    [switch]$RestartMo2,
    [int]$TimeoutSeconds = 30,
    [int]$PollIntervalMilliseconds = 500
)

$ErrorActionPreference = "Stop"

Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$liveMo2Root = "D:\awesome-bgs-mod-master\.artifacts\mo2"
$profileName = "Default"
$mo2ExecutablePath = Join-Path $liveMo2Root "ModOrganizer.exe"
$modOrganizerIniPath = Join-Path $liveMo2Root "ModOrganizer.ini"
$runtimeRoot = Join-Path $liveMo2Root "plugins\Mo2AgentControl\bootstrap\runtime"
$cliPath = Join-Path $repoRoot "tools/mo2-vfs-launcher/xedit-client.ps1"
$realXeditLauncherPath = Join-Path $liveMo2Root "Stock Game\Fallout 4\Tools\OpenCodeXEdit\xEdit.exe"
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
. (Join-Path $repoRoot "tests/mo2-control-plane/live-sandbox.ps1")

function Assert-Equal {
    param($Actual, $Expected, [string]$Message)
    if ($Actual -ne $Expected) { throw "$Message`nExpected: $Expected`nActual: $Actual" }
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Get-RequiredOutputValue {
    param([string]$Output, [string]$FieldName)

    if ($Output -notmatch ("(?m)^" + [regex]::Escape($FieldName) + ":\s*(.+)$")) {
        throw "Missing output field: $FieldName`nActual output:`n$Output"
    }

    return $Matches[1].Trim()
}

function Invoke-Cli {
    param([string[]]$Arguments)

    $records = @(& pwsh -NoProfile -File $cliPath @Arguments 2>&1)
    $output = ($records | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine

    return [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = $output }
}

function Test-RuntimeFilesPresent {
    foreach ($path in $runtimeFilePaths) {
        if (-not (Test-Path $path -PathType Leaf)) { return $false }
    }
    return $true
}

function Wait-ForRuntimeFiles {
    param($FreshnessThreshold = $null)

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
            if ($isFresh) { return }
        }

        Start-Sleep -Milliseconds $PollIntervalMilliseconds
    }

    if (-not (Test-RuntimeFilesPresent)) { throw "Expected live bootstrap runtime files under $runtimeRoot" }
    throw "Expected live bootstrap runtime files under $runtimeRoot to be freshly recreated after restart"
}

if (-not $AllowLiveSandbox) {
    throw "This real harness touches D:\awesome-bgs-mod-master\.artifacts\mo2. Re-run with -AllowLiveSandbox to opt in."
}

foreach ($requiredPath in @($liveMo2Root, $mo2ExecutablePath, $modOrganizerIniPath, $cliPath, $realXeditLauncherPath)) {
    if (-not (Test-Path $requiredPath)) { throw "Missing required path: $requiredPath" }
}

$modOrganizerIni = Get-Content -Path $modOrganizerIniPath -Raw
if ($modOrganizerIni -notmatch [regex]::Escape("selected_profile=@ByteArray($profileName)")) {
    throw "The project-local MO2 sandbox must be configured to use profile $profileName before this real probe runs."
}

$sandboxHarnessMutex = Enter-SandboxHarnessLock -Path $mo2ExecutablePath -TimeoutSeconds $TimeoutSeconds
$tempRoot = Join-Path $env:TEMP ("xedit-client-mo2-sandbox-real-" + [guid]::NewGuid().ToString("N"))
$xeditLaunchId = $null
$xeditPid = $null

try {
    $freshnessThreshold = $null
    if ($RestartMo2) {
        $freshnessThreshold = [DateTime]::UtcNow
        Stop-SandboxMo2FromPath -Path $mo2ExecutablePath -TimeoutSeconds $TimeoutSeconds -PollIntervalMilliseconds $PollIntervalMilliseconds
        $null = Start-Process -FilePath $mo2ExecutablePath -PassThru
    }

    if ($null -eq $freshnessThreshold) { Wait-ForRuntimeFiles } else { Wait-ForRuntimeFiles -FreshnessThreshold $freshnessThreshold }

    $null = New-Item -ItemType Directory -Path $tempRoot -Force

    $cliLaunch = Invoke-Cli -Arguments @(
        'process', 'launch',
        '--launcher-path', $realXeditLauncherPath,
        '--game-mode', 'Fallout4',
        '--mo-profile', $profileName
    )
    Set-Content -Path (Join-Path $tempRoot 'xedit-client-launch-output.txt') -Value $cliLaunch.Output

    Assert-Equal -Actual $cliLaunch.ExitCode -Expected 0 -Message "xedit-client process launch should succeed under the real MO2 sandbox"
    Assert-True -Condition ($cliLaunch.Output -match [regex]::Escape('mo2-launch-backend: organizer')) -Message 'xEdit launch should report organizer backend under MO2 control plane'

    $requestFilePath = Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'mo2-launch-request-file'
    $responseFilePath = Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'mo2-launch-response-file'
    $launcherStatePath = Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'mo2-launch-state-file'
    $xeditLaunchId = Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'mo2-launch-id'
    $xeditPid = [int](Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'xedit-pid')

    Assert-True -Condition (Test-Path $requestFilePath -PathType Leaf) -Message 'xEdit launch should persist the control-plane launch request artifact'
    Assert-True -Condition (Test-Path $responseFilePath -PathType Leaf) -Message 'xEdit launch should persist the control-plane launch response artifact'
    Assert-True -Condition (Test-Path $launcherStatePath -PathType Leaf) -Message 'xEdit launch should persist the launcher state artifact'
    Assert-True -Condition ($xeditPid -gt 0) -Message 'xEdit launch should return a positive real xEdit pid'

    $launchResponse = Get-Content -Path $responseFilePath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    Assert-True -Condition ([bool]$launchResponse.ok) -Message 'xEdit launch response artifact should preserve ok=true'
    Assert-True -Condition ([string]$launchResponse.result.launch_id -eq $xeditLaunchId) -Message 'xEdit launch response artifact should preserve the same launch id surfaced by the CLI'
    Assert-True -Condition ([string]$launchResponse.result.artifacts.backend -eq 'organizer') -Message 'xEdit launch response artifact should preserve organizer backend evidence'

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

    Write-Host "xedit-client real MO2 sandbox native serve/call passed for profile $profileName."
    Write-Host "evidence-root: $tempRoot"
}
finally {
    if (-not [string]::IsNullOrWhiteSpace($xeditLaunchId)) {
        try {
            $stopResponse = Invoke-Mo2ControlPlaneClientRequest -LiveRoot $runtimeRoot -Request (New-Mo2ControlPlaneRequest -SessionId "cleanup-$xeditLaunchId" -Command "launch.stop" -Payload @{ launch_id = $xeditLaunchId })
            $null = $stopResponse
        } catch {}
    }

    if ($xeditPid -gt 0) { Stop-Process -Id $xeditPid -Force -ErrorAction SilentlyContinue }

    if ($null -ne $sandboxHarnessMutex) {
        $sandboxHarnessMutex.ReleaseMutex()
        $sandboxHarnessMutex.Dispose()
    }
}

exit 0

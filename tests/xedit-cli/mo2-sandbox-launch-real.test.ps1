param(
    [switch]$AllowLiveSandbox,
    [switch]$EnsureBridge,
    [switch]$XeditLoadAll,
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
$deployScriptPath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1"
$probePath = Join-Path $repoRoot "tools/mo2-vfs-launcher/mo2-vfs-probe.ps1"
$xeditCliPath = Join-Path $repoRoot "tools/xedit-cli/bin/xedit-cli.ps1"
$realXeditLauncherPath = Join-Path $liveMo2Root "Stock Game\Fallout 4\Tools\FO4Edit\FO4Edit.exe"
$probeVisiblePath = Join-Path $liveMo2Root "Stock Game\Fallout 4\Data\CraftingTools.esp"
$expectedPluginsPath = Join-Path $env:LOCALAPPDATA "Fallout4\plugins.txt"
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

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Get-RequiredOutputValue {
    param(
        [string]$Output,
        [string]$FieldName
    )

    if ($Output -notmatch ("(?m)^" + [regex]::Escape($FieldName) + ":\s*(.+)$")) {
        throw "Missing output field: $FieldName`nActual output:`n$Output"
    }

    return $Matches[1].Trim()
}

function Invoke-Cli {
    param(
        [string[]]$Arguments
    )

    $records = @(& pwsh -NoProfile -File $xeditCliPath @Arguments 2>&1)
    $output = ($records | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine

    return [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = $output
    }
}

function ConvertTo-PowerShellSingleQuotedLiteral {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    return "'" + ($Value -replace "'", "''") + "'"
}

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
        $FreshnessThreshold = $null
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

function Wait-ForPath {
    param(
        [string]$Path,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $Path -PathType Leaf) {
            return
        }

        Start-Sleep -Milliseconds 200
    }

    throw "Timed out waiting for file: $Path"
}

function Wait-ForHookStatusSuccess {
    param(
        [string]$Path,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastStatus = $null
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $Path -PathType Leaf) {
            $lastStatus = Get-Content -Path $Path -Raw
            if ($lastStatus -match '(?m)^selection_confirmed=true\s*$') {
                return $lastStatus
            }

            if ($lastStatus -match '(?m)^status=failed\s*$') {
                throw "hook status reported failure:`n$lastStatus"
            }
        }

        Start-Sleep -Milliseconds 500
    }

    throw "Timed out waiting for confirmed hook status at $Path`nLast status:`n$lastStatus"
}

function New-LiveLaunchRequest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SessionId,
        [Parameter(Mandatory = $true)]
        [string]$TargetPath,
        [string[]]$Arguments = @(),
        [string]$WorkingDirectory = $null
    )

    return New-Mo2ControlPlaneRequest -SessionId $SessionId -Command "launch.start" -Payload ([ordered]@{
        transport = [ordered]@{
        target_path = $TargetPath
        args = $Arguments
        cwd = $WorkingDirectory
        env = [ordered]@{}
        }
    })
}

if (-not $AllowLiveSandbox) {
    throw "This real harness touches D:\awesome-bgs-mod-master\.artifacts\mo2. Re-run with -AllowLiveSandbox to opt in."
}

foreach ($requiredPath in @($liveMo2Root, $mo2ExecutablePath, $modOrganizerIniPath, $probePath)) {
    if (-not (Test-Path $requiredPath)) {
        throw "Missing required path: $requiredPath"
    }
}

$pwshCommand = Get-Command pwsh -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $pwshCommand -or [string]::IsNullOrWhiteSpace([string]$pwshCommand.Source)) {
    throw "Unable to resolve pwsh for the real MO2 sandbox launcher probe"
}

if ($EnsureBridge -and -not (Test-Path $deployScriptPath -PathType Leaf)) {
    throw "Missing live bridge deploy helper: $deployScriptPath"
}

$modOrganizerIni = Get-Content -Path $modOrganizerIniPath -Raw
if ($modOrganizerIni -notmatch [regex]::Escape("selected_profile=@ByteArray($profileName)")) {
    throw "The project-local MO2 sandbox must be configured to use profile $profileName before this real probe runs."
}

$sandboxHarnessMutex = Enter-SandboxHarnessLock -Path $mo2ExecutablePath -TimeoutSeconds $TimeoutSeconds
$tempRoot = Join-Path $env:TEMP ("xedit-cli-mo2-sandbox-real-" + [guid]::NewGuid().ToString("N"))
$probeLaunchId = $null
$probeLaunchPid = $null
$xeditLaunchId = $null
$xeditPid = $null

try {
    $freshnessThreshold = $null
    if ($EnsureBridge) {
        $freshnessThreshold = [DateTime]::UtcNow
        $liveRepoRoot = Split-Path (Split-Path $liveMo2Root -Parent) -Parent
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
    }

    if ($null -eq $freshnessThreshold) {
        Wait-ForRuntimeFiles
    }
    else {
        Wait-ForRuntimeFiles -FreshnessThreshold $freshnessThreshold
    }

    $null = New-Item -ItemType Directory -Path $tempRoot -Force
    $probeSessionId = "sess-xedit-cli-mo2-sandbox-probe-" + [guid]::NewGuid().ToString("N")
    $probeLaunchStatePath = Join-Path $tempRoot "probe.launch-state.json"
    $probeResultPath = Join-Path $tempRoot "probe.result.json"
    $probeWrapperPath = Join-Path $tempRoot "probe-wrapper.ps1"
    $probeWrapperContent = @(
        '$ErrorActionPreference = "Stop"',
        '$launchState = [ordered]@{',
        "    status = 'spawned'",
        '    pid = $PID',
        "    session_id = $(ConvertTo-PowerShellSingleQuotedLiteral -Value $probeSessionId)",
        '} | ConvertTo-Json -Compress',
        "Set-Content -LiteralPath $(ConvertTo-PowerShellSingleQuotedLiteral -Value $probeLaunchStatePath) -Value `$launchState",
        "& $(ConvertTo-PowerShellSingleQuotedLiteral -Value $probePath) --path $(ConvertTo-PowerShellSingleQuotedLiteral -Value $probeVisiblePath) --result-path $(ConvertTo-PowerShellSingleQuotedLiteral -Value $probeResultPath)",
        'if ($LASTEXITCODE -ne 0) {',
        '    exit $LASTEXITCODE',
        '}',
        'exit 0'
    ) -join [Environment]::NewLine
    Set-Content -LiteralPath $probeWrapperPath -Value $probeWrapperContent

    Assert-True -Condition (-not (Test-Path -LiteralPath $probeVisiblePath)) -Message "host process should not see CraftingTools.esp at the stock Data path before entering MO2/usvfs"

    $probeLaunchRequest = New-LiveLaunchRequest -SessionId $probeSessionId -TargetPath $pwshCommand.Source -WorkingDirectory (Split-Path $probePath -Parent) -Arguments @(
        '-NoProfile',
        '-File',
        $probeWrapperPath
    )

    $probeLaunchResponse = Invoke-Mo2ControlPlaneClientRequest -LiveRoot $runtimeRoot -Request $probeLaunchRequest
    if (-not $probeLaunchResponse.ok) {
        throw "live control-plane launch.start for the MO2 VFS probe should succeed: $($probeLaunchResponse.error.message)"
    }

    $probeLaunchId = [string]$probeLaunchResponse.result.launch_id
    $probeLaunchPid = [int]$probeLaunchResponse.result.pid
    Assert-True -Condition (-not [string]::IsNullOrWhiteSpace($probeLaunchId)) -Message "real MO2 VFS probe launch should return a launch_id"
    Assert-True -Condition ($probeLaunchPid -gt 0) -Message "real MO2 VFS probe launch should return a positive PID"
    Assert-True -Condition ([string]$probeLaunchResponse.result.artifacts.backend -eq "organizer") -Message "real MO2 VFS probe should launch through the organizer backend inside the sandbox"

    Wait-ForPath -Path $probeLaunchStatePath -TimeoutSeconds $TimeoutSeconds
    Wait-ForPath -Path $probeResultPath -TimeoutSeconds $TimeoutSeconds

    $probeLaunchState = Get-Content -Path $probeLaunchStatePath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    $probePayload = Get-Content -Path $probeResultPath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop

    Assert-True -Condition ([string]$probeLaunchState.status -eq 'spawned') -Message "real MO2 VFS probe should write a launcher-facing state file"
    Assert-True -Condition ([int]$probeLaunchState.pid -gt 0) -Message "real MO2 VFS probe state file should preserve a positive process id"
    Assert-True -Condition ($probeLaunchState.session_id -eq $probeSessionId) -Message "real MO2 VFS probe state file should preserve the session id"
    Assert-True -Condition ($probePayload.path -eq $probeVisiblePath) -Message "probe should echo the requested sandbox path"
    Assert-True -Condition ([bool]$probePayload.visible) -Message "probe should report CraftingTools.esp visible at the game Data path inside the MO2 sandbox"
    Assert-True -Condition ($probePayload.plugins_txt_path -eq $expectedPluginsPath) -Message "probe should inspect %LOCALAPPDATA%\Fallout4\plugins.txt from the launched process context"
    Assert-True -Condition ([bool]$probePayload.plugins_txt_visible) -Message "probe should report %LOCALAPPDATA%\Fallout4\plugins.txt visible inside the MO2 sandbox"
    $expectedEntries = @('*ArmorKeywords.esm', '*CraftingTools.esp', '*RaiderOverhaul.esp')
    foreach ($entry in $expectedEntries) {
        Assert-True -Condition ($probePayload.plugins_txt_entries -contains $entry) -Message "probe should report profile-local plugins.txt entry $entry inside the MO2 sandbox"
    }

    if ($XeditLoadAll) {
        foreach ($requiredPath in @($xeditCliPath, $realXeditLauncherPath)) {
            if (-not (Test-Path $requiredPath -PathType Leaf)) {
                throw "Missing required xEdit launch path: $requiredPath"
            }
        }

        $cliLaunch = Invoke-Cli -Arguments @(
            'process',
            'launch',
            '--launcher-path',
            $realXeditLauncherPath,
            '--game-mode',
            'Fallout4',
            '--load-mode',
            'all',
            '--mo-profile',
            $profileName
        )
        $cliOutputPath = Join-Path $tempRoot 'xedit-cli-launch-response.txt'
        Set-Content -Path $cliOutputPath -Value $cliLaunch.Output

        if ($cliLaunch.ExitCode -ne 0) {
            throw "xedit-cli process launch failed.`n$($cliLaunch.Output)"
        }

        $sessionPath = Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'hook-session-path'
        $requestFilePath = Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'mo2-launch-request-file'
        $responseFilePath = Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'mo2-launch-response-file'
        $launcherStatePath = Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'mo2-launch-state-file'
        $xeditLaunchId = Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'mo2-launch-id'
        $xeditPid = [int](Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'xedit-pid')
        $hookStatusPath = Join-Path $sessionPath 'hook-status.txt'

        Assert-True -Condition ($cliLaunch.Output -match [regex]::Escape('mo2-launch-backend: organizer')) -Message 'xEdit launch should report organizer backend under MO2 control plane'
        Assert-True -Condition (Test-Path $requestFilePath -PathType Leaf) -Message 'xEdit launch should persist the control-plane launch request artifact'
        Assert-True -Condition (Test-Path $responseFilePath -PathType Leaf) -Message 'xEdit launch should persist the control-plane launch response artifact'
        Assert-True -Condition ($xeditPid -gt 0) -Message 'xEdit launch should return a positive real xEdit pid'

        $launchResponse = Get-Content -Path $responseFilePath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
        Assert-True -Condition ([bool]$launchResponse.ok) -Message 'xEdit launch response artifact should preserve ok=true'
        Assert-True -Condition ([string]$launchResponse.result.launch_id -eq $xeditLaunchId) -Message 'xEdit launch response artifact should preserve the same launch id surfaced by the CLI'
        Assert-True -Condition ([string]$launchResponse.result.artifacts.backend -eq 'organizer') -Message 'xEdit launch response artifact should preserve organizer backend evidence'

        Wait-ForPath -Path $launcherStatePath -TimeoutSeconds $TimeoutSeconds
        $launcherState = Get-Content -Path $launcherStatePath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
        Assert-True -Condition ([string]$launcherState.status -eq 'spawned') -Message 'xEdit launch should write a spawned launcher state file'
        Assert-True -Condition ([int]$launcherState.pid -eq $xeditPid) -Message 'launcher state should preserve the real xEdit pid'

        $hookStatus = Wait-ForHookStatusSuccess -Path $hookStatusPath -TimeoutSeconds 120
        Assert-True -Condition ($hookStatus -match '(?m)^load_mode=all\s*$') -Message 'hook status should persist load_mode=all'
        Assert-True -Condition ($hookStatus -match '(?m)^selection_detected=true\s*$') -Message 'hook status should report Module Selection detection'
        Assert-True -Condition ($hookStatus -match '(?m)^selection_confirmed=true\s*$') -Message 'hook status should report automatic Module Selection confirmation'

        Write-Host "xedit-cli real MO2 sandbox load-all launch passed for profile $profileName."
        Write-Host "evidence-root: $tempRoot"
    }
    else {
        Write-Host "xedit-cli real MO2 sandbox direct probe passed for profile $profileName."
    }
}
finally {
    foreach ($launchId in @($probeLaunchId, $xeditLaunchId)) {
        if ([string]::IsNullOrWhiteSpace($launchId)) {
            continue
        }

        try {
            $stopResponse = Invoke-Mo2ControlPlaneClientRequest -LiveRoot $runtimeRoot -Request (New-Mo2ControlPlaneRequest -SessionId "cleanup-$launchId" -Command "launch.stop" -Payload @{ launch_id = $launchId })
            $null = $stopResponse
        }
        catch {
        }
    }

    foreach ($processId in @($probeLaunchPid, $xeditPid)) {
        if ($processId -gt 0) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }

    if ((Test-Path $tempRoot) -and -not $XeditLoadAll) {
        Remove-Item -Path $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }

    if ($null -ne $sandboxHarnessMutex) {
        $sandboxHarnessMutex.ReleaseMutex()
        $sandboxHarnessMutex.Dispose()
    }
}

exit 0

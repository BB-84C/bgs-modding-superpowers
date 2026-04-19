param(
    [switch]$AllowLiveSandbox,
    [switch]$EnsureBridge,
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
$xeditCliPath = Join-Path $repoRoot "tools/xedit-cli/bin/xedit-cli.ps1"
$realXeditLauncherPath = Join-Path $liveMo2Root "Stock Game\Fallout 4\Tools\FO4Edit\FO4Edit.exe"
$bridgeDllPath = Join-Path $repoRoot "tools/xedit-hook-bridge/src/xEditHookBridge.dll"
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

function Assert-Equal {
    param(
        $Actual,
        $Expected,
        [string]$Message
    )

    if ($Actual -ne $Expected) {
        throw "$Message`nExpected: $Expected`nActual: $Actual"
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

function Get-StatusValue {
    param(
        [string]$Content,
        [string]$Key
    )

    if ($Content -notmatch ("(?m)^" + [regex]::Escape($Key) + "=(.*)$")) {
        throw "Missing status key: $Key`nActual status:`n$Content"
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

function Read-NormalizedPluginLines {
    param(
        [string]$Path
    )

    return @(
        Get-Content -Path $Path |
            ForEach-Object { ([string]$_).Trim() } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            Where-Object { -not $_.StartsWith('#') }
    )
}

function Get-SelectedModulesList {
    param(
        [string]$SelectedModulesValue
    )

    if ([string]::IsNullOrWhiteSpace($SelectedModulesValue)) {
        return @()
    }

    return @($SelectedModulesValue -split '\|' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

function Stop-LiveScenario {
    param(
        [pscustomobject]$Scenario
    )

    if ($null -eq $Scenario) {
        return
    }

    if (-not [string]::IsNullOrWhiteSpace([string]$Scenario.LaunchId)) {
        try {
            $stopResponse = Invoke-Mo2ControlPlaneClientRequest -LiveRoot $runtimeRoot -Request (New-Mo2ControlPlaneRequest -SessionId ("cleanup-" + $Scenario.LaunchId) -Command "launch.stop" -Payload @{ launch_id = $Scenario.LaunchId })
            $null = $stopResponse
        }
        catch {
        }
    }

    if (($Scenario.Pid -as [int]) -gt 0) {
        Stop-Process -Id ([int]$Scenario.Pid) -Force -ErrorAction SilentlyContinue
    }
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

function Write-JsonArtifact {
    param(
        [string]$Path,
        [object]$Value
    )

    $json = $Value | ConvertTo-Json -Depth 10
    Set-Content -LiteralPath $Path -Value $json
}

function Invoke-SessionPluginsScenario {
    param(
        [string]$TempRoot,
        [string]$ScenarioName,
        [string[]]$PluginLines
    )

    $scenarioRoot = Join-Path $TempRoot $ScenarioName
    $null = New-Item -ItemType Directory -Path $scenarioRoot -Force
    $requestedPluginsPath = Join-Path $scenarioRoot 'requested-plugins.txt'
    $cliOutputPath = Join-Path $scenarioRoot 'xedit-cli-launch-response.txt'
    $hookStatusCopyPath = Join-Path $scenarioRoot 'hook-status.txt'
    $launchId = $null
    $xeditPid = 0
    Set-Content -Path $requestedPluginsPath -Value $PluginLines

    try {
        $cliLaunch = Invoke-Cli -Arguments @(
            'process',
            'launch',
            '--launcher-path',
            $realXeditLauncherPath,
            '--game-mode',
            'Fallout4',
            '--plugins-file',
            $requestedPluginsPath,
            '--mo-profile',
            $profileName
        )
        Set-Content -Path $cliOutputPath -Value $cliLaunch.Output

        if ($cliLaunch.ExitCode -ne 0) {
            throw "xedit-cli process launch failed for scenario '$ScenarioName'.`n$($cliLaunch.Output)"
        }

        $sessionPath = Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'hook-session-path'
        $requestFilePath = Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'mo2-launch-request-file'
        $responseFilePath = Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'mo2-launch-response-file'
        $launcherStatePath = Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'mo2-launch-state-file'
        $launchId = Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'mo2-launch-id'
        $xeditPid = [int](Get-RequiredOutputValue -Output $cliLaunch.Output -FieldName 'xedit-pid')
        $sessionPluginsPath = Join-Path $sessionPath 'plugins.txt'
        $hookStatusPath = Join-Path $sessionPath 'hook-status.txt'
        $expectedSessionPluginsArgument = '-P:' + $sessionPluginsPath

        Assert-True -Condition (Test-Path $sessionPath -PathType Container) -Message "$ScenarioName should create a hook session directory"
        Assert-True -Condition (Test-Path $sessionPluginsPath -PathType Leaf) -Message "$ScenarioName should write a session plugins.txt"
        Assert-True -Condition ($requestedPluginsPath -ne $sessionPluginsPath) -Message "$ScenarioName should copy plugins into a session-scoped plugins.txt"
        Assert-True -Condition ($cliLaunch.Output -match [regex]::Escape('mo2-launch-runner: OpenCodeVfsLauncher')) -Message "$ScenarioName should target the OpenCodeVfsLauncher runner"
        Assert-True -Condition ($cliLaunch.Output -match [regex]::Escape('mo2-launch-backend: organizer')) -Message "$ScenarioName should report organizer backend under MO2 control plane"
        Assert-True -Condition (Test-Path $requestFilePath -PathType Leaf) -Message "$ScenarioName should persist the control-plane launch request artifact"
        Assert-True -Condition (Test-Path $responseFilePath -PathType Leaf) -Message "$ScenarioName should persist the control-plane launch response artifact"
        Assert-True -Condition ($xeditPid -gt 0) -Message "$ScenarioName should return a positive real xEdit pid"

        $requestedPluginLines = Read-NormalizedPluginLines -Path $requestedPluginsPath
        $sessionPluginLines = Read-NormalizedPluginLines -Path $sessionPluginsPath
        Assert-Equal -Actual ($sessionPluginLines -join '|') -Expected ($requestedPluginLines -join '|') -Message "$ScenarioName should preserve the requested plugin file contents in the session plugins file"

        $launchRequest = Get-Content -Path $requestFilePath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
        $launchResponse = Get-Content -Path $responseFilePath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop

        Assert-Equal -Actual ([string]$launchRequest.profile) -Expected $profileName -Message "$ScenarioName launch request should preserve the MO2 profile"
        Assert-Equal -Actual ([string]$launchRequest.runner) -Expected 'OpenCodeVfsLauncher' -Message "$ScenarioName launch request should target OpenCodeVfsLauncher"
        Assert-True -Condition (@($launchRequest.request.payload.target.args) -contains $expectedSessionPluginsArgument) -Message "$ScenarioName launch request should launch xEdit with the session plugins path through -P:"
        Assert-True -Condition (-not (@($launchRequest.request.payload.target.args) -contains ('-P:' + $requestedPluginsPath))) -Message "$ScenarioName launch request should not pass the caller plugin file path directly to xEdit"
        Assert-True -Condition ([bool]$launchResponse.ok) -Message "$ScenarioName launch response artifact should preserve ok=true"
        Assert-Equal -Actual ([string]$launchResponse.result.launch_id) -Expected $launchId -Message "$ScenarioName launch response artifact should preserve the surfaced launch id"
        Assert-Equal -Actual ([string]$launchResponse.result.artifacts.backend) -Expected 'organizer' -Message "$ScenarioName launch response artifact should preserve organizer backend evidence"

        Wait-ForPath -Path $launcherStatePath -TimeoutSeconds $TimeoutSeconds
        $launcherState = Get-Content -Path $launcherStatePath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
        Assert-Equal -Actual ([string]$launcherState.status) -Expected 'spawned' -Message "$ScenarioName should write a spawned launcher state file"
        Assert-Equal -Actual ([int]$launcherState.pid) -Expected $xeditPid -Message "$ScenarioName launcher state should preserve the real xEdit pid"

        $hookStatus = Wait-ForHookStatusSuccess -Path $hookStatusPath -TimeoutSeconds 120
        Set-Content -Path $hookStatusCopyPath -Value $hookStatus
        $selectedModules = Get-SelectedModulesList -SelectedModulesValue (Get-StatusValue -Content $hookStatus -Key 'selected_modules')

        Assert-True -Condition ($hookStatus -match '(?m)^status=module-selection-confirmed\s*$') -Message "$ScenarioName hook status should reach the module-selection-confirmed terminal state"
        Assert-True -Condition ($hookStatus -match '(?m)^selection_detected=true\s*$') -Message "$ScenarioName hook status should report Module Selection detection"
        Assert-True -Condition ($hookStatus -match '(?m)^selection_confirmed=true\s*$') -Message "$ScenarioName hook status should report automatic Module Selection confirmation"
        Assert-True -Condition ($hookStatus -match '(?m)^detail=.*Module Selection.*\s*$') -Message "$ScenarioName hook status should retain Module Selection checkpoint detail"
        Assert-True -Condition ($hookStatus -notmatch '(?m)^load_mode=') -Message "$ScenarioName hook status should not expose retired load_mode metadata"
        Assert-True -Condition ($hookStatus -notmatch '(?m)^plugins=') -Message "$ScenarioName hook status should not expose retired plugins metadata"
        Assert-True -Condition ($hookStatus -notmatch '(?m)^selection_method=') -Message "$ScenarioName hook status should not expose retired selection_method metadata"
        Assert-True -Condition ($hookStatus -notmatch '(?m)^forced_dependencies=') -Message "$ScenarioName hook status should not expose retired forced_dependencies metadata"
        Assert-True -Condition ($hookStatus -notmatch '(?m)^blocked_exclusions=') -Message "$ScenarioName hook status should not expose retired blocked_exclusions metadata"

        foreach ($pluginLine in $sessionPluginLines) {
            $pluginName = $pluginLine.TrimStart('*')
            Assert-True -Condition ($selectedModules -contains $pluginName) -Message "$ScenarioName selected modules should include $pluginName from the session plugins file"
        }

        return [pscustomobject]@{
            ScenarioName = $ScenarioName
            RequestedPluginsPath = $requestedPluginsPath
            RequestedPluginLines = $requestedPluginLines
            CliOutputPath = $cliOutputPath
            CliOutput = $cliLaunch.Output
            SessionPath = $sessionPath
            SessionPluginsPath = $sessionPluginsPath
            SessionPluginLines = $sessionPluginLines
            RequestFilePath = $requestFilePath
            ResponseFilePath = $responseFilePath
            LauncherStatePath = $launcherStatePath
            HookStatusPath = $hookStatusPath
            HookStatusCopyPath = $hookStatusCopyPath
            HookStatus = $hookStatus
            SelectedModules = $selectedModules
            LaunchId = $launchId
            Pid = $xeditPid
            LaunchRequest = $launchRequest
            LaunchResponse = $launchResponse
            LauncherState = $launcherState
        }
    }
    catch {
        Stop-LiveScenario -Scenario ([pscustomobject]@{
            LaunchId = $launchId
            Pid = $xeditPid
        })
        throw
    }
}

if (-not $AllowLiveSandbox) {
    throw "This real harness touches D:\awesome-bgs-mod-master\.artifacts\mo2. Re-run with -AllowLiveSandbox to opt in."
}

foreach ($requiredPath in @($liveMo2Root, $mo2ExecutablePath, $modOrganizerIniPath, $xeditCliPath, $realXeditLauncherPath, $bridgeDllPath)) {
    if (-not (Test-Path $requiredPath)) {
        throw "Missing required path: $requiredPath"
    }
}

if ($EnsureBridge -and -not (Test-Path $deployScriptPath -PathType Leaf)) {
    throw "Missing live bridge deploy helper: $deployScriptPath"
}

$modOrganizerIni = Get-Content -Path $modOrganizerIniPath -Raw
if ($modOrganizerIni -notmatch [regex]::Escape("selected_profile=@ByteArray($profileName)")) {
    throw "The project-local MO2 sandbox must be configured to use profile $profileName before this real probe runs."
}

$sandboxHarnessMutex = Enter-SandboxHarnessLock -Path $mo2ExecutablePath -TimeoutSeconds $TimeoutSeconds
$tempRoot = Join-Path $env:TEMP ("xedit-cli-mo2-sandbox-session-plugins-real-" + [guid]::NewGuid().ToString("N"))
$scenario = $null

try {
    $null = New-Item -ItemType Directory -Path $tempRoot -Force

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

    $scenario = Invoke-SessionPluginsScenario -TempRoot $tempRoot -ScenarioName 'session-plugin-load-set' -PluginLines @(
        '*ArmorKeywords.esm',
        '*CraftingTools.esp',
        '*RaiderOverhaul.esp'
    )

    $evidencePath = Join-Path $tempRoot 'session-plugins-evidence.json'
    Write-JsonArtifact -Path $evidencePath -Value ([ordered]@{
        harness = 'mo2-sandbox-model-selection-real'
        evidence_root = $tempRoot
        scenario = [ordered]@{
            name = $scenario.ScenarioName
            requested_plugins_path = $scenario.RequestedPluginsPath
            requested_plugin_lines = $scenario.RequestedPluginLines
            cli_output_path = $scenario.CliOutputPath
            session_path = $scenario.SessionPath
            session_plugins_path = $scenario.SessionPluginsPath
            session_plugin_lines = $scenario.SessionPluginLines
            request_file_path = $scenario.RequestFilePath
            response_file_path = $scenario.ResponseFilePath
            state_file_path = $scenario.LauncherStatePath
            hook_status_path = $scenario.HookStatusPath
            launch_id = $scenario.LaunchId
            pid = $scenario.Pid
            selected_modules = $scenario.SelectedModules
        }
    })

    Write-Host "xedit-cli real MO2 sandbox session-plugins launch passed for profile $profileName."
    Write-Host "evidence-root: $tempRoot"
}
finally {
    Stop-LiveScenario -Scenario $scenario

    if ($null -ne $sandboxHarnessMutex) {
        $sandboxHarnessMutex.ReleaseMutex()
        $sandboxHarnessMutex.Dispose()
    }
}

exit 0

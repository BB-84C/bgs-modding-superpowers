function Get-XeditCliWorktreeRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
}

function Get-XeditCliProjectRoot {
    $worktreeRoot = Get-XeditCliWorktreeRoot
    $parent = Split-Path -Path $worktreeRoot -Parent
    if ((Split-Path -Path $parent -Leaf) -eq ".worktrees") {
        return Split-Path -Path $parent -Parent
    }

    return $worktreeRoot
}

function Get-XeditCliDefaultMo2SandboxRoot {
    $repoRoot = Get-XeditCliProjectRoot
    return Join-Path $repoRoot ".artifacts\mo2"
}

function Get-XeditCliMo2LaunchStateFilePath {
    param(
        [pscustomobject]$HookSession
    )

    return Join-Path $HookSession.SessionPath "mo2-launch-state.json"
}

function Get-XeditCliMo2LaunchRequestFilePath {
    param(
        [pscustomobject]$HookSession
    )

    return Join-Path $HookSession.SessionPath "mo2-launch-request.json"
}

function Get-XeditCliMo2LaunchResponseFilePath {
    param(
        [pscustomobject]$HookSession
    )

    return Join-Path $HookSession.SessionPath "mo2-launch-response.json"
}

function Get-XeditCliMo2LaunchWrapperFilePath {
    param(
        [pscustomobject]$HookSession
    )

    return Join-Path $HookSession.SessionPath "mo2-launch-wrapper.ps1"
}

function Get-XeditCliMo2VfsLauncherPath {
    return Join-Path (Get-XeditCliWorktreeRoot) "tools\mo2-vfs-launcher\mo2-vfs-launcher.cmd"
}

function Get-XeditCliMo2VfsLauncherScriptPath {
    return Join-Path (Get-XeditCliWorktreeRoot) "tools\mo2-vfs-launcher\mo2-vfs-launcher.ps1"
}

function Get-XeditCliPwshPath {
    $pwshCommand = Get-Command pwsh -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $pwshCommand -or [string]::IsNullOrWhiteSpace([string]$pwshCommand.Source)) {
        throw "Unable to resolve pwsh for MO2 VFS launcher transport"
    }

    return [string]$pwshCommand.Source
}

function ConvertTo-XeditCliPowerShellSingleQuotedLiteral {
    param(
        [string]$Value
    )

    return "'" + ($Value -replace "'", "''") + "'"
}

$script:XeditCliMo2BrokerCommonPath = Join-Path (Get-XeditCliWorktreeRoot) "tools\mo2-control-plane\broker\lib\common.ps1"
$script:XeditCliMo2BrokerProtocolPath = Join-Path (Get-XeditCliWorktreeRoot) "tools\mo2-control-plane\broker\lib\protocol.ps1"
$script:XeditCliMo2BrokerSessionPath = Join-Path (Get-XeditCliWorktreeRoot) "tools\mo2-control-plane\broker\lib\session.ps1"
$script:XeditCliMo2BrokerLaunchPath = Join-Path (Get-XeditCliWorktreeRoot) "tools\mo2-control-plane\broker\lib\launch.ps1"
$script:XeditCliMo2BrokerIpcClientPath = Join-Path (Get-XeditCliWorktreeRoot) "tools\mo2-control-plane\broker\lib\ipc-client.ps1"
$script:XeditCliMo2BrokerLiveBootstrapPath = Join-Path (Get-XeditCliWorktreeRoot) "tools\mo2-control-plane\broker\lib\live-bootstrap.ps1"
$script:XeditCliMo2BrokerClientPath = Join-Path (Get-XeditCliWorktreeRoot) "tools\mo2-control-plane\broker\lib\client.ps1"

$script:XeditCliMo2BrokerLibPaths = @(
    $script:XeditCliMo2BrokerCommonPath,
    $script:XeditCliMo2BrokerProtocolPath,
    $script:XeditCliMo2BrokerSessionPath,
    $script:XeditCliMo2BrokerLaunchPath,
    $script:XeditCliMo2BrokerIpcClientPath,
    $script:XeditCliMo2BrokerLiveBootstrapPath,
    $script:XeditCliMo2BrokerClientPath
)

if ((@($script:XeditCliMo2BrokerLibPaths | Where-Object { Test-Path $_ -PathType Leaf })).Count -eq $script:XeditCliMo2BrokerLibPaths.Count) {
    foreach ($brokerLibPath in $script:XeditCliMo2BrokerLibPaths) {
        . $brokerLibPath
    }
}

function Get-XeditCliMo2LiveRuntimeRoot {
    param(
        [string]$SandboxRoot
    )

    return Join-Path $SandboxRoot "plugins\Mo2AgentControl\bootstrap\runtime"
}

function New-XeditCliMo2TransportArguments {
    param(
        [string]$LauncherScriptPath,
        [string]$TargetPath,
        [string[]]$TargetArguments,
        [pscustomobject]$HookSession
    )

    $arguments = @(
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        $LauncherScriptPath,
        '--target-path',
        $TargetPath,
        '--session-id',
        $HookSession.SessionId,
        '--state-file',
        (Get-XeditCliMo2LaunchStateFilePath -HookSession $HookSession),
        '--wait-mode',
        'spawned',
        '--transport-mode',
        'direct-child'
    )

    foreach ($targetArgument in $TargetArguments) {
        $arguments += @('--target-arg', [string]$targetArgument)
    }

    foreach ($entry in $HookSession.EnvironmentVariables.GetEnumerator()) {
        $arguments += @('--env', ('{0}={1}' -f [string]$entry.Key, [string]$entry.Value))
    }

    return $arguments
}

function Write-XeditCliMo2LaunchWrapperScript {
    param(
        [string]$LauncherScriptPath,
        [string[]]$LauncherArguments,
        [pscustomobject]$HookSession
    )

    $wrapperPath = Get-XeditCliMo2LaunchWrapperFilePath -HookSession $HookSession
    $wrapperLines = @(
        '$ErrorActionPreference = "Stop"',
        '$launcherArgs = @('
    )

    foreach ($launcherArgument in $LauncherArguments) {
        $wrapperLines += ('    ' + (ConvertTo-XeditCliPowerShellSingleQuotedLiteral -Value ([string]$launcherArgument)))
    }

    $wrapperLines += @(
        ')',
        ('& ' + (ConvertTo-XeditCliPowerShellSingleQuotedLiteral -Value $LauncherScriptPath) + ' @launcherArgs'),
        'exit $LASTEXITCODE'
    )

    Set-Content -Path $wrapperPath -Value ($wrapperLines -join [Environment]::NewLine)
    return $wrapperPath
}

function Wait-XeditCliMo2ArtifactFile {
    param(
        [string]$Path,
        [int]$TimeoutSeconds = 15,
        [int]$PollIntervalMilliseconds = 200
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $Path -PathType Leaf) {
            return
        }

        Start-Sleep -Milliseconds $PollIntervalMilliseconds
    }

    throw "Timed out waiting for MO2 launch artifact: $Path"
}

function Invoke-XeditCliMo2LaunchStart {
    param(
        [hashtable]$LaunchRequest
    )

    if (-not (Get-Command Invoke-Mo2ControlPlaneClientRequest -ErrorAction SilentlyContinue)) {
        throw "MO2 control-plane client functions are unavailable"
    }

    $runtimeRoot = Get-XeditCliMo2LiveRuntimeRoot -SandboxRoot ([string]$LaunchRequest.sandbox_root)
    $response = Invoke-Mo2ControlPlaneClientRequest -Request $LaunchRequest.request -LiveRoot $runtimeRoot
    if (-not $response.ok) {
        throw "MO2 control-plane launch.start failed: $($response.error.message)"
    }

    $stateFile = [string]$LaunchRequest.artifacts.state_file
    Wait-XeditCliMo2ArtifactFile -Path $stateFile
    $state = Get-Content -Path $stateFile -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop

    return [pscustomobject]@{
        RuntimeRoot = $runtimeRoot
        Response = $response
        State = $state
    }
}

function Write-XeditCliMo2LaunchResponseArtifact {
    param(
        [hashtable]$LaunchRequest,
        [object]$LaunchResponse
    )

    $responseFile = [string]$LaunchRequest.artifacts.response_file
    if ([string]::IsNullOrWhiteSpace($responseFile)) {
        return
    }

    $parent = Split-Path -Path $responseFile -Parent
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path $parent)) {
        $null = New-Item -ItemType Directory -Path $parent -Force
    }

    $LaunchResponse | ConvertTo-Json -Depth 20 | Set-Content -Path $responseFile
}

function New-XeditCliMo2LaunchRequest {
    param(
        [string]$Profile,
        [string]$SandboxRoot,
        [string]$TargetPath,
        [string[]]$TargetArguments,
        [string]$TargetWorkingDirectory,
        [pscustomobject]$HookSession
    )

    $resolvedSandboxRoot = if ([string]::IsNullOrWhiteSpace($SandboxRoot)) {
        Get-XeditCliDefaultMo2SandboxRoot
    }
    else {
        $SandboxRoot
    }

    $stateFile = Get-XeditCliMo2LaunchStateFilePath -HookSession $HookSession
    $resolvedTargetArguments = @($TargetArguments)
    $sessionPluginsArgument = '-P:' + $HookSession.SessionPluginsFilePath
    if ($resolvedTargetArguments -notcontains $sessionPluginsArgument) {
        $resolvedTargetArguments += $sessionPluginsArgument
    }
    $launcherPath = Get-XeditCliPwshPath
    $launcherScriptPath = Get-XeditCliMo2VfsLauncherScriptPath
    $transportRunnerArguments = @(New-XeditCliMo2TransportArguments -LauncherScriptPath $launcherScriptPath -TargetPath $TargetPath -TargetArguments $resolvedTargetArguments -HookSession $HookSession)
    $transportWrapperPath = Write-XeditCliMo2LaunchWrapperScript -LauncherScriptPath $launcherScriptPath -LauncherArguments $transportRunnerArguments[5..($transportRunnerArguments.Count - 1)] -HookSession $HookSession
    $transportArguments = @(
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        $transportWrapperPath
    )

    $payload = [ordered]@{
        profile = $Profile
        runner = "OpenCodeVfsLauncher"
        target = [ordered]@{
            path = $TargetPath
            args = @($resolvedTargetArguments)
            cwd = $TargetWorkingDirectory
            env = [ordered]@{} + $HookSession.EnvironmentVariables
        }
        sandbox = [ordered]@{
            root = $resolvedSandboxRoot
        }
        state = [ordered]@{
            file = $stateFile
        }
        session = [ordered]@{
            id = $HookSession.SessionId
            path = $HookSession.SessionPath
        }
        transport = [ordered]@{
            target_path = $launcherPath
            args = $transportArguments
            cwd = (Split-Path -Path $launcherScriptPath -Parent)
            env = [ordered]@{}
        }
    }

    $request = if (Get-Command New-Mo2ControlPlaneRequest -ErrorAction SilentlyContinue) {
        New-Mo2ControlPlaneRequest -SessionId $HookSession.SessionId -Command "launch.start" -Payload $payload
    }
    else {
        [ordered]@{
            protocol_version = "1"
            request_id = "req-" + [guid]::NewGuid().ToString("N")
            session_id = $HookSession.SessionId
            command = "launch.start"
            payload = $payload
        }
    }

    return [ordered]@{
        profile = $Profile
        sandbox_root = $resolvedSandboxRoot
        runner = "OpenCodeVfsLauncher"
        target = $payload.target
        artifacts = [ordered]@{
            state_file = $stateFile
            request_file = (Get-XeditCliMo2LaunchRequestFilePath -HookSession $HookSession)
            response_file = (Get-XeditCliMo2LaunchResponseFilePath -HookSession $HookSession)
            wrapper_file = $transportWrapperPath
        }
        request = $request
    }
}

function Write-XeditCliMo2LaunchRequestArtifact {
    param(
        [hashtable]$LaunchRequest
    )

    $requestFile = [string]$LaunchRequest.artifacts.request_file
    if ([string]::IsNullOrWhiteSpace($requestFile)) {
        return
    }

    $parent = Split-Path -Path $requestFile -Parent
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path $parent)) {
        $null = New-Item -ItemType Directory -Path $parent -Force
    }

    $LaunchRequest | ConvertTo-Json -Depth 10 | Set-Content -Path $requestFile
}

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir 'xedit-client.common.ps1')
. (Join-Path $scriptDir 'xedit-client.session.ps1')
. (Join-Path $scriptDir 'xedit-client.call.ps1')

function Get-XeditClientWorktreeRoot { return (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path }

function Get-XeditClientProjectRoot {
    $worktreeRoot = Get-XeditClientWorktreeRoot
    $parent = Split-Path -Path $worktreeRoot -Parent
    if ((Split-Path -Path $parent -Leaf) -eq '.worktrees') { return Split-Path -Path $parent -Parent }
    return $worktreeRoot
}

function Get-XeditClientDefaultMo2SandboxRoot {
    # Resolution priority for the MO2 root the launcher should drive:
    #   1. $env:BGS_MO2_ROOT  — end-user install path (set by the harness MCP
    #      server config, or by the setting-up-bgs-modding-environment skill
    #      once MO2 is detected).
    #   2. <project-root>\.artifacts\mo2  — dev sandbox; only used when it
    #      actually exists. End-user clones do not carry this tree.
    # If neither resolves, callers see an empty string and surface a clear
    # error rather than silently constructing a wrong sandbox path under the
    # plugin install location.
    $envRoot = [System.Environment]::GetEnvironmentVariable('BGS_MO2_ROOT')
    if (-not [string]::IsNullOrWhiteSpace($envRoot)) { return $envRoot }
    $devRoot = Join-Path (Get-XeditClientProjectRoot) '.artifacts\mo2'
    if (Test-Path -LiteralPath $devRoot -PathType Container) { return $devRoot }
    return ''
}
function Get-XeditClientMo2LaunchStateFilePath { param([pscustomobject]$Session) return Join-Path $Session.SessionPath 'mo2-launch-state.json' }
function Get-XeditClientMo2LaunchRequestFilePath { param([pscustomobject]$Session) return Join-Path $Session.SessionPath 'mo2-launch-request.json' }
function Get-XeditClientMo2LaunchResponseFilePath { param([pscustomobject]$Session) return Join-Path $Session.SessionPath 'mo2-launch-response.json' }
function Get-XeditClientMo2LaunchWrapperFilePath { param([pscustomobject]$Session) return Join-Path $Session.SessionPath 'mo2-launch-wrapper.ps1' }
function Get-XeditClientMo2VfsLauncherScriptPath { return Join-Path (Get-XeditClientWorktreeRoot) 'tools\mo2-vfs-launcher\mo2-vfs-launcher.ps1' }

function Get-XeditClientPwshPath {
    $pwshCommand = Get-Command pwsh -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $pwshCommand -or [string]::IsNullOrWhiteSpace([string]$pwshCommand.Source)) { throw 'Unable to resolve pwsh for MO2 VFS launcher transport' }
    return [string]$pwshCommand.Source
}

function ConvertTo-XeditClientPowerShellSingleQuotedLiteral { param([string]$Value) return "'" + ($Value -replace "'", "''") + "'" }

function ConvertTo-XeditClientNativeWindowsPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $Path }
    return ($Path -replace '/', '\')
}

function ConvertTo-XeditClientFlatStringArray {
    param([object[]]$Values)

    $flatValues = @()
    foreach ($value in @($Values)) {
        if ($null -eq $value) { continue }
        if ($value -is [string]) {
            $flatValues += [string]$value
            continue
        }
        if ($value -is [System.Collections.IEnumerable]) {
            $flatValues += ConvertTo-XeditClientFlatStringArray -Values @($value)
            continue
        }
        $flatValues += [string]$value
    }

    return $flatValues
}

$script:XeditClientMo2BrokerLibPaths = @(
    (Join-Path (Get-XeditClientWorktreeRoot) 'tools\mo2-control-plane\broker\lib\common.ps1'),
    (Join-Path (Get-XeditClientWorktreeRoot) 'tools\mo2-control-plane\broker\lib\protocol.ps1'),
    (Join-Path (Get-XeditClientWorktreeRoot) 'tools\mo2-control-plane\broker\lib\session.ps1'),
    (Join-Path (Get-XeditClientWorktreeRoot) 'tools\mo2-control-plane\broker\lib\launch.ps1'),
    (Join-Path (Get-XeditClientWorktreeRoot) 'tools\mo2-control-plane\broker\lib\ipc-client.ps1'),
    (Join-Path (Get-XeditClientWorktreeRoot) 'tools\mo2-control-plane\broker\lib\live-bootstrap.ps1'),
    (Join-Path (Get-XeditClientWorktreeRoot) 'tools\mo2-control-plane\broker\lib\client.ps1')
)
if ((@($script:XeditClientMo2BrokerLibPaths | Where-Object { Test-Path $_ -PathType Leaf })).Count -eq $script:XeditClientMo2BrokerLibPaths.Count) {
    foreach ($brokerLibPath in $script:XeditClientMo2BrokerLibPaths) { . $brokerLibPath }
}

function Get-XeditClientMo2LiveRuntimeRoot { param([string]$SandboxRoot) return Join-Path $SandboxRoot 'plugins\Mo2AgentControl\bootstrap\runtime' }

function New-XeditClientMo2TransportArguments {
    param([string]$LauncherScriptPath, [string]$TargetPath, [string[]]$TargetArguments, [pscustomobject]$Session)

    $arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $LauncherScriptPath, '--target-path', $TargetPath, '--session-id', $Session.SessionId, '--state-file', (Get-XeditClientMo2LaunchStateFilePath -Session $Session), '--wait-mode', 'spawned', '--transport-mode', 'direct-child')
    foreach ($targetArgument in (ConvertTo-XeditClientFlatStringArray -Values @($TargetArguments))) { $arguments += @('--target-arg', [string]$targetArgument) }
    foreach ($entry in $Session.EnvironmentVariables.GetEnumerator()) { $arguments += @('--env', ('{0}={1}' -f [string]$entry.Key, [string]$entry.Value)) }
    return $arguments
}

function Write-XeditClientMo2LaunchWrapperScript {
    param([string]$LauncherScriptPath, [string[]]$LauncherArguments, [pscustomobject]$Session)

    $wrapperPath = Get-XeditClientMo2LaunchWrapperFilePath -Session $Session
    $wrapperLines = @('$ErrorActionPreference = "Stop"', '$launcherArgs = @(')
    foreach ($launcherArgument in $LauncherArguments) { $wrapperLines += ('    ' + (ConvertTo-XeditClientPowerShellSingleQuotedLiteral -Value ([string]$launcherArgument))) }
    $wrapperLines += @(')', ('& ' + (ConvertTo-XeditClientPowerShellSingleQuotedLiteral -Value $LauncherScriptPath) + ' @launcherArgs'), 'exit $LASTEXITCODE')
    Set-Content -Path $wrapperPath -Value ($wrapperLines -join [Environment]::NewLine)
    return $wrapperPath
}

function New-XeditClientMo2LaunchRequest {
    param([string]$Profile, [string]$SandboxRoot, [string]$TargetPath, [string[]]$TargetArguments, [string]$TargetWorkingDirectory, [pscustomobject]$Session)

    $resolvedSandboxRoot = if ([string]::IsNullOrWhiteSpace($SandboxRoot)) { Get-XeditClientDefaultMo2SandboxRoot } else { $SandboxRoot }
    $stateFile = Get-XeditClientMo2LaunchStateFilePath -Session $Session
    $resolvedTargetArguments = @(ConvertTo-XeditClientFlatStringArray -Values @($TargetArguments))
    $sessionPluginsArgument = '-P:' + $Session.SessionPluginsFilePath
    if ($resolvedTargetArguments -notcontains '-automation-serve') { $resolvedTargetArguments += '-automation-serve' }
    if ($resolvedTargetArguments -notcontains $sessionPluginsArgument) { $resolvedTargetArguments += $sessionPluginsArgument }
    $resolvedTargetArguments = @($resolvedTargetArguments | Where-Object { $_ -notmatch '^-moprofile:' })

    $launcherPath = Get-XeditClientPwshPath
    $launcherScriptPath = Get-XeditClientMo2VfsLauncherScriptPath
    $transportRunnerArguments = @(New-XeditClientMo2TransportArguments -LauncherScriptPath $launcherScriptPath -TargetPath $TargetPath -TargetArguments $resolvedTargetArguments -Session $Session)
    $transportWrapperPath = Write-XeditClientMo2LaunchWrapperScript -LauncherScriptPath $launcherScriptPath -LauncherArguments $transportRunnerArguments[5..($transportRunnerArguments.Count - 1)] -Session $Session
    $transportArguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $transportWrapperPath)

    $payload = [ordered]@{
        profile = $Profile
        runner = 'OpenCodeVfsLauncher'
        target = [ordered]@{ path = $TargetPath; args = @($resolvedTargetArguments); cwd = $TargetWorkingDirectory; env = [ordered]@{} + $Session.EnvironmentVariables }
        sandbox = [ordered]@{ root = $resolvedSandboxRoot }
        state = [ordered]@{ file = $stateFile }
        session = [ordered]@{ id = $Session.SessionId; path = $Session.SessionPath }
        transport = [ordered]@{ target_path = $launcherPath; args = $transportArguments; cwd = (Split-Path -Path $launcherScriptPath -Parent); env = [ordered]@{} }
    }

    $request = if (Get-Command New-Mo2ControlPlaneRequest -ErrorAction SilentlyContinue) {
        New-Mo2ControlPlaneRequest -SessionId $Session.SessionId -Command 'launch.start' -Payload $payload
    }
    else {
        [ordered]@{ protocol_version = '1'; request_id = 'req-' + [guid]::NewGuid().ToString('N'); session_id = $Session.SessionId; command = 'launch.start'; payload = $payload }
    }

    return [ordered]@{
        profile = $Profile
        sandbox_root = $resolvedSandboxRoot
        runner = 'OpenCodeVfsLauncher'
        target = $payload.target
        artifacts = [ordered]@{ state_file = $stateFile; request_file = (Get-XeditClientMo2LaunchRequestFilePath -Session $Session); response_file = (Get-XeditClientMo2LaunchResponseFilePath -Session $Session); wrapper_file = $transportWrapperPath }
        request = $request
    }
}

function Write-XeditClientMo2LaunchRequestArtifact {
    param($LaunchRequest)
    $requestFile = [string]$LaunchRequest.artifacts.request_file
    if ([string]::IsNullOrWhiteSpace($requestFile)) { return }
    $parent = Split-Path -Path $requestFile -Parent
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path $parent)) { $null = New-Item -ItemType Directory -Path $parent -Force }
    $LaunchRequest | ConvertTo-Json -Depth 20 | Set-Content -Path $requestFile
}

function Write-XeditClientMo2LaunchResponseArtifact {
    param($LaunchRequest, [object]$LaunchResponse)
    $responseFile = [string]$LaunchRequest.artifacts.response_file
    if ([string]::IsNullOrWhiteSpace($responseFile)) { return }
    $parent = Split-Path -Path $responseFile -Parent
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path $parent)) { $null = New-Item -ItemType Directory -Path $parent -Force }
    $LaunchResponse | ConvertTo-Json -Depth 20 | Set-Content -Path $responseFile
}

function Wait-XeditClientMo2ArtifactFile {
    param([string]$Path, [int]$TimeoutSeconds = 15, [int]$PollIntervalMilliseconds = 200)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $Path -PathType Leaf) { return }
        Start-Sleep -Milliseconds $PollIntervalMilliseconds
    }
    throw "Timed out waiting for MO2 launch artifact: $Path"
}

function Invoke-XeditClientMo2LaunchStart {
    param($LaunchRequest)
    if (-not (Get-Command Invoke-Mo2ControlPlaneClientRequest -ErrorAction SilentlyContinue)) { throw 'MO2 control-plane client functions are unavailable' }
    $runtimeRoot = Get-XeditClientMo2LiveRuntimeRoot -SandboxRoot ([string]$LaunchRequest.sandbox_root)
    $response = Invoke-Mo2ControlPlaneClientRequest -Request $LaunchRequest.request -LiveRoot $runtimeRoot
    if (-not $response.ok) { throw "MO2 control-plane launch.start failed: $($response.error.message)" }
    $stateFile = [string]$LaunchRequest.artifacts.state_file
    Wait-XeditClientMo2ArtifactFile -Path $stateFile
    $state = Get-Content -Path $stateFile -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    return [pscustomobject]@{ RuntimeRoot = $runtimeRoot; Response = $response; State = $state }
}

function Get-XeditClientDescendantProcesses {
    param([int]$RootProcessId)
    $allProcesses = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $queue = [System.Collections.Generic.Queue[int]]::new()
    $queue.Enqueue($RootProcessId)
    $descendants = @()
    while ($queue.Count -gt 0) {
        $parentId = $queue.Dequeue()
        $children = @($allProcesses | Where-Object { $_.ParentProcessId -eq $parentId })
        foreach ($child in $children) { $descendants += $child; $queue.Enqueue([int]$child.ProcessId) }
    }
    return $descendants
}

function Get-XeditClientValidatedLiveProcess {
    param([string]$ProcessId)
    $parsedPid = ConvertTo-XeditClientProcessId -ProcessId $ProcessId
    if ($null -eq $parsedPid) { Write-Host "Invalid xEdit PID: $ProcessId"; return $null }
    $processInfo = Get-XeditClientProcessById -ProcessId $parsedPid
    if ($null -eq $processInfo) { Write-Host "xEdit PID is not running: $ProcessId"; return $null }
    if (-not (Test-XeditClientProcessLooksLikeXedit -Process $processInfo)) { Write-Host "Process is not an xEdit instance: $parsedPid"; return $null }
    return [pscustomobject]@{ ProcessId = $parsedPid; ProcessInfo = $processInfo; LiveProcess = (Get-Process -Id $parsedPid -ErrorAction SilentlyContinue) }
}

function Get-XeditClientNormalizedPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
    try { return (Get-Item -Path $Path -ErrorAction Stop).FullName } catch { return $Path }
}

function Get-XeditClientNewTargetProcesses {
    param([datetime]$StartedAt, [int[]]$KnownProcessIds, [string]$LauncherPath)
    $allProcesses = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $normalizedLauncherPath = Get-XeditClientNormalizedPath -Path $LauncherPath
    $matches = foreach ($process in $allProcesses) {
        if ($process.ProcessId -in $KnownProcessIds) { continue }
        if (-not (Test-XeditClientProcessLooksLikeXedit -Process $process)) { continue }
        if ([string]::IsNullOrWhiteSpace($process.ExecutablePath)) { continue }
        $normalizedExecutablePath = Get-XeditClientNormalizedPath -Path $process.ExecutablePath
        if ([string]::IsNullOrWhiteSpace($normalizedExecutablePath) -or -not $normalizedExecutablePath.Equals($normalizedLauncherPath, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
        try {
            $createdAt = if ($process.CreationDate -is [datetime]) { $process.CreationDate } else { [System.Management.ManagementDateTimeConverter]::ToDateTime($process.CreationDate) }
            if ($createdAt -lt $StartedAt.AddSeconds(-1)) { continue }
        } catch { continue }
        $process
    }
    return @($matches | Sort-Object CreationDate, ProcessId)
}

function Get-XeditClientLaunchedProcessId {
    param([System.Diagnostics.Process]$WrapperProcess, [string]$LauncherPath, [datetime]$StartedAt, [int[]]$KnownProcessIds)
    $deadline = (Get-Date).AddSeconds(5)
    do {
        $wrapperLive = Get-XeditClientProcessById -ProcessId $WrapperProcess.Id
        $descendants = @(Get-XeditClientDescendantProcesses -RootProcessId $WrapperProcess.Id)
        $newTargets = @(Get-XeditClientNewTargetProcesses -StartedAt $StartedAt -KnownProcessIds $KnownProcessIds -LauncherPath $LauncherPath)
        $preferredChild = $descendants | Where-Object { Test-XeditClientProcessLooksLikeXedit -Process $_ } | Select-Object -First 1
        if ($preferredChild) { return $preferredChild.ProcessId }
        if ($newTargets.Count -gt 0) { return $newTargets[-1].ProcessId }
        if ($wrapperLive -and (Test-XeditClientProcessLooksLikeXedit -Process $wrapperLive)) { return $WrapperProcess.Id }
        Start-Sleep -Milliseconds 200
    } while ((Get-Date) -lt $deadline)
    throw "Unable to determine launched process PID from launcher: $LauncherPath"
}

function Get-XeditClientRequiredOptionValues {
    param([hashtable]$Options, [string[]]$Names)
    $missing = @()
    foreach ($name in $Names) { if (-not $Options.ContainsKey($name)) { $missing += $name } }
    if ($missing.Count -gt 0) { Write-Host "Missing required options: $($missing -join ', ')"; return $null }
    return $Options
}

function Get-XeditClientValidatedMoProfile {
    param([hashtable]$Options)
    if (-not $Options.ContainsKey('--mo-profile')) { return $null }
    $profileName = [string]$Options['--mo-profile']
    if ([string]::IsNullOrWhiteSpace($profileName)) { Write-Host 'MO profile name must be non-empty'; return $false }
    $trimmedProfileName = $profileName.Trim()
    if ($trimmedProfileName -match '[\\/]' -or $trimmedProfileName -match '(^|[\\/])\.\.($|[\\/])' -or $trimmedProfileName -eq '..') { Write-Host 'MO profile name must not contain path separators or traversal'; return $false }
    return $trimmedProfileName
}

function ConvertFrom-XeditClientLauncherToken {
    param([string]$Token)
    if ([string]::IsNullOrWhiteSpace($Token)) { return $Token }
    $trimmed = $Token.Trim()
    if ($trimmed.Length -ge 2 -and $trimmed.StartsWith('"') -and $trimmed.EndsWith('"')) { return $trimmed.Substring(1, $trimmed.Length - 2) }
    return $trimmed
}

function Split-XeditClientLauncherCommandLine {
    param([string]$CommandLine)
    $matches = [regex]::Matches($CommandLine, '"[^"]*"|\S+')
    return @($matches | ForEach-Object { ConvertFrom-XeditClientLauncherToken -Token $_.Value })
}

function Get-XeditClientNormalizedLauncherCommand {
    param([string]$LauncherPath, [string]$GameModeArgument)

    $wrapperDirectory = Split-Path -Path $LauncherPath -Parent
    $extension = [System.IO.Path]::GetExtension($LauncherPath).ToLowerInvariant()
    if ($extension -eq '.exe') {
        if (-not (Test-XeditClientExecutablePathLooksLikeXedit -Path $LauncherPath)) { throw "Launcher executable is not xEdit-compatible: $LauncherPath" }
        return [pscustomobject]@{ FilePath = $LauncherPath; ArgumentList = @($GameModeArgument); NativeArgumentList = @($GameModeArgument); SourcePath = $LauncherPath; DetectionPath = $LauncherPath; WorkingDirectory = $wrapperDirectory }
    }

    $wrapperLines = @(Get-Content -Path $LauncherPath | ForEach-Object { $_.Trim() } | Where-Object { $_ -and $_ -notmatch '^(?i)@?echo\s+off$' -and $_ -notmatch '^(?i)rem\b' -and $_ -notmatch '^::' })
    if ($wrapperLines.Count -ne 1) { throw "Unsupported launcher wrapper shape: $LauncherPath" }
    $commandLine = $wrapperLines[0]
    if ($commandLine -match '(?i)(\&\&|\|\||[\|<>%!]|\bcall\b|\bstart\b|\bset\b)') { throw "Unsupported launcher wrapper shape: $LauncherPath" }
    $tokens = @(Split-XeditClientLauncherCommandLine -CommandLine $commandLine)
    if ($tokens.Count -lt 1) { throw "Unsupported launcher wrapper shape: $LauncherPath" }
    $modeArguments = @($tokens | Where-Object { Test-XeditClientGameModeArgument -Argument $_ })
    if ($modeArguments.Count -gt 0) { throw "Conflicting xEdit mode argument in launcher wrapper: $LauncherPath" }

    $resolvedFilePath = $tokens[0]
    if (-not [System.IO.Path]::IsPathRooted($resolvedFilePath)) { $resolvedFilePath = Join-Path $wrapperDirectory $resolvedFilePath }
    if ([System.IO.Path]::GetExtension($resolvedFilePath).ToLowerInvariant() -ne '.exe' -or -not (Test-Path $resolvedFilePath -PathType Leaf)) { throw "Unsupported launcher wrapper shape: $LauncherPath" }

    $filePath = $resolvedFilePath
    $argumentList = @()
    $nativeArgumentList = @()
    if (-not (Test-XeditClientExecutablePathLooksLikeXedit -Path $resolvedFilePath)) {
        if ($tokens.Count -lt 2) { throw "Unsupported launcher wrapper command: $LauncherPath" }
        $resolvedXeditPath = $tokens[1]
        if (-not [System.IO.Path]::IsPathRooted($resolvedXeditPath)) { $resolvedXeditPath = Join-Path $wrapperDirectory $resolvedXeditPath }
        if ([System.IO.Path]::GetExtension($resolvedXeditPath).ToLowerInvariant() -ne '.exe' -or -not (Test-XeditClientExecutablePathLooksLikeXedit -Path $resolvedXeditPath)) { throw "Unsupported launcher wrapper command: $LauncherPath" }
        $argumentList += $tokens[1..($tokens.Count - 1)]
        if ($tokens.Count -gt 2) { $nativeArgumentList += $tokens[2..($tokens.Count - 1)] }
    }
    elseif ($tokens.Count -gt 1) {
        $argumentList += $tokens[1..($tokens.Count - 1)]
        $nativeArgumentList += $tokens[1..($tokens.Count - 1)]
    }

    $argumentList += $GameModeArgument
    $nativeArgumentList += $GameModeArgument
    return [pscustomobject]@{ FilePath = $filePath; ArgumentList = $argumentList; NativeArgumentList = $nativeArgumentList; SourcePath = $LauncherPath; DetectionPath = $(if ($tokens.Count -gt 1 -and -not (Test-XeditClientExecutablePathLooksLikeXedit -Path $resolvedFilePath)) { $resolvedXeditPath } else { $filePath }); WorkingDirectory = $wrapperDirectory }
}

function Start-XeditClientLauncherProcess {
    param([string]$LauncherPath, [string[]]$ArgumentList, [string]$WorkingDirectory, [hashtable]$EnvironmentVariables)
    $startProcessParameters = @{ FilePath = $LauncherPath; ArgumentList = @($ArgumentList); PassThru = $true }
    if ($null -ne $EnvironmentVariables -and $EnvironmentVariables.Count -gt 0) { $startProcessParameters.Environment = $EnvironmentVariables }
    if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) { $startProcessParameters.WorkingDirectory = $WorkingDirectory }
    if ([System.IO.Path]::GetExtension($LauncherPath).ToLowerInvariant() -in @('.bat', '.cmd')) { $startProcessParameters.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden }
    return Start-Process @startProcessParameters
}

function Invoke-XeditClientProcessLaunch {
    param([string[]]$Arguments)

    $processId = $null
    try {
        $options = ConvertTo-XeditClientOptionMap -Arguments $Arguments -AllowedNames @('--launcher-path', '--game-mode', '--plugins-file', '--mo-profile', '--load-mode', '--plugin', '--data-path', '--mo2-root', '--i-know-what-im-doing')
        if ($null -eq (Get-XeditClientRequiredOptionValues -Options $options -Names @('--launcher-path', '--game-mode'))) { return 1 }
        $unsupportedLegacyOptions = @(Get-XeditClientUnsupportedLegacyLaunchOptions -Options $options)
        if ($unsupportedLegacyOptions.Count -gt 0) { Write-Host "Legacy options are no longer supported: $($unsupportedLegacyOptions -join ', ')"; return 1 }
        $launcherPath = $options['--launcher-path']
        if (-not (Test-XeditClientLauncherPath -Path $launcherPath)) { Write-Host "Launcher path must end with .bat, .cmd, or .exe: $launcherPath"; return 1 }
        $gameModeArgument = Get-XeditClientValidatedGameModeArgument -GameMode $options['--game-mode']
        if ($null -eq $gameModeArgument) { return 1 }
        $moProfile = Get-XeditClientValidatedMoProfile -Options $options
        if ($moProfile -is [bool] -and -not $moProfile) { return 1 }
        # MO2 sandbox root: explicit --mo2-root wins; else fall through to
        # Get-XeditClientDefaultMo2SandboxRoot which honors $env:BGS_MO2_ROOT
        # and the dev-sandbox fallback. End-user installs MUST pass one of
        # those; otherwise we surface a clear error rather than constructing
        # a wrong path under the plugin install root.
        $sandboxRootOverride = if ($options.ContainsKey('--mo2-root')) { [string]$options['--mo2-root'] } else { $null }
        $resolvedSandboxRoot = if (-not [string]::IsNullOrWhiteSpace($sandboxRootOverride)) { $sandboxRootOverride } else { Get-XeditClientDefaultMo2SandboxRoot }
        if ([string]::IsNullOrWhiteSpace($resolvedSandboxRoot)) {
            Write-Host "MO2 sandbox root is not configured. Pass --mo2-root <path>, set `$env:BGS_MO2_ROOT, or run from a dev checkout that has .artifacts\mo2\."
            return 1
        }
        $pluginSource = Get-XeditClientResolvedPluginSource -Options $options -GameMode $options['--game-mode'] -MoProfile $moProfile -SandboxRoot $resolvedSandboxRoot
        if ($null -eq $pluginSource) { return 1 }

        $normalizedLauncherCommand = Get-XeditClientNormalizedLauncherCommand -LauncherPath $launcherPath -GameModeArgument $gameModeArgument
        $session = New-XeditClientSessionContext -PluginLines $pluginSource.PluginLines
        $normalizedLauncherCommand.ArgumentList = @(@($normalizedLauncherCommand.ArgumentList) + @('-automation-serve', ('-P:' + $session.SessionPluginsFilePath)))
        $nativeTargetArgumentList = if ($normalizedLauncherCommand.PSObject.Properties.Name -contains 'NativeArgumentList') { @(ConvertTo-XeditClientFlatStringArray -Values @($normalizedLauncherCommand.NativeArgumentList)) } else { @(ConvertTo-XeditClientFlatStringArray -Values @($normalizedLauncherCommand.ArgumentList)) }
        $nativeTargetArgumentList = @(ConvertTo-XeditClientFlatStringArray -Values @(@($nativeTargetArgumentList) + @('-automation-serve', ('-P:' + $session.SessionPluginsFilePath))))

        # --data-path (optional) translates to xEdit's -D:<path>\ flag.
        # xEdit's docs Section 2.8.1 require a trailing backslash for -D:. Without
        # this flag, xEdit auto-discovers the game install via the Windows registry
        # — which on Steam-installed FO4 points at the Steam library Data, NOT
        # MO2's Stock Game Data. Pass an explicit dataPath to force the agent's
        # intended Data directory.
        if ($options.ContainsKey('--data-path')) {
            $dataPathArg = ConvertTo-XeditClientNativeWindowsPath -Path ([string]$options['--data-path'])
            if (-not [string]::IsNullOrWhiteSpace($dataPathArg)) {
                if (-not $dataPathArg.EndsWith('\')) {
                    $dataPathArg += '\'
                }
                $normalizedLauncherCommand.ArgumentList = @($normalizedLauncherCommand.ArgumentList + @('-D:' + $dataPathArg))
                $nativeTargetArgumentList = @(ConvertTo-XeditClientFlatStringArray -Values @($nativeTargetArgumentList + @('-D:' + $dataPathArg)))
            }
        }

        # --i-know-what-im-doing (optional, sentinel "1") translates to xEdit's
        # -IKnowWhatImDoing startup flag, which the daemon then advertises via
        # `consentEnabled: true` in system.describe. xedit-mcp's TS side gates
        # mutating intent tools on this flag — without it, requests fast-fail
        # with `mutation_requires_iknowwhatimdoing` BEFORE the daemon is hit.
        # Adding the flag is explicit, per-launch, and audited at the MCP call
        # site (no env-var fallback by design).
        if ($options.ContainsKey('--i-know-what-im-doing') -and [string]$options['--i-know-what-im-doing'] -eq '1') {
            $normalizedLauncherCommand.ArgumentList = @($normalizedLauncherCommand.ArgumentList + @('-IKnowWhatImDoing'))
            $nativeTargetArgumentList = @(ConvertTo-XeditClientFlatStringArray -Values @($nativeTargetArgumentList + @('-IKnowWhatImDoing')))
        }

        $mo2LaunchRequest = $null
        $mo2LaunchResult = $null
        if ($null -ne $moProfile) {
            $mo2LaunchRequest = New-XeditClientMo2LaunchRequest -Profile $moProfile -SandboxRoot $resolvedSandboxRoot -TargetPath $normalizedLauncherCommand.DetectionPath -TargetArguments $nativeTargetArgumentList -TargetWorkingDirectory $normalizedLauncherCommand.WorkingDirectory -Session $session
            Write-XeditClientMo2LaunchRequestArtifact -LaunchRequest $mo2LaunchRequest
        }

        if ($null -ne $mo2LaunchRequest) {
            $mo2LaunchResult = Invoke-XeditClientMo2LaunchStart -LaunchRequest $mo2LaunchRequest
            Write-XeditClientMo2LaunchResponseArtifact -LaunchRequest $mo2LaunchRequest -LaunchResponse $mo2LaunchResult.Response
            if ([string]$mo2LaunchResult.State.status -eq 'failed') { throw "MO2 VFS launcher failed: $($mo2LaunchResult.State.error)" }
            if ($null -ne $mo2LaunchResult.State.pid) { $processId = [int]$mo2LaunchResult.State.pid }
            elseif ($null -ne $mo2LaunchResult.Response.result.pid) { $processId = [int]$mo2LaunchResult.Response.result.pid }
        }
        else {
            $knownProcessIds = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessId)
            $startedAt = Get-Date
            $process = Start-XeditClientLauncherProcess -LauncherPath $normalizedLauncherCommand.FilePath -ArgumentList $normalizedLauncherCommand.ArgumentList -WorkingDirectory $normalizedLauncherCommand.WorkingDirectory -EnvironmentVariables $session.EnvironmentVariables
            $processId = Get-XeditClientLaunchedProcessId -WrapperProcess $process -LauncherPath $normalizedLauncherCommand.DetectionPath -StartedAt $startedAt -KnownProcessIds $knownProcessIds
        }

        # Allow env-var override; default 240s — xEdit's automation-serve needs
        # to finish loading active masters before system.describe answers, and
        # 30s tripped on real profiles. See Wait-XeditClientAutomationReady def.
        $readyTimeoutSeconds = 240
        if ($env:BGS_XEDIT_READY_TIMEOUT_SECONDS -and [int]::TryParse($env:BGS_XEDIT_READY_TIMEOUT_SECONDS, [ref]$null)) {
            $parsed = [int]$env:BGS_XEDIT_READY_TIMEOUT_SECONDS
            if ($parsed -gt 0) { $readyTimeoutSeconds = $parsed }
        }
        $null = Wait-XeditClientAutomationReady -XeditExecutablePath $normalizedLauncherCommand.DetectionPath -XeditPid $processId -SessionPath $session.SessionPath -TimeoutSeconds $readyTimeoutSeconds

        Write-Host 'process launch'
        Write-Host 'status: ok'
        Write-Host "launcher-path: $launcherPath"
        Write-Host "session-id: $($session.SessionId)"
        Write-Host "session-path: $($session.SessionPath)"
        Write-Host "session-plugins-file: $($session.SessionPluginsFilePath)"
        if ($null -ne $mo2LaunchRequest) {
            Write-Host "mo2-sandbox-root: $($mo2LaunchRequest.sandbox_root)"
            Write-Host "mo2-launch-runner: $($mo2LaunchRequest.runner)"
            Write-Host "mo2-launch-runtime-root: $($mo2LaunchResult.RuntimeRoot)"
            Write-Host "mo2-launch-request-file: $($mo2LaunchRequest.artifacts.request_file)"
            Write-Host "mo2-launch-response-file: $($mo2LaunchRequest.artifacts.response_file)"
            Write-Host "mo2-launch-state-file: $($mo2LaunchRequest.artifacts.state_file)"
            Write-Host "mo2-launch-id: $($mo2LaunchResult.Response.result.launch_id)"
            Write-Host "mo2-launch-backend: $($mo2LaunchResult.Response.result.artifacts.backend)"
        }
        Write-Host "xedit-pid: $processId"
        return 0
    }
    catch {
        if ($null -ne $processId) {
            $validatedCleanupProcess = Get-XeditClientValidatedLiveProcess -ProcessId $processId
            if ($null -ne $validatedCleanupProcess) {
                Stop-Process -Id $validatedCleanupProcess.ProcessId -Force -ErrorAction SilentlyContinue
                Write-Host "cleanup-xedit-pid: $($validatedCleanupProcess.ProcessId)"
            }
        }
        Write-Host $_.Exception.Message
        return 1
    }
}

function Invoke-XeditClientProcessStatus {
    param([string[]]$Arguments)
    try { $options = ConvertTo-XeditClientOptionMap -Arguments $Arguments -AllowedNames @('--xedit-pid') } catch { Write-Host $_.Exception.Message; return 1 }
    if ($null -eq (Get-XeditClientRequiredOptionValues -Options $options -Names @('--xedit-pid'))) { return 1 }
    $validated = Get-XeditClientValidatedLiveProcess -ProcessId $options['--xedit-pid']
    if ($null -eq $validated) { return 1 }
    Write-Host 'process status'
    Write-Host 'status: running'
    Write-Host "xedit-pid: $($validated.ProcessId)"
    return 0
}

function Invoke-XeditClientProcessWait {
    param([string[]]$Arguments)
    try { $options = ConvertTo-XeditClientOptionMap -Arguments $Arguments -AllowedNames @('--xedit-pid', '--timeout-seconds') } catch { Write-Host $_.Exception.Message; return 1 }
    if ($null -eq (Get-XeditClientRequiredOptionValues -Options $options -Names @('--xedit-pid', '--timeout-seconds'))) { return 1 }
    $timeoutSeconds = ConvertTo-XeditClientPositiveIntValue -Value $options['--timeout-seconds']
    if ($null -eq $timeoutSeconds) { Write-Host "Invalid timeout seconds: $($options['--timeout-seconds'])"; return 1 }
    $validated = Get-XeditClientValidatedLiveProcess -ProcessId $options['--xedit-pid']
    if ($null -eq $validated) { return 1 }
    if ($validated.LiveProcess.WaitForExit($timeoutSeconds * 1000)) { Write-Host 'process wait'; Write-Host 'status: exited'; Write-Host "xedit-pid: $($validated.ProcessId)"; return 0 }
    Write-Host 'process wait'
    Write-Host 'status: timeout'
    Write-Host "xedit-pid: $($validated.ProcessId)"
    return 0
}

function Invoke-XeditClientProcessStop {
    param([string[]]$Arguments)
    try { $options = ConvertTo-XeditClientOptionMap -Arguments $Arguments -AllowedNames @('--xedit-pid') } catch { Write-Host $_.Exception.Message; return 1 }
    if ($null -eq (Get-XeditClientRequiredOptionValues -Options $options -Names @('--xedit-pid'))) { return 1 }
    $validated = Get-XeditClientValidatedLiveProcess -ProcessId $options['--xedit-pid']
    if ($null -eq $validated) { return 1 }
    Stop-Process -Id $validated.ProcessId -Force
    $validated.LiveProcess.WaitForExit()
    Write-Host 'process stop'
    Write-Host 'status: stopped'
    Write-Host "xedit-pid: $($validated.ProcessId)"
    return 0
}

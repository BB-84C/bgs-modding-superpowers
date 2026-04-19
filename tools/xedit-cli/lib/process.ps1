function Get-XeditCliDescendantProcesses {
    param(
        [int]$RootProcessId
    )

    $allProcesses = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $queue = [System.Collections.Generic.Queue[int]]::new()
    $queue.Enqueue($RootProcessId)
    $descendants = @()

    while ($queue.Count -gt 0) {
        $parentId = $queue.Dequeue()
        $children = @($allProcesses | Where-Object { $_.ParentProcessId -eq $parentId })
        foreach ($child in $children) {
            $descendants += $child
            $queue.Enqueue([int]$child.ProcessId)
        }
    }

    return $descendants
}

function Get-XeditCliValidatedLiveProcess {
    param(
        [string]$ProcessId
    )

    $parsedPid = ConvertTo-XeditCliProcessId -ProcessId $ProcessId
    if ($null -eq $parsedPid) {
        Write-Host "Invalid xEdit PID: $ProcessId"
        return $null
    }

    $processInfo = Get-XeditCliProcessById -ProcessId $parsedPid
    if ($null -eq $processInfo) {
        Write-Host "xEdit PID is not running: $ProcessId"
        return $null
    }

    if (-not (Test-XeditCliProcessLooksLikeXedit -Process $processInfo)) {
        Write-Host "Process is not an xEdit instance: $parsedPid"
        return $null
    }

    return [pscustomobject]@{
        ProcessId = $parsedPid
        ProcessInfo = $processInfo
        LiveProcess = (Get-Process -Id $parsedPid -ErrorAction SilentlyContinue)
    }
}

function Get-XeditCliNormalizedPath {
    param(
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $null
    }

    try {
        return (Get-Item -Path $Path -ErrorAction Stop).FullName
    }
    catch {
        return $Path
    }
}

function Get-XeditCliNewTargetProcesses {
    param(
        [datetime]$StartedAt,
        [int[]]$KnownProcessIds,
        [string]$LauncherPath
    )

    $allProcesses = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $normalizedLauncherPath = Get-XeditCliNormalizedPath -Path $LauncherPath
    $matches = foreach ($process in $allProcesses) {
        if ($process.ProcessId -in $KnownProcessIds) {
            continue
        }

        if (-not (Test-XeditCliProcessLooksLikeXedit -Process $process)) {
            continue
        }

        if ([string]::IsNullOrWhiteSpace($process.ExecutablePath)) {
            continue
        }

        $normalizedExecutablePath = Get-XeditCliNormalizedPath -Path $process.ExecutablePath
        if ([string]::IsNullOrWhiteSpace($normalizedExecutablePath) -or -not $normalizedExecutablePath.Equals($normalizedLauncherPath, [System.StringComparison]::OrdinalIgnoreCase)) {
            continue
        }

        try {
            if ($process.CreationDate -is [datetime]) {
                $createdAt = $process.CreationDate
            }
            else {
                $createdAt = [System.Management.ManagementDateTimeConverter]::ToDateTime($process.CreationDate)
            }

            if ($createdAt -lt $StartedAt.AddSeconds(-1)) {
                continue
            }
        }
        catch {
            continue
        }

        $process
    }

    return @($matches | Sort-Object CreationDate, ProcessId)
}

function Get-XeditCliLaunchedProcessId {
    param(
        [System.Diagnostics.Process]$WrapperProcess,
        [string]$LauncherPath,
        [datetime]$StartedAt,
        [int[]]$KnownProcessIds
    )

    $deadline = (Get-Date).AddSeconds(5)

    do {
        $wrapperLive = Get-XeditCliProcessById -ProcessId $WrapperProcess.Id
        $descendants = @(Get-XeditCliDescendantProcesses -RootProcessId $WrapperProcess.Id)
        $newTargets = @(Get-XeditCliNewTargetProcesses -StartedAt $StartedAt -KnownProcessIds $KnownProcessIds -LauncherPath $LauncherPath)

        $preferredChild = $descendants | Where-Object {
            Test-XeditCliProcessLooksLikeXedit -Process $_
        } | Select-Object -First 1

        if ($preferredChild) {
            return $preferredChild.ProcessId
        }

        if ($newTargets.Count -gt 0) {
            return $newTargets[-1].ProcessId
        }

        if ($wrapperLive -and (Test-XeditCliProcessLooksLikeXedit -Process $wrapperLive)) {
            return $WrapperProcess.Id
        }

        Start-Sleep -Milliseconds 200
    } while ((Get-Date) -lt $deadline)

    throw "Unable to determine launched process PID from launcher: $LauncherPath"
}

function Get-XeditCliRequiredOptionValues {
    param(
        [hashtable]$Options,
        [string[]]$Names
    )

    $missing = @()
    foreach ($name in $Names) {
        if (-not $Options.ContainsKey($name)) {
            $missing += $name
        }
    }

    if ($missing.Count -gt 0) {
        Write-Host "Missing required options: $($missing -join ', ')"
        return $null
    }

    return $Options
}

function Get-XeditCliValidatedMoProfile {
    param(
        [hashtable]$Options
    )

    if (-not $Options.ContainsKey("--mo-profile")) {
        return $null
    }

    $profileName = [string]$Options["--mo-profile"]
    if ([string]::IsNullOrWhiteSpace($profileName)) {
        Write-Host "MO profile name must be non-empty"
        return $false
    }

    $trimmedProfileName = $profileName.Trim()
    if ($trimmedProfileName -match '[\\/]' -or $trimmedProfileName -match '(^|[\\/])\.\.($|[\\/])' -or $trimmedProfileName -eq '..') {
        Write-Host "MO profile name must not contain path separators or traversal"
        return $false
    }

    return $trimmedProfileName
}

function Get-XeditCliHookBridgeBinaryPath {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
    return Join-Path $repoRoot "tools\xedit-hook-bridge\src\xEditHookBridge.dll"
}

function Get-XeditCliExpectedHookDllPath {
    param(
        [string]$XeditExecutablePath
    )

    $current = Split-Path -Path $XeditExecutablePath -Parent
    while (-not [string]::IsNullOrWhiteSpace($current)) {
        if (Test-Path (Join-Path $current "Data") -PathType Container) {
            return Join-Path $current "Mod Organizer\hook.dll"
        }

        $parent = Split-Path -Path $current -Parent
        if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $current) {
            break
        }

        $current = $parent
    }

    $xeditDirectory = Split-Path -Path $XeditExecutablePath -Parent
    return [System.IO.Path]::GetFullPath((Join-Path $xeditDirectory "..\Mod Organizer\hook.dll"))
}

function Copy-XeditCliHookBridgeForRealLaunch {
    param(
        [string]$XeditExecutablePath
    )

    $sourcePath = Get-XeditCliHookBridgeBinaryPath
    if (-not (Test-Path $sourcePath -PathType Leaf)) {
        throw "Built hook bridge DLL not found: $sourcePath"
    }

    $targetPath = Get-XeditCliExpectedHookDllPath -XeditExecutablePath $XeditExecutablePath
    Ensure-XeditCliParentDirectory -Path $targetPath
    Copy-Item -Path $sourcePath -Destination $targetPath -Force

    return [pscustomobject]@{
        SourcePath = $sourcePath
        TargetPath = $targetPath
    }
}

function Invoke-XeditCliWithEnvironmentOverrides {
    param(
        [hashtable]$Variables,
        [scriptblock]$ScriptBlock
    )

    $previous = @{}

    try {
        foreach ($entry in $Variables.GetEnumerator()) {
            $name = [string]$entry.Key
            $path = "Env:$name"
            $existing = Get-Item -Path $path -ErrorAction SilentlyContinue
            $previous[$name] = if ($null -eq $existing) { $null } else { $existing.Value }
            Set-Item -Path $path -Value ([string]$entry.Value)
        }

        return & $ScriptBlock
    }
    finally {
        foreach ($name in $Variables.Keys) {
            $path = "Env:$name"
            if ($null -eq $previous[$name]) {
                Remove-Item -Path $path -ErrorAction SilentlyContinue
            }
            else {
                Set-Item -Path $path -Value $previous[$name]
            }
        }
    }
}

function Start-XeditCliLauncherProcess {
    param(
        [string]$LauncherPath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory,
        [hashtable]$EnvironmentVariables
    )

    $startProcessParameters = @{
        FilePath = $LauncherPath
        ArgumentList = @($ArgumentList)
        PassThru = $true
        Environment = $EnvironmentVariables
    }

    if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
        $startProcessParameters.WorkingDirectory = $WorkingDirectory
    }

    return Start-Process @startProcessParameters
}

function Wait-XeditCliProcessExit {
    param(
        [System.Diagnostics.Process]$Process,
        [int]$TimeoutSeconds = 60
    )

    if (-not $Process.WaitForExit($TimeoutSeconds * 1000)) {
        try {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        }
        catch {
        }

        throw "Launcher timed out after $TimeoutSeconds seconds"
    }

    return $Process.ExitCode
}

function Wait-XeditCliProcessIdExit {
    param(
        [int]$ProcessId,
        [int]$TimeoutSeconds = 60
    )

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return 0
    }

    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        try {
            Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
        }
        catch {
        }

        throw "Launcher timed out after $TimeoutSeconds seconds"
    }

    return $process.ExitCode
}

function ConvertFrom-XeditCliLauncherToken {
    param(
        [string]$Token
    )

    if ([string]::IsNullOrWhiteSpace($Token)) {
        return $Token
    }

    $trimmed = $Token.Trim()
    if ($trimmed.Length -ge 2 -and $trimmed.StartsWith('"') -and $trimmed.EndsWith('"')) {
        return $trimmed.Substring(1, $trimmed.Length - 2)
    }

    return $trimmed
}

function Split-XeditCliLauncherCommandLine {
    param(
        [string]$CommandLine
    )

    $matches = [regex]::Matches($CommandLine, '"[^"]*"|\S+')
    return @($matches | ForEach-Object { ConvertFrom-XeditCliLauncherToken -Token $_.Value })
}

function Get-XeditCliNormalizedLauncherCommand {
    param(
        [string]$LauncherPath,
        [string]$GameModeArgument
    )

    $wrapperDirectory = Split-Path -Path $LauncherPath -Parent
    $extension = [System.IO.Path]::GetExtension($LauncherPath).ToLowerInvariant()
    if ($extension -eq '.exe') {
        if (-not (Test-XeditCliExecutablePathLooksLikeXedit -Path $LauncherPath)) {
            throw "Launcher executable is not xEdit-compatible: $LauncherPath"
        }

        return [pscustomobject]@{
            FilePath = $LauncherPath
            ArgumentList = @($GameModeArgument)
            SourcePath = $LauncherPath
            DetectionPath = $LauncherPath
            WorkingDirectory = $wrapperDirectory
        }
    }

    $wrapperLines = @(Get-Content -Path $LauncherPath | ForEach-Object { $_.Trim() } | Where-Object {
        $_ -and
        $_ -notmatch '^(?i)@?echo\s+off$' -and
        $_ -notmatch '^(?i)rem\b' -and
        $_ -notmatch '^::'
    })

    if ($wrapperLines.Count -ne 1) {
        throw "Unsupported launcher wrapper shape: $LauncherPath"
    }

    $commandLine = $wrapperLines[0]
    if ($commandLine -match '(?i)(\&\&|\|\||[\|<>%!]|\bcall\b|\bstart\b|\bset\b)') {
        throw "Unsupported launcher wrapper shape: $LauncherPath"
    }

    $tokens = @(Split-XeditCliLauncherCommandLine -CommandLine $commandLine)
    if ($tokens.Count -lt 1) {
        throw "Unsupported launcher wrapper shape: $LauncherPath"
    }

    $modeArguments = @($tokens | Where-Object { Test-XeditCliGameModeArgument -Argument $_ })
    if ($modeArguments.Count -gt 0) {
        throw "Conflicting xEdit mode argument in launcher wrapper: $LauncherPath"
    }

    $resolvedFilePath = $tokens[0]
    if (-not [System.IO.Path]::IsPathRooted($resolvedFilePath)) {
        $resolvedFilePath = Join-Path $wrapperDirectory $resolvedFilePath
    }

    if ([System.IO.Path]::GetExtension($resolvedFilePath).ToLowerInvariant() -ne '.exe' -or -not (Test-Path $resolvedFilePath -PathType Leaf)) {
        throw "Unsupported launcher wrapper shape: $LauncherPath"
    }

    $filePath = $resolvedFilePath
    $argumentList = @()

    if (-not (Test-XeditCliExecutablePathLooksLikeXedit -Path $resolvedFilePath)) {
        if ($tokens.Count -lt 2) {
            throw "Unsupported launcher wrapper command: $LauncherPath"
        }

        $xeditToken = $tokens[1]
        $resolvedXeditPath = $xeditToken
        if (-not [System.IO.Path]::IsPathRooted($resolvedXeditPath)) {
            $resolvedXeditPath = Join-Path $wrapperDirectory $resolvedXeditPath
        }

        if ([System.IO.Path]::GetExtension($resolvedXeditPath).ToLowerInvariant() -ne '.exe' -or -not (Test-XeditCliExecutablePathLooksLikeXedit -Path $resolvedXeditPath)) {
            throw "Unsupported launcher wrapper command: $LauncherPath"
        }

        $argumentList += $tokens[1..($tokens.Count - 1)]
    }
    elseif ($tokens.Count -gt 1) {
        $argumentList += $tokens[1..($tokens.Count - 1)]
    }

    $argumentList += $GameModeArgument

    return [pscustomobject]@{
        FilePath = $filePath
        ArgumentList = $argumentList
        SourcePath = $LauncherPath
        DetectionPath = $(if ($tokens.Count -gt 1 -and -not (Test-XeditCliExecutablePathLooksLikeXedit -Path $resolvedFilePath)) { $resolvedXeditPath } else { $filePath })
        WorkingDirectory = $wrapperDirectory
    }
}

function Invoke-XeditCliProcessLaunch {
    param(
        [string[]]$Arguments
    )

    $options = ConvertTo-XeditCliOptionMap -Arguments $Arguments
    if ($null -eq (Get-XeditCliRequiredOptionValues -Options $options -Names @("--launcher-path", "--game-mode"))) {
        return 1
    }

    $unsupportedLegacyOptions = @(Get-XeditCliUnsupportedLegacyLaunchOptions -Options $options)
    if ($unsupportedLegacyOptions.Count -gt 0) {
        Write-Host "Legacy options are no longer supported: $($unsupportedLegacyOptions -join ', ')"
        return 1
    }

    $launcherPath = $options["--launcher-path"]
    if (-not (Test-XeditCliLauncherPath -Path $launcherPath)) {
        Write-Host "Launcher path must end with .bat, .cmd, or .exe: $launcherPath"
        return 1
    }

    $gameModeArgument = Get-XeditCliValidatedGameModeArgument -GameMode $options["--game-mode"]
    if ($null -eq $gameModeArgument) {
        return 1
    }

    $moProfile = Get-XeditCliValidatedMoProfile -Options $options
    if ($moProfile -is [bool] -and -not $moProfile) {
        return 1
    }

    $pluginSource = Get-XeditCliResolvedPluginSource -Options $options -GameMode $options["--game-mode"] -MoProfile $moProfile -SandboxRoot $null
    if ($null -eq $pluginSource) {
        return 1
    }

    $normalizedLauncherCommand = Get-XeditCliNormalizedLauncherCommand -LauncherPath $launcherPath -GameModeArgument $gameModeArgument
    $hookSession = New-XeditCliHookSession -PluginLines $pluginSource.PluginLines
    $hookDeployment = $null

    if ($null -ne $moProfile) {
        $hookDeployment = Copy-XeditCliHookBridgeForRealLaunch -XeditExecutablePath $normalizedLauncherCommand.DetectionPath
        $normalizedLauncherCommand.ArgumentList += ('-moprofile:"{0}"' -f $moProfile.Replace('"', ''))
    }

    $normalizedLauncherCommand.ArgumentList += ('-P:' + $hookSession.SessionPluginsFilePath)
    $mo2LaunchRequest = $null
    $mo2LaunchResult = $null
    $processId = $null
    if ($null -ne $moProfile) {
        $mo2LaunchRequest = New-XeditCliMo2LaunchRequest -Profile $moProfile -SandboxRoot $null -TargetPath $normalizedLauncherCommand.DetectionPath -TargetArguments $normalizedLauncherCommand.ArgumentList -TargetWorkingDirectory $normalizedLauncherCommand.WorkingDirectory -HookSession $hookSession
        Write-XeditCliMo2LaunchRequestArtifact -LaunchRequest $mo2LaunchRequest
    }

    if ($null -ne $mo2LaunchRequest) {
        $mo2LaunchResult = Invoke-XeditCliMo2LaunchStart -LaunchRequest $mo2LaunchRequest
        Write-XeditCliMo2LaunchResponseArtifact -LaunchRequest $mo2LaunchRequest -LaunchResponse $mo2LaunchResult.Response
        if ([string]$mo2LaunchResult.State.status -eq 'failed') {
            throw "MO2 VFS launcher failed: $($mo2LaunchResult.State.error)"
        }

        if ($null -ne $mo2LaunchResult.State.pid) {
            $processId = [int]$mo2LaunchResult.State.pid
        }
        elseif ($null -ne $mo2LaunchResult.Response.result.pid) {
            $processId = [int]$mo2LaunchResult.Response.result.pid
        }
    }
    else {
        $process = $null
        $knownProcessIds = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessId)
        $startedAt = Get-Date

        $process = Start-XeditCliLauncherProcess -LauncherPath $normalizedLauncherCommand.FilePath -ArgumentList $normalizedLauncherCommand.ArgumentList -WorkingDirectory $normalizedLauncherCommand.WorkingDirectory -EnvironmentVariables $hookSession.EnvironmentVariables

        $processId = Get-XeditCliLaunchedProcessId -WrapperProcess $process -LauncherPath $normalizedLauncherCommand.DetectionPath -StartedAt $startedAt -KnownProcessIds $knownProcessIds
    }

    Write-Host "process launch"
    Write-Host "status: ok"
    Write-Host "launcher-path: $launcherPath"
    Write-Host "hook-session-id: $($hookSession.SessionId)"
    Write-Host "hook-session-path: $($hookSession.SessionPath)"
    if ($null -ne $hookDeployment) {
        Write-Host "hook-dll-path: $($hookDeployment.TargetPath)"
    }
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

function Invoke-XeditCliProcessStatus {
    param(
        [string[]]$Arguments
    )

    $options = ConvertTo-XeditCliOptionMap -Arguments $Arguments
    if ($null -eq (Get-XeditCliRequiredOptionValues -Options $options -Names @("--xedit-pid"))) {
        return 1
    }

    $validated = Get-XeditCliValidatedLiveProcess -ProcessId $options["--xedit-pid"]
    if ($null -eq $validated) {
        return 1
    }

    Write-Host "process status"
    Write-Host "status: running"
    Write-Host "xedit-pid: $($validated.ProcessId)"

    return 0
}

function Invoke-XeditCliProcessWait {
    param(
        [string[]]$Arguments
    )

    $options = ConvertTo-XeditCliOptionMap -Arguments $Arguments
    if ($null -eq (Get-XeditCliRequiredOptionValues -Options $options -Names @("--xedit-pid", "--timeout-seconds"))) {
        return 1
    }

    $timeoutSeconds = ConvertTo-XeditCliPositiveIntValue -Value $options["--timeout-seconds"]
    if ($null -eq $timeoutSeconds) {
        Write-Host "Invalid timeout seconds: $($options['--timeout-seconds'])"
        return 1
    }

    $validated = Get-XeditCliValidatedLiveProcess -ProcessId $options["--xedit-pid"]
    if ($null -eq $validated) {
        return 1
    }

    if ($validated.LiveProcess.WaitForExit($timeoutSeconds * 1000)) {
        Write-Host "process wait"
        Write-Host "status: exited"
        Write-Host "xedit-pid: $($validated.ProcessId)"
        return 0
    }

    Write-Host "process wait"
    Write-Host "status: timeout"
    Write-Host "xedit-pid: $($validated.ProcessId)"

    return 0
}

function Invoke-XeditCliProcessStop {
    param(
        [string[]]$Arguments
    )

    $options = ConvertTo-XeditCliOptionMap -Arguments $Arguments
    if ($null -eq (Get-XeditCliRequiredOptionValues -Options $options -Names @("--xedit-pid"))) {
        return 1
    }

    $validated = Get-XeditCliValidatedLiveProcess -ProcessId $options["--xedit-pid"]
    if ($null -eq $validated) {
        return 1
    }

    Stop-Process -Id $validated.ProcessId -Force
    $validated.LiveProcess.WaitForExit()

    Write-Host "process stop"
    Write-Host "status: stopped"
    Write-Host "xedit-pid: $($validated.ProcessId)"

    return 0
}

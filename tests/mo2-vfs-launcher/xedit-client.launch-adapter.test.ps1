$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path
$commonLibPath = Join-Path $repoRoot "tools/mo2-vfs-launcher/lib/xedit-client.common.ps1"
$sessionLibPath = Join-Path $repoRoot "tools/mo2-vfs-launcher/lib/xedit-client.session.ps1"
$launchLibPath = Join-Path $repoRoot "tools/mo2-vfs-launcher/lib/xedit-client.launch.ps1"

. $commonLibPath
. $sessionLibPath
. $launchLibPath

function Assert-Equal {
    param($Actual, $Expected, [string]$Message)
    if ($Actual -ne $Expected) {
        throw "$Message`nExpected: $Expected`nActual: $Actual"
    }
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Null {
    param($Actual, [string]$Message)
    if ($null -ne $Actual) {
        throw "$Message`nExpected: <null>`nActual: $Actual"
    }
}

function Invoke-ProcessLaunchWithOutput {
    param([string[]]$Arguments)

    $records = @(& { Invoke-XeditClientProcessLaunch -Arguments $Arguments } 6>&1)
    $result = [int]($records | Where-Object { $_ -is [int] } | Select-Object -Last 1)
    $output = ($records | Where-Object { $_ -isnot [int] } | ForEach-Object { $_.ToString() }) -join "`n"
    return [pscustomobject]@{ Result = $result; Output = $output }
}

$session = New-XeditClientSessionContext -PluginLines @('*Example.esm', '*Patch.esp')
$projectRoot = Get-XeditClientProjectRoot
$tempSandboxRoot = Join-Path $env:TEMP ('xedit-client-mo2-adapter-' + [guid]::NewGuid().ToString('N'))

try {
    $expectedPwshPath = (Get-Command pwsh -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $expectedLauncherScriptPath = Join-Path $repoRoot 'tools\mo2-vfs-launcher\mo2-vfs-launcher.ps1'
    $expectedSessionPluginsArgument = ('-P:' + $session.SessionPluginsFilePath)

    $request = New-XeditClientMo2LaunchRequest -Profile 'Default' -SandboxRoot $null -TargetPath 'C:\Games\xEdit\FO4Edit.exe' -TargetArguments @('-FO4', '-automation-serve', $expectedSessionPluginsArgument) -TargetWorkingDirectory 'C:\Games\xEdit' -Session $session

    Assert-Equal -Actual $request.profile -Expected 'Default' -Message 'adapter should preserve the requested MO2 profile'
    Assert-Equal -Actual $request.runner -Expected 'OpenCodeVfsLauncher' -Message 'adapter metadata should target the generic OpenCodeVfsLauncher runner'
    Assert-Equal -Actual $request.target.path -Expected 'C:\Games\xEdit\FO4Edit.exe' -Message 'adapter should preserve the xEdit target path in generic target metadata'
    Assert-Equal -Actual $request.target.cwd -Expected 'C:\Games\xEdit' -Message 'adapter should preserve the xEdit working directory in generic target metadata'
    Assert-True -Condition ($request.target.args -contains '-automation-serve') -Message 'launch args should always enable native automation serve mode'
    Assert-True -Condition ($request.target.args[-1] -eq ('-P:' + $session.SessionPluginsFilePath)) -Message 'launch args should end with the session plugins file'
    Assert-True -Condition (-not (@($request.target.args) | Where-Object { $_ -match '^-moprofile:' })) -Message 'the new client should not forward -moprofile into native xEdit args'
    Assert-Equal -Actual $request.artifacts.state_file -Expected (Join-Path $session.SessionPath 'mo2-launch-state.json') -Message 'adapter should materialize a predictable state file path under the session'
    Assert-Equal -Actual $request.artifacts.request_file -Expected (Join-Path $session.SessionPath 'mo2-launch-request.json') -Message 'adapter should materialize a predictable request file path under the session'
    Assert-Equal -Actual $request.artifacts.response_file -Expected (Join-Path $session.SessionPath 'mo2-launch-response.json') -Message 'adapter should materialize a predictable response file path under the session'
    Assert-Equal -Actual $request.sandbox_root -Expected (Join-Path $projectRoot '.artifacts\mo2') -Message 'adapter should default the real verification sandbox root to the repo-level .artifacts/mo2'

    Assert-Equal -Actual $request.request.command -Expected 'launch.start' -Message 'adapter should emit a control-plane launch.start request'
    Assert-Equal -Actual $request.request.session_id -Expected $session.SessionId -Message 'adapter should preserve the client session id in the control-plane envelope'
    Assert-Equal -Actual $request.request.payload.profile -Expected 'Default' -Message 'adapter should preserve the requested profile in the generic payload'
    Assert-Equal -Actual $request.request.payload.runner -Expected 'OpenCodeVfsLauncher' -Message 'adapter should target OpenCodeVfsLauncher in the generic payload'
    Assert-Equal -Actual $request.request.payload.target.path -Expected 'C:\Games\xEdit\FO4Edit.exe' -Message 'adapter should preserve the xEdit target path in the generic payload'
    Assert-Equal -Actual $request.request.payload.target.cwd -Expected 'C:\Games\xEdit' -Message 'adapter should preserve the xEdit working directory in the generic payload'
    Assert-True -Condition ($request.request.payload.target.args -contains '-automation-serve') -Message 'adapter should carry native automation serve mode into the generic payload'
    Assert-Equal -Actual $request.request.payload.target.args[-1] -Expected $expectedSessionPluginsArgument -Message 'adapter should carry the session plugins argument into the generic payload'
    Assert-Equal -Actual $request.request.payload.sandbox.root -Expected (Join-Path $projectRoot '.artifacts\mo2') -Message 'adapter should carry the repo-level sandbox root in the generic payload'
    Assert-Equal -Actual $request.request.payload.transport.target_path -Expected $expectedPwshPath -Message 'adapter should launch the VFS launcher through pwsh.exe for organizer-backed transport'
    Assert-Equal -Actual $request.request.payload.transport.cwd -Expected (Join-Path $repoRoot 'tools\mo2-vfs-launcher') -Message 'adapter should launch the VFS launcher from its tool directory'
    Assert-Equal -Actual $request.request.payload.transport.args[4] -Expected $request.artifacts.wrapper_file -Message 'adapter transport should invoke the generated wrapper script'
    Assert-True -Condition (Test-Path $request.artifacts.wrapper_file -PathType Leaf) -Message 'adapter should materialize a wrapper script artifact for organizer-backed launch'

    $wrapperContent = Get-Content -Path $request.artifacts.wrapper_file -Raw
    Assert-True -Condition ($wrapperContent -match [regex]::Escape($expectedLauncherScriptPath)) -Message 'adapter wrapper should invoke the VFS launcher PowerShell entrypoint'
    Assert-True -Condition ($wrapperContent -match [regex]::Escape('direct-child')) -Message 'adapter wrapper should force the VFS launcher to launch the real target directly inside the MO2 context'
    Assert-True -Condition ($wrapperContent -match [regex]::Escape('C:\Games\xEdit\FO4Edit.exe')) -Message 'adapter wrapper should forward the real xEdit executable path'
    Assert-True -Condition ($wrapperContent -match [regex]::Escape('-automation-serve')) -Message 'adapter wrapper should forward native automation serve mode'
    Assert-True -Condition ($wrapperContent -match [regex]::Escape($expectedSessionPluginsArgument)) -Message 'adapter wrapper should forward the session plugins argument through the VFS launcher'

    $script:CapturedStartProcessParameters = $null
    function Start-Process {
        param(
            [string]$FilePath,
            [string[]]$ArgumentList,
            [switch]$PassThru,
            [hashtable]$Environment,
            [string]$WorkingDirectory,
            [System.Diagnostics.ProcessWindowStyle]$WindowStyle
        )
        $script:CapturedStartProcessParameters = $PSBoundParameters
        return [pscustomobject]@{ Id = 4242 }
    }

    $null = Start-XeditClientLauncherProcess -LauncherPath 'D:\launcher\runFO4Edit.cmd' -ArgumentList @('-FO4') -WorkingDirectory 'D:\launcher' -EnvironmentVariables @{}
    Assert-Equal -Actual $script:CapturedStartProcessParameters.WindowStyle -Expected ([System.Diagnostics.ProcessWindowStyle]::Hidden) -Message 'wrapper .cmd launchers should start hidden so their helper console does not interrupt desktop work'

    $null = Start-XeditClientLauncherProcess -LauncherPath 'D:\xedit\FO4Edit.exe' -ArgumentList @('-FO4') -WorkingDirectory 'D:\xedit' -EnvironmentVariables @{}
    Assert-Null -Actual $script:CapturedStartProcessParameters.WindowStyle -Message 'direct .exe xEdit launches should not be globally hidden'

    $profilePluginsPath = Join-Path $tempSandboxRoot 'profiles\Default\plugins.txt'
    $null = New-Item -ItemType Directory -Path (Split-Path -Path $profilePluginsPath -Parent) -Force
    Set-Content -Path $profilePluginsPath -Value @('*ProfileOnly.esm', '*ProfilePatch.esp')
    $resolvedMo2ProfilePluginSource = Get-XeditClientResolvedPluginSource -Options @{ '--mo-profile' = 'Default' } -GameMode 'Fallout4' -MoProfile 'Default' -SandboxRoot $tempSandboxRoot
    Assert-Equal -Actual $resolvedMo2ProfilePluginSource.SourcePluginFilePath -Expected $profilePluginsPath -Message 'plugin resolution should prefer the selected MO2 profile plugins.txt when --mo-profile is present'
    Assert-Equal -Actual $resolvedMo2ProfilePluginSource.PluginLines.Count -Expected 2 -Message 'plugin resolution should read plugin lines from the selected MO2 profile plugins.txt'

    $callerPluginsPath = Join-Path $tempSandboxRoot 'caller-plugins.txt'
    Set-Content -Path $callerPluginsPath -Value @('*Caller.esm', '*CallerPatch.esp')

    $realWrapperSandbox = Join-Path $tempSandboxRoot 'real-wrapper-shape'
    $null = New-Item -ItemType Directory -Path $realWrapperSandbox -Force
    $realWrapperPath = Join-Path $realWrapperSandbox 'runFO4Edit.bat'
    $realHelperPath = Join-Path $realWrapperSandbox 'hdtTES5EditUTF8_loader.exe'
    $realFo4EditPath = Join-Path $realWrapperSandbox 'FO4Edit.exe'
    Set-Content -Path $realWrapperPath -Value @'
@echo off
hdtTES5EditUTF8_loader.exe FO4Edit.exe
'@
    Set-Content -Path $realHelperPath -Value 'fixture helper executable placeholder'
    Set-Content -Path $realFo4EditPath -Value 'fixture xEdit executable placeholder'

    function Test-XeditClientExecutablePathLooksLikeXedit {
        param([string]$Path)
        return ([System.IO.Path]::GetFileName($Path) -ieq 'FO4Edit.exe')
    }

    $normalizedRealWrapperCommand = Get-XeditClientNormalizedLauncherCommand -LauncherPath $realWrapperPath -GameModeArgument '-FO4'
    Assert-True -Condition (@($normalizedRealWrapperCommand.ArgumentList) -contains 'FO4Edit.exe') -Message 'direct helper launch args should keep the wrapped xEdit path for non-MO2 wrapper execution'
    Assert-True -Condition (-not (@($normalizedRealWrapperCommand.NativeArgumentList) | Where-Object { $_ -ieq 'FO4Edit.exe' -or $_ -ieq $realFo4EditPath })) -Message 'native xEdit args should exclude the wrapped xEdit path for MO2 execution'
    Assert-True -Condition (@($normalizedRealWrapperCommand.NativeArgumentList) -contains '-FO4') -Message 'native xEdit args should preserve the mapped game mode for MO2 execution'

    $script:CapturedRealWrapperLaunchRequest = $null
    function Invoke-Mo2ControlPlaneClientRequest {
        param([hashtable]$Request, [string]$LiveRoot)
        $script:CapturedRealWrapperLaunchRequest = [pscustomobject]@{ Request = $Request; LiveRoot = $LiveRoot }
        $stateFile = [string]$Request.payload.state.file
        $stateDirectory = Split-Path -Path $stateFile -Parent
        if (-not (Test-Path $stateDirectory)) { $null = New-Item -ItemType Directory -Path $stateDirectory -Force }
        @{ status = 'spawned'; pid = 54321; session_id = [string]$Request.session_id; target_path = [string]$Request.payload.target.path; args = @($Request.payload.target.args) } |
            ConvertTo-Json -Depth 10 | Set-Content -Path $stateFile
        return [ordered]@{ ok = $true; result = [ordered]@{ launch_id = 'real-wrapper-launch'; pid = 12345; status = 'running'; artifacts = [ordered]@{ backend = 'organizer' } } }
    }
    function Wait-XeditClientAutomationReady {
        param([string]$XeditExecutablePath, [int]$XeditPid, [string]$SessionPath, [int]$TimeoutSeconds = 30)
        return @{ ok = $true; result = @{ command = 'system.describe' } }
    }

    $realWrapperLaunch = Invoke-ProcessLaunchWithOutput -Arguments @('--launcher-path', $realWrapperPath, '--game-mode', 'Fallout4', '--plugins-file', $callerPluginsPath, '--mo-profile', 'Default')
    Assert-Equal -Actual $realWrapperLaunch.Result -Expected 0 -Message 'real parsed wrapper launch should succeed while constructing the MO2 launch request'
    Assert-True -Condition ($null -ne $script:CapturedRealWrapperLaunchRequest) -Message 'real parsed wrapper launch should dispatch an MO2 request'
    $capturedRealWrapperArgs = $script:CapturedRealWrapperLaunchRequest.Request.payload.target.args
    $realWrapperTargetArgs = @($capturedRealWrapperArgs | ForEach-Object { $_ })
    $realWrapperTargetArgsText = $realWrapperTargetArgs -join "`n"
    Assert-Equal -Actual $script:CapturedRealWrapperLaunchRequest.Request.payload.target.path -Expected $realFo4EditPath -Message 'real parsed wrapper launch should target the wrapped xEdit executable under MO2'
    Assert-True -Condition (-not ($realWrapperTargetArgs | Where-Object { $_ -ieq 'FO4Edit.exe' -or $_ -ieq $realFo4EditPath })) -Message 'real parsed wrapper launch should not forward the wrapped xEdit path as a positional native argument'
    Assert-True -Condition ($realWrapperTargetArgsText.Contains('-automation-serve')) -Message 'real parsed wrapper launch should enable native automation serve mode'
    Assert-True -Condition ($realWrapperTargetArgsText.Contains('-P:')) -Message 'real parsed wrapper launch should include a session plugins file argument'

    $script:CapturedLaunchRequest = $null
    function Test-XeditClientLauncherPath { param([string]$Path) return $true }
    function Get-XeditClientNormalizedLauncherCommand {
        param([string]$LauncherPath, [string]$GameModeArgument)
        return [pscustomobject]@{
            FilePath = 'D:\launcher\OpenCodeVfsLauncher.cmd'
            ArgumentList = @('-FO4')
            SourcePath = $LauncherPath
            DetectionPath = 'D:\xedit\FO4Edit.exe'
            WorkingDirectory = 'D:\xedit'
        }
    }
    function Invoke-Mo2ControlPlaneClientRequest {
        param([hashtable]$Request, [string]$LiveRoot)
        $script:CapturedLaunchRequest = [pscustomobject]@{ Request = $Request; LiveRoot = $LiveRoot }
        $stateFile = [string]$Request.payload.state.file
        $stateDirectory = Split-Path -Path $stateFile -Parent
        if (-not (Test-Path $stateDirectory)) { $null = New-Item -ItemType Directory -Path $stateDirectory -Force }
        @{ status = 'spawned'; pid = 54321; session_id = [string]$Request.session_id; target_path = [string]$Request.payload.target.path; args = @($Request.payload.target.args) } |
            ConvertTo-Json -Depth 10 | Set-Content -Path $stateFile
        return [ordered]@{ ok = $true; result = [ordered]@{ launch_id = 'launch-123'; pid = 12345; status = 'running'; artifacts = [ordered]@{ backend = 'organizer' } } }
    }

    $beforeSessions = @{}
    Get-ChildItem (Join-Path $env:TEMP 'xedit-client-sessions') -Directory -ErrorAction SilentlyContinue | ForEach-Object { $beforeSessions[$_.FullName] = $true }

    $launchInvocation = Invoke-ProcessLaunchWithOutput -Arguments @('--launcher-path', 'D:\launcher\runFO4EditCN.bat', '--game-mode', 'Fallout4', '--plugins-file', $callerPluginsPath, '--mo-profile', 'Default')

    Assert-Equal -Actual $launchInvocation.Result -Expected 0 -Message 'Invoke-XeditClientProcessLaunch should succeed while constructing the MO2 launch request'
    Assert-True -Condition ($null -ne $script:CapturedLaunchRequest) -Message 'Invoke-XeditClientProcessLaunch should dispatch the MO2 request through the live control plane'
    Assert-Equal -Actual $script:CapturedLaunchRequest.LiveRoot -Expected (Join-Path $projectRoot '.artifacts\mo2\plugins\Mo2AgentControl\bootstrap\runtime') -Message 'Invoke-XeditClientProcessLaunch should target the project-local MO2 live runtime root'
    Assert-True -Condition ($launchInvocation.Output -match [regex]::Escape('mo2-sandbox-root: ' + (Join-Path $projectRoot '.artifacts\mo2'))) -Message 'Invoke-XeditClientProcessLaunch should surface the resolved MO2 sandbox root'
    Assert-True -Condition ($launchInvocation.Output -match [regex]::Escape('mo2-launch-runner: OpenCodeVfsLauncher')) -Message 'Invoke-XeditClientProcessLaunch should surface the selected MO2 launch runner'
    Assert-True -Condition ($launchInvocation.Output -match [regex]::Escape('mo2-launch-state-file: ')) -Message 'Invoke-XeditClientProcessLaunch should surface the launcher state artifact path'
    Assert-True -Condition ($launchInvocation.Output -match [regex]::Escape('mo2-launch-response-file: ')) -Message 'Invoke-XeditClientProcessLaunch should surface the control-plane response artifact path'
    Assert-True -Condition ($launchInvocation.Output -match [regex]::Escape('mo2-launch-backend: organizer')) -Message 'Invoke-XeditClientProcessLaunch should surface the organizer-backed launch backend'
    Assert-True -Condition ($launchInvocation.Output -match [regex]::Escape('xedit-pid: 54321')) -Message 'Invoke-XeditClientProcessLaunch should prefer the VFS launcher state pid as the real xEdit pid'
    Assert-True -Condition (-not $launchInvocation.Output.Contains('hook-session-id:')) -Message 'launch output should not expose removed hook-session fields'
    Assert-True -Condition (-not $launchInvocation.Output.Contains('hook-session-path:')) -Message 'launch output should not expose removed hook-session fields'
    Assert-True -Condition (-not $launchInvocation.Output.Contains('hook-dll-path:')) -Message 'launch output should not expose removed hook-session fields'

    $newSession = Get-ChildItem (Join-Path $env:TEMP 'xedit-client-sessions') -Directory -ErrorAction SilentlyContinue | Where-Object { -not $beforeSessions.ContainsKey($_.FullName) } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    Assert-True -Condition ($null -ne $newSession) -Message 'Invoke-XeditClientProcessLaunch should create a new client session directory'
    $requestFilePath = Join-Path $newSession.FullName 'mo2-launch-request.json'
    $responseFilePath = Join-Path $newSession.FullName 'mo2-launch-response.json'
    $wrapperFilePath = Join-Path $newSession.FullName 'mo2-launch-wrapper.ps1'
    Assert-True -Condition (Test-Path $requestFilePath -PathType Leaf) -Message 'Invoke-XeditClientProcessLaunch should materialize the MO2 launch request artifact'
    Assert-True -Condition (Test-Path $responseFilePath -PathType Leaf) -Message 'Invoke-XeditClientProcessLaunch should materialize the MO2 launch response artifact'
    Assert-True -Condition (Test-Path $wrapperFilePath -PathType Leaf) -Message 'Invoke-XeditClientProcessLaunch should materialize the MO2 launch wrapper artifact'
    $cliRequest = Get-Content -Path $requestFilePath -Raw | ConvertFrom-Json -AsHashtable
    $cliResponse = Get-Content -Path $responseFilePath -Raw | ConvertFrom-Json -AsHashtable
    Assert-Equal -Actual $cliRequest.request.command -Expected 'launch.start' -Message 'The CLI path should emit a real control-plane launch.start request artifact'
    Assert-Equal -Actual $cliRequest.request.payload.runner -Expected 'OpenCodeVfsLauncher' -Message 'The CLI path should target OpenCodeVfsLauncher in the generic payload'
    Assert-Equal -Actual $cliRequest.request.payload.transport.target_path -Expected $expectedPwshPath -Message 'The CLI request artifact should target pwsh.exe for the VFS launcher transport path'
    Assert-True -Condition ($cliRequest.request.payload.target.args -contains '-automation-serve') -Message 'The CLI request artifact should enable native automation serve mode'
    Assert-True -Condition (-not (@($cliRequest.request.payload.target.args) | Where-Object { $_ -match '^-moprofile:' })) -Message 'The CLI request artifact should not forward -moprofile into native xEdit args'
    Assert-Equal -Actual $cliRequest.request.payload.target.args[-1] -Expected ('-P:' + (Join-Path $newSession.FullName 'plugins.txt')) -Message 'The CLI request artifact should carry the session plugins argument'
    Assert-Equal -Actual $cliResponse.result.launch_id -Expected 'launch-123' -Message 'The CLI response artifact should preserve the control-plane launch id'
    Assert-Equal -Actual $cliResponse.result.artifacts.backend -Expected 'organizer' -Message 'The CLI response artifact should preserve the organizer backend'

    $script:CapturedSingleNativeArgLaunchRequest = $null
    function Test-XeditClientLauncherPath { param([string]$Path) return $true }
    function Get-XeditClientNormalizedLauncherCommand {
        param([string]$LauncherPath, [string]$GameModeArgument)
        return [pscustomobject]@{
            FilePath = 'D:\xedit\SF1Edit64.exe'
            ArgumentList = @($GameModeArgument)
            NativeArgumentList = @($GameModeArgument)
            SourcePath = $LauncherPath
            DetectionPath = 'D:\xedit\SF1Edit64.exe'
            WorkingDirectory = 'D:\xedit'
        }
    }
    function Invoke-Mo2ControlPlaneClientRequest {
        param([hashtable]$Request, [string]$LiveRoot)
        $script:CapturedSingleNativeArgLaunchRequest = [pscustomobject]@{ Request = $Request; LiveRoot = $LiveRoot }
        $stateFile = [string]$Request.payload.state.file
        $stateDirectory = Split-Path -Path $stateFile -Parent
        if (-not (Test-Path $stateDirectory)) { $null = New-Item -ItemType Directory -Path $stateDirectory -Force }
        @{ status = 'spawned'; pid = 65432; session_id = [string]$Request.session_id; target_path = [string]$Request.payload.target.path; args = @($Request.payload.target.args) } |
            ConvertTo-Json -Depth 10 | Set-Content -Path $stateFile
        return [ordered]@{ ok = $true; result = [ordered]@{ launch_id = 'single-native-arg-launch'; pid = 65432; status = 'running'; artifacts = [ordered]@{ backend = 'organizer' } } }
    }
    function Wait-XeditClientAutomationReady {
        param([string]$XeditExecutablePath, [int]$XeditPid, [string]$SessionPath, [int]$TimeoutSeconds = 30)
        return @{ ok = $true; result = @{ command = 'system.describe' } }
    }

    $singleNativeArgLaunch = Invoke-ProcessLaunchWithOutput -Arguments @('--launcher-path', 'D:\xedit\SF1Edit64.exe', '--game-mode', 'Starfield', '--plugins-file', $callerPluginsPath, '--mo-profile', 'Default')
    Assert-Equal -Actual $singleNativeArgLaunch.Result -Expected 0 -Message 'single native xEdit mode launch should succeed while constructing the MO2 launch request'
    Assert-True -Condition ($null -ne $script:CapturedSingleNativeArgLaunchRequest) -Message 'single native xEdit mode launch should dispatch an MO2 request'
    $singleNativeArgTargetArgs = @($script:CapturedSingleNativeArgLaunchRequest.Request.payload.target.args)
    Assert-Equal -Actual $singleNativeArgTargetArgs.Count -Expected 3 -Message 'single native xEdit mode launch should preserve three distinct native arguments'
    Assert-Equal -Actual $singleNativeArgTargetArgs[0] -Expected '-SF1' -Message 'single native xEdit mode launch should preserve the mapped game mode as its own argument'
    Assert-Equal -Actual $singleNativeArgTargetArgs[1] -Expected '-automation-serve' -Message 'single native xEdit mode launch should preserve automation serve as a separate argument'
    Assert-True -Condition ($singleNativeArgTargetArgs[2].StartsWith('-P:')) -Message 'single native xEdit mode launch should preserve the session plugins file as a separate argument'
    Assert-True -Condition (-not ($singleNativeArgTargetArgs | Where-Object { $_ -like '-SF1-automation-serve*' })) -Message 'single native xEdit mode launch should never glue the game mode and automation flags into one token'

    $script:CapturedDirectReadiness = $null
    function Test-XeditClientLauncherPath { param([string]$Path) return $true }
    function Get-XeditClientNormalizedLauncherCommand {
        param([string]$LauncherPath, [string]$GameModeArgument)
        return [pscustomobject]@{
            FilePath = 'D:\xedit\FO4Edit.exe'
            ArgumentList = @($GameModeArgument)
            SourcePath = $LauncherPath
            DetectionPath = 'D:\xedit\FO4Edit.exe'
            WorkingDirectory = 'D:\xedit'
        }
    }
    function Start-XeditClientLauncherProcess {
        param([string]$LauncherPath, [string[]]$ArgumentList, [string]$WorkingDirectory, [hashtable]$EnvironmentVariables)
        return [pscustomobject]@{ Id = 13579 }
    }
    function Get-XeditClientLaunchedProcessId {
        param([object]$WrapperProcess, [string]$LauncherPath, [datetime]$StartedAt, [int[]]$KnownProcessIds)
        return 24680
    }
    function Wait-XeditClientAutomationReady {
        param([string]$XeditExecutablePath, [int]$XeditPid, [string]$SessionPath, [int]$TimeoutSeconds = 30)
        $script:CapturedDirectReadiness = $PSBoundParameters
        return @{ ok = $true; result = @{ command = 'system.describe' } }
    }

    $directReadinessLaunch = Invoke-ProcessLaunchWithOutput -Arguments @('--launcher-path', 'D:\xedit\FO4Edit.exe', '--game-mode', 'Fallout4', '--plugins-file', $callerPluginsPath)
    Assert-Equal -Actual $directReadinessLaunch.Result -Expected 0 -Message 'direct process launch should succeed after native automation readiness is confirmed'
    Assert-True -Condition ($null -ne $script:CapturedDirectReadiness) -Message 'direct process launch should use native automation readiness as its success gate'
    Assert-Equal -Actual $script:CapturedDirectReadiness.XeditExecutablePath -Expected 'D:\xedit\FO4Edit.exe' -Message 'direct readiness should call the launched xEdit executable directly'
    Assert-Equal -Actual $script:CapturedDirectReadiness.XeditPid -Expected 24680 -Message 'direct readiness should target the discovered xEdit pid'

    $script:StoppedPidsAfterReadinessFailure = @()
    function Stop-Process {
        param([int]$Id, [switch]$Force, [System.Management.Automation.ActionPreference]$ErrorAction)
        $script:StoppedPidsAfterReadinessFailure += $Id
    }
    function Wait-XeditClientAutomationReady {
        param([string]$XeditExecutablePath, [int]$XeditPid, [string]$SessionPath, [int]$TimeoutSeconds = 30)
        throw 'readiness failed for cleanup regression'
    }

    $directReadinessFailure = Invoke-ProcessLaunchWithOutput -Arguments @('--launcher-path', 'D:\xedit\FO4Edit.exe', '--game-mode', 'Fallout4', '--plugins-file', $callerPluginsPath)
    Assert-Equal -Actual $directReadinessFailure.Result -Expected 1 -Message 'direct process launch should fail when native automation readiness fails'
    Assert-True -Condition ($directReadinessFailure.Output.Contains('readiness failed for cleanup regression')) -Message 'direct readiness failure should report the readiness error'
    Assert-True -Condition ($script:StoppedPidsAfterReadinessFailure -contains 24680) -Message 'direct readiness failure should stop the launched xEdit pid before returning failure'

    $script:StoppedPidsAfterReadinessFailure = @()
    function Invoke-Mo2ControlPlaneClientRequest {
        param([hashtable]$Request, [string]$LiveRoot)
        $stateFile = [string]$Request.payload.state.file
        $stateDirectory = Split-Path -Path $stateFile -Parent
        if (-not (Test-Path $stateDirectory)) { $null = New-Item -ItemType Directory -Path $stateDirectory -Force }
        @{ status = 'spawned'; pid = 54321; session_id = [string]$Request.session_id; target_path = [string]$Request.payload.target.path; args = @($Request.payload.target.args) } |
            ConvertTo-Json -Depth 10 | Set-Content -Path $stateFile
        return [ordered]@{ ok = $true; result = [ordered]@{ launch_id = 'readiness-failure-launch'; pid = 12345; status = 'running'; artifacts = [ordered]@{ backend = 'organizer' } } }
    }

    $mo2ReadinessFailure = Invoke-ProcessLaunchWithOutput -Arguments @('--launcher-path', 'D:\xedit\FO4Edit.exe', '--game-mode', 'Fallout4', '--plugins-file', $callerPluginsPath, '--mo-profile', 'Default')
    Assert-Equal -Actual $mo2ReadinessFailure.Result -Expected 1 -Message 'MO2 process launch should fail when native automation readiness fails'
    Assert-True -Condition ($mo2ReadinessFailure.Output.Contains('readiness failed for cleanup regression')) -Message 'MO2 readiness failure should report the readiness error'
    Assert-True -Condition ($script:StoppedPidsAfterReadinessFailure -contains 54321) -Message 'MO2 readiness failure should stop the launched xEdit pid before returning failure'
}
finally {
    if ($session -and (Test-Path $session.SessionPath -PathType Container)) { Remove-Item -Path $session.SessionPath -Recurse -Force }
    if ($tempSandboxRoot -and (Test-Path $tempSandboxRoot -PathType Container)) { Remove-Item -Path $tempSandboxRoot -Recurse -Force }
}

Write-Host 'xedit-client MO2 launch adapter checks passed.'
exit 0

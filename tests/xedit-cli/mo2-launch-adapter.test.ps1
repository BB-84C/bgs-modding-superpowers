$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$commonLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/common.ps1"
$sessionPluginsLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/session-plugins.ps1"
$hookSessionLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/hook-session.ps1"
$processLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/process.ps1"
$mo2LaunchLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/mo2-launch.ps1"

. $commonLibPath
. $sessionPluginsLibPath
. $hookSessionLibPath
. $processLibPath
. $mo2LaunchLibPath

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

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Invoke-ProcessLaunchWithOutput {
    param(
        [string[]]$Arguments
    )

    $records = @(& { Invoke-XeditCliProcessLaunch -Arguments $Arguments } 6>&1)
    $result = [int]($records | Where-Object { $_ -is [int] } | Select-Object -Last 1)
    $output = ($records | Where-Object { $_ -isnot [int] } | ForEach-Object { $_.ToString() }) -join "`n"

    return [pscustomobject]@{
        Result = $result
        Output = $output
    }
}

$hookSession = New-XeditCliHookSession -PluginLines @("*Example.esm", "*Patch.esp")
$projectRoot = Get-XeditCliProjectRoot

try {
    $expectedPwshPath = (Get-Command pwsh -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $expectedLauncherScriptPath = Join-Path $repoRoot 'tools\mo2-vfs-launcher\mo2-vfs-launcher.ps1'
    $expectedSessionPluginsArgument = ('-P:' + $hookSession.SessionPluginsFilePath)
    $request = New-XeditCliMo2LaunchRequest -Profile "Default" -SandboxRoot $null -TargetPath "C:\Games\xEdit\FO4Edit.exe" -TargetArguments @("-FO4", '-moprofile:"Default"') -TargetWorkingDirectory "C:\Games\xEdit" -HookSession $hookSession
    $tempSandboxRoot = Join-Path $env:TEMP ('xedit-cli-mo2-adapter-' + [guid]::NewGuid().ToString('N'))
    $profilePluginsPath = Join-Path $tempSandboxRoot 'profiles\Default\plugins.txt'
    $null = New-Item -ItemType Directory -Path (Split-Path -Path $profilePluginsPath -Parent) -Force
    Set-Content -Path $profilePluginsPath -Value @('*ProfileOnly.esm', '*ProfilePatch.esp')

    Assert-Equal -Actual $request.profile -Expected "Default" -Message "adapter should preserve the requested MO2 profile"
    Assert-Equal -Actual $request.runner -Expected "OpenCodeVfsLauncher" -Message "adapter metadata should target the generic OpenCodeVfsLauncher runner"
    Assert-Equal -Actual $request.target.path -Expected "C:\Games\xEdit\FO4Edit.exe" -Message "adapter should preserve the xEdit target path in generic target metadata"
    Assert-Equal -Actual $request.target.cwd -Expected "C:\Games\xEdit" -Message "adapter should preserve the xEdit working directory in generic target metadata"
    Assert-Equal -Actual $request.target.args.Count -Expected 3 -Message "adapter should append one session plugins argument to the xEdit target metadata"
    Assert-Equal -Actual $request.target.args[0] -Expected "-FO4" -Message "adapter should preserve the first target arg"
    Assert-Equal -Actual $request.target.args[1] -Expected '-moprofile:"Default"' -Message "adapter should preserve the second target arg"
    Assert-Equal -Actual $request.target.args[2] -Expected $expectedSessionPluginsArgument -Message "adapter should always append the session plugins file to xEdit launch arguments"
    Assert-True -Condition (-not $request.target.env.Contains('XEDIT_CLI_HOOK_LOAD_MODE')) -Message "adapter should stop exporting the old load mode hook env"
    Assert-True -Condition (-not $request.target.env.Contains('XEDIT_CLI_HOOK_PLUGINS')) -Message "adapter should stop exporting the old plugin list hook env"
    Assert-Equal -Actual $request.artifacts.state_file -Expected (Join-Path $hookSession.SessionPath "mo2-launch-state.json") -Message "adapter should materialize a predictable state file path under the session"
    Assert-Equal -Actual $request.artifacts.request_file -Expected (Join-Path $hookSession.SessionPath "mo2-launch-request.json") -Message "adapter should materialize a predictable request file path under the session"
    Assert-Equal -Actual $request.artifacts.response_file -Expected (Join-Path $hookSession.SessionPath "mo2-launch-response.json") -Message "adapter should materialize a predictable response file path under the session"
    Assert-Equal -Actual $request.sandbox_root -Expected (Join-Path $projectRoot ".artifacts\mo2") -Message "adapter should default the real verification sandbox root to the repo-level .artifacts/mo2"

    Assert-Equal -Actual $request.request.command -Expected "launch.start" -Message "adapter should emit a control-plane launch.start request"
    Assert-Equal -Actual $request.request.session_id -Expected $hookSession.SessionId -Message "adapter should preserve the hook session id in the control-plane envelope"
    Assert-Equal -Actual $request.request.payload.profile -Expected "Default" -Message "adapter should preserve the requested profile in the generic payload"
    Assert-Equal -Actual $request.request.payload.runner -Expected "OpenCodeVfsLauncher" -Message "adapter should target OpenCodeVfsLauncher in the generic payload"
    Assert-Equal -Actual $request.request.payload.target.path -Expected "C:\Games\xEdit\FO4Edit.exe" -Message "adapter should preserve the xEdit target path in the generic payload"
    Assert-Equal -Actual $request.request.payload.target.cwd -Expected "C:\Games\xEdit" -Message "adapter should preserve the xEdit working directory in the generic payload"
    Assert-Equal -Actual $request.request.payload.target.args[2] -Expected $expectedSessionPluginsArgument -Message "adapter should carry the session plugins argument into the generic payload"
    Assert-True -Condition (Test-Path $hookSession.SessionPluginsFilePath -PathType Leaf) -Message "adapter should target a materialized session plugins file"
    Assert-Equal -Actual $request.request.payload.sandbox.root -Expected (Join-Path $projectRoot ".artifacts\mo2") -Message "adapter should carry the repo-level sandbox root in the generic payload"
    Assert-Equal -Actual $request.request.payload.transport.target_path -Expected $expectedPwshPath -Message "adapter should launch the VFS launcher through pwsh.exe for organizer-backed transport"
    Assert-Equal -Actual $request.request.payload.transport.cwd -Expected (Join-Path $repoRoot 'tools\mo2-vfs-launcher') -Message "adapter should launch the VFS launcher from its tool directory"
    Assert-Equal -Actual $request.request.payload.transport.args[4] -Expected $request.artifacts.wrapper_file -Message "adapter transport should invoke the generated wrapper script"
    Assert-True -Condition (Test-Path $request.artifacts.wrapper_file -PathType Leaf) -Message "adapter should materialize a wrapper script artifact for organizer-backed launch"
    $wrapperContent = Get-Content -Path $request.artifacts.wrapper_file -Raw
    Assert-True -Condition ($wrapperContent -match [regex]::Escape($expectedLauncherScriptPath)) -Message "adapter wrapper should invoke the VFS launcher PowerShell entrypoint"
    Assert-True -Condition ($wrapperContent -match [regex]::Escape('direct-child')) -Message "adapter wrapper should force the VFS launcher to launch the real target directly inside the MO2 context"
    Assert-True -Condition ($wrapperContent -match [regex]::Escape('C:\Games\xEdit\FO4Edit.exe')) -Message "adapter wrapper should forward the real xEdit executable path"
    Assert-True -Condition ($wrapperContent -match [regex]::Escape($expectedSessionPluginsArgument)) -Message "adapter wrapper should forward the session plugins argument through the VFS launcher"

    $bakedKeys = @("game_mode", "load_mode", "plugin", "launcher_path", "xedit")
    foreach ($key in $bakedKeys) {
        Assert-True -Condition (-not $request.request.payload.Contains($key)) -Message "adapter should not bake xEdit-specific field '$key' into the control-plane request payload"
    }

    $resolvedMo2ProfilePluginSource = Get-XeditCliResolvedPluginSource -Options @{ '--mo-profile' = 'Default' } -GameMode 'Fallout4' -MoProfile 'Default' -SandboxRoot $tempSandboxRoot
    Assert-Equal -Actual $resolvedMo2ProfilePluginSource.SourcePluginFilePath -Expected $profilePluginsPath -Message 'plugin resolution should prefer the selected MO2 profile plugins.txt when --mo-profile is present'
    Assert-Equal -Actual $resolvedMo2ProfilePluginSource.PluginLines.Count -Expected 2 -Message 'plugin resolution should read plugin lines from the selected MO2 profile plugins.txt'

    $script:CapturedLaunchRequest = $null

    function Test-XeditCliLauncherPath { param([string]$Path) return $true }
    function Copy-XeditCliHookBridgeForRealLaunch { param([string]$XeditExecutablePath) return [pscustomobject]@{ TargetPath = 'D:\fake\hook.dll' } }
    function Get-XeditCliNormalizedLauncherCommand {
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
        $script:CapturedLaunchRequest = [pscustomobject]@{
            Request = $Request
            LiveRoot = $LiveRoot
        }
        $stateFile = [string]$Request.payload.state.file
        $stateDirectory = Split-Path -Path $stateFile -Parent
        if (-not (Test-Path $stateDirectory)) {
            $null = New-Item -ItemType Directory -Path $stateDirectory -Force
        }
        @{
            status = 'spawned'
            pid = 54321
            session_id = [string]$Request.session_id
            target_path = [string]$Request.payload.target.path
            args = @($Request.payload.target.args)
        } | ConvertTo-Json -Depth 10 | Set-Content -Path $stateFile

        return [ordered]@{
            ok = $true
            result = [ordered]@{
                launch_id = 'launch-123'
                pid = 12345
                status = 'running'
                artifacts = [ordered]@{
                    backend = 'organizer'
                }
            }
        }
    }

    $beforeSessions = @{}
    Get-ChildItem (Join-Path $env:TEMP 'xedit-cli-hook-sessions') -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $beforeSessions[$_.FullName] = $true
    }

    $launchInvocation = Invoke-ProcessLaunchWithOutput -Arguments @(
        '--launcher-path',
        'D:\launcher\runFO4EditCN.bat',
        '--game-mode',
        'Fallout4',
        '--plugins-file',
        $hookSession.SessionPluginsFilePath,
        '--mo-profile',
        'Default'
    )

    Assert-Equal -Actual $launchInvocation.Result -Expected 0 -Message 'Invoke-XeditCliProcessLaunch should succeed while constructing the MO2 launch request'
    Assert-True -Condition ($null -ne $script:CapturedLaunchRequest) -Message 'Invoke-XeditCliProcessLaunch should dispatch the MO2 request through the live control plane'
    Assert-Equal -Actual $script:CapturedLaunchRequest.LiveRoot -Expected (Join-Path $projectRoot '.artifacts\mo2\plugins\Mo2AgentControl\bootstrap\runtime') -Message 'Invoke-XeditCliProcessLaunch should target the project-local MO2 live runtime root'
    Assert-True -Condition ($launchInvocation.Output -match [regex]::Escape('mo2-sandbox-root: ' + (Join-Path $projectRoot '.artifacts\mo2'))) -Message 'Invoke-XeditCliProcessLaunch should surface the resolved MO2 sandbox root'
    Assert-True -Condition ($launchInvocation.Output -match [regex]::Escape('mo2-launch-runner: OpenCodeVfsLauncher')) -Message 'Invoke-XeditCliProcessLaunch should surface the selected MO2 launch runner'
    Assert-True -Condition ($launchInvocation.Output -match [regex]::Escape('mo2-launch-state-file: ')) -Message 'Invoke-XeditCliProcessLaunch should surface the launcher state artifact path'
    Assert-True -Condition ($launchInvocation.Output -match [regex]::Escape('mo2-launch-response-file: ')) -Message 'Invoke-XeditCliProcessLaunch should surface the control-plane response artifact path'
    Assert-True -Condition ($launchInvocation.Output -match [regex]::Escape('mo2-launch-backend: organizer')) -Message 'Invoke-XeditCliProcessLaunch should surface the organizer-backed launch backend'
    Assert-True -Condition ($launchInvocation.Output -match [regex]::Escape('xedit-pid: 54321')) -Message 'Invoke-XeditCliProcessLaunch should prefer the VFS launcher state pid as the real xEdit pid'

    $newSession = Get-ChildItem (Join-Path $env:TEMP 'xedit-cli-hook-sessions') -Directory -ErrorAction SilentlyContinue | Where-Object { -not $beforeSessions.ContainsKey($_.FullName) } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    Assert-True -Condition ($null -ne $newSession) -Message 'Invoke-XeditCliProcessLaunch should create a new hook session directory'
    $requestFilePath = Join-Path $newSession.FullName 'mo2-launch-request.json'
    $responseFilePath = Join-Path $newSession.FullName 'mo2-launch-response.json'
    $wrapperFilePath = Join-Path $newSession.FullName 'mo2-launch-wrapper.ps1'
    Assert-True -Condition (Test-Path $requestFilePath -PathType Leaf) -Message 'Invoke-XeditCliProcessLaunch should materialize the MO2 launch request artifact'
    Assert-True -Condition (Test-Path $responseFilePath -PathType Leaf) -Message 'Invoke-XeditCliProcessLaunch should materialize the MO2 launch response artifact'
    Assert-True -Condition (Test-Path $wrapperFilePath -PathType Leaf) -Message 'Invoke-XeditCliProcessLaunch should materialize the MO2 launch wrapper artifact'
    $cliRequest = Get-Content -Path $requestFilePath -Raw | ConvertFrom-Json -AsHashtable
    $cliResponse = Get-Content -Path $responseFilePath -Raw | ConvertFrom-Json -AsHashtable
    Assert-Equal -Actual $cliRequest.request.command -Expected 'launch.start' -Message 'The CLI path should emit a real control-plane launch.start request artifact'
    Assert-Equal -Actual $cliRequest.request.payload.runner -Expected 'OpenCodeVfsLauncher' -Message 'The CLI path should target OpenCodeVfsLauncher in the generic payload'
    Assert-Equal -Actual $cliRequest.request.payload.transport.target_path -Expected $expectedPwshPath -Message 'The CLI request artifact should target pwsh.exe for the VFS launcher transport path'
    Assert-Equal -Actual ([System.IO.Path]::GetFileName([string]$cliRequest.artifacts.wrapper_file)) -Expected ([System.IO.Path]::GetFileName($wrapperFilePath)) -Message 'The CLI request artifact should report the generated wrapper file name'
    Assert-Equal -Actual $cliRequest.request.payload.target.args[-1] -Expected ('-P:' + (Join-Path $newSession.FullName 'plugins.txt')) -Message 'The CLI request artifact should carry the session plugins argument'
    Assert-Equal -Actual $cliResponse.result.launch_id -Expected 'launch-123' -Message 'The CLI response artifact should preserve the control-plane launch id'
    Assert-Equal -Actual $cliResponse.result.artifacts.backend -Expected 'organizer' -Message 'The CLI response artifact should preserve the organizer backend'
}
finally {
    if ($hookSession -and (Test-Path $hookSession.SessionPath -PathType Container)) {
        Remove-Item -Path $hookSession.SessionPath -Recurse -Force
    }
    if ($tempSandboxRoot -and (Test-Path $tempSandboxRoot -PathType Container)) {
        Remove-Item -Path $tempSandboxRoot -Recurse -Force
    }
}

Write-Host "xedit-cli MO2 launch adapter checks passed."
exit 0

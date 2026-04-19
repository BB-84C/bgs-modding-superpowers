$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$commonLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/common.ps1"
$sessionPluginsLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/session-plugins.ps1"
$hookSessionLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/hook-session.ps1"
$mo2LaunchLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/mo2-launch.ps1"
$processLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/process.ps1"

. $commonLibPath
. $sessionPluginsLibPath
. $hookSessionLibPath
. $mo2LaunchLibPath
. $processLibPath

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

function New-TestLauncherPath {
    $tempRoot = Join-Path $env:TEMP ("xedit-cli-hook-session-" + [guid]::NewGuid().ToString("N"))
    $null = New-Item -ItemType Directory -Path $tempRoot -Force
    $launcherPath = Join-Path $tempRoot "launch-xedit.cmd"
    Set-Content -Path $launcherPath -Value "@echo off"
    return $launcherPath
}

function New-TestPluginsFile {
    param(
        [string[]]$Lines
    )

    $tempRoot = Join-Path $env:TEMP ("xedit-cli-hook-session-plugins-" + [guid]::NewGuid().ToString("N"))
    $null = New-Item -ItemType Directory -Path $tempRoot -Force
    $pluginsFilePath = Join-Path $tempRoot "plugins.txt"
    Set-Content -Path $pluginsFilePath -Value $Lines
    return $pluginsFilePath
}

$launcherPath = New-TestLauncherPath
$pluginsFilePath = New-TestPluginsFile -Lines @("*Example.esm", "*Example.esm", "*Another.esp")

try {
    $expectedPwshPath = (Get-Command pwsh -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $expectedLauncherScriptPath = Join-Path $repoRoot 'tools\mo2-vfs-launcher\mo2-vfs-launcher.ps1'
    $allSession = New-XeditCliHookSession -PluginLines @("*Skyrim.esm")

    Assert-True -Condition ($allSession.SessionId -match '^[0-9a-f]{32}$') -Message "hook sessions should create a stable diagnostic session id"
    Assert-True -Condition ([System.IO.Path]::IsPathRooted($allSession.SessionPath)) -Message "hook sessions should create a rooted diagnostic session path"
    Assert-True -Condition (Test-Path $allSession.SessionPath -PathType Container) -Message "hook sessions should create the diagnostic session directory"
    Assert-True -Condition ($allSession.EnvironmentVariables.ContainsKey("XEDIT_CLI_HOOK_SESSION_ID")) -Message "hook sessions should include a diagnostic session id"
    Assert-True -Condition ($allSession.EnvironmentVariables.ContainsKey("XEDIT_CLI_HOOK_SESSION_PATH")) -Message "hook sessions should include a diagnostic session path"
    Assert-True -Condition (-not $allSession.EnvironmentVariables.ContainsKey("XEDIT_CLI_HOOK_LOAD_MODE")) -Message "hook sessions should stop exporting the legacy load mode env"
    Assert-True -Condition (-not $allSession.EnvironmentVariables.ContainsKey("XEDIT_CLI_HOOK_PLUGINS")) -Message "hook sessions should stop exporting the legacy plugin list env"
    Assert-Equal -Actual $allSession.EnvironmentVariables.Keys.Count -Expected 2 -Message "hook sessions should now only export session identity metadata"
    Assert-Equal -Actual $allSession.SessionPluginsFilePath -Expected (Join-Path $allSession.SessionPath 'plugins.txt') -Message "hook sessions should materialize a session plugins file"
    Assert-True -Condition (Test-Path $allSession.SessionPluginsFilePath -PathType Leaf) -Message "hook sessions should write plugins.txt inside the session directory"
    $allSessionPlugins = Get-Content -Path $allSession.SessionPluginsFilePath
    Assert-Equal -Actual $allSessionPlugins.Count -Expected 1 -Message "hook sessions should preserve one plugin line when one is provided"

    $dedupedSession = New-XeditCliHookSession -PluginLines @("*Example.esm", "*Example.esm", "*Another.esp")
    $dedupedSessionPlugins = Get-Content -Path $dedupedSession.SessionPluginsFilePath
    Assert-Equal -Actual $dedupedSessionPlugins.Count -Expected 2 -Message "hook sessions should deduplicate repeated plugin lines in the session plugins file"
    Assert-Equal -Actual $dedupedSessionPlugins[0] -Expected '*Example.esm' -Message "hook sessions should preserve the first normalized plugin line"
    Assert-Equal -Actual $dedupedSessionPlugins[1] -Expected '*Another.esp' -Message "hook sessions should preserve the second normalized plugin line"

    $script:CapturedLaunch = $null
    $script:CapturedDetectionPath = $null
    $script:CapturedHookDeployment = $null
    $script:CapturedMo2Request = $null
    $detectionPath = Join-Path (Split-Path -Path $launcherPath -Parent) 'ResolvedTarget.exe'

    function Get-XeditCliNormalizedLauncherCommand {
        param(
            [string]$LauncherPath,
            [string]$GameModeArgument
        )

        return [pscustomobject]@{
            FilePath = $LauncherPath
            ArgumentList = @($GameModeArgument)
            DetectionPath = $detectionPath
            WorkingDirectory = Split-Path -Path $LauncherPath -Parent
        }
    }

    function Start-XeditCliLauncherProcess {
        param(
            [string]$LauncherPath,
            [string[]]$ArgumentList,
            [string]$WorkingDirectory,
            [hashtable]$EnvironmentVariables
        )

        $script:CapturedLaunch = [pscustomobject]@{
            LauncherPath = $LauncherPath
            ArgumentList = @($ArgumentList)
            WorkingDirectory = $WorkingDirectory
            EnvironmentVariables = $EnvironmentVariables
        }

        return [pscustomobject]@{ Id = 42 }
    }

    function Get-XeditCliLaunchedProcessId {
        param(
            $WrapperProcess,
            [string]$LauncherPath,
            [datetime]$StartedAt,
            [int[]]$KnownProcessIds
        )

        $script:CapturedDetectionPath = $LauncherPath
        return 4242
    }

    function Copy-XeditCliHookBridgeForRealLaunch {
        param(
            [string]$XeditExecutablePath
        )

        $script:CapturedHookDeployment = $XeditExecutablePath
        return [pscustomobject]@{
            SourcePath = 'C:\bridge\xEditHookBridge.dll'
            TargetPath = 'C:\game\Tools\Mod Organizer\hook.dll'
        }
    }

    function Invoke-Mo2ControlPlaneClientRequest {
        param(
            [hashtable]$Request,
            [string]$LiveRoot
        )

        $script:CapturedMo2Request = [pscustomobject]@{
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
            pid = 9898
            session_id = [string]$Request.session_id
        } | ConvertTo-Json -Depth 10 | Set-Content -Path $stateFile

        return [ordered]@{
            ok = $true
            result = [ordered]@{
                launch_id = 'launch-hook-test'
                pid = 7878
                status = 'running'
                artifacts = [ordered]@{
                    backend = 'organizer'
                }
            }
        }
    }

    function Resolve-XeditCliPluginSource {
        param(
            [string]$PluginFilePath,
            [string]$ProfilePluginFilePath
        )

        if ([string]::IsNullOrWhiteSpace($PluginFilePath)) {
            return [pscustomobject]@{
                SourcePluginFilePath = $ProfilePluginFilePath
                PluginLines = @('*ProfileOnly.esm', '*ProfilePatch.esp')
            }
        }

        return [pscustomobject]@{
            SourcePluginFilePath = $PluginFilePath
            PluginLines = @('*Example.esm', '*Another.esp')
        }
    }

    $launchOutput = & {
        Invoke-XeditCliProcessLaunch -Arguments @(
            "--launcher-path",
            $launcherPath,
            "--game-mode",
            "Fallout4",
            "--plugins-file",
            $pluginsFilePath
        )
    } 6>&1

    $launchMessages = @($launchOutput | ForEach-Object {
        if ($_ -is [System.Management.Automation.InformationRecord]) {
            [string]$_.MessageData
        }
        else {
            [string]$_
        }
    })

    Assert-True -Condition ($null -ne $script:CapturedLaunch) -Message "process launch should reach the launcher seam"
    Assert-True -Condition (-not $script:CapturedLaunch.EnvironmentVariables.ContainsKey('XEDIT_CLI_HOOK_LOAD_MODE')) -Message "process launch should stop passing the hook load mode into the launcher environment"
    Assert-True -Condition (-not $script:CapturedLaunch.EnvironmentVariables.ContainsKey('XEDIT_CLI_HOOK_PLUGINS')) -Message "process launch should stop passing plugin filenames through the launcher environment"
    $capturedSessionPluginsPath = Join-Path $script:CapturedLaunch.EnvironmentVariables['XEDIT_CLI_HOOK_SESSION_PATH'] 'plugins.txt'
    Assert-True -Condition ($script:CapturedLaunch.ArgumentList -contains ('-P:' + $capturedSessionPluginsPath)) -Message "process launch should pass the session plugins file to xEdit"
    Assert-True -Condition (Test-Path $capturedSessionPluginsPath -PathType Leaf) -Message "process launch should always create a session plugins file"
    Assert-Equal -Actual $script:CapturedDetectionPath -Expected $detectionPath -Message "process launch should pass the normalized detection target into PID discovery"
    Assert-True -Condition (($launchMessages | Where-Object { $_ -match "^hook-session-id:\s*.+$" }).Count -gt 0) -Message "process launch output should surface a hook session id for diagnostics"
    Assert-True -Condition (($launchMessages | Where-Object { $_ -match "^hook-session-path:\s*.+$" }).Count -gt 0) -Message "process launch output should surface a hook session path for diagnostics"
    Assert-True -Condition ($script:CapturedLaunch.EnvironmentVariables["XEDIT_CLI_HOOK_SESSION_PATH"] -like ($allSession.SessionPath.Substring(0, $allSession.SessionPath.LastIndexOf('\')) + '*')) -Message "hook session paths should stay rooted under the diagnostic session base"

    $script:CapturedLaunch = $null
    $script:CapturedDetectionPath = $null
    $script:CapturedHookDeployment = $null

    $realLaunchOutput = & {
        Invoke-XeditCliProcessLaunch -Arguments @(
            "--launcher-path",
            $launcherPath,
            "--game-mode",
            "Fallout4",
            "--mo-profile",
            "CK与调试"
        )
    } 6>&1

    $realLaunchMessages = @($realLaunchOutput | ForEach-Object {
        if ($_ -is [System.Management.Automation.InformationRecord]) {
            [string]$_.MessageData
        }
        else {
            [string]$_
        }
    })

    Assert-Equal -Actual $script:CapturedHookDeployment -Expected $detectionPath -Message "real hook launch should deploy the built bridge next to the resolved xEdit executable"
    Assert-True -Condition ($null -ne $script:CapturedMo2Request) -Message "real hook launch should route through the live MO2 control plane"
    Assert-Equal -Actual $script:CapturedMo2Request.Request.payload.target.args.Count -Expected 3 -Message "real hook launch should append the MO profile and session plugins arguments"
    Assert-Equal -Actual $script:CapturedMo2Request.Request.payload.target.args[1] -Expected '-moprofile:"CK与调试"' -Message "real hook launch should append the upstream MO profile switch"
    Assert-Equal -Actual $script:CapturedMo2Request.Request.payload.target.args[2] -Expected ('-P:' + (Join-Path ([string]$script:CapturedMo2Request.Request.payload.session.path) 'plugins.txt')) -Message "real hook launch should always append the session plugins path"
    Assert-Equal -Actual $script:CapturedMo2Request.Request.payload.transport.target_path -Expected $expectedPwshPath -Message "real hook launch should target pwsh.exe for the MO2 VFS launcher transport path"
    $wrapperPath = [string]$script:CapturedMo2Request.Request.payload.transport.args[4]
    Assert-True -Condition (Test-Path $wrapperPath -PathType Leaf) -Message "real hook launch should materialize a wrapper script for organizer-backed launch"
    $wrapperContent = Get-Content -Path $wrapperPath -Raw
    Assert-True -Condition ($wrapperContent -match [regex]::Escape($expectedLauncherScriptPath)) -Message "real hook launch should invoke the VFS launcher PowerShell entrypoint"
    Assert-True -Condition ($wrapperContent -match [regex]::Escape('-P:')) -Message "real hook launch should forward the session plugins file through the wrapper transport"
    Assert-True -Condition (($realLaunchMessages | Where-Object { $_ -match '^hook-dll-path:\s*.+hook\.dll$' }).Count -gt 0) -Message "real hook launch output should surface the deployed hook path"
    Assert-True -Condition (($realLaunchMessages | Where-Object { $_ -match '^mo2-launch-backend:\s*organizer$' }).Count -gt 0) -Message "real hook launch output should surface the organizer backend"
}
finally {
    if ($launcherPath) {
        $launcherRoot = Split-Path -Path $launcherPath -Parent
        if (Test-Path $launcherRoot) {
            Remove-Item -Path $launcherRoot -Recurse -Force
        }
    }

    if ($pluginsFilePath) {
        $pluginsRoot = Split-Path -Path $pluginsFilePath -Parent
        if (Test-Path $pluginsRoot) {
            Remove-Item -Path $pluginsRoot -Recurse -Force
        }
    }
}

exit 0

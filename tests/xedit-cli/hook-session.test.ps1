$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$commonLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/common.ps1"
$hookSessionLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/hook-session.ps1"
$processLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/process.ps1"

. $commonLibPath
. $hookSessionLibPath
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

$launcherPath = New-TestLauncherPath

try {
    $allPolicy = Get-XeditCliNormalizedSelectionPolicy -Options @{ "--load-mode" = "all" }
    $allSession = New-XeditCliHookSession -SelectionPolicy $allPolicy

    Assert-True -Condition ($allSession.SessionId -match '^[0-9a-f]{32}$') -Message "hook sessions should create a stable diagnostic session id"
    Assert-True -Condition ([System.IO.Path]::IsPathRooted($allSession.SessionPath)) -Message "hook sessions should create a rooted diagnostic session path"
    Assert-True -Condition (Test-Path $allSession.SessionPath -PathType Container) -Message "hook sessions should create the diagnostic session directory"
    Assert-Equal -Actual $allSession.EnvironmentVariables["XEDIT_CLI_HOOK_LOAD_MODE"] -Expected "all" -Message "all mode should flow into the hook environment"
    Assert-True -Condition ($allSession.EnvironmentVariables.ContainsKey("XEDIT_CLI_HOOK_SESSION_ID")) -Message "hook sessions should include a diagnostic session id"
    Assert-True -Condition ($allSession.EnvironmentVariables.ContainsKey("XEDIT_CLI_HOOK_SESSION_PATH")) -Message "hook sessions should include a diagnostic session path"
    Assert-True -Condition (-not $allSession.EnvironmentVariables.ContainsKey("XEDIT_CLI_HOOK_PLUGINS")) -Message "all mode should not emit an explicit plugin list"
    Assert-Equal -Actual $allSession.EnvironmentVariables.Keys.Count -Expected 3 -Message "all mode should produce a minimal policy payload"

    $onlyPolicy = Get-XeditCliNormalizedSelectionPolicy -Options @{ "--load-mode" = "only"; "--plugin" = @("Example.esm", "Example.esm", "Another.esp") }
    $onlySession = New-XeditCliHookSession -SelectionPolicy $onlyPolicy

    Assert-Equal -Actual $onlySession.EnvironmentVariables["XEDIT_CLI_HOOK_PLUGINS"] -Expected "Example.esm|Another.esp" -Message "only mode should emit deduplicated plugin filenames"

    $excludePolicy = Get-XeditCliNormalizedSelectionPolicy -Options @{ "--load-mode" = "exclude"; "--plugin" = @("Skip.esm", "Skip.esm", "SkipToo.esp") }
    $excludeSession = New-XeditCliHookSession -SelectionPolicy $excludePolicy

    Assert-Equal -Actual $excludeSession.EnvironmentVariables["XEDIT_CLI_HOOK_PLUGINS"] -Expected "Skip.esm|SkipToo.esp" -Message "exclude mode should emit deduplicated plugin filenames"
    Assert-True -Condition (-not $excludeSession.EnvironmentVariables.ContainsKey("XEDIT_CLI_HOOK_ALL_PLUGINS")) -Message "hook payload should not try to reproduce the full MO2 plugin list"

    $script:CapturedLaunch = $null
    $script:CapturedDetectionPath = $null
    $script:CapturedHookDeployment = $null
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

    $launchOutput = & {
        Invoke-XeditCliProcessLaunch -Arguments @(
            "--launcher-path",
            $launcherPath,
            "--game-mode",
            "Fallout4",
            "--load-mode",
            "only",
            "--plugin",
            "Example.esm",
            "--plugin",
            "Example.esm",
            "--plugin",
            "Another.esp"
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
    Assert-Equal -Actual $script:CapturedLaunch.EnvironmentVariables["XEDIT_CLI_HOOK_LOAD_MODE"] -Expected "only" -Message "process launch should pass the hook load mode into the launcher environment"
    Assert-Equal -Actual $script:CapturedLaunch.EnvironmentVariables["XEDIT_CLI_HOOK_PLUGINS"] -Expected "Example.esm|Another.esp" -Message "process launch should pass deduplicated plugin filenames into the launcher environment"
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
            "--load-mode",
            "all",
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
    Assert-Equal -Actual $script:CapturedLaunch.ArgumentList.Count -Expected 2 -Message "real hook launch should append one extra xEdit argument for the MO profile"
    Assert-Equal -Actual $script:CapturedLaunch.ArgumentList[1] -Expected '-moprofile:"CK与调试"' -Message "real hook launch should append the upstream MO profile switch"
    Assert-True -Condition (($realLaunchMessages | Where-Object { $_ -match '^hook-dll-path:\s*.+hook\.dll$' }).Count -gt 0) -Message "real hook launch output should surface the deployed hook path"
}
finally {
    if ($launcherPath) {
        $launcherRoot = Split-Path -Path $launcherPath -Parent
        if (Test-Path $launcherRoot) {
            Remove-Item -Path $launcherRoot -Recurse -Force
        }
    }
}

exit 0

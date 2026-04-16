$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$cliPath = Join-Path $repoRoot "tools/xedit-cli/bin/xedit-cli.ps1"
$commonLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/common.ps1"
$hookSessionLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/hook-session.ps1"
$processLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/process.ps1"

. $commonLibPath
. $hookSessionLibPath
. $processLibPath

function Invoke-Cli {
    param(
        [string[]]$Arguments
    )

    $output = & pwsh -NoProfile -File $cliPath @Arguments 2>&1

    [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = ($output | ForEach-Object { $_.ToString() }) -join "`n"
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
    $tempRoot = Join-Path $env:TEMP ("xedit-cli-module-selection-" + [guid]::NewGuid().ToString("N"))
    $null = New-Item -ItemType Directory -Path $tempRoot -Force
    $launcherPath = Join-Path $tempRoot "launch-xedit.cmd"
    Set-Content -Path $launcherPath -Value "@echo off"
    return $launcherPath
}

$launcherPath = New-TestLauncherPath

try {
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

    $launchAllExitCode = Invoke-XeditCliProcessLaunch -Arguments @(
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "Fallout4",
        "--load-mode",
        "all"
    )

    Assert-Equal -Actual $launchAllExitCode -Expected 0 -Message "process launch should accept --load-mode all"
    Assert-True -Condition ($null -ne $script:CapturedLaunch) -Message "process launch should reach the launcher seam when --load-mode all is valid"

    $missingLoadModeExitCode = Invoke-XeditCliProcessLaunch -Arguments @(
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "Fallout4"
    )

    Assert-Equal -Actual $missingLoadModeExitCode -Expected 1 -Message "process launch should reject a missing --load-mode"

    $allWithPluginExitCode = Invoke-XeditCliProcessLaunch -Arguments @(
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "Fallout4",
        "--load-mode",
        "all",
        "--plugin",
        "Example.esp"
    )

    Assert-Equal -Actual $allWithPluginExitCode -Expected 1 -Message "--load-mode all should reject any --plugin"

    $onlyWithoutPluginExitCode = Invoke-XeditCliProcessLaunch -Arguments @(
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "Fallout4",
        "--load-mode",
        "only"
    )

    Assert-Equal -Actual $onlyWithoutPluginExitCode -Expected 1 -Message "--load-mode only should require one or more --plugin values"

    $excludeWithoutPluginExitCode = Invoke-XeditCliProcessLaunch -Arguments @(
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "Fallout4",
        "--load-mode",
        "exclude"
    )

    Assert-Equal -Actual $excludeWithoutPluginExitCode -Expected 1 -Message "--load-mode exclude should require one or more --plugin values"

    $blankPluginOptions = ConvertTo-XeditCliOptionMap -Arguments @(
        "--load-mode",
        "only",
        "--plugin",
        "   "
    ) -RepeatableNames @("--plugin")

    $blankPluginPolicy = Get-XeditCliNormalizedSelectionPolicy -Options $blankPluginOptions
    Assert-True -Condition ($null -eq $blankPluginPolicy) -Message "whitespace-only plugin values should be rejected"

    $selectionOptions = ConvertTo-XeditCliOptionMap -Arguments @(
        "--load-mode",
        "only",
        "--plugin",
        "Example Plugin.esm",
        "--plugin",
        "Example Plugin.esm",
        "--plugin",
        "AnotherPlugin.esp"
    ) -RepeatableNames @("--plugin")

    $selectionPolicy = Get-XeditCliNormalizedSelectionPolicy -Options $selectionOptions

    Assert-Equal -Actual $selectionPolicy.LoadMode -Expected "only" -Message "selection policy should normalize the load mode"
    Assert-Equal -Actual $selectionPolicy.Plugins.Count -Expected 2 -Message "duplicate --plugin values should be deduplicated"
    Assert-Equal -Actual $selectionPolicy.Plugins[0] -Expected "Example Plugin.esm" -Message "plugin names should be preserved as exact filenames"
    Assert-Equal -Actual $selectionPolicy.Plugins[1] -Expected "AnotherPlugin.esp" -Message "plugin ordering should preserve the first occurrence of each plugin"
    Assert-Equal -Actual $script:CapturedDetectionPath -Expected $detectionPath -Message "process launch should resolve and pass the normalized detection target to PID discovery"

    $missingMoProfileValue = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "Fallout4",
        "--load-mode",
        "all",
        "--mo-profile"
    )

    Assert-Equal -Actual $missingMoProfileValue.ExitCode -Expected 1 -Message "the CLI entrypoint should reject a missing --mo-profile value"
    Assert-True -Condition ($missingMoProfileValue.Output -match [regex]::Escape("Missing value for option: --mo-profile")) -Message "the CLI entrypoint should surface the missing --mo-profile value clearly"

    $blankMoProfileOptions = ConvertTo-XeditCliOptionMap -Arguments @(
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "Fallout4",
        "--load-mode",
        "all",
        "--mo-profile",
        "   "
    )

    $blankMoProfileExitCode = Invoke-XeditCliProcessLaunch -Arguments @(
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "Fallout4",
        "--load-mode",
        "all",
        "--mo-profile",
        "   "
    )

    Assert-Equal -Actual $blankMoProfileExitCode -Expected 1 -Message "process launch should reject a whitespace-only --mo-profile"

    $cliMissingLoadMode = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "Fallout4"
    )

    Assert-Equal -Actual $cliMissingLoadMode.ExitCode -Expected 1 -Message "the CLI entrypoint should reject missing --load-mode"
    Assert-True -Condition ($cliMissingLoadMode.Output -match [regex]::Escape("Missing required options: --load-mode")) -Message "the CLI entrypoint should surface the missing --load-mode error"

    $cliMissingPluginValue = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "Fallout4",
        "--load-mode",
        "only",
        "--plugin",
        "--plugin",
        "Example.esp"
    )

    Assert-Equal -Actual $cliMissingPluginValue.ExitCode -Expected 1 -Message "the CLI entrypoint should reject a missing --plugin value"
    Assert-True -Condition ($cliMissingPluginValue.Output -match [regex]::Escape("Missing value for option: --plugin")) -Message "the CLI entrypoint should surface the missing --plugin value clearly"

    $cliAllWithPlugin = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "Fallout4",
        "--load-mode",
        "all",
        "--plugin",
        "Example.esp"
    )

    Assert-Equal -Actual $cliAllWithPlugin.ExitCode -Expected 1 -Message "the CLI entrypoint should reject --plugin when --load-mode is all"
    Assert-True -Condition ($cliAllWithPlugin.Output -match [regex]::Escape("Load mode 'all' does not accept --plugin")) -Message "the CLI entrypoint should surface the all-plus-plugin contract clearly"

    $cliWhitespacePlugin = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "Fallout4",
        "--load-mode",
        "only",
        "--plugin",
        "   "
    )

    Assert-Equal -Actual $cliWhitespacePlugin.ExitCode -Expected 1 -Message "the CLI entrypoint should reject whitespace-only plugin values"
    Assert-True -Condition ($cliWhitespacePlugin.Output -match [regex]::Escape("Plugin names must be non-empty filenames")) -Message "the CLI entrypoint should surface whitespace-only plugin rejection clearly"
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

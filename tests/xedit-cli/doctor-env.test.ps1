$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path
$cliPath = Join-Path $repoRoot "tools/xedit-cli/bin/xedit-cli.ps1"
$commonLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/common.ps1"

. $commonLibPath

function New-XeditCliFixtureExecutable {
    param(
        [string]$TempRoot,
        [string]$BinaryName,
        [string]$ProjectName = [System.IO.Path]::GetFileNameWithoutExtension($BinaryName),
        [string]$AssemblyName = [System.IO.Path]::GetFileNameWithoutExtension($BinaryName),
        [string]$ProductName = "xEdit",
        [string]$FileDescription = [System.IO.Path]::GetFileNameWithoutExtension($BinaryName),
        [string]$CompanyName = "ElminsterAU"
    )

    $projectRoot = Join-Path $TempRoot $ProjectName
    $publishRoot = Join-Path $projectRoot "publish"

    $null = New-Item -ItemType Directory -Path $projectRoot -Force

    Set-Content -Path (Join-Path $projectRoot "$AssemblyName.csproj") -Value @"
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <RuntimeIdentifier>win-x64</RuntimeIdentifier>
    <PublishSingleFile>true</PublishSingleFile>
    <SelfContained>false</SelfContained>
    <AssemblyName>$AssemblyName</AssemblyName>
    <Product>$ProductName</Product>
    <FileDescription>$FileDescription</FileDescription>
    <Company>$CompanyName</Company>
  </PropertyGroup>
</Project>
"@

    Set-Content -Path (Join-Path $projectRoot "Program.cs") -Value @'
Thread.Sleep(TimeSpan.FromSeconds(5));
return 0;
'@

    $publishOutput = & dotnet publish $projectRoot -nologo -v quiet -c Release -o $publishRoot 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build xEdit doctor fixture executable ${BinaryName}: $($publishOutput -join "`n")"
    }

    $fixtureExecutablePath = Join-Path $publishRoot $BinaryName
    if (-not (Test-Path $fixtureExecutablePath)) {
        throw "Failed to locate built xEdit doctor fixture executable: $fixtureExecutablePath"
    }

    return $fixtureExecutablePath
}

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

$missingInputs = Invoke-Cli -Arguments @("doctor", "env")
if ($missingInputs.ExitCode -eq 0) {
    throw "doctor env should fail when required inputs are missing"
}

if ($missingInputs.Output -notmatch [regex]::Escape("Missing required options: --launcher-path, --game-mode")) {
    throw "doctor env should explain which required options are missing"
}

$gameModeMap = Get-XeditCliGameModeMap
if ($null -eq $gameModeMap) {
    throw "common.ps1 should expose a shared game-mode map"
}

foreach ($mapping in @(
    @{ Name = "Fallout4"; Argument = "-FO4" },
    @{ Name = "Skyrim"; Argument = "-TES5" },
    @{ Name = "SkyrimSE"; Argument = "-SSE" },
    @{ Name = "Starfield"; Argument = "-SF1" }
)) {
    if ($gameModeMap[$mapping.Name] -ne $mapping.Argument) {
        throw "game-mode map should contain $($mapping.Name) -> $($mapping.Argument)"
    }
}

$tempRoot = Join-Path $env:TEMP ("xedit-cli-doctor-env-" + [guid]::NewGuid().ToString("N"))
$null = New-Item -ItemType Directory -Path $tempRoot -Force

try {
    $fo4LauncherPath = New-XeditCliFixtureExecutable -TempRoot $tempRoot -BinaryName "FO4Edit.exe"
    $sseLauncherPath = New-XeditCliFixtureExecutable -TempRoot $tempRoot -BinaryName "SSEEdit.exe"
    $launcherPath = Join-Path $tempRoot "launch-xedit.bat"
    Set-Content -Path $launcherPath -Value @'
@echo off
FO4Edit.exe
'@

    $cmdLauncherPath = Join-Path $tempRoot "launch-xedit.cmd"
    Set-Content -Path $cmdLauncherPath -Value @'
@echo off
SSEEdit.exe
'@

    $exeLauncherPath = New-XeditCliFixtureExecutable -TempRoot $tempRoot -BinaryName "SF1Edit64.exe"
    Copy-Item -Path $fo4LauncherPath -Destination (Join-Path $tempRoot "FO4Edit.exe")
    Copy-Item -Path $sseLauncherPath -Destination (Join-Path $tempRoot "SSEEdit.exe")

    $spoofedLauncherPath = Join-Path (Join-Path $tempRoot "spoof") "FO4Edit.exe"
    $null = New-Item -ItemType Directory -Path (Split-Path -Path $spoofedLauncherPath -Parent) -Force
    Copy-Item -Path "$env:SystemRoot\System32\cmd.exe" -Destination $spoofedLauncherPath
    $spoofedMetadataLauncherPath = New-XeditCliFixtureExecutable -TempRoot $tempRoot -ProjectName "SpoofedMetadataFo4Edit" -BinaryName "FO4Edit.exe" -AssemblyName "FO4Edit" -ProductName "xEdit" -FileDescription "FO4Edit" -CompanyName "Contoso"

    $missingGameMode = Invoke-Cli -Arguments @(
        "doctor",
        "env",
        "--launcher-path",
        $launcherPath
    )

    if ($missingGameMode.ExitCode -eq 0) {
        throw "doctor env should reject a missing --game-mode even when launcher-path is present"
    }

    if ($missingGameMode.Output -notmatch [regex]::Escape("Missing required options: --game-mode")) {
        throw "doctor env should explain when --game-mode is missing"
    }

    foreach ($supportedMode in @(
        @{ Name = "Fallout4"; Argument = "-FO4"; LauncherPath = $launcherPath },
        @{ Name = "Skyrim"; Argument = "-TES5"; LauncherPath = $cmdLauncherPath },
        @{ Name = "SkyrimSE"; Argument = "-SSE"; LauncherPath = $cmdLauncherPath },
        @{ Name = "Starfield"; Argument = "-SF1"; LauncherPath = $exeLauncherPath }
    )) {
        $success = Invoke-Cli -Arguments @(
            "doctor",
            "env",
            "--launcher-path",
            $supportedMode.LauncherPath,
            "--game-mode",
            $supportedMode.Name
        )

        if ($success.ExitCode -ne 0) {
            throw "doctor env should accept supported game mode $($supportedMode.Name)"
        }

        foreach ($phrase in @(
            "doctor env",
            "status: ok",
            "game-mode: $($supportedMode.Name) ($($supportedMode.Argument))",
            "launcher-path: $($supportedMode.LauncherPath)"
        )) {
            if ($success.Output -notmatch [regex]::Escape($phrase)) {
                throw "doctor env summary is missing phrase for $($supportedMode.Name): $phrase"
            }
        }
    }

    $unsupportedMode = Invoke-Cli -Arguments @(
        "doctor",
        "env",
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "Oblivion"
    )

    if ($unsupportedMode.ExitCode -eq 0) {
        throw "doctor env should reject unsupported game modes"
    }

    if ($unsupportedMode.Output -notmatch [regex]::Escape("Unsupported game mode: Oblivion. Supported game modes: Fallout4, Skyrim, SkyrimSE, Starfield")) {
        throw "doctor env should explain unsupported game modes cleanly"
    }

    $badLauncher = Join-Path $tempRoot "launch-xedit.txt"
    Set-Content -Path $badLauncher -Value "placeholder"

    $badLauncherResult = Invoke-Cli -Arguments @(
        "doctor",
        "env",
        "--launcher-path",
        $badLauncher,
        "--game-mode",
        "SkyrimSE"
    )

    if ($badLauncherResult.ExitCode -eq 0) {
        throw "doctor env should reject unsupported launcher extensions"
    }

    if ($badLauncherResult.Output -notmatch [regex]::Escape("Launcher path must end with .bat, .cmd, or .exe: $badLauncher")) {
        throw "doctor env should explain unsupported launcher extensions"
    }

    $spoofedLauncherResult = Invoke-Cli -Arguments @(
        "doctor",
        "env",
        "--launcher-path",
        $spoofedLauncherPath,
        "--game-mode",
        "Fallout4"
    )

    if ($spoofedLauncherResult.ExitCode -eq 0) {
        throw "doctor env should reject explicit launchers that are not xEdit-compatible even when they use an xEdit image name"
    }

    if ($spoofedLauncherResult.Output -notmatch [regex]::Escape("Launcher executable is not xEdit-compatible: $spoofedLauncherPath")) {
        throw "doctor env should validate launcher usability with the same explicit-mode rules as process launch"
    }

    $spoofedMetadataLauncherResult = Invoke-Cli -Arguments @(
        "doctor",
        "env",
        "--launcher-path",
        $spoofedMetadataLauncherPath,
        "--game-mode",
        "Fallout4"
    )

    if ($spoofedMetadataLauncherResult.ExitCode -ne 0) {
        throw "doctor env should accept explicit launchers whose metadata identifies them as xEdit even when provenance fields differ"
    }

    foreach ($phrase in @(
        "doctor env",
        "status: ok",
        "game-mode: Fallout4 (-FO4)",
        "launcher-path: $spoofedMetadataLauncherPath"
    )) {
        if ($spoofedMetadataLauncherResult.Output -notmatch [regex]::Escape($phrase)) {
            throw "doctor env summary is missing phrase for metadata-identified xEdit launchers: $phrase"
        }
    }

    $nonXeditProcess = Start-Process -FilePath "pwsh" -ArgumentList @("-NoProfile", "-Command", "Start-Sleep -Seconds 30") -PassThru
    try {
        $nonXeditPid = Invoke-Cli -Arguments @(
            "doctor",
            "env",
            "--launcher-path",
            $launcherPath,
            "--game-mode",
            "SkyrimSE",
            "--xedit-pid",
            $nonXeditProcess.Id.ToString()
        )

        if ($nonXeditPid.ExitCode -eq 0) {
            throw "doctor env should reject a live pid that is not an xEdit process"
        }

        if ($nonXeditPid.Output -notmatch [regex]::Escape("Process is not an xEdit instance: $($nonXeditProcess.Id)")) {
            throw "doctor env should explain when a live pid is not xEdit"
        }
    }
    finally {
        if (-not $nonXeditProcess.HasExited) {
            Stop-Process -Id $nonXeditProcess.Id -Force
            $nonXeditProcess.WaitForExit()
        }
    }

    $wrapperProcess = Start-Process -FilePath "pwsh" -ArgumentList @("-NoProfile", "-Command", "& '$exeLauncherPath' /c ping -n 30 127.0.0.1 > nul") -PassThru
    try {
        Start-Sleep -Milliseconds 500

        $wrapperPid = Invoke-Cli -Arguments @(
            "doctor",
            "env",
            "--launcher-path",
            $launcherPath,
            "--game-mode",
            "SkyrimSE",
            "--xedit-pid",
            $wrapperProcess.Id.ToString()
        )

        if ($wrapperPid.ExitCode -eq 0) {
            throw "doctor env should reject a wrapper pid even when its command line references xEdit"
        }

        if ($wrapperPid.Output -notmatch [regex]::Escape("Process is not an xEdit instance: $($wrapperProcess.Id)")) {
            throw "doctor env should reject wrapper pids instead of treating command-line mentions as xEdit"
        }
    }
    finally {
        if (-not $wrapperProcess.HasExited) {
            Stop-Process -Id $wrapperProcess.Id -Force
            $wrapperProcess.WaitForExit()
        }
    }

    $missingPid = Invoke-Cli -Arguments @(
        "doctor",
        "env",
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "SkyrimSE",
        "--xedit-pid",
        "999999"
    )

    if ($missingPid.ExitCode -eq 0) {
        throw "doctor env should fail for a missing pid"
    }

    if ($missingPid.Output -notmatch [regex]::Escape("xEdit PID is not running: 999999")) {
        throw "doctor env should explain when the requested pid is missing"
    }

    $deadProcess = Start-Process -FilePath "pwsh" -ArgumentList @("-NoProfile", "-Command", "Start-Sleep -Milliseconds 100") -PassThru
    $deadProcess.WaitForExit()

    $deadPid = Invoke-Cli -Arguments @(
        "doctor",
        "env",
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "SkyrimSE",
        "--xedit-pid",
        $deadProcess.Id.ToString()
    )

    if ($deadPid.ExitCode -eq 0) {
        throw "doctor env should fail for a dead pid"
    }

    if ($deadPid.Output -notmatch [regex]::Escape("xEdit PID is not running: $($deadProcess.Id)")) {
        throw "doctor env should explain when the requested pid is dead"
    }

    $invalidPid = Invoke-Cli -Arguments @(
        "doctor",
        "env",
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "SkyrimSE",
        "--xedit-pid",
        "abc"
    )

    if ($invalidPid.ExitCode -eq 0) {
        throw "doctor env should fail for an invalid pid"
    }

    if ($invalidPid.Output -notmatch [regex]::Escape("Invalid xEdit PID: abc")) {
        throw "doctor env should distinguish invalid pid input from a dead pid"
    }

    $compactSummary = Invoke-Cli -Arguments @(
        "doctor",
        "env",
        "--launcher-path",
        $launcherPath,
        "--game-mode",
        "Skyrim"
    )

    if ($compactSummary.Output -match [regex]::Escape("PSModulePath") -or $compactSummary.Output -match [regex]::Escape("USERNAME=")) {
        throw "doctor env should emit a compact summary instead of raw environment noise"
    }
}
finally {
    if (Test-Path $exeLauncherPath) {
        Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $exeLauncherPath } | ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }

    if (Test-Path $tempRoot) {
        Remove-Item -Path $tempRoot -Recurse -Force
    }
}

Write-Host "doctor env checks passed."

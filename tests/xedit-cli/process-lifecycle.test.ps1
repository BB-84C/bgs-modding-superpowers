$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path
$cliPath = Join-Path $repoRoot "tools/xedit-cli/bin/xedit-cli.ps1"

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
using System.Diagnostics;

var exeName = Path.GetFileName(Environment.ProcessPath ?? AppDomain.CurrentDomain.FriendlyName);
var logPath = Environment.GetEnvironmentVariable("XEDIT_CLI_TEST_ARG_LOG");
if (!string.IsNullOrWhiteSpace(logPath))
{
    File.AppendAllText(logPath, exeName + "|" + string.Join(" ", args) + "|cwd=" + Environment.CurrentDirectory + Environment.NewLine);
}

if (exeName.Contains("loader", StringComparison.OrdinalIgnoreCase))
{
    if (args.Length == 0)
    {
        return 2;
    }

    var targetPath = args[0];
    if (!Path.IsPathRooted(targetPath))
    {
        targetPath = Path.Combine(Environment.CurrentDirectory, targetPath);
    }

    var startInfo = new ProcessStartInfo
    {
        FileName = targetPath,
        WorkingDirectory = Environment.CurrentDirectory,
        UseShellExecute = false
    };

    foreach (var argument in args.Skip(1))
    {
        startInfo.ArgumentList.Add(argument);
    }

    Process.Start(startInfo);
}

Thread.Sleep(TimeSpan.FromSeconds(30));
return 0;
'@

    $publishOutput = & dotnet publish $projectRoot -nologo -v quiet -c Release -o $publishRoot 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build xEdit process fixture executable ${BinaryName}: $($publishOutput -join "`n")"
    }

    $fixtureExecutablePath = Join-Path $publishRoot $BinaryName
    if (-not (Test-Path $fixtureExecutablePath)) {
        throw "Failed to locate built fixture executable: $fixtureExecutablePath"
    }

    return $fixtureExecutablePath
}

function Wait-ForLogMatch {
    param(
        [string]$LogPath,
        [string]$Pattern,
        [int]$TimeoutSeconds = 5
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if ((Test-Path $LogPath) -and ((Get-Content -Path $LogPath -Raw) -match $Pattern)) {
            return $true
        }

        Start-Sleep -Milliseconds 100
    } while ((Get-Date) -lt $deadline)

    return $false
}

function Get-MatchingLogLine {
    param(
        [string]$LogPath,
        [string]$Pattern,
        [int]$TimeoutSeconds = 5
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Test-Path $LogPath) {
            $match = Get-Content -Path $LogPath | Where-Object { $_ -match $Pattern } | Select-Object -Last 1
            if ($null -ne $match) {
                return $match
            }
        }

        Start-Sleep -Milliseconds 100
    } while ((Get-Date) -lt $deadline)

    return $null
}

$tempRoot = Join-Path $env:TEMP ("xedit-cli-process-lifecycle-" + [guid]::NewGuid().ToString("N"))
$null = New-Item -ItemType Directory -Path $tempRoot -Force
$normalizedTempRoot = (Get-Item -Path $tempRoot).FullName

$fixtureExecutablePaths = @()
$argLogPath = $null
$directLauncherPath = $null
$batWrapperPath = $null
$cmdWrapperPath = $null
$complexWrapperPath = $null
$helperOnlyWrapperPath = $null
$conflictingModeWrapperPath = $null
$subdirectoryWrapperPath = $null
$fo4EditPath = $null
$sseEditPath = $null
$sf1EditPath = $null
$loaderPath = $null
$subdirectoryLoaderPath = $null
$badExeLauncherPath = $null
$spoofedXeditPath = $null
$spoofedMetadataXeditPath = $null
$launchedPid = $null
$wrapperBatPid = $null
$wrapperCmdPid = $null
$subdirectoryWrapperPid = $null
$skyrimPid = $null
$skyrimSePid = $null
$starfieldPid = $null
$nonXeditPid = $null
$spoofedMetadataXeditPid = $null

try {
    $builtFo4EditPath = New-XeditCliFixtureExecutable -TempRoot $tempRoot -BinaryName "FO4Edit.exe"
    $fixtureExecutablePaths += $builtFo4EditPath
    $builtSseEditPath = New-XeditCliFixtureExecutable -TempRoot $tempRoot -BinaryName "SSEEdit.exe"
    $fixtureExecutablePaths += $builtSseEditPath
    $builtSf1EditPath = New-XeditCliFixtureExecutable -TempRoot $tempRoot -BinaryName "SF1Edit64.exe"
    $fixtureExecutablePaths += $builtSf1EditPath
    $builtLoaderPath = New-XeditCliFixtureExecutable -TempRoot $tempRoot -BinaryName "hdtTES5EditUTF8_loader.exe" -ProductName "Helper Loader" -FileDescription "Helper Loader" -CompanyName "Contoso"
    $fixtureExecutablePaths += $builtLoaderPath
    $builtSpoofedMetadataFo4EditPath = New-XeditCliFixtureExecutable -TempRoot $tempRoot -ProjectName "SpoofedMetadataFo4Edit" -BinaryName "FO4Edit.exe" -AssemblyName "FO4Edit" -ProductName "xEdit" -FileDescription "FO4Edit" -CompanyName "Contoso"
    $fixtureExecutablePaths += $builtSpoofedMetadataFo4EditPath
    $argLogPath = Join-Path $tempRoot "launch-args.log"
    $env:XEDIT_CLI_TEST_ARG_LOG = $argLogPath

    $fo4EditPath = Join-Path $tempRoot "FO4Edit.exe"
    $sseEditPath = Join-Path $tempRoot "SSEEdit.exe"
    $sf1EditPath = Join-Path $tempRoot "SF1Edit64.exe"
    $loaderPath = Join-Path $tempRoot "hdtTES5EditUTF8_loader.exe"
    $subdirectoryLoaderPath = Join-Path (Join-Path $tempRoot "helpers") "hdtTES5EditUTF8_loader.exe"
    $badExeLauncherPath = Join-Path $tempRoot "launcher-wrapper.exe"
    $spoofedXeditPath = Join-Path (Join-Path $tempRoot "spoof") "FO4Edit.exe"
    $spoofedMetadataXeditPath = Join-Path (Join-Path $tempRoot "spoof-metadata") "FO4Edit.exe"

    $null = New-Item -ItemType Directory -Path (Split-Path -Path $subdirectoryLoaderPath -Parent) -Force
    $null = New-Item -ItemType Directory -Path (Split-Path -Path $spoofedXeditPath -Parent) -Force
    $null = New-Item -ItemType Directory -Path (Split-Path -Path $spoofedMetadataXeditPath -Parent) -Force

    Copy-Item -Path $builtFo4EditPath -Destination $fo4EditPath
    Copy-Item -Path $builtSseEditPath -Destination $sseEditPath
    Copy-Item -Path $builtSf1EditPath -Destination $sf1EditPath
    Copy-Item -Path $builtLoaderPath -Destination $loaderPath
    Copy-Item -Path $builtLoaderPath -Destination $subdirectoryLoaderPath
    Copy-Item -Path "$env:SystemRoot\System32\cmd.exe" -Destination $badExeLauncherPath
    Copy-Item -Path "$env:SystemRoot\System32\cmd.exe" -Destination $spoofedXeditPath
    Copy-Item -Path $builtSpoofedMetadataFo4EditPath -Destination $spoofedMetadataXeditPath

    $missingMode = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $fo4EditPath
    )

    if ($missingMode.ExitCode -eq 0) {
        throw "process launch should reject a missing --game-mode option"
    }

    if ($missingMode.Output -notmatch [regex]::Escape("Missing required options: --launcher-path, --game-mode") -and
        $missingMode.Output -notmatch [regex]::Escape("Missing required options: --game-mode")) {
        throw "process launch should explain when --game-mode is missing"
    }

    $directLauncherPath = $fo4EditPath
    $launch = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $directLauncherPath,
        "--game-mode",
        "Fallout4"
    )

    if ($launch.ExitCode -ne 0) {
        throw "process launch should succeed for a direct .exe launcher with --game-mode"
    }

    if ($launch.Output -notmatch "xedit-pid:\s*(\d+)") {
        throw "process launch should report the launched pid"
    }

    $launchedPid = [int]$Matches[1]

    $liveProcess = Get-Process -Id $launchedPid -ErrorAction SilentlyContinue
    if ($null -eq $liveProcess) {
        throw "process launch should return a live pid"
    }

    if ($liveProcess.Path -ne $fo4EditPath) {
        throw "process launch should return the direct .exe pid when launching xEdit directly"
    }

    if (-not (Wait-ForLogMatch -LogPath $argLogPath -Pattern '(?m)^FO4Edit\.exe\|-FO4\|cwd=.*$')) {
        throw "direct .exe launch should append the explicit Fallout 4 mode argument"
    }

    $status = Invoke-Cli -Arguments @(
        "process",
        "status",
        "--xedit-pid",
        $launchedPid.ToString()
    )

    if ($status.ExitCode -ne 0) {
        throw "process status should succeed for a live pid"
    }

    foreach ($phrase in @(
        "process status",
        "status: running",
        "xedit-pid: $launchedPid"
    )) {
        if ($status.Output -notmatch [regex]::Escape($phrase)) {
            throw "process status summary is missing phrase: $phrase"
        }
    }

    $waitTimeout = Invoke-Cli -Arguments @(
        "process",
        "wait",
        "--xedit-pid",
        $launchedPid.ToString(),
        "--timeout-seconds",
        "1"
    )

    if ($waitTimeout.ExitCode -ne 0) {
        throw "process wait should time out cleanly without failing"
    }

    foreach ($phrase in @(
        "process wait",
        "status: timeout",
        "xedit-pid: $launchedPid"
    )) {
        if ($waitTimeout.Output -notmatch [regex]::Escape($phrase)) {
            throw "process wait timeout summary is missing phrase: $phrase"
        }
    }

    $stop = Invoke-Cli -Arguments @(
        "process",
        "stop",
        "--xedit-pid",
        $launchedPid.ToString()
    )

    if ($stop.ExitCode -ne 0) {
        throw "process stop should succeed for a live pid"
    }

    foreach ($phrase in @(
        "process stop",
        "status: stopped",
        "xedit-pid: $launchedPid"
    )) {
        if ($stop.Output -notmatch [regex]::Escape($phrase)) {
            throw "process stop summary is missing phrase: $phrase"
        }
    }

    Start-Sleep -Milliseconds 300
    if (Get-Process -Id $launchedPid -ErrorAction SilentlyContinue) {
        throw "process stop should terminate the chosen process"
    }

    $skyrimLaunch = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $sseEditPath,
        "--game-mode",
        "Skyrim"
    )

    if ($skyrimLaunch.ExitCode -ne 0 -or $skyrimLaunch.Output -notmatch "xedit-pid:\s*(\d+)") {
        throw "process launch should support direct Skyrim normalization"
    }

    $skyrimPid = [int]$Matches[1]
    if (-not (Wait-ForLogMatch -LogPath $argLogPath -Pattern '(?m)^SSEEdit\.exe\|-TES5\|cwd=.*$')) {
        throw "direct Skyrim launch should append the explicit -TES5 mode argument"
    }

    Stop-Process -Id $skyrimPid -Force -ErrorAction SilentlyContinue
    $skyrimPid = $null
    Start-Sleep -Milliseconds 300

    $skyrimSeLaunch = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $sseEditPath,
        "--game-mode",
        "SkyrimSE"
    )

    if ($skyrimSeLaunch.ExitCode -ne 0 -or $skyrimSeLaunch.Output -notmatch "xedit-pid:\s*(\d+)") {
        throw "process launch should support direct SkyrimSE normalization"
    }

    $skyrimSePid = [int]$Matches[1]
    if (-not (Wait-ForLogMatch -LogPath $argLogPath -Pattern '(?m)^SSEEdit\.exe\|-SSE\|cwd=.*$')) {
        throw "direct SkyrimSE launch should append the explicit -SSE mode argument"
    }

    Stop-Process -Id $skyrimSePid -Force -ErrorAction SilentlyContinue
    $skyrimSePid = $null
    Start-Sleep -Milliseconds 300

    $starfieldLaunch = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $sf1EditPath,
        "--game-mode",
        "Starfield"
    )

    if ($starfieldLaunch.ExitCode -ne 0 -or $starfieldLaunch.Output -notmatch "xedit-pid:\s*(\d+)") {
        throw "process launch should support direct Starfield normalization"
    }

    $starfieldPid = [int]$Matches[1]
    if (-not (Wait-ForLogMatch -LogPath $argLogPath -Pattern '(?m)^SF1Edit64\.exe\|-SF1\|cwd=.*$')) {
        throw "direct Starfield 64-bit launch should append the explicit -SF1 mode argument"
    }

    Stop-Process -Id $starfieldPid -Force -ErrorAction SilentlyContinue
    $starfieldPid = $null
    Start-Sleep -Milliseconds 300

    $batWrapperPath = Join-Path $tempRoot "runFO4Edit.bat"
    Set-Content -Path $batWrapperPath -Value @'
@echo off
hdtTES5EditUTF8_loader.exe FO4Edit.exe
'@

    $wrapperBatLaunch = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $batWrapperPath,
        "--game-mode",
        "Fallout4"
    )

    if ($wrapperBatLaunch.ExitCode -ne 0) {
        throw "process launch should succeed for a simple .bat wrapper"
    }

    if ($wrapperBatLaunch.Output -notmatch "xedit-pid:\s*(\d+)") {
        throw "simple .bat wrapper launch should report the launched pid"
    }

    $wrapperBatPid = [int]$Matches[1]
    $wrapperBatProcess = Get-Process -Id $wrapperBatPid -ErrorAction SilentlyContinue
    $wrapperBatProcessName = if ($null -eq $wrapperBatProcess) { $null } elseif (-not [string]::IsNullOrWhiteSpace($wrapperBatProcess.Path)) { [System.IO.Path]::GetFileName($wrapperBatProcess.Path) } else { "$($wrapperBatProcess.ProcessName).exe" }
    if ($null -eq $wrapperBatProcess -or $wrapperBatProcessName -ne "FO4Edit.exe") {
        throw "simple .bat wrappers should normalize to the spawned xEdit process"
    }

    if (-not (Wait-ForLogMatch -LogPath $argLogPath -Pattern '(?m)^hdtTES5EditUTF8_loader\.exe\|.*-FO4\|cwd=.*$')) {
        throw "simple .bat wrappers should receive the mapped explicit mode argument"
    }

    Stop-Process -Id $wrapperBatPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300

    $cmdWrapperPath = Join-Path $tempRoot "runTES5Edit.cmd"
    Set-Content -Path $cmdWrapperPath -Value @'
@echo off
hdtTES5EditUTF8_loader.exe SSEEdit.exe
'@

    $wrapperCmdLaunch = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $cmdWrapperPath,
        "--game-mode",
        "Skyrim"
    )

    if ($wrapperCmdLaunch.ExitCode -ne 0) {
        throw "process launch should succeed for a simple .cmd wrapper"
    }

    if ($wrapperCmdLaunch.Output -notmatch "xedit-pid:\s*(\d+)") {
        throw "simple .cmd wrapper launch should report the launched pid"
    }

    $wrapperCmdPid = [int]$Matches[1]
    $wrapperCmdProcess = Get-Process -Id $wrapperCmdPid -ErrorAction SilentlyContinue
    $wrapperCmdProcessName = if ($null -eq $wrapperCmdProcess) { $null } elseif (-not [string]::IsNullOrWhiteSpace($wrapperCmdProcess.Path)) { [System.IO.Path]::GetFileName($wrapperCmdProcess.Path) } else { "$($wrapperCmdProcess.ProcessName).exe" }
    if ($null -eq $wrapperCmdProcess -or $wrapperCmdProcessName -ne "SSEEdit.exe") {
        throw "simple .cmd wrappers should normalize to the spawned xEdit process"
    }

    if (-not (Wait-ForLogMatch -LogPath $argLogPath -Pattern '(?m)^hdtTES5EditUTF8_loader\.exe\|.*-TES5\|cwd=.*$')) {
        throw "simple .cmd wrappers should receive the mapped explicit mode argument"
    }

    Stop-Process -Id $wrapperCmdPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300

    $subdirectoryWrapperPath = Join-Path $tempRoot "runFO4Edit-subdir.bat"
    Set-Content -Path $subdirectoryWrapperPath -Value @'
@echo off
helpers\hdtTES5EditUTF8_loader.exe FO4Edit.exe
'@

    $subdirectoryWrapperLaunch = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $subdirectoryWrapperPath,
        "--game-mode",
        "Fallout4"
    )

    if ($subdirectoryWrapperLaunch.ExitCode -ne 0) {
        throw "process launch should preserve wrapper-directory semantics for subdirectory helper wrappers"
    }

    if ($subdirectoryWrapperLaunch.Output -notmatch "xedit-pid:\s*(\d+)") {
        throw "subdirectory helper wrapper launch should report the launched pid"
    }

    $subdirectoryWrapperPid = [int]$Matches[1]
    $subdirectoryWrapperProcess = Get-Process -Id $subdirectoryWrapperPid -ErrorAction SilentlyContinue
    $subdirectoryWrapperProcessName = if ($null -eq $subdirectoryWrapperProcess) { $null } elseif (-not [string]::IsNullOrWhiteSpace($subdirectoryWrapperProcess.Path)) { [System.IO.Path]::GetFileName($subdirectoryWrapperProcess.Path) } else { "$($subdirectoryWrapperProcess.ProcessName).exe" }
    if ($null -eq $subdirectoryWrapperProcess -or $subdirectoryWrapperProcessName -ne "FO4Edit.exe") {
        throw "subdirectory helper wrappers should still launch the wrapper-relative xEdit target"
    }

    $subdirectoryWrapperLog = Get-MatchingLogLine -LogPath $argLogPath -Pattern '^hdtTES5EditUTF8_loader\.exe\|FO4Edit\.exe -FO4\|cwd=' 
    if ($null -eq $subdirectoryWrapperLog -or $subdirectoryWrapperLog -notmatch ('\|cwd=' + [regex]::Escape($normalizedTempRoot) + '$')) {
        throw "subdirectory helper wrappers should report the wrapper directory as cwd"
    }

    Stop-Process -Id $subdirectoryWrapperPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300

    $complexWrapperPath = Join-Path $tempRoot "run-complex-wrapper.bat"
    Set-Content -Path $complexWrapperPath -Value @'
@echo off
hdtTES5EditUTF8_loader.exe FO4Edit.exe
echo unsupported
'@

    $complexWrapperLaunch = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $complexWrapperPath,
        "--game-mode",
        "Fallout4"
    )

    if ($complexWrapperLaunch.ExitCode -eq 0) {
        throw "process launch should fail closed for unsupported wrapper shapes"
    }

    if ($complexWrapperLaunch.Output -notmatch [regex]::Escape("Unsupported launcher wrapper shape: $complexWrapperPath")) {
        throw "process launch should explain when a wrapper shape is unsupported"
    }

    $helperOnlyWrapperPath = Join-Path $tempRoot "run-helper-only.bat"
    Set-Content -Path $helperOnlyWrapperPath -Value @'
@echo off
hdtTES5EditUTF8_loader.exe
'@

    $helperOnlyLaunch = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $helperOnlyWrapperPath,
        "--game-mode",
        "Fallout4"
    )

    if ($helperOnlyLaunch.ExitCode -eq 0) {
        throw "process launch should fail closed for semantically unsupported helper wrappers"
    }

    if ($helperOnlyLaunch.Output -notmatch [regex]::Escape("Unsupported launcher wrapper command: $helperOnlyWrapperPath")) {
        throw "process launch should explain when a wrapper cannot be normalized into an explicit xEdit launch command"
    }

    $conflictingModeWrapperPath = Join-Path $tempRoot "run-conflicting-mode.bat"
    Set-Content -Path $conflictingModeWrapperPath -Value @'
@echo off
hdtTES5EditUTF8_loader.exe FO4Edit.exe -TES5
'@

    $conflictingModeLaunch = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $conflictingModeWrapperPath,
        "--game-mode",
        "Fallout4"
    )

    if ($conflictingModeLaunch.ExitCode -eq 0) {
        throw "process launch should reject wrappers that already contain a conflicting explicit mode switch"
    }

    if ($conflictingModeLaunch.Output -notmatch [regex]::Escape("Conflicting xEdit mode argument in launcher wrapper: $conflictingModeWrapperPath")) {
        throw "process launch should explain when a wrapper preempts the authoritative --game-mode"
    }

    $nonXeditProcess = Start-Process -FilePath "pwsh" -ArgumentList @("-NoProfile", "-Command", "Start-Sleep -Seconds 30") -PassThru
    $nonXeditPid = $nonXeditProcess.Id

    $badStatus = Invoke-Cli -Arguments @(
        "process",
        "status",
        "--xedit-pid",
        $nonXeditPid.ToString()
    )

    if ($badStatus.ExitCode -eq 0) {
        throw "process status should reject a live pid that is not xEdit"
    }

    if ($badStatus.Output -notmatch [regex]::Escape("Process is not an xEdit instance: $nonXeditPid")) {
        throw "process status should explain when the pid is not xEdit"
    }

    $badStop = Invoke-Cli -Arguments @(
        "process",
        "stop",
        "--xedit-pid",
        $nonXeditPid.ToString()
    )

    if ($badStop.ExitCode -eq 0) {
        throw "process stop should reject a live pid that is not xEdit"
    }

    if ($badStop.Output -notmatch [regex]::Escape("Process is not an xEdit instance: $nonXeditPid")) {
        throw "process stop should explain when the pid is not xEdit"
    }

    if (-not (Get-Process -Id $nonXeditPid -ErrorAction SilentlyContinue)) {
        throw "process stop should not terminate a non-xEdit pid when validation fails"
    }

    $spoofedXeditProcess = Start-Process -FilePath $spoofedXeditPath -ArgumentList "/c ping -n 30 127.0.0.1 > nul" -PassThru
    $spoofedXeditPid = $spoofedXeditProcess.Id
    try {
        $spoofedStatus = Invoke-Cli -Arguments @(
            "process",
            "status",
            "--xedit-pid",
            $spoofedXeditPid.ToString()
        )

        if ($spoofedStatus.ExitCode -eq 0) {
            throw "process status should reject a pid whose image name looks like xEdit but whose executable is not xEdit-compatible"
        }

        if ($spoofedStatus.Output -notmatch [regex]::Escape("Process is not an xEdit instance: $spoofedXeditPid")) {
            throw "process status should use stronger xEdit validation than image-name matching alone"
        }

        $spoofedWait = Invoke-Cli -Arguments @(
            "process",
            "wait",
            "--xedit-pid",
            $spoofedXeditPid.ToString(),
            "--timeout-seconds",
            "1"
        )

        if ($spoofedWait.ExitCode -eq 0) {
            throw "process wait should reject a pid whose image name looks like xEdit but whose executable is not xEdit-compatible"
        }

        if ($spoofedWait.Output -notmatch [regex]::Escape("Process is not an xEdit instance: $spoofedXeditPid")) {
            throw "process wait should use stronger xEdit validation than image-name matching alone"
        }

        $spoofedStop = Invoke-Cli -Arguments @(
            "process",
            "stop",
            "--xedit-pid",
            $spoofedXeditPid.ToString()
        )

        if ($spoofedStop.ExitCode -eq 0) {
            throw "process stop should reject a pid whose image name looks like xEdit but whose executable is not xEdit-compatible"
        }

        if ($spoofedStop.Output -notmatch [regex]::Escape("Process is not an xEdit instance: $spoofedXeditPid")) {
            throw "process stop should use stronger xEdit validation than image-name matching alone"
        }

        if (-not (Get-Process -Id $spoofedXeditPid -ErrorAction SilentlyContinue)) {
            throw "process stop should not terminate a spoofed xEdit image when validation fails"
        }
    }
    finally {
        if (-not $spoofedXeditProcess.HasExited) {
            Stop-Process -Id $spoofedXeditPid -Force -ErrorAction SilentlyContinue
            $spoofedXeditProcess.WaitForExit()
        }
    }

    $badLaunch = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $spoofedXeditPath,
        "--game-mode",
        "Fallout4"
    )

    if ($badLaunch.ExitCode -eq 0) {
        throw "process launch should fail closed before launching a non-xEdit executable whose image name looks like xEdit"
    }

    if ($badLaunch.Output -notmatch [regex]::Escape("Launcher executable is not xEdit-compatible: $spoofedXeditPath")) {
        throw "process launch should reject spoofed xEdit executable paths before launching them"
    }

    $spoofedMetadataXeditProcess = Start-Process -FilePath $spoofedMetadataXeditPath -PassThru
    $spoofedMetadataXeditPid = $spoofedMetadataXeditProcess.Id
    try {
        $spoofedMetadataStatus = Invoke-Cli -Arguments @(
            "process",
            "status",
            "--xedit-pid",
            $spoofedMetadataXeditPid.ToString()
        )

        if ($spoofedMetadataStatus.ExitCode -ne 0) {
            throw "process status should accept a pid whose executable metadata identifies it as xEdit"
        }

        foreach ($phrase in @(
            "process status",
            "status: running",
            "xedit-pid: $spoofedMetadataXeditPid"
        )) {
            if ($spoofedMetadataStatus.Output -notmatch [regex]::Escape($phrase)) {
                throw "process status summary is missing phrase for metadata-identified xEdit processes: $phrase"
            }
        }

        $spoofedMetadataWait = Invoke-Cli -Arguments @(
            "process",
            "wait",
            "--xedit-pid",
            $spoofedMetadataXeditPid.ToString(),
            "--timeout-seconds",
            "1"
        )

        if ($spoofedMetadataWait.ExitCode -ne 0) {
            throw "process wait should accept a pid whose executable metadata identifies it as xEdit"
        }

        foreach ($phrase in @(
            "process wait",
            "status: timeout",
            "xedit-pid: $spoofedMetadataXeditPid"
        )) {
            if ($spoofedMetadataWait.Output -notmatch [regex]::Escape($phrase)) {
                throw "process wait summary is missing phrase for metadata-identified xEdit processes: $phrase"
            }
        }

        $spoofedMetadataStop = Invoke-Cli -Arguments @(
            "process",
            "stop",
            "--xedit-pid",
            $spoofedMetadataXeditPid.ToString()
        )

        if ($spoofedMetadataStop.ExitCode -ne 0) {
            throw "process stop should accept a pid whose executable metadata identifies it as xEdit"
        }

        foreach ($phrase in @(
            "process stop",
            "status: stopped",
            "xedit-pid: $spoofedMetadataXeditPid"
        )) {
            if ($spoofedMetadataStop.Output -notmatch [regex]::Escape($phrase)) {
                throw "process stop summary is missing phrase for metadata-identified xEdit processes: $phrase"
            }
        }
    }
    finally {
        if (-not $spoofedMetadataXeditProcess.HasExited) {
            Stop-Process -Id $spoofedMetadataXeditPid -Force -ErrorAction SilentlyContinue
            $spoofedMetadataXeditProcess.WaitForExit()
        }
    }

    $badMetadataLaunch = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $spoofedMetadataXeditPath,
        "--game-mode",
        "Fallout4"
    )

    if ($badMetadataLaunch.ExitCode -ne 0) {
        throw "process launch should accept a direct executable whose metadata identifies it as xEdit"
    }

    if ($badMetadataLaunch.Output -notmatch "xedit-pid:\s*(\d+)") {
        throw "process launch should report the launched pid for metadata-identified xEdit executables"
    }

    $spoofedMetadataLaunchPid = [int]$Matches[1]
    Stop-Process -Id $spoofedMetadataLaunchPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300

    if (Get-Process -Id $spoofedMetadataLaunchPid -ErrorAction SilentlyContinue) {
        throw "process stop should terminate metadata-identified xEdit launches when requested"
    }

    $badWrapperLaunch = Invoke-Cli -Arguments @(
        "process",
        "launch",
        "--launcher-path",
        $badExeLauncherPath,
        "--game-mode",
        "Fallout4"
    )

    if ($badWrapperLaunch.ExitCode -eq 0) {
        throw "process launch should fail closed for a non-xEdit .exe launcher"
    }

    if ($badWrapperLaunch.Output -notmatch [regex]::Escape("Launcher executable is not xEdit-compatible: $badExeLauncherPath")) {
        throw "process launch should explain when a launcher does not produce an xEdit process"
    }
}
finally {
    Remove-Item Env:XEDIT_CLI_TEST_ARG_LOG -ErrorAction SilentlyContinue

    if ($null -ne $launchedPid) {
        Stop-Process -Id $launchedPid -Force -ErrorAction SilentlyContinue
    }

    if ($null -ne $wrapperBatPid) {
        Stop-Process -Id $wrapperBatPid -Force -ErrorAction SilentlyContinue
    }

    if ($null -ne $wrapperCmdPid) {
        Stop-Process -Id $wrapperCmdPid -Force -ErrorAction SilentlyContinue
    }

    if ($null -ne $nonXeditPid) {
        Stop-Process -Id $nonXeditPid -Force -ErrorAction SilentlyContinue
    }

    if ($null -ne $spoofedMetadataXeditPid) {
        Stop-Process -Id $spoofedMetadataXeditPid -Force -ErrorAction SilentlyContinue
    }

    if ($null -ne $subdirectoryWrapperPid) {
        Stop-Process -Id $subdirectoryWrapperPid -Force -ErrorAction SilentlyContinue
    }

    if ($null -ne $skyrimPid) {
        Stop-Process -Id $skyrimPid -Force -ErrorAction SilentlyContinue
    }

    if ($null -ne $skyrimSePid) {
        Stop-Process -Id $skyrimSePid -Force -ErrorAction SilentlyContinue
    }

    if ($null -ne $starfieldPid) {
        Stop-Process -Id $starfieldPid -Force -ErrorAction SilentlyContinue
    }

    foreach ($fixturePath in @($fo4EditPath, $sseEditPath, $sf1EditPath, $loaderPath, $subdirectoryLoaderPath)) {
        if (-not (Test-Path $fixturePath)) {
            continue
        }

        Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $fixturePath } | ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }

    if (Test-Path $badExeLauncherPath) {
        Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $badExeLauncherPath } | ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }

    if (Test-Path $tempRoot) {
        Remove-Item -Path $tempRoot -Recurse -Force
    }
}

Write-Host "process lifecycle checks passed."

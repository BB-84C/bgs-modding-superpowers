$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path
$cliPath = Join-Path $repoRoot 'tools/mo2-vfs-launcher/xedit-client.ps1'

function Invoke-Cli {
    param([string[]]$Arguments)
    $output = & pwsh -NoProfile -File $cliPath @Arguments 2>&1
    [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = ($output | ForEach-Object { $_.ToString() }) -join "`n" }
}

function New-XeditClientFixtureExecutable {
    param(
        [string]$TempRoot,
        [string]$BinaryName,
        [string]$ProjectName = [System.IO.Path]::GetFileNameWithoutExtension($BinaryName),
        [string]$AssemblyName = [System.IO.Path]::GetFileNameWithoutExtension($BinaryName),
        [string]$ProductName = 'xEdit',
        [string]$FileDescription = [System.IO.Path]::GetFileNameWithoutExtension($BinaryName),
        [string]$CompanyName = 'ElminsterAU'
    )

    $projectRoot = Join-Path $TempRoot $ProjectName
    $publishRoot = Join-Path $projectRoot 'publish'
    $null = New-Item -ItemType Directory -Path $projectRoot -Force

    Set-Content -Path (Join-Path $projectRoot "$AssemblyName.csproj") -Value @"
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>WinExe</OutputType>
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

    Set-Content -Path (Join-Path $projectRoot 'Program.cs') -Value @'
using System.Diagnostics;

var exeName = Path.GetFileName(Environment.ProcessPath ?? AppDomain.CurrentDomain.FriendlyName);
var logPath = Environment.GetEnvironmentVariable("XEDIT_CLIENT_TEST_ARG_LOG");
if (!string.IsNullOrWhiteSpace(logPath))
{
    File.AppendAllText(logPath, exeName + "|" + string.Join(" ", args) + "|cwd=" + Environment.CurrentDirectory + Environment.NewLine);
}

var responseArgument = args.FirstOrDefault(argument => argument.StartsWith("-automation-call-response:", StringComparison.OrdinalIgnoreCase));
if (!string.IsNullOrWhiteSpace(responseArgument))
{
    var responsePath = responseArgument.Substring("-automation-call-response:".Length);
    File.WriteAllText(responsePath, "{\"ok\":true,\"result\":{\"name\":\"xEdit fixture\"}}");
    return 0;
}

if (exeName.Contains("loader", StringComparison.OrdinalIgnoreCase))
{
    if (args.Length == 0) { return 2; }
    var targetPath = args[0];
    if (!Path.IsPathRooted(targetPath)) { targetPath = Path.Combine(Environment.CurrentDirectory, targetPath); }
    var startInfo = new ProcessStartInfo { FileName = targetPath, WorkingDirectory = Environment.CurrentDirectory, UseShellExecute = false };
    foreach (var argument in args.Skip(1)) { startInfo.ArgumentList.Add(argument); }
    Process.Start(startInfo);
}

Thread.Sleep(TimeSpan.FromSeconds(30));
return 0;
'@

    $publishOutput = & dotnet publish $projectRoot -nologo -v quiet -c Release -o $publishRoot 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Failed to build xEdit process fixture executable ${BinaryName}: $($publishOutput -join "`n")" }
    $fixtureExecutablePath = Join-Path $publishRoot $BinaryName
    if (-not (Test-Path $fixtureExecutablePath)) { throw "Failed to locate built fixture executable: $fixtureExecutablePath" }
    return $fixtureExecutablePath
}

function Get-MatchingLogLine {
    param([string]$LogPath, [string]$Pattern, [int]$TimeoutSeconds = 5)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Test-Path $LogPath) {
            $match = Get-Content -Path $LogPath | Where-Object { $_ -match $Pattern } | Select-Object -Last 1
            if ($null -ne $match) { return $match }
        }
        Start-Sleep -Milliseconds 100
    } while ((Get-Date) -lt $deadline)
    return $null
}

$tempRoot = Join-Path $env:TEMP ('xedit-client-process-lifecycle-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $tempRoot -Force
$launchedPid = $null
$wrapperPid = $null
$metadataPid = $null
$nonXeditPid = $null

try {
    $builtFo4EditPath = New-XeditClientFixtureExecutable -TempRoot $tempRoot -BinaryName 'FO4Edit.exe'
    $builtSseEditPath = New-XeditClientFixtureExecutable -TempRoot $tempRoot -BinaryName 'SSEEdit.exe'
    $builtLoaderPath = New-XeditClientFixtureExecutable -TempRoot $tempRoot -BinaryName 'hdtTES5EditUTF8_loader.exe' -ProductName 'Helper Loader' -FileDescription 'Helper Loader' -CompanyName 'Contoso'
    $builtSpoofedMetadataFo4EditPath = New-XeditClientFixtureExecutable -TempRoot $tempRoot -ProjectName 'SpoofedMetadataFo4Edit' -BinaryName 'FO4Edit.exe' -AssemblyName 'FO4Edit' -ProductName 'xEdit' -FileDescription 'FO4Edit' -CompanyName 'Contoso'

    $argLogPath = Join-Path $tempRoot 'launch-args.log'
    $env:XEDIT_CLIENT_TEST_ARG_LOG = $argLogPath
    $env:XEDIT_CLI_TEST_ARG_LOG = $argLogPath
    $fo4EditPath = Join-Path $tempRoot 'FO4Edit.exe'
    $sseEditPath = Join-Path $tempRoot 'SSEEdit.exe'
    $loaderPath = Join-Path $tempRoot 'hdtTES5EditUTF8_loader.exe'
    $spoofedMetadataXeditPath = Join-Path (Join-Path $tempRoot 'spoof-metadata') 'FO4Edit.exe'
    $null = New-Item -ItemType Directory -Path (Split-Path -Path $spoofedMetadataXeditPath -Parent) -Force
    Copy-Item -Path $builtFo4EditPath -Destination $fo4EditPath
    Copy-Item -Path $builtSseEditPath -Destination $sseEditPath
    Copy-Item -Path $builtLoaderPath -Destination $loaderPath
    Copy-Item -Path $builtSpoofedMetadataFo4EditPath -Destination $spoofedMetadataXeditPath
    $pluginsFilePath = Join-Path $tempRoot 'caller-plugins.txt'
    Set-Content -Path $pluginsFilePath -Value @('*Fallout4.esm', '*ExamplePatch.esp')

    $missingMode = Invoke-Cli -Arguments @('process', 'launch', '--launcher-path', $fo4EditPath)
    if ($missingMode.ExitCode -eq 0 -or $missingMode.Output -notmatch [regex]::Escape('Missing required options: --game-mode')) { throw 'process launch should reject and explain a missing --game-mode option' }

    $misspelledMoProfileLaunch = Invoke-Cli -Arguments @('process', 'launch', '--launcher-path', $fo4EditPath, '--game-mode', 'Fallout4', '--mo-profle', 'Default', '--plugins-file', $pluginsFilePath)
    if ($misspelledMoProfileLaunch.ExitCode -eq 0 -or $misspelledMoProfileLaunch.Output -notmatch [regex]::Escape('Unexpected option: --mo-profle')) { throw 'process launch should fail closed on misspelled option names' }

    $legacyLoadModeLaunch = Invoke-Cli -Arguments @('process', 'launch', '--launcher-path', $fo4EditPath, '--game-mode', 'Fallout4', '--load-mode', 'all')
    if ($legacyLoadModeLaunch.ExitCode -eq 0 -or $legacyLoadModeLaunch.Output -notmatch [regex]::Escape('Legacy options are no longer supported: --load-mode')) { throw 'process launch should reject the removed --load-mode option' }

    $directLaunch = Invoke-Cli -Arguments @('process', 'launch', '--launcher-path', $fo4EditPath, '--game-mode', 'Fallout4', '--plugins-file', $pluginsFilePath)
    if ($directLaunch.ExitCode -ne 0) { throw "process launch should succeed for a direct .exe launcher: $($directLaunch.Output)" }
    if ($directLaunch.Output -notmatch 'xedit-pid:\s*(\d+)') { throw 'process launch should report the launched pid' }
    $launchedPid = [int]$Matches[1]
    $directLaunchLogLine = Get-MatchingLogLine -LogPath $argLogPath -Pattern '(?m)^FO4Edit\.exe\|.*-FO4.*-automation-serve.*-P:.*\|cwd=.*$'
    if ($null -eq $directLaunchLogLine) { throw 'direct .exe launch should append mode, -automation-serve, and session plugins arguments' }
    if ($directLaunchLogLine -match '-moprofile:') { throw 'direct launch should not forward -moprofile into native xEdit args' }
    if ($directLaunchLogLine -notmatch '-P:([^|]+plugins\.txt)') { throw 'direct .exe launch should log the session plugins path passed through -P:' }
    $launchedSessionPluginsPath = $Matches[1]
    $launchedSessionPlugins = Get-Content -Path $launchedSessionPluginsPath
    if ($launchedSessionPlugins.Count -ne 2 -or $launchedSessionPlugins[0] -ne '*Fallout4.esm' -or $launchedSessionPlugins[1] -ne '*ExamplePatch.esp') { throw 'process launch should normalize the caller plugin file into the session plugins file' }

    $status = Invoke-Cli -Arguments @('process', 'status', '--xedit-pid', $launchedPid.ToString())
    if ($status.ExitCode -ne 0 -or $status.Output -notmatch [regex]::Escape('status: running')) { throw "process status should accept the launched xEdit pid: $($status.Output)" }
    $wait = Invoke-Cli -Arguments @('process', 'wait', '--xedit-pid', $launchedPid.ToString(), '--timeout-seconds', '1')
    if ($wait.ExitCode -ne 0 -or $wait.Output -notmatch [regex]::Escape('status: timeout')) { throw "process wait should report timeout for a live xEdit pid: $($wait.Output)" }
    $stop = Invoke-Cli -Arguments @('process', 'stop', '--xedit-pid', $launchedPid.ToString())
    if ($stop.ExitCode -ne 0 -or $stop.Output -notmatch [regex]::Escape('status: stopped')) { throw "process stop should terminate the launched xEdit pid: $($stop.Output)" }
    $launchedPid = $null

    $wrapperPath = Join-Path $tempRoot 'runFO4Edit.bat'
    Set-Content -Path $wrapperPath -Value "@echo off`nhdtTES5EditUTF8_loader.exe FO4Edit.exe"
    $wrapperLaunch = Invoke-Cli -Arguments @('process', 'launch', '--launcher-path', $wrapperPath, '--game-mode', 'Fallout4', '--plugins-file', $pluginsFilePath)
    if ($wrapperLaunch.ExitCode -ne 0 -or $wrapperLaunch.Output -notmatch 'xedit-pid:\s*(\d+)') { throw "process launch should succeed for a simple wrapper: $($wrapperLaunch.Output)" }
    $wrapperPid = [int]$Matches[1]
    $wrapperLogLine = Get-MatchingLogLine -LogPath $argLogPath -Pattern '(?m)^hdtTES5EditUTF8_loader\.exe\|.*-FO4.*-automation-serve.*-P:.*\|cwd=.*$'
    if ($null -eq $wrapperLogLine) { throw 'simple wrappers should receive mapped mode, -automation-serve, and session plugins arguments' }
    Stop-Process -Id $wrapperPid -Force -ErrorAction SilentlyContinue
    $wrapperPid = $null

    $skyrimLaunch = Invoke-Cli -Arguments @('process', 'launch', '--launcher-path', $sseEditPath, '--game-mode', 'Skyrim', '--plugins-file', $pluginsFilePath)
    if ($skyrimLaunch.ExitCode -ne 0 -or $skyrimLaunch.Output -notmatch 'xedit-pid:\s*(\d+)') { throw 'process launch should support direct Skyrim normalization' }
    $skyrimPid = [int]$Matches[1]
    if ($null -eq (Get-MatchingLogLine -LogPath $argLogPath -Pattern '(?m)^SSEEdit\.exe\|.*-TES5.*-automation-serve.*-P:.*\|cwd=.*$')) { throw 'direct Skyrim launch should append -TES5, -automation-serve, and -P:' }
    Stop-Process -Id $skyrimPid -Force -ErrorAction SilentlyContinue

    $metadataProcess = Start-Process -FilePath $spoofedMetadataXeditPath -WindowStyle Hidden -PassThru
    $metadataPid = $metadataProcess.Id
    $metadataStatus = Invoke-Cli -Arguments @('process', 'status', '--xedit-pid', $metadataPid.ToString())
    if ($metadataStatus.ExitCode -ne 0 -or $metadataStatus.Output -notmatch [regex]::Escape("xedit-pid: $metadataPid")) { throw 'process status should accept a pid whose executable metadata identifies it as xEdit' }
    $metadataStop = Invoke-Cli -Arguments @('process', 'stop', '--xedit-pid', $metadataPid.ToString())
    if ($metadataStop.ExitCode -ne 0 -or $metadataStop.Output -notmatch [regex]::Escape('status: stopped')) { throw 'process stop should accept a pid whose executable metadata identifies it as xEdit' }
    $metadataPid = $null

    $nonXedit = Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile', '-Command', 'Start-Sleep -Seconds 30') -WindowStyle Hidden -PassThru
    $nonXeditPid = $nonXedit.Id
    $badStatus = Invoke-Cli -Arguments @('process', 'status', '--xedit-pid', $nonXeditPid.ToString())
    if ($badStatus.ExitCode -eq 0 -or $badStatus.Output -notmatch [regex]::Escape("Process is not an xEdit instance: $nonXeditPid")) { throw 'process status should reject a live pid that is not xEdit' }
}
finally {
    Remove-Item Env:XEDIT_CLIENT_TEST_ARG_LOG -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_TEST_ARG_LOG -ErrorAction SilentlyContinue
    foreach ($pidToStop in @($launchedPid, $wrapperPid, $metadataPid, $nonXeditPid)) {
        if ($null -ne $pidToStop) { Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue }
    }
    if (Test-Path $tempRoot) { Remove-Item -Path $tempRoot -Recurse -Force -ErrorAction SilentlyContinue }
}

Write-Host 'xedit-client process lifecycle checks passed.'
exit 0

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path
$cliPath = Join-Path $repoRoot "tools/xedit-cli/bin/xedit-cli.ps1"
$fixturePath = Join-Path $repoRoot "tools/xedit-cli/fixtures/sample-conflicts-report.txt"

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
        [string]$BinaryName
    )

    $assemblyName = [System.IO.Path]::GetFileNameWithoutExtension($BinaryName)
    $projectRoot = Join-Path $TempRoot $assemblyName
    $publishRoot = Join-Path $projectRoot "publish"

    $null = New-Item -ItemType Directory -Path $projectRoot -Force

    Set-Content -Path (Join-Path $projectRoot "$assemblyName.csproj") -Value @"
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <RuntimeIdentifier>win-x64</RuntimeIdentifier>
    <PublishSingleFile>true</PublishSingleFile>
    <SelfContained>false</SelfContained>
    <AssemblyName>$assemblyName</AssemblyName>
    <Product>$assemblyName</Product>
    <FileDescription>$assemblyName</FileDescription>
  </PropertyGroup>
</Project>
"@

    Set-Content -Path (Join-Path $projectRoot "Program.cs") -Value @'
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

function Invoke-SqliteScalar {
    param(
        [string]$DatabasePath,
        [string]$Query
    )

    (& sqlite3 $DatabasePath $Query).Trim()
}

function Get-OutputValue {
    param(
        [string]$Output,
        [string]$Name
    )

    $match = [regex]::Match($Output, "(?m)^$([regex]::Escape($Name)): (.+)$")
    if (-not $match.Success) {
        return $null
    }

    return $match.Groups[1].Value.Trim()
}

$tempRoot = Join-Path $env:TEMP ("xedit-cli-conflicts-index-" + [guid]::NewGuid().ToString("N"))
$null = New-Item -ItemType Directory -Path $tempRoot -Force

try {
    $databasePath = Join-Path $tempRoot "conflicts.sqlite"
    $launcherPath = Join-Path $tempRoot "test-launcher.cmd"
    $launcherProbePath = Join-Path $tempRoot "launch-probe.txt"
    $launcherPidPath = Join-Path $tempRoot "launch-pid.txt"
    $xeditPath = Join-Path $tempRoot "FO4Edit.exe"
    $builtXeditPath = New-XeditCliFixtureExecutable -TempRoot $tempRoot -BinaryName "FO4Edit.exe"
    $pwshPath = (Get-Command pwsh).Source
    $probeCommand = '"' + $pwshPath + '" -NoProfile -Command "$reportParentExists = Test-Path (Split-Path -Path $env:XEDIT_CLI_REPORT_PATH -Parent); $logParentExists = Test-Path (Split-Path -Path $env:XEDIT_CLI_LOG_PATH -Parent); Set-Content -Path $env:XEDIT_CLI_PROBE_PATH -Value (\"report-parent-exists=$reportParentExists`nlog-parent-exists=$logParentExists\")"'
    $pidCommand = '"' + $pwshPath + '" -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $env:XEDIT_CLI_TEST_EXE } | Sort-Object CreationDate -Descending | Select-Object -First 1 -ExpandProperty ProcessId; Set-Content -Path $env:XEDIT_CLI_PID_PATH -Value $p"'

    Copy-Item -Path $builtXeditPath -Destination $xeditPath
    Set-Content -Path $launcherPath -Value @(
        "@echo off"
        $probeCommand
        'start "" "%XEDIT_CLI_TEST_EXE%" /c ping -n 30 127.0.0.1 ^> nul'
        $pidCommand
        'if "%XEDIT_CLI_TEST_MODE%"=="write-report" copy /y "%XEDIT_CLI_FIXTURE_REPORT%" "%XEDIT_CLI_REPORT_PATH%" >nul & exit /b 0'
        'if "%XEDIT_CLI_TEST_MODE%"=="partial-report" > "%XEDIT_CLI_REPORT_PATH%" echo run^|partial^|2026-04-13T18:00:00Z^|SkyrimSE^|plugins.txt & exit /b 0'
        'if "%XEDIT_CLI_TEST_MODE%"=="launcher-fails" exit /b 23'
        "exit /b %ERRORLEVEL%"
    )

    $missingLauncherResult = Invoke-Cli -Arguments @(
        "conflicts",
        "index",
        "--output-path",
        $databasePath
    )

    if ($missingLauncherResult.ExitCode -eq 0) {
        throw "live conflicts index should require --launcher-path"
    }

    if ($missingLauncherResult.Output -notmatch [regex]::Escape("Missing required options: --launcher-path")) {
        throw "live conflicts index should report the missing launcher path requirement"
    }

    $env:XEDIT_CLI_TEST_MODE = "write-report"
    $env:XEDIT_CLI_FIXTURE_REPORT = $fixturePath
    $env:XEDIT_CLI_PROBE_PATH = $launcherProbePath
    $env:XEDIT_CLI_PID_PATH = $launcherPidPath
    $env:XEDIT_CLI_TEST_EXE = $xeditPath

    $result = Invoke-Cli -Arguments @(
        "conflicts",
        "index",
        "--launcher-path",
        $launcherPath,
        "--output-path",
        $databasePath
    )

    Remove-Item Env:XEDIT_CLI_TEST_MODE -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_FIXTURE_REPORT -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_PROBE_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_PID_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_TEST_EXE -ErrorAction SilentlyContinue

    if ($result.ExitCode -ne 0) {
        throw "live conflicts index should succeed when the launcher produces a report"
    }

    if (-not (Test-Path $databasePath)) {
        throw "conflicts index should create a SQLite-backed run artifact"
    }

    if (-not (Test-Path $launcherProbePath)) {
        throw "live conflicts index should create artifact directories before launch"
    }

    $probeContent = Get-Content -Path $launcherProbePath -Raw
    foreach ($phrase in @("report-parent-exists=True", "log-parent-exists=True")) {
        if ($probeContent -notmatch [regex]::Escape($phrase)) {
            throw "live conflicts index should create run-scoped artifact paths before launch"
        }
    }

    $launchedPid = Get-OutputValue -Output $result.Output -Name "xedit-pid"
    if ([string]::IsNullOrWhiteSpace($launchedPid) -or $launchedPid -notmatch '^\d+$') {
        throw "live conflicts index should report the PID it launched"
    }

    $expectedPid = (Get-Content -Path $launcherPidPath -Raw).Trim()
    if ($launchedPid -ne $expectedPid) {
        throw "live conflicts index should report the xEdit child PID rather than the launcher wrapper pid"
    }

    foreach ($name in @("report-path", "log-path")) {
        $value = Get-OutputValue -Output $result.Output -Name $name
        if ([string]::IsNullOrWhiteSpace($value)) {
            throw "live conflicts index should report $name"
        }

        if (-not (Test-Path $value)) {
            throw "live conflicts index should preserve the $name artifact"
        }
    }

    foreach ($phrase in @(
        "conflicts index",
        "status: ok",
        "database: $databasePath",
        "files:",
        "records:"
    )) {
        if ($result.Output -notmatch [regex]::Escape($phrase)) {
            throw "conflicts index summary is missing phrase: $phrase"
        }
    }

    if ($result.Output -match [regex]::Escape("override|") -or $result.Output -match [regex]::Escape("record|")) {
        throw "conflicts index should emit a compact summary instead of dumping fixture rows"
    }

    if ((Invoke-SqliteScalar -DatabasePath $databasePath -Query "select count(*) from runs;") -ne "1") {
        throw "conflicts index should record one run row"
    }

    if ([int](Invoke-SqliteScalar -DatabasePath $databasePath -Query "select count(*) from files;") -lt 1) {
        throw "conflicts index should record scanned plugin rows"
    }

    if ([int](Invoke-SqliteScalar -DatabasePath $databasePath -Query "select count(*) from records;") -lt 1) {
        throw "conflicts index should record conflict index rows"
    }

    $missingReportDatabasePath = Join-Path $tempRoot "missing-report.sqlite"
    $env:XEDIT_CLI_TEST_MODE = "missing-report"
    $env:XEDIT_CLI_FIXTURE_REPORT = $fixturePath
    $env:XEDIT_CLI_PROBE_PATH = $launcherProbePath
    $env:XEDIT_CLI_PID_PATH = $launcherPidPath
    $env:XEDIT_CLI_TEST_EXE = $xeditPath

    $missingReportResult = Invoke-Cli -Arguments @(
        "conflicts",
        "index",
        "--launcher-path",
        $launcherPath,
        "--output-path",
        $missingReportDatabasePath
    )

    Remove-Item Env:XEDIT_CLI_TEST_MODE -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_FIXTURE_REPORT -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_PROBE_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_PID_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_TEST_EXE -ErrorAction SilentlyContinue

    if ($missingReportResult.ExitCode -eq 0) {
        throw "live conflicts index should fail when the launcher does not produce a report"
    }

    if ($missingReportResult.Output -notmatch [regex]::Escape("Live conflicts report was not produced")) {
        throw "live conflicts index should fail cleanly when the report file is missing"
    }

    if ($missingReportResult.Output -match [regex]::Escape("database: $missingReportDatabasePath")) {
        throw "live conflicts index should not advertise a database artifact when no database was created"
    }

    $partialReportDatabasePath = Join-Path $tempRoot "partial-report.sqlite"
    $env:XEDIT_CLI_TEST_MODE = "partial-report"
    $env:XEDIT_CLI_FIXTURE_REPORT = $fixturePath
    $env:XEDIT_CLI_PROBE_PATH = $launcherProbePath
    $env:XEDIT_CLI_PID_PATH = $launcherPidPath
    $env:XEDIT_CLI_TEST_EXE = $xeditPath

    $partialReportResult = Invoke-Cli -Arguments @(
        "conflicts",
        "index",
        "--launcher-path",
        $launcherPath,
        "--output-path",
        $partialReportDatabasePath
    )

    Remove-Item Env:XEDIT_CLI_TEST_MODE -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_FIXTURE_REPORT -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_PROBE_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_PID_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_TEST_EXE -ErrorAction SilentlyContinue

    if ($partialReportResult.ExitCode -eq 0) {
        throw "live conflicts index should fail when the report is incomplete"
    }

    if ($partialReportResult.Output -notmatch [regex]::Escape("Live conflicts report was incomplete")) {
        throw "live conflicts index should explain incomplete report failures clearly"
    }

    $launcherFailureDatabasePath = Join-Path $tempRoot "launcher-failure.sqlite"
    $env:XEDIT_CLI_TEST_MODE = "launcher-fails"
    $env:XEDIT_CLI_FIXTURE_REPORT = $fixturePath
    $env:XEDIT_CLI_PROBE_PATH = $launcherProbePath
    $env:XEDIT_CLI_PID_PATH = $launcherPidPath
    $env:XEDIT_CLI_TEST_EXE = $xeditPath

    $launcherFailureResult = Invoke-Cli -Arguments @(
        "conflicts",
        "index",
        "--launcher-path",
        $launcherPath,
        "--output-path",
        $launcherFailureDatabasePath
    )

    Remove-Item Env:XEDIT_CLI_TEST_MODE -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_FIXTURE_REPORT -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_PROBE_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_PID_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:XEDIT_CLI_TEST_EXE -ErrorAction SilentlyContinue

    if ($launcherFailureResult.ExitCode -eq 0) {
        throw "live conflicts index should fail when the launcher exits non-zero"
    }

    if ($launcherFailureResult.Output -notmatch [regex]::Escape("Launcher exited with code: 23")) {
        throw "live conflicts index should report launcher failures clearly"
    }

    if ($launcherFailureResult.Output -match [regex]::Escape("database: $launcherFailureDatabasePath")) {
        throw "live conflicts index should not advertise a database artifact when the launcher fails"
    }

    $parentAsFile = Join-Path $tempRoot "not-a-directory.txt"
    Set-Content -Path $parentAsFile -Value "placeholder"

    $brokenOutputPath = Join-Path $parentAsFile "conflicts.sqlite"
    $brokenResult = Invoke-Cli -Arguments @(
        "conflicts",
        "index",
        "--fixture-report",
        $fixturePath,
        "--output-path",
        $brokenOutputPath
    )

    if ($brokenResult.ExitCode -eq 0) {
        throw "conflicts index should fail when sqlite cannot create the output database"
    }

    if ($brokenResult.Output -notmatch [regex]::Escape("sqlite3 failed")) {
        throw "conflicts index should surface sqlite failures clearly"
    }
}
finally {
    if (Test-Path $xeditPath) {
        $xeditProcesses = @(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $xeditPath })
        $xeditProcesses | ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }

        $xeditProcesses | ForEach-Object {
            Wait-Process -Id $_.ProcessId -Timeout 5 -ErrorAction SilentlyContinue
        }
    }

    if (Test-Path $tempRoot) {
        for ($attempt = 0; $attempt -lt 10 -and (Test-Path $tempRoot); $attempt++) {
            try {
                Remove-Item -Path $tempRoot -Recurse -Force -ErrorAction Stop
            }
            catch {
                Start-Sleep -Milliseconds 200
            }
        }
    }
}

Write-Host "conflicts index checks passed."

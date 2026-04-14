function Read-XeditCliFixtureReport {
    param(
        [string]$Path
    )

    $report = [ordered]@{
        Run = $null
        Files = @()
        Groups = @()
        Records = @()
        Overrides = @()
    }

    foreach ($line in Get-Content $Path) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) {
            continue
        }

        $parts = $line -split "\|"
        switch ($parts[0]) {
            "run" {
                $report.Run = [pscustomobject]@{
                    RunId = $parts[1]
                    GeneratedAt = $parts[2]
                    GameMode = $parts[3]
                    LoadOrderSource = $parts[4]
                }
            }
            "file" {
                $report.Files += [pscustomobject]@{
                    PluginName = $parts[1]
                    LoadOrder = [int]$parts[2]
                    Role = $parts[3]
                }
            }
            "group" {
                $report.Groups += [pscustomobject]@{
                    Signature = $parts[1]
                    Label = $parts[2]
                    RecordCount = [int]$parts[3]
                }
            }
            "record" {
                $report.Records += [pscustomobject]@{
                    RecordId = $parts[1]
                    Signature = $parts[2]
                    EditorId = $parts[3]
                    ConflictState = $parts[4]
                    WinnerPlugin = $parts[5]
                }
            }
            "override" {
                $report.Overrides += [pscustomobject]@{
                    RecordId = $parts[1]
                    Ordinal = [int]$parts[2]
                    PluginName = $parts[3]
                    Role = $parts[4]
                }
            }
        }
    }

    if ($null -eq $report.Run) {
        throw "Fixture report is missing a run row"
    }

    return [pscustomobject]$report
}

function New-XeditCliConflictsArtifacts {
    param(
        [string]$OutputPath
    )

    Ensure-XeditCliParentDirectory -Path $OutputPath

    $outputDirectory = Split-Path -Path $OutputPath -Parent
    $outputName = [System.IO.Path]::GetFileNameWithoutExtension($OutputPath)
    $runToken = "{0}-{1}" -f (Get-Date -Format "yyyyMMddHHmmss"), ([guid]::NewGuid().ToString("N").Substring(0, 8))
    $runDirectory = Join-Path $outputDirectory ("{0}-run-{1}" -f $outputName, $runToken)
    $reportPath = Join-Path $runDirectory "conflicts-report.txt"
    $logPath = Join-Path $runDirectory "xedit.log"

    $null = New-Item -ItemType Directory -Path $runDirectory -Force
    Set-Content -Path $logPath -Value ""

    return [pscustomobject]@{
        RunDirectory = $runDirectory
        ReportPath = $reportPath
        LogPath = $logPath
    }
}

function Write-XeditCliConflictsIndexSummary {
    param(
        [string]$Status,
        [string]$DatabasePath,
        [string]$ReportPath,
        [string]$LogPath,
        [int]$ProcessId,
        $Report
    )

    Write-Host "conflicts index"
    Write-Host "status: $Status"

    if ($ProcessId -gt 0) {
        Write-Host "xedit-pid: $ProcessId"
    }

    if (-not [string]::IsNullOrWhiteSpace($ReportPath)) {
        Write-Host "report-path: $ReportPath"
    }

    if (-not [string]::IsNullOrWhiteSpace($LogPath)) {
        Write-Host "log-path: $LogPath"
    }

    if (-not [string]::IsNullOrWhiteSpace($DatabasePath)) {
        Write-Host "database: $DatabasePath"
    }

    if ($null -ne $Report) {
        Write-Host "files: $($Report.Files.Count)"
        Write-Host "records: $($Report.Records.Count)"
    }
}

function Test-XeditCliConflictsReportComplete {
    param(
        $Report
    )

    if ($null -eq $Report) {
        return $false
    }

    return ($Report.Files.Count -gt 0 -and $Report.Records.Count -gt 0)
}

function Invoke-XeditCliConflictsIndex {
    param(
        [string[]]$Arguments
    )

    $options = ConvertTo-XeditCliOptionMap -Arguments $Arguments
    $outputPath = $options["--output-path"]

    if (-not $options.ContainsKey("--output-path")) {
        Write-Host "Missing required options: --output-path"
        return 1
    }

    if ($options.ContainsKey("--fixture-report")) {
        $fixtureReport = $options["--fixture-report"]

        if (-not (Test-Path $fixtureReport)) {
            Write-Host "Fixture report does not exist: $fixtureReport"
            return 1
        }

        $report = Read-XeditCliFixtureReport -Path $fixtureReport

        Initialize-XeditCliSqliteStore -DatabasePath $outputPath
        Write-XeditCliSqliteRun -DatabasePath $outputPath -Report $report -ReportSource $fixtureReport

        Write-XeditCliConflictsIndexSummary -Status "ok" -DatabasePath $outputPath -ReportPath $null -LogPath $null -ProcessId 0 -Report $report
        return 0
    }

    if (-not $options.ContainsKey("--launcher-path")) {
        Write-Host "Missing required options: --launcher-path"
        return 1
    }

    $launcherPath = $options["--launcher-path"]
    if (-not (Test-XeditCliLauncherPath -Path $launcherPath)) {
        Write-Host "Launcher path must end with .bat, .cmd, or .exe: $launcherPath"
        return 1
    }

    $artifacts = New-XeditCliConflictsArtifacts -OutputPath $outputPath
    $knownProcessIds = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessId)
    $startedAt = Get-Date
    $process = Invoke-XeditCliWithEnvironmentOverrides -Variables @{
        XEDIT_CLI_REPORT_PATH = $artifacts.ReportPath
        XEDIT_CLI_LOG_PATH = $artifacts.LogPath
    } -ScriptBlock {
        Start-XeditCliLauncherProcess -LauncherPath $launcherPath -EnvironmentVariables @{}
    }
    $launchedPid = Get-XeditCliLaunchedProcessId -WrapperProcess $process -LauncherPath $launcherPath -StartedAt $startedAt -KnownProcessIds $knownProcessIds

    # The launcher owns the task result for wrapper-driven runs; the child PID is reported for lifecycle follow-up.
    $exitCode = Wait-XeditCliProcessExit -Process $process

    if ($exitCode -ne 0) {
        Write-XeditCliConflictsIndexSummary -Status "failed" -DatabasePath $null -ReportPath $artifacts.ReportPath -LogPath $artifacts.LogPath -ProcessId $launchedPid -Report $null
        Write-Host "Launcher exited with code: $exitCode"
        return 1
    }

    if (-not (Test-Path $artifacts.ReportPath)) {
        Write-XeditCliConflictsIndexSummary -Status "failed" -DatabasePath $null -ReportPath $artifacts.ReportPath -LogPath $artifacts.LogPath -ProcessId $launchedPid -Report $null
        Write-Host "Live conflicts report was not produced"
        return 1
    }

    $report = Read-XeditCliFixtureReport -Path $artifacts.ReportPath
    if (-not (Test-XeditCliConflictsReportComplete -Report $report)) {
        Write-XeditCliConflictsIndexSummary -Status "failed" -DatabasePath $null -ReportPath $artifacts.ReportPath -LogPath $artifacts.LogPath -ProcessId $launchedPid -Report $null
        Write-Host "Live conflicts report was incomplete"
        return 1
    }

    Initialize-XeditCliSqliteStore -DatabasePath $outputPath
    Write-XeditCliSqliteRun -DatabasePath $outputPath -Report $report -ReportSource $artifacts.ReportPath

    Write-XeditCliConflictsIndexSummary -Status "ok" -DatabasePath $outputPath -ReportPath $artifacts.ReportPath -LogPath $artifacts.LogPath -ProcessId $launchedPid -Report $report

    return 0
}

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

$tempRoot = Join-Path $env:TEMP ("xedit-cli-conflicts-inspect-" + [guid]::NewGuid().ToString("N"))
$null = New-Item -ItemType Directory -Path $tempRoot -Force

try {
    $databasePath = Join-Path $tempRoot "conflicts.sqlite"

    $indexResult = Invoke-Cli -Arguments @(
        "conflicts",
        "index",
        "--fixture-report",
        $fixturePath,
        "--output-path",
        $databasePath
    )

    if ($indexResult.ExitCode -ne 0) {
        throw "conflicts inspect test setup failed to create the fixture-backed database"
    }

    $inspectResult = Invoke-Cli -Arguments @(
        "conflicts",
        "inspect",
        "--database-path",
        $databasePath,
        "--record",
        "ARMO:00012E46"
    )

    if ($inspectResult.ExitCode -ne 0) {
        throw "conflicts inspect should succeed for a known record"
    }

    foreach ($phrase in @(
        "conflicts inspect",
        "status: ok",
        "record: ARMO:00012E46",
        "signature: ARMO",
        "editor-id: IronArmor",
        "winner: ExamplePatch.esp",
        "overrides:"
    )) {
        if ($inspectResult.Output -notmatch [regex]::Escape($phrase)) {
            throw "conflicts inspect output is missing phrase: $phrase"
        }
    }

    if ($inspectResult.Output -match [regex]::Escape("WEAP:00013989")) {
        throw "conflicts inspect should emit a scoped result instead of the whole dataset"
    }

    $missingRecord = Invoke-Cli -Arguments @(
        "conflicts",
        "inspect",
        "--database-path",
        $databasePath,
        "--record",
        "MISC:UNKNOWN"
    )

    if ($missingRecord.ExitCode -eq 0) {
        throw "conflicts inspect should fail for an unknown record"
    }

    if ($missingRecord.Output -notmatch [regex]::Escape("Unknown record: MISC:UNKNOWN")) {
        throw "conflicts inspect should explain when a record is not found"
    }
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -Path $tempRoot -Recurse -Force
    }
}

Write-Host "conflicts inspect checks passed."

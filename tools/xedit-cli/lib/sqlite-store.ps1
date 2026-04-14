function ConvertTo-SqliteTextLiteral {
    param(
        [AllowNull()]
        [string]$Value
    )

    if ($null -eq $Value) {
        return "NULL"
    }

    return "'" + $Value.Replace("'", "''") + "'"
}

function Invoke-XeditCliSqliteRaw {
    param(
        [string[]]$SqliteArguments
    )

    $output = & sqlite3 @SqliteArguments 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        $message = ($output | ForEach-Object { $_.ToString() }) -join "`n"
        if ([string]::IsNullOrWhiteSpace($message)) {
            $message = "sqlite3 exited with code $exitCode"
        }

        throw "sqlite3 failed: $message"
    }

    return $output
}

function Invoke-XeditCliSqlite {
    param(
        [string]$DatabasePath,
        [string]$Query
    )

    Invoke-XeditCliSqliteRaw -SqliteArguments @($DatabasePath, $Query)
}

function Read-XeditCliSqliteJson {
    param(
        [string]$DatabasePath,
        [string]$Query
    )

    $json = (Invoke-XeditCliSqliteRaw -SqliteArguments @("-json", $DatabasePath, $Query)) -join "`n"
    if ([string]::IsNullOrWhiteSpace($json)) {
        return @()
    }

    $rows = $json | ConvertFrom-Json
    if ($null -eq $rows) {
        return @()
    }

    if ($rows -is [System.Array]) {
        return $rows
    }

    return @($rows)
}

function Initialize-XeditCliSqliteStore {
    param(
        [string]$DatabasePath
    )

    if (Test-Path $DatabasePath) {
        Remove-Item -Path $DatabasePath -Force
    }

    Ensure-XeditCliParentDirectory -Path $DatabasePath

    $schema = @"
create table runs (
    run_id text primary key,
    generated_at text not null,
    game_mode text not null,
    load_order_source text not null,
    report_source text not null
);

create table files (
    run_id text not null,
    plugin_name text not null,
    load_order integer not null,
    role text not null
);

create table groups (
    run_id text not null,
    signature text not null,
    label text not null,
    record_count integer not null
);

create table records (
    run_id text not null,
    record_id text not null,
    signature text not null,
    editor_id text not null,
    conflict_state text not null,
    winner_plugin text not null
);

create table overrides (
    run_id text not null,
    record_id text not null,
    ordinal integer not null,
    plugin_name text not null,
    role text not null
);
"@

    Invoke-XeditCliSqlite -DatabasePath $DatabasePath -Query $schema | Out-Null
}

function Write-XeditCliSqliteRun {
    param(
        [string]$DatabasePath,
        [pscustomobject]$Report,
        [string]$ReportSource
    )

    $run = $Report.Run

    $queries = @(
        "insert into runs (run_id, generated_at, game_mode, load_order_source, report_source) values ($(ConvertTo-SqliteTextLiteral $run.RunId), $(ConvertTo-SqliteTextLiteral $run.GeneratedAt), $(ConvertTo-SqliteTextLiteral $run.GameMode), $(ConvertTo-SqliteTextLiteral $run.LoadOrderSource), $(ConvertTo-SqliteTextLiteral $ReportSource));"
    )

    foreach ($file in $Report.Files) {
        $queries += "insert into files (run_id, plugin_name, load_order, role) values ($(ConvertTo-SqliteTextLiteral $run.RunId), $(ConvertTo-SqliteTextLiteral $file.PluginName), $($file.LoadOrder), $(ConvertTo-SqliteTextLiteral $file.Role));"
    }

    foreach ($group in $Report.Groups) {
        $queries += "insert into groups (run_id, signature, label, record_count) values ($(ConvertTo-SqliteTextLiteral $run.RunId), $(ConvertTo-SqliteTextLiteral $group.Signature), $(ConvertTo-SqliteTextLiteral $group.Label), $($group.RecordCount));"
    }

    foreach ($record in $Report.Records) {
        $queries += "insert into records (run_id, record_id, signature, editor_id, conflict_state, winner_plugin) values ($(ConvertTo-SqliteTextLiteral $run.RunId), $(ConvertTo-SqliteTextLiteral $record.RecordId), $(ConvertTo-SqliteTextLiteral $record.Signature), $(ConvertTo-SqliteTextLiteral $record.EditorId), $(ConvertTo-SqliteTextLiteral $record.ConflictState), $(ConvertTo-SqliteTextLiteral $record.WinnerPlugin));"
    }

    foreach ($override in $Report.Overrides) {
        $queries += "insert into overrides (run_id, record_id, ordinal, plugin_name, role) values ($(ConvertTo-SqliteTextLiteral $run.RunId), $(ConvertTo-SqliteTextLiteral $override.RecordId), $($override.Ordinal), $(ConvertTo-SqliteTextLiteral $override.PluginName), $(ConvertTo-SqliteTextLiteral $override.Role));"
    }

    Invoke-XeditCliSqlite -DatabasePath $DatabasePath -Query ($queries -join "`n") | Out-Null
}

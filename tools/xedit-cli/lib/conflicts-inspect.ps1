function Invoke-XeditCliConflictsInspect {
    param(
        [string[]]$Arguments
    )

    $options = ConvertTo-XeditCliOptionMap -Arguments $Arguments

    $missing = @()
    foreach ($name in @("--database-path", "--record")) {
        if (-not $options.ContainsKey($name)) {
            $missing += $name
        }
    }

    if ($missing.Count -gt 0) {
        Write-Host "Missing required options: $($missing -join ', ')"
        return 1
    }

    $databasePath = $options["--database-path"]
    $recordId = $options["--record"]

    if (-not (Test-Path $databasePath)) {
        Write-Host "Database does not exist: $databasePath"
        return 1
    }

    $recordRows = Read-XeditCliSqliteJson -DatabasePath $databasePath -Query "select record_id, signature, editor_id, conflict_state, winner_plugin from records where record_id = $(ConvertTo-SqliteTextLiteral $recordId) limit 1;"
    if ($recordRows.Count -eq 0) {
        Write-Host "Unknown record: $recordId"
        return 1
    }

    $record = $recordRows[0]
    $overrideRows = Read-XeditCliSqliteJson -DatabasePath $databasePath -Query "select ordinal, plugin_name, role from overrides where record_id = $(ConvertTo-SqliteTextLiteral $recordId) order by ordinal;"

    Write-Host "conflicts inspect"
    Write-Host "status: ok"
    Write-Host "record: $($record.record_id)"
    Write-Host "signature: $($record.signature)"
    Write-Host "editor-id: $($record.editor_id)"
    Write-Host "conflict-state: $($record.conflict_state)"
    Write-Host "winner: $($record.winner_plugin)"
    Write-Host "overrides:"

    foreach ($override in $overrideRows) {
        Write-Host "[$($override.ordinal)] $($override.plugin_name) ($($override.role))"
    }

    return 0
}

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path

$requiredPaths = @(
    "tools/xedit-cli/schema/intermediate-report.md",
    "tools/xedit-cli/schema/sqlite-schema.md"
)

$missing = $requiredPaths | Where-Object { -not (Test-Path (Join-Path $repoRoot $_)) }
if ($missing.Count -gt 0) {
    throw "Missing schema docs: $($missing -join ', ')"
}

$combined = @(
    Get-Content (Join-Path $repoRoot "tools/xedit-cli/schema/intermediate-report.md") -Raw
    Get-Content (Join-Path $repoRoot "tools/xedit-cli/schema/sqlite-schema.md") -Raw
) -join "`n"

foreach ($heading in @(
    "## Scan Metadata",
    "## File And Plugin Rows",
    "## Group And Signature Summaries",
    "## Record And Conflict Index Rows",
    "## Override Chain Rows",
    "## Inspection Detail Strategy"
)) {
    if ($combined -notmatch [regex]::Escape($heading)) {
        throw "Schema docs are missing heading: $heading"
    }
}

Write-Host "xedit-cli schema checks passed."

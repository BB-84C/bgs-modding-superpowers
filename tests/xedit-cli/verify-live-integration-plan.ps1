$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path
$path = Join-Path $repoRoot "tools/xedit-cli/live-integration.md"

if (-not (Test-Path $path)) {
    throw "Missing live integration doc: tools/xedit-cli/live-integration.md"
}

$content = Get-Content $path -Raw

foreach ($heading in @(
    "## Phase 1 Launch Arguments",
    "## Report-Script Execution Flow",
    "## Log Capture And Timeout Handling",
    "## Read-Only Constraints",
    "## Known Unknowns",
    "## Fallback Behavior"
)) {
    if ($content -notmatch [regex]::Escape($heading)) {
        throw "live integration doc is missing heading: $heading"
    }
}

foreach ($phrase in @(
    "-script",
    "-autoload",
    "-autoexit",
    "-R:",
    "-S:",
    "timeout",
    "read-only",
    "fallback"
)) {
    if ($content -notmatch [regex]::Escape($phrase)) {
        throw "live integration doc is missing phrase: $phrase"
    }
}

Write-Host "xedit-cli live integration plan checks passed."

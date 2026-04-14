$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path
$path = Join-Path $repoRoot "tools/xedit-cli/scripts/conflicts-index.pas.md"

if (-not (Test-Path $path)) {
    throw "Missing script contract doc: tools/xedit-cli/scripts/conflicts-index.pas.md"
}

$content = Get-Content $path -Raw

foreach ($phrase in @(
    "read-only",
    "xEdit",
    "Initialize",
    "Process",
    "Finalize",
    "intermediate report",
    "prohibited",
    "mutation"
)) {
    if ($content -notmatch [regex]::Escape($phrase)) {
        throw "tools/xedit-cli/scripts/conflicts-index.pas.md is missing phrase: $phrase"
    }
}

Write-Host "xedit-cli script contract checks passed."

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path

$documents = @(
    @{
        Path = "tools/xedit-cli/scripts/README.md"
        Phrases = @("Pascal scripts", "xEdit")
    },
    @{
        Path = "tools/xedit-cli/schema/README.md"
        Phrases = @("SQLite", "report schema")
    },
    @{
        Path = "tools/xedit-cli/fixtures/README.md"
        Phrases = @("fixtures", "sample outputs")
    },
    @{
        Path = "tools/xedit-cli/output/README.md"
        Phrases = @("wrapper-owned", "run artifacts")
    }
)

$missing = $documents | Where-Object {
    -not (Test-Path (Join-Path $repoRoot $_.Path))
}

if ($missing.Count -gt 0) {
    throw "Missing layout docs: $($missing.Path -join ', ')"
}

foreach ($document in $documents) {
    $content = Get-Content (Join-Path $repoRoot $document.Path) -Raw
    foreach ($phrase in $document.Phrases) {
        if ($content -notmatch [regex]::Escape($phrase)) {
            throw "$($document.Path) is missing phrase: $phrase"
        }
    }
}

Write-Host "xedit-cli layout checks passed."

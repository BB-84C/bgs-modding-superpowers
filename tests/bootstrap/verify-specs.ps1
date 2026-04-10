$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path

$requiredPaths = @(
    "tools/xedit-cli/README.md",
    "tools/xedit-cli/CONTRACT.md",
    "mcps/nexus-metadata.md",
    "mcps/loot-metadata.md",
    "mcps/xedit-readonly.md",
    "mcps/translation-memory.md"
)

$missing = $requiredPaths | Where-Object { -not (Test-Path (Join-Path $repoRoot $_)) }
if ($missing.Count -gt 0) {
    throw "Missing spec files: $($missing -join ', ')"
}

$xeditReadme = Get-Content (Join-Path $repoRoot "tools/xedit-cli/README.md") -Raw
foreach ($phrase in @("wrapper", "orchestrates upstream xEdit", "keep xEdit external")) {
    if ($xeditReadme -notmatch [regex]::Escape($phrase)) {
        throw "tools/xedit-cli/README.md is missing phrase: $phrase"
    }
}

$contract = Get-Content (Join-Path $repoRoot "tools/xedit-cli/CONTRACT.md") -Raw
foreach ($heading in @("## Goals", "## Read-Only Commands", "## Future Write Commands", "## Safety Rules")) {
    if ($contract -notmatch [regex]::Escape($heading)) {
        throw "xedit-cli contract is missing heading: $heading"
    }
}

foreach ($path in @(
    "mcps/nexus-metadata.md",
    "mcps/loot-metadata.md",
    "mcps/xedit-readonly.md",
    "mcps/translation-memory.md"
)) {
    $content = Get-Content (Join-Path $repoRoot $path) -Raw
    if ($content -notmatch [regex]::Escape("Planned purpose:")) {
        throw "$path is missing placeholder framing: Planned purpose:"
    }
}

Write-Host "Spec bootstrap checks passed."

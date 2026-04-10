$ErrorActionPreference = "Stop"

$requiredPaths = @(
    "agents/repo-bootstrap/AGENT.md",
    "commands/README.md",
    "knowledge/README.md",
    "research/summaries/README.md",
    "templates/README.md",
    "tools/README.md",
    "mcps/README.md",
    "tests/README.md",
    ".artifacts/.gitkeep"
)

$missing = $requiredPaths | Where-Object { -not (Test-Path $_) }
if ($missing.Count -gt 0) {
    throw "Missing layout files: $($missing -join ', ')"
}

$agent = Get-Content "agents/repo-bootstrap/AGENT.md" -Raw
foreach ($phrase in @("initialize git", "create directory scaffold", "prepare GitHub-facing files", "do not commit raw artifacts")) {
    if ($agent -notmatch [regex]::Escape($phrase)) {
        throw "agents/repo-bootstrap/AGENT.md is missing phrase: $phrase"
    }
}

$knowledge = Get-Content "knowledge/README.md" -Raw
foreach ($phrase in @("stable reusable guidance", "promoted from research summaries")) {
    if ($knowledge -notmatch [regex]::Escape($phrase)) {
        throw "knowledge/README.md is missing phrase: $phrase"
    }
}

$summaries = Get-Content "research/summaries/README.md" -Raw
foreach ($phrase in @("source-derived or investigation-specific summaries", "may later be promoted")) {
    if ($summaries -notmatch [regex]::Escape($phrase)) {
        throw "research/summaries/README.md is missing phrase: $phrase"
    }
}

$commands = Get-Content "commands/README.md" -Raw
if ($commands -notmatch [regex]::Escape("thin entrypoints or wrappers")) {
    throw "commands/README.md is missing phrase: thin entrypoints or wrappers"
}

$tools = Get-Content "tools/README.md" -Raw
if ($tools -notmatch [regex]::Escape("implementation code or automation")) {
    throw "tools/README.md is missing phrase: implementation code or automation"
}

$mcps = Get-Content "mcps/README.md" -Raw
if ($mcps -notmatch [regex]::Escape("specs and contracts only")) {
    throw "mcps/README.md is missing phrase: specs and contracts only"
}

$tests = Get-Content "tests/README.md" -Raw
foreach ($phrase in @("bootstrap verification", "future tests for scripts, templates, and tools")) {
    if ($tests -notmatch [regex]::Escape($phrase)) {
        throw "tests/README.md is missing phrase: $phrase"
    }
}

Write-Host "Layout bootstrap checks passed."

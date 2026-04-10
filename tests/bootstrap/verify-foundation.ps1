$ErrorActionPreference = "Stop"

$requiredPaths = @(
    ".gitignore",
    ".opencode/INSTALL.md",
    ".opencode/README.md",
    "README.md",
    "docs/roadmap.md",
    "docs/standards/repo-hygiene.md"
)

$missing = $requiredPaths | Where-Object { -not (Test-Path $_) }
if ($missing.Count -gt 0) {
    throw "Missing required bootstrap files: $($missing -join ', ')"
}

$readme = Get-Content "README.md" -Raw
if ($readme -notmatch "BGS modpack curation" -or $readme -notmatch "not general mod authoring") {
    throw "README.md is missing the curation-vs-authoring scope statement"
}

$roadmap = Get-Content "docs/roadmap.md" -Raw
foreach ($heading in @("## Now", "## Next", "## Later", "## Blocked / Needs Research", "## Done")) {
    if ($roadmap -notmatch [regex]::Escape($heading)) {
        throw "docs/roadmap.md is missing heading: $heading"
    }
}
if ($roadmap -notmatch "docs/plans/" -or $roadmap -match "\d{4}-\d{2}-\d{2}-") {
    throw "docs/roadmap.md should point to the plans area without date-stamped filename churn"
}

$gitignore = Get-Content ".gitignore" -Raw
foreach ($rule in @(".artifacts/*", "!.artifacts/.gitkeep", ".playwright-mcp/")) {
    if ($gitignore -notmatch [regex]::Escape($rule)) {
        throw ".gitignore is missing ignore rule: $rule"
    }
}

$repoHygiene = Get-Content "docs/standards/repo-hygiene.md" -Raw
foreach ($section in @("## Ignored Working Content", "## Artifact Lifecycle")) {
    if ($repoHygiene -notmatch [regex]::Escape($section)) {
        throw "docs/standards/repo-hygiene.md is missing section: $section"
    }
}

$install = Get-Content ".opencode/INSTALL.md" -Raw
foreach ($section in @("## Purpose", "## Bootstrap State", "## Later Work")) {
    if ($install -notmatch [regex]::Escape($section)) {
        throw ".opencode/INSTALL.md is missing section: $section"
    }
}
if ($install -notmatch "install commands" -or $install -notmatch "plugin metadata") {
    throw ".opencode/INSTALL.md is missing bootstrap install guidance"
}

Write-Host "Foundation bootstrap checks passed."

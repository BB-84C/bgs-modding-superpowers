$ErrorActionPreference = "Stop"

function Test-HasTransientPromptReference {
    param([string]$Content)

    return $Content -match '(?i)(docs[/\\][^\r\n`]*initial[^\r\n`]*p\w*mpt[^\r\n`]*\.md|initial\s+prompt\s+file)'
}

function Get-SectionContent {
    param(
        [string]$Content,
        [string]$Heading
    )

    $escapedHeading = [regex]::Escape($Heading)
    $match = [regex]::Match($Content, "(?sm)^$escapedHeading\s*(.*?)(?=^##\s|\z)")
    if (-not $match.Success) {
        throw "docs/roadmap.md is missing heading: $Heading"
    }

    return $match.Groups[1].Value
}

if (-not (Test-HasTransientPromptReference "See docs/initial_prompt.md for context.")) {
    throw "Transient prompt guard should catch the standard initial prompt file reference"
}
if (-not (Test-HasTransientPromptReference "See docs/initial_pormpt.md for context.")) {
    throw "Transient prompt guard should catch the typo variant too"
}
if (Test-HasTransientPromptReference "See docs/plans/ for durable project docs.") {
    throw "Transient prompt guard should not flag normal supporting-doc references"
}

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
$goalSection = Get-SectionContent -Content $roadmap -Heading "## Goal"
$workflowSection = Get-SectionContent -Content $roadmap -Heading "## Workflow Coverage"
$baselineSection = Get-SectionContent -Content $roadmap -Heading "## Current Baseline"
$nextTracksSection = Get-SectionContent -Content $roadmap -Heading "## Next Major Tracks"
$deferredSection = Get-SectionContent -Content $roadmap -Heading "## Deferred / Blocked"
$supportingDocsSection = Get-SectionContent -Content $roadmap -Heading "## Supporting Docs"

foreach ($signal in @("BGS modpack curation", "not general mod authoring")) {
    if ($goalSection -notmatch [regex]::Escape($signal)) {
        throw "docs/roadmap.md goal section is missing signal: $signal"
    }
}

foreach ($signal in @("setup", "runtime", "toolchain", "MO2", "xEdit", "localization", "testing")) {
    if ($workflowSection -notmatch [regex]::Escape($signal)) {
        throw "docs/roadmap.md workflow section is missing signal: $signal"
    }
}

if ($baselineSection -notmatch 'bootstrap' -or ($baselineSection -notmatch 'skeleton' -and $baselineSection -notmatch 'placeholder')) {
    throw "docs/roadmap.md current baseline section must describe the bootstrap baseline honestly"
}

if ($nextTracksSection -notmatch 'workflow' -or $nextTracksSection -notmatch 'xEdit') {
    throw "docs/roadmap.md next major tracks section is missing the next implementation signals"
}

if ($deferredSection -notmatch 'defer' -and $deferredSection -notmatch 'block') {
    throw "docs/roadmap.md deferred section must clearly mark deferred or blocked work"
}

foreach ($signal in @("docs/plans/", "docs/standards/repo-hygiene.md")) {
    if ($supportingDocsSection -notmatch [regex]::Escape($signal)) {
        throw "docs/roadmap.md supporting docs section is missing signal: $signal"
    }
}

if (Test-HasTransientPromptReference $roadmap) {
    throw "docs/roadmap.md should not treat the transient initial prompt file as a supporting source"
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

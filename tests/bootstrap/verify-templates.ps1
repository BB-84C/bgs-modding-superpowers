$ErrorActionPreference = "Stop"

$requiredPaths = @(
    "templates/modpack/dev-log-template.md",
    "templates/modpack/dev-log-index-template.md",
    "templates/modpack/release-changelog-template.md"
)

$missing = $requiredPaths | Where-Object { -not (Test-Path $_) }
if ($missing.Count -gt 0) {
    throw "Missing template files: $($missing -join ', ')"
}

$devLog = Get-Content "templates/modpack/dev-log-template.md" -Raw
foreach ($heading in @("# Modpack Development Log", "## Table of Contents", "## Active Decisions", "## Unresolved Issues")) {
    if ($devLog -notmatch [regex]::Escape($heading)) {
        throw "Dev log template is missing heading: $heading"
    }
}

foreach ($phrase in @("Use short dated bullets or mini-subheadings", "Example:", "Keep each entry scoped to one decision, install batch, or investigation thread")) {
    if ($devLog -notmatch [regex]::Escape($phrase)) {
        throw "Dev log template is missing guidance: $phrase"
    }
}

$devLogIndex = Get-Content "templates/modpack/dev-log-index-template.md" -Raw
foreach ($phrase in @("# Dev Log Index Companion", "## How To Use", "| Entry | Section | Status | Anchor |", "Example decision", "Active Decisions", "Deferred", '`#active-decisions`')) {
    if ($devLogIndex -notmatch [regex]::Escape($phrase)) {
        throw "Dev log index template is missing expected structure: $phrase"
    }
}

$changelog = Get-Content "templates/modpack/release-changelog-template.md" -Raw
foreach ($heading in @("# Changelog", "## Added", "## Changed", "## Fixed", "## Removed", "## Upgrade Notes")) {
    if ($changelog -notmatch [regex]::Escape($heading)) {
        throw "Release changelog template is missing heading: $heading"
    }
}

if ($changelog -notmatch [regex]::Escape("List player-facing upgrade steps, save-impact warnings, required tool reruns, and known migration risks.")) {
    throw "Release changelog template is missing Upgrade Notes guidance"
}

Write-Host "Template bootstrap checks passed."

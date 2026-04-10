$ErrorActionPreference = "Stop"

$requiredPaths = @(
    "skills/mod-evaluator/SKILL.md",
    "skills/install-planner/SKILL.md",
    "skills/conflict-auditor/SKILL.md",
    "skills/write-dev-log/SKILL.md",
    "skills/write-release-changelog/SKILL.md",
    "skills/localization-assistant/SKILL.md",
    "skills/test-session-guide/SKILL.md"
)

$missing = $requiredPaths | Where-Object { -not (Test-Path $_) }
if ($missing.Count -gt 0) {
    throw "Missing skill files: $($missing -join ', ')"
}

$requiredHeadings = @("## Purpose", "## When To Use", "## Workflow", "## Outputs")

function Get-SectionBody {
    param(
        [string]$Content,
        [string]$Heading
    )

    $escapedHeading = [regex]::Escape($Heading)
    $pattern = "(?ms)^$escapedHeading\s*(.*?)\s*(?=^##\s|\z)"
    $match = [regex]::Match($Content, $pattern)

    if (-not $match.Success) {
        return $null
    }

    return $match.Groups[1].Value.Trim()
}

foreach ($path in $requiredPaths) {
    $content = Get-Content $path -Raw
    foreach ($heading in $requiredHeadings) {
        $sectionBody = Get-SectionBody -Content $content -Heading $heading
        if ($null -eq $sectionBody) {
            throw "$path is missing heading: $heading"
        }

        if ([string]::IsNullOrWhiteSpace($sectionBody)) {
            throw "$path has an empty section body: $heading"
        }
    }
}

Write-Host "Skill bootstrap checks passed."

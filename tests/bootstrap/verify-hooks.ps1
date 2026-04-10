$ErrorActionPreference = "Stop"

$requiredPaths = @(
    "hooks/runtime-compatibility.md",
    "hooks/repo-cleanliness.md",
    "hooks/scope-guard.md",
    "hooks/dev-log-reminder.md"
)

$missing = $requiredPaths | Where-Object { -not (Test-Path $_) }
if ($missing.Count -gt 0) {
    throw "Missing hook files: $($missing -join ', ')"
}

foreach ($path in $requiredPaths) {
    $content = Get-Content $path -Raw
    foreach ($heading in @("## Trigger", "## Check", "## Action")) {
        if ($content -notmatch [regex]::Escape($heading)) {
            throw "$path is missing heading: $heading"
        }
    }
}

Write-Host "Hook bootstrap checks passed."

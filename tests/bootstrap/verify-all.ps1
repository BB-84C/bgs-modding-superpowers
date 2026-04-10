$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path

$checks = @(
    "tests/bootstrap/verify-foundation.ps1",
    "tests/bootstrap/verify-layout.ps1",
    "tests/bootstrap/verify-skills.ps1",
    "tests/bootstrap/verify-hooks.ps1",
    "tests/bootstrap/verify-templates.ps1",
    "tests/bootstrap/verify-specs.ps1"
)

Push-Location $repoRoot
try {
    foreach ($check in $checks) {
        & (Join-Path $repoRoot $check)
    }
}
finally {
    Pop-Location
}

Write-Host "All bootstrap checks passed."

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "..\helpers\tracked-temp.ps1")

$first = New-TrackedTestTempDirectory -Prefix "mo2-vfs-tracked-temp-"
$sessionRoot = New-TrackedTestTempDirectory -Prefix "xedit-client-sessions-test-"
New-Item -ItemType Directory -Path (Join-Path $sessionRoot "secondary-session") -Force | Out-Null

try {
    if (-not (Test-Path $first -PathType Container)) { throw "tracked primary temp directory was not created" }
    if (-not (Test-Path (Join-Path $sessionRoot "secondary-session") -PathType Container)) { throw "tracked secondary session directory was not created" }
}
finally {
    Remove-TrackedTestTempDirectories
}

if ((Test-Path $first) -or (Test-Path $sessionRoot)) {
    throw "tracked test cleanup must remove primary and secondary session directories"
}

Write-Host "tracked PowerShell test temp cleanup checks passed."

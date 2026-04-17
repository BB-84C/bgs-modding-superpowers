$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/common.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/session.ps1")

$sessionId = "sess-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
$session = Open-Mo2ControlPlaneSession -SessionId $sessionId
$expectedRoot = Join-Path (Join-Path $env:TEMP "mo2-control-plane") $sessionId

if ($session.SessionId -ne $sessionId) { throw "Expected session id to round-trip" }
if ($session.Root -ne $expectedRoot) { throw "Expected deterministic session root" }
if ($session.LaunchesRoot -ne (Join-Path $expectedRoot "launches")) { throw "Expected launches child path" }
if ($session.ArtifactsRoot -ne (Join-Path $expectedRoot "artifacts")) { throw "Expected artifacts child path" }

foreach ($path in @($session.Root, $session.LaunchesRoot, $session.ArtifactsRoot)) {
    if (-not (Test-Path $path -PathType Container)) {
        throw "Expected session path to exist: $path"
    }
}

$reopenedSession = Open-Mo2ControlPlaneSession -SessionId $sessionId
if ($reopenedSession.Root -ne $session.Root) { throw "Expected session reopen to reuse the same root" }
if ($reopenedSession.ArtifactsRoot -ne $session.ArtifactsRoot) { throw "Expected session reopen to reuse the same artifact root" }

$externallySuppliedSessionId = "sess-11111111111111111111111111111111"
$externalSession = Open-Mo2ControlPlaneSession -SessionId $externallySuppliedSessionId
if ($externalSession.SessionId -ne $externallySuppliedSessionId) {
    throw "Expected externally supplied valid session ids to work"
}

foreach ($invalidSessionId in @("", "..\\escape", "sess-nothex", "sess-123", "sess-11111111111111111111111111111111\\child", "sess-11111111111111111111111111111111/child", "plain-text")) {
    try {
        $null = Get-Mo2ControlPlaneSession -SessionId $invalidSessionId
        throw "Invalid session ids should fail closed: $invalidSessionId"
    }
    catch {
        if ($_.Exception.Message -notmatch [regex]::Escape("Invalid session id: $invalidSessionId")) {
            throw
        }
    }
}

$unknownSessionId = "sess-22222222222222222222222222222222"
if (Test-Path (Join-Path (Get-Mo2ControlPlaneRoot) $unknownSessionId)) {
    Remove-Item -Path (Join-Path (Get-Mo2ControlPlaneRoot) $unknownSessionId) -Recurse -Force
}

try {
    $null = Get-Mo2ControlPlaneSession -SessionId $unknownSessionId
    throw "Unknown sessions should not be materialized by read-only lookup"
}
catch {
    if ($_.Exception.Message -notmatch [regex]::Escape("Session not found: $unknownSessionId")) {
        throw
    }
}

if (Test-Path (Join-Path (Get-Mo2ControlPlaneRoot) $unknownSessionId)) {
    throw "Read-only session lookup should not create directories for unknown sessions"
}

Write-Host "MO2 control-plane session checks passed."

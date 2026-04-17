$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/common.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/protocol.ps1")

$request = New-Mo2ControlPlaneRequest -SessionId "sess-1" -Command "system.ping" -Payload @{ ok = $true }
if ($request.protocol_version -ne "1") { throw "Expected protocol version 1" }
if ($request.request_id -notmatch '^req-[0-9a-f]{32}$') { throw "Expected request_id to use req- GUID format" }
if ($request.session_id -ne "sess-1") { throw "Expected session_id to round-trip" }
if ($request.command -ne "system.ping") { throw "Expected command to round-trip" }
if ($request.payload.ok -ne $true) { throw "Expected payload to round-trip" }

$structuredError = New-Mo2ControlPlaneError -Code "validation_error" -Message "Bad request" -Details @{ field = "command" }
if ($structuredError.code -ne "validation_error") { throw "Expected structured error code" }
if ($structuredError.message -ne "Bad request") { throw "Expected structured error message" }
if ($structuredError.details.field -ne "command") { throw "Expected structured error details" }

$metadata = Get-Mo2ControlPlaneCommandClassMetadata
foreach ($className in @("safe-read", "controlled-write", "dangerous-write")) {
    if (-not $metadata.Contains($className)) {
        throw "Missing command class metadata for $className"
    }

    if ($metadata[$className].name -ne $className) {
        throw "Command class metadata should preserve the class name for $className"
    }
}

$parsedOptions = ConvertTo-Mo2ControlPlaneOptionMap -Arguments @("--session-id", "sess-11111111111111111111111111111111")
if ($parsedOptions["--session-id"] -ne "sess-11111111111111111111111111111111") {
    throw "Expected well-formed options to parse"
}

foreach ($case in @(
    @{ Arguments = @("--session-id", "--foo"); Message = "Missing value for option: --session-id" },
    @{ Arguments = @("--session-id"); Message = "Missing value for option: --session-id" },
    @{ Arguments = @("unexpected-value"); Message = "Unexpected argument: unexpected-value" },
    @{ Arguments = @("--session-id", "sess-11111111111111111111111111111111", "dangling-value"); Message = "Unexpected argument: dangling-value" }
)) {
    try {
        $null = ConvertTo-Mo2ControlPlaneOptionMap -Arguments $case.Arguments
        throw "Malformed option sequences should fail closed: $($case.Arguments -join ' ')"
    }
    catch {
        if ($_.Exception.Message -notmatch [regex]::Escape($case.Message)) {
            throw
        }
    }
}

Write-Host "MO2 control-plane protocol checks passed."

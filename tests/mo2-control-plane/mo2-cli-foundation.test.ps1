$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$cliPath = Join-Path $repoRoot "tools/mo2-control-plane/broker/bin/mo2-cli.ps1"
$fakeKernelResponsePath = Join-Path $PSScriptRoot "fixtures/fake-kernel-response.json"

function Invoke-Cli {
    param(
        [string[]]$Arguments
    )

    $output = & pwsh -NoProfile -File $cliPath @Arguments 2>&1

    [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = ($output | ForEach-Object { $_.ToString() }) -join "`n"
    }
}

$env:MO2_CONTROL_PLANE_FAKE_RESPONSE_PATH = $fakeKernelResponsePath

$ping = Invoke-Cli -Arguments @("system", "ping")
if ($ping.ExitCode -ne 0) {
    throw "mo2-cli system ping should succeed"
}

$pingJson = $ping.Output | ConvertFrom-Json -ErrorAction Stop
if (-not $pingJson.ok) { throw "system ping should report ok=true" }
if ($pingJson.result.status -ne "ok") { throw "system ping should report status ok" }

$pingUnexpected = Invoke-Cli -Arguments @("system", "ping", "unexpected")
if ($pingUnexpected.ExitCode -eq 0) {
    throw "system ping should reject unexpected trailing arguments"
}

$pingUnexpectedJson = $pingUnexpected.Output | ConvertFrom-Json -ErrorAction Stop
if ($pingUnexpectedJson.ok -ne $false) { throw "system ping trailing arguments should return ok=false" }
if ($pingUnexpectedJson.error.code -ne "validation_error") { throw "system ping trailing arguments should return validation_error" }

$capabilities = Invoke-Cli -Arguments @("system", "capabilities")
if ($capabilities.ExitCode -ne 0) {
    throw "mo2-cli system capabilities should succeed"
}

$capabilitiesJson = $capabilities.Output | ConvertFrom-Json -ErrorAction Stop
foreach ($commandName in @("system.ping", "system.capabilities", "session.open", "session.artifacts")) {
    if ($capabilitiesJson.result.commands -notcontains $commandName) {
        throw "system capabilities should advertise $commandName"
    }
}

$capabilitiesUnexpected = Invoke-Cli -Arguments @("system", "capabilities", "--foo", "bar")
if ($capabilitiesUnexpected.ExitCode -eq 0) {
    throw "system capabilities should reject unexpected options"
}

$capabilitiesUnexpectedJson = $capabilitiesUnexpected.Output | ConvertFrom-Json -ErrorAction Stop
if ($capabilitiesUnexpectedJson.ok -ne $false) { throw "system capabilities unexpected options should return ok=false" }
if ($capabilitiesUnexpectedJson.error.code -ne "validation_error") { throw "system capabilities unexpected options should return validation_error" }

$sessionOpen = Invoke-Cli -Arguments @("session", "open")
if ($sessionOpen.ExitCode -ne 0) {
    throw "mo2-cli session open should succeed"
}

$sessionOpenJson = $sessionOpen.Output | ConvertFrom-Json -ErrorAction Stop
if ($sessionOpenJson.result.session_id -notmatch '^sess-[0-9a-f]{32}$') {
    throw "session open should generate a session id"
}

if (-not (Test-Path $sessionOpenJson.result.artifacts_root -PathType Container)) {
    throw "session open should create the artifacts root"
}

$sessionOpenUnexpected = Invoke-Cli -Arguments @("session", "open", "unexpected")
if ($sessionOpenUnexpected.ExitCode -eq 0) {
    throw "session open should reject unexpected trailing arguments"
}

$sessionOpenUnexpectedJson = $sessionOpenUnexpected.Output | ConvertFrom-Json -ErrorAction Stop
if ($sessionOpenUnexpectedJson.ok -ne $false) { throw "session open trailing arguments should return ok=false" }
if ($sessionOpenUnexpectedJson.error.code -ne "validation_error") { throw "session open trailing arguments should return validation_error" }

$sessionArtifacts = Invoke-Cli -Arguments @("session", "artifacts", "--session-id", $sessionOpenJson.result.session_id)
if ($sessionArtifacts.ExitCode -ne 0) {
    throw "mo2-cli session artifacts should succeed"
}

$sessionArtifactsJson = $sessionArtifacts.Output | ConvertFrom-Json -ErrorAction Stop
if ($sessionArtifactsJson.result.session_id -ne $sessionOpenJson.result.session_id) {
    throw "session artifacts should round-trip the requested session id"
}

if ($sessionArtifactsJson.result.artifacts_root -ne $sessionOpenJson.result.artifacts_root) {
    throw "session artifacts should report the session artifact root"
}

$sessionArtifactsUnexpected = Invoke-Cli -Arguments @("session", "artifacts", "--session-id", $sessionOpenJson.result.session_id, "--foo", "bar")
if ($sessionArtifactsUnexpected.ExitCode -eq 0) {
    throw "session artifacts should reject unexpected trailing options"
}

$sessionArtifactsUnexpectedJson = $sessionArtifactsUnexpected.Output | ConvertFrom-Json -ErrorAction Stop
if ($sessionArtifactsUnexpectedJson.ok -ne $false) { throw "session artifacts trailing options should return ok=false" }
if ($sessionArtifactsUnexpectedJson.error.code -ne "validation_error") { throw "session artifacts trailing options should return validation_error" }

$missingOptions = Invoke-Cli -Arguments @()
if ($missingOptions.ExitCode -eq 0) {
    throw "mo2-cli should reject missing command arguments"
}

$missingOptionsJson = $missingOptions.Output | ConvertFrom-Json -ErrorAction Stop
if ($missingOptionsJson.ok -ne $false) { throw "missing command arguments should return ok=false" }
if ($missingOptionsJson.error.code -ne "validation_error") { throw "missing command arguments should return validation_error" }

$unknownCommand = Invoke-Cli -Arguments @("system", "wat")
if ($unknownCommand.ExitCode -eq 0) {
    throw "mo2-cli should reject unknown commands"
}

$unknownCommandJson = $unknownCommand.Output | ConvertFrom-Json -ErrorAction Stop
if ($unknownCommandJson.ok -ne $false) { throw "unknown commands should return ok=false" }
if ($unknownCommandJson.error.code -ne "unsupported_command") { throw "unknown commands should return unsupported_command" }

$missingSessionId = Invoke-Cli -Arguments @("session", "artifacts")
if ($missingSessionId.ExitCode -eq 0) {
    throw "session artifacts should reject missing --session-id"
}

$missingSessionIdJson = $missingSessionId.Output | ConvertFrom-Json -ErrorAction Stop
if ($missingSessionIdJson.ok -ne $false) { throw "missing --session-id should return ok=false" }
if ($missingSessionIdJson.error.code -ne "validation_error") { throw "missing --session-id should return validation_error" }

$sessionOpenForLaunch = Invoke-Cli -Arguments @("session", "open")
if ($sessionOpenForLaunch.ExitCode -ne 0) {
    throw "session open should succeed before launch validation checks"
}

$sessionOpenForLaunchJson = $sessionOpenForLaunch.Output | ConvertFrom-Json -ErrorAction Stop
foreach ($launchCommand in @("status", "wait", "stop")) {
    $missingLaunchId = Invoke-Cli -Arguments @("launch", $launchCommand, "--session-id", $sessionOpenForLaunchJson.result.session_id)
    if ($missingLaunchId.ExitCode -eq 0) {
        throw "launch $launchCommand should reject missing --launch-id even without fake-kernel mode"
    }

    $missingLaunchIdJson = $missingLaunchId.Output | ConvertFrom-Json -ErrorAction Stop
    if ($missingLaunchIdJson.ok -ne $false) { throw "launch $launchCommand missing --launch-id should return ok=false" }
    if ($missingLaunchIdJson.error.code -ne "validation_error") { throw "launch $launchCommand missing --launch-id should return validation_error" }
}

$invalidSessionId = Invoke-Cli -Arguments @("session", "artifacts", "--session-id", "..\\escape")
if ($invalidSessionId.ExitCode -eq 0) {
    throw "session artifacts should reject invalid session ids"
}

$invalidSessionIdJson = $invalidSessionId.Output | ConvertFrom-Json -ErrorAction Stop
if ($invalidSessionIdJson.ok -ne $false) { throw "invalid session ids should return ok=false" }
if ($invalidSessionIdJson.error.code -ne "validation_error") { throw "invalid session ids should return validation_error" }

$unknownSessionId = "sess-33333333333333333333333333333333"
$unknownSessionRoot = Join-Path (Join-Path $env:TEMP "mo2-control-plane") $unknownSessionId
if (Test-Path $unknownSessionRoot) {
    Remove-Item -Path $unknownSessionRoot -Recurse -Force
}

$unknownSession = Invoke-Cli -Arguments @("session", "artifacts", "--session-id", $unknownSessionId)
if ($unknownSession.ExitCode -eq 0) {
    throw "session artifacts should fail for unknown but well-formed session ids"
}

$unknownSessionJson = $unknownSession.Output | ConvertFrom-Json -ErrorAction Stop
if ($unknownSessionJson.ok -ne $false) { throw "unknown sessions should return ok=false" }
if ($unknownSessionJson.error.code -ne "mo2_state_error") { throw "unknown sessions should return mo2_state_error" }
if (Test-Path $unknownSessionRoot) {
    throw "unknown session lookups should not create directories"
}

$malformedOptions = Invoke-Cli -Arguments @("session", "artifacts", "--session-id", "--foo")
if ($malformedOptions.ExitCode -eq 0) {
    throw "session artifacts should fail closed for malformed option sequences"
}

$malformedOptionsJson = $malformedOptions.Output | ConvertFrom-Json -ErrorAction Stop
if ($malformedOptionsJson.ok -ne $false) { throw "malformed options should return ok=false" }
if ($malformedOptionsJson.error.code -ne "validation_error") { throw "malformed options should return validation_error" }

$originalFixture = $env:MO2_CONTROL_PLANE_FAKE_RESPONSE_PATH
$env:MO2_CONTROL_PLANE_FAKE_RESPONSE_PATH = Join-Path $PSScriptRoot "fixtures/missing-fixture.json"
$missingFixture = Invoke-Cli -Arguments @("system", "ping")
$env:MO2_CONTROL_PLANE_FAKE_RESPONSE_PATH = $originalFixture

if ($missingFixture.ExitCode -eq 0) {
    throw "system ping should fail when the fake fixture is unavailable"
}

$missingFixtureJson = $missingFixture.Output | ConvertFrom-Json -ErrorAction Stop
if ($missingFixtureJson.ok -ne $false) { throw "missing fixture should return ok=false" }
if ($missingFixtureJson.error.code -ne "transport_error") { throw "missing fixture should return transport_error" }

Write-Host "MO2 control-plane CLI foundation checks passed."

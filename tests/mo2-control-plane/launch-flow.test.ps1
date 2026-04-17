$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$cliPath = Join-Path $repoRoot "tools/mo2-control-plane/broker/bin/mo2-cli.ps1"
$fakeKernelResponsePath = Join-Path $PSScriptRoot "fixtures/fake-kernel-response.json"
$fakeKernelPath = Join-Path $PSScriptRoot "fixtures/fake-kernel.ps1"
$kernelLogPath = Join-Path $env:TEMP ("mo2-control-plane-launch-flow-" + [guid]::NewGuid().ToString("N") + ".log")

. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/common.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/protocol.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/session.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/launch.ps1")

function Invoke-Cli {
    param(
        [string[]]$Arguments
    )

    $output = & pwsh -NoProfile -File $cliPath @Arguments 2>&1

    return [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = ($output | ForEach-Object { $_.ToString() }) -join "`n"
    }
}

function Read-JsonLogEntries {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path -PathType Leaf)) {
        return @()
    }

    $entries = @()
    foreach ($line in (Get-Content -Path $Path | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })) {
        $entries += ($line | ConvertFrom-Json -ErrorAction Stop)
    }

    return $entries
}

$env:MO2_CONTROL_PLANE_FAKE_RESPONSE_PATH = $fakeKernelResponsePath
$env:MO2_CONTROL_PLANE_FAKE_KERNEL_PATH = $fakeKernelPath
$env:MO2_CONTROL_PLANE_FAKE_KERNEL_LOG_PATH = $kernelLogPath

$missingLaunchIdRequest = New-Mo2ControlPlaneRequest -SessionId "sess-11111111111111111111111111111111" -Command "launch.status" -Payload @{}
try {
    $null = Invoke-Mo2ControlPlaneFakeKernelLaunchCommand -Request $missingLaunchIdRequest
    throw "launch helper should reject missing launch_id for non-start commands"
}
catch {
    if ($_.Exception.Message -ne "Missing launch id for launch.status") {
        throw "launch helper should fail explicitly for missing launch_id"
    }
}

$sessionOpen = Invoke-Cli -Arguments @("session", "open")
if ($sessionOpen.ExitCode -ne 0) {
    throw "session open should succeed before launch-flow checks"
}

$sessionOpenJson = $sessionOpen.Output | ConvertFrom-Json -ErrorAction Stop
$sessionId = $sessionOpenJson.result.session_id

$start = Invoke-Cli -Arguments @("launch", "start", "--session-id", $sessionId)
if ($start.ExitCode -ne 0) {
    throw "launch start should succeed with a fake kernel: $($start.Output)"
}

$startJson = $start.Output | ConvertFrom-Json -ErrorAction Stop
if (-not $startJson.ok) { throw "launch start should report ok=true" }
if ($startJson.result.launch_id -notmatch '^launch-[0-9a-f]{32}$') {
    throw "launch start should return a normalized launch_id"
}
if ([int]$startJson.result.pid -le 0) {
    throw "launch start should return a positive pid"
}
if ($startJson.result.status -ne "running") {
    throw "launch start should report running status"
}
if ([string]::IsNullOrWhiteSpace($startJson.result.artifacts.state_file)) {
    throw "launch start should report artifacts.state_file"
}
if (-not (Test-Path $startJson.result.artifacts.state_file -PathType Leaf)) {
    throw "launch start should materialize the reported state file"
}

$launchId = $startJson.result.launch_id

$status = Invoke-Cli -Arguments @("launch", "status", "--session-id", $sessionId, "--launch-id", $launchId)
if ($status.ExitCode -ne 0) {
    throw "launch status should succeed with a fake kernel: $($status.Output)"
}

$statusJson = $status.Output | ConvertFrom-Json -ErrorAction Stop
if (-not $statusJson.ok) { throw "launch status should report ok=true" }
if ($statusJson.result.launch_id -ne $launchId) {
    throw "launch status should preserve launch_id"
}
if ($statusJson.result.pid -ne $startJson.result.pid) {
    throw "launch status should preserve pid"
}
if ($statusJson.result.status -ne "running") {
    throw "launch status should report running before wait"
}
if ($statusJson.result.artifacts.state_file -ne $startJson.result.artifacts.state_file) {
    throw "launch status should preserve artifacts.state_file"
}

$wait = Invoke-Cli -Arguments @("launch", "wait", "--session-id", $sessionId, "--launch-id", $launchId)
if ($wait.ExitCode -ne 0) {
    throw "launch wait should succeed with a fake kernel: $($wait.Output)"
}

$waitJson = $wait.Output | ConvertFrom-Json -ErrorAction Stop
if (-not $waitJson.ok) { throw "launch wait should report ok=true" }
if ($waitJson.result.launch_id -ne $launchId) {
    throw "launch wait should preserve launch_id"
}
if ($waitJson.result.status -ne "running") {
    throw "launch wait should preserve running status when fake-kernel transport has no real process to await"
}
if ($waitJson.result.artifacts.state_file -ne $startJson.result.artifacts.state_file) {
    throw "launch wait should preserve artifacts.state_file"
}

$stop = Invoke-Cli -Arguments @("launch", "stop", "--session-id", $sessionId, "--launch-id", $launchId)
if ($stop.ExitCode -ne 0) {
    throw "launch stop should succeed with a fake kernel: $($stop.Output)"
}

$stopJson = $stop.Output | ConvertFrom-Json -ErrorAction Stop
if (-not $stopJson.ok) { throw "launch stop should report ok=true" }
if ($stopJson.result.launch_id -ne $launchId) {
    throw "launch stop should preserve launch_id"
}
if ($stopJson.result.status -ne "stopped") {
    throw "launch stop should report stopped status"
}
if ($stopJson.result.artifacts.state_file -ne $startJson.result.artifacts.state_file) {
    throw "launch stop should preserve artifacts.state_file"
}

$stateDocument = Get-Content -Path $startJson.result.artifacts.state_file -Raw | ConvertFrom-Json -ErrorAction Stop
if ($stateDocument.status -ne "stopped") {
    throw "launch stop should persist the latest status transition"
}

$realTargetPath = Join-Path $repoRoot "tests/mo2-vfs-launcher/fixtures/target-ok.ps1"

$realWaitStartRequest = New-Mo2ControlPlaneRequest -SessionId $sessionId -Command "launch.start" -Payload ([ordered]@{
    transport = [ordered]@{
        target_path = $realTargetPath
        args = @()
        env = @{}
        wait_mode = "spawned"
        fake_wait_milliseconds = 250
        fake_exit_code = 0
    }
})
if (-not (Test-Mo2ControlPlaneTransportPayload -Request $realWaitStartRequest)) {
    throw "ordered launch.start payloads should be recognized as transport launches"
}

$realWaitStart = Invoke-Mo2ControlPlaneFakeKernelLaunchCommand -Request $realWaitStartRequest
if ($realWaitStart.status -ne "running") {
    throw "fake-kernel launch.start with transport should begin in running state before wait"
}

$realWaitLogEntry = @(Read-JsonLogEntries -Path $kernelLogPath | Where-Object {
    $_.command -eq "launch.start" -and
    $_.launch_id -eq $realWaitStart.launch_id
} | Select-Object -Last 1)
if ($null -eq $realWaitLogEntry) {
    throw "fake-kernel transport start should be logged"
}

if ($realWaitLogEntry.session_id -ne $sessionId) {
    throw "fake-kernel transport should preserve the caller session id"
}

$realWaitRequest = New-Mo2ControlPlaneRequest -SessionId $sessionId -Command "launch.wait" -Payload @{ launch_id = $realWaitStart.launch_id }
$realWait = Invoke-Mo2ControlPlaneFakeKernelLaunchCommand -Request $realWaitRequest
if ($realWait.status -ne "completed") {
    throw "fake-kernel launch.wait should report completed after the target exits"
}

$realWaitState = Get-Content -Path $realWait.artifacts.state_file -Raw | ConvertFrom-Json -ErrorAction Stop
if ($realWaitState.status -ne "completed") {
    throw "fake-kernel launch.wait should persist the completed status after the target exits"
}

if ($realWaitState.exit_code -ne 0) {
    throw "fake-kernel launch.wait should persist the real target exit code"
}

Write-Host "MO2 launch fake-kernel flow checks passed."

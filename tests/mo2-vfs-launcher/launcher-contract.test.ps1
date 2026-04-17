$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path
$launcherPath = Join-Path $repoRoot "tools/mo2-vfs-launcher/mo2-vfs-launcher.ps1"
$fakeKernelPath = Join-Path $repoRoot "tests/mo2-control-plane/fixtures/fake-kernel.ps1"
$targetOkPath = Join-Path $PSScriptRoot "fixtures/target-ok.ps1"
$targetSleepPath = Join-Path $PSScriptRoot "fixtures/target-sleep.ps1"
$targetFailPath = Join-Path $PSScriptRoot "fixtures/target-fail.ps1"

function Invoke-Launcher {
    param(
        [string[]]$Arguments
    )

    $output = & pwsh -NoProfile -File $launcherPath @Arguments 2>&1

    [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = ($output | ForEach-Object { $_.ToString() }) -join "`n"
    }
}

function Read-StateJson {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path -PathType Leaf)) {
        throw "Expected launcher state file to exist: $Path"
    }

    return Get-Content -Path $Path -Raw | ConvertFrom-Json -ErrorAction Stop
}

function Read-TextFile {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path -PathType Leaf)) {
        throw "Expected file to exist: $Path"
    }

    return [System.IO.File]::ReadAllText($Path)
}

function Assert-LauncherSourceIsBrokerOnly {
    param(
        [string]$Path
    )

    $source = Read-TextFile -Path $Path
    foreach ($forbiddenPattern in @(
        'function\s+Invoke-Mo2VfsLauncherDirectTransport\b',
        'Invoke-Mo2VfsLauncherDirectTransport\s+-',
        'StartInfo\s*=\s*\[System\.Diagnostics\.ProcessStartInfo\]::new\(',
        'process\.StandardOutput\.ReadToEndAsync\('
    )) {
        if ($source -match $forbiddenPattern) {
            throw "launcher should remain transport-agnostic and broker-only: matched '$forbiddenPattern'"
        }
    }
}

function Read-KernelLogEntries {
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

function Assert-JsonCoreFields {
    param(
        $State,
        [string]$ExpectedStatus,
        [string]$ExpectedSessionId,
        [string]$ExpectedTargetPath
    )

    if ($State.status -ne $ExpectedStatus) {
        throw "Expected state status '$ExpectedStatus' but received '$($State.status)'"
    }

    if ($State.session_id -ne $ExpectedSessionId) {
        throw "Expected state session_id '$ExpectedSessionId' but received '$($State.session_id)'"
    }

    if ($State.target_path -ne $ExpectedTargetPath) {
        throw "Expected state target_path '$ExpectedTargetPath' but received '$($State.target_path)'"
    }

    if (-not $State.pid) {
        throw "Expected state pid to be populated"
    }
}

foreach ($path in @($targetOkPath, $targetSleepPath, $targetFailPath)) {
    if (-not (Test-Path $path -PathType Leaf)) {
        throw "Missing required fixture: $path"
    }
}

if (-not (Test-Path $fakeKernelPath -PathType Leaf)) {
    throw "Missing fake kernel fixture: $fakeKernelPath"
}

$tempRoot = Join-Path $env:TEMP ("mo2-vfs-launcher-test-" + [guid]::NewGuid().ToString("N"))
$null = New-Item -ItemType Directory -Path $tempRoot -Force
$spawnedPids = @()
$kernelLogPath = Join-Path $tempRoot "broker-kernel.log"
$env:MO2_CONTROL_PLANE_FAKE_KERNEL_PATH = $fakeKernelPath
$env:MO2_CONTROL_PLANE_FAKE_KERNEL_LOG_PATH = $kernelLogPath

try {
    Assert-LauncherSourceIsBrokerOnly -Path $launcherPath

    $missingRequired = Invoke-Launcher -Arguments @()
    if ($missingRequired.ExitCode -eq 0) {
        throw "launcher should fail when required options are missing"
    }

    if ($missingRequired.Output -notmatch [regex]::Escape("Missing required options: --target-path, --session-id, --state-file")) {
        throw "launcher should explain missing required options cleanly"
    }

    $malformedStatePath = Join-Path $tempRoot "malformed-env-state.json"
    $malformedEnv = Invoke-Launcher -Arguments @(
        "--target-path",
        $targetOkPath,
        "--session-id",
        "session-malformed-env",
        "--state-file",
        $malformedStatePath,
        "--env",
        "BROKEN"
    )

    if ($malformedEnv.ExitCode -eq 0) {
        throw "launcher should reject malformed --env values"
    }

    if ($malformedEnv.Output -notmatch [regex]::Escape("Invalid --env value: BROKEN")) {
        throw "launcher should fail closed for malformed --env"
    }

    $malformedState = Read-StateJson -Path $malformedStatePath
    if ($malformedState.status -ne "failed") {
        throw "malformed --env should write failed status to state file"
    }

    if ($malformedState.session_id -ne "session-malformed-env") {
        throw "malformed --env should preserve session_id in state file"
    }

    if ($malformedState.target_path -ne $targetOkPath) {
        throw "malformed --env should preserve target_path in state file"
    }

    if ($malformedState.error -ne "Invalid --env value: BROKEN") {
        throw "malformed --env should record the failure reason in state file"
    }

    $invalidWaitStatePath = Join-Path $tempRoot "invalid-wait-state.json"
    $invalidWaitMode = Invoke-Launcher -Arguments @(
        "--target-path",
        $targetOkPath,
        "--session-id",
        "session-invalid-wait",
        "--state-file",
        $invalidWaitStatePath,
        "--wait-mode",
        "later"
    )

    if ($invalidWaitMode.ExitCode -eq 0) {
        throw "launcher should reject unsupported wait modes"
    }

    if ($invalidWaitMode.Output -notmatch [regex]::Escape("Invalid --wait-mode: later. Supported wait modes: spawned, exit")) {
        throw "launcher should fail closed for invalid wait modes"
    }

    $invalidWaitState = Read-StateJson -Path $invalidWaitStatePath
    if ($invalidWaitState.status -ne "failed") {
        throw "invalid --wait-mode should write failed status to state file"
    }

    if ($invalidWaitState.error -ne "Invalid --wait-mode: later. Supported wait modes: spawned, exit") {
        throw "invalid --wait-mode should record the failure reason in state file"
    }

    $spawnedCaptureStatePath = Join-Path $tempRoot "target-sleep-spawned-capture-state.json"
    $spawnedCaptureStdoutPath = Join-Path $tempRoot "target-sleep-spawned.stdout.log"
    $spawnedCaptureStderrPath = Join-Path $tempRoot "target-sleep-spawned.stderr.log"
    $spawnedCaptureResult = Invoke-Launcher -Arguments @(
        "--target-path",
        $targetSleepPath,
        "--session-id",
        "session-spawned-capture",
        "--state-file",
        $spawnedCaptureStatePath,
        "--wait-mode",
        "spawned",
        "--stdout-file",
        $spawnedCaptureStdoutPath,
        "--stderr-file",
        $spawnedCaptureStderrPath
    )

    if ($spawnedCaptureResult.ExitCode -eq 0) {
        throw "launcher should reject --stdout-file/--stderr-file in spawned wait mode"
    }

    if ($spawnedCaptureResult.Output -notmatch [regex]::Escape("--stdout-file and --stderr-file are only supported when --wait-mode=exit")) {
        throw "spawned capture misuse should report a deterministic error"
    }

    $spawnedCaptureState = Read-StateJson -Path $spawnedCaptureStatePath
    if ($spawnedCaptureState.status -ne "failed") {
        throw "spawned capture misuse should write failed status to state file"
    }

    if ($spawnedCaptureState.session_id -ne "session-spawned-capture") {
        throw "spawned capture misuse should preserve session_id in state file"
    }

    if ($spawnedCaptureState.target_path -ne $targetSleepPath) {
        throw "spawned capture misuse should preserve target_path in state file"
    }

    if ($spawnedCaptureState.error -ne "--stdout-file and --stderr-file are only supported when --wait-mode=exit") {
        throw "spawned capture misuse should be recorded in state"
    }

    if ($null -ne $spawnedCaptureState.pid) {
        throw "spawned capture misuse should not report a pid when no process was started"
    }

    if (Test-Path $spawnedCaptureStdoutPath -PathType Leaf) {
        throw "spawned capture misuse should not create stdout files"
    }

    if (Test-Path $spawnedCaptureStderrPath -PathType Leaf) {
        throw "spawned capture misuse should not create stderr files"
    }

    $exitStatePath = Join-Path $tempRoot "target-ok-exit-state.json"
    $targetResultPath = Join-Path $tempRoot "target-ok.json"
    $exitStdoutPath = Join-Path $tempRoot "target-ok.stdout.log"
    $exitStderrPath = Join-Path $tempRoot "target-ok.stderr.log"
    $exitResult = Invoke-Launcher -Arguments @(
        "--target-path",
        $targetOkPath,
        "--session-id",
        "session-exit",
        "--state-file",
        $exitStatePath,
        "--wait-mode",
        "exit",
        "--stdout-file",
        $exitStdoutPath,
        "--stderr-file",
        $exitStderrPath,
        "--target-arg",
        "first",
        "--target-arg",
        "second item",
        "--target-arg",
        "third",
        "--env",
        "ALPHA=one",
        "--env",
        "BRAVO=two words",
        "--env",
        "MO2_VFS_TEST_EMIT_STREAMS=1",
        "--env",
        "MO2_VFS_TEST_RESULT_PATH=$targetResultPath"
    )

    if ($exitResult.ExitCode -ne 0) {
        throw "launcher should succeed in exit wait mode: $($exitResult.Output)"
    }

    if (-not [string]::IsNullOrWhiteSpace($exitResult.Output)) {
        throw "launcher should write state to --state-file instead of stdout"
    }

    $exitState = Read-StateJson -Path $exitStatePath
    Assert-JsonCoreFields -State $exitState -ExpectedStatus "exited" -ExpectedSessionId "session-exit" -ExpectedTargetPath $targetOkPath

    $exitArgsJson = @($exitState.args) | ConvertTo-Json -Compress
    if ($exitArgsJson -ne '["first","second item","third"]') {
        throw "launcher state should preserve repeated --target-arg values in order"
    }

    if ($exitState.error -ne $null) {
        throw "successful exit state should record null error"
    }

    if ($exitState.exit_code -ne 0) {
        throw "exit wait mode should include exit_code from the target process"
    }

    $exitStdout = Read-TextFile -Path $exitStdoutPath
    if ($exitStdout -notmatch [regex]::Escape("target-ok stdout")) {
        throw "--stdout-file should capture target standard output"
    }

    $exitStderr = Read-TextFile -Path $exitStderrPath
    if ($exitStderr -notmatch [regex]::Escape("target-ok stderr")) {
        throw "--stderr-file should capture target standard error"
    }

    if (-not (Test-Path $targetResultPath -PathType Leaf)) {
        throw "target-ok fixture should write its result file"
    }

    $targetResult = Get-Content -Path $targetResultPath -Raw | ConvertFrom-Json -ErrorAction Stop
    $actualArgsJson = @($targetResult.args) | ConvertTo-Json -Compress
    if ($actualArgsJson -ne '["first","second item","third"]') {
        throw "launcher should preserve repeated --target-arg values in order"
    }

    if ($targetResult.env.ALPHA -ne "one") {
        throw "launcher should apply repeated --env values"
    }

    if ($targetResult.env.BRAVO -ne "two words") {
        throw "launcher should preserve spaces in --env values"
    }

    $kernelLogEntries = @(Read-KernelLogEntries -Path $kernelLogPath | Where-Object { $_.command -eq "launch.start" })
    $exitKernelEntry = $kernelLogEntries | Where-Object { $_.payload.transport.target_path -eq $targetOkPath -and $_.payload.transport.wait_mode -eq "exit" } | Select-Object -Last 1
    if ($null -eq $exitKernelEntry) {
        throw "launcher should hand target execution to broker launch.start in exit wait mode"
    }

    if ($exitKernelEntry.session_id -ne "session-exit") {
        throw "launcher should preserve the caller session id when invoking broker launch.start"
    }

    if ((@($exitKernelEntry.payload.transport.args) | ConvertTo-Json -Compress) -ne '["first","second item","third"]') {
        throw "launcher should pass repeated target args to broker launch.start in order"
    }

    if ($exitKernelEntry.payload.transport.env.ALPHA -ne "one") {
        throw "launcher should forward launch environment through broker launch.start"
    }

    $failedExitStatePath = Join-Path $tempRoot "target-fail-exit-state.json"
    $failedExitStdoutPath = Join-Path $tempRoot "target-fail.stdout.log"
    $failedExitStderrPath = Join-Path $tempRoot "target-fail.stderr.log"
    $failedExitResult = Invoke-Launcher -Arguments @(
        "--target-path",
        $targetFailPath,
        "--session-id",
        "session-fail-exit",
        "--state-file",
        $failedExitStatePath,
        "--wait-mode",
        "exit",
        "--env",
        "MO2_VFS_TEST_EMIT_STREAMS=1",
        "--stdout-file",
        $failedExitStdoutPath,
        "--stderr-file",
        $failedExitStderrPath
    )

    if ($failedExitResult.ExitCode -ne 7) {
        throw "launcher should return the target exit code in exit wait mode"
    }

    $failedExitState = Read-StateJson -Path $failedExitStatePath
    Assert-JsonCoreFields -State $failedExitState -ExpectedStatus "failed" -ExpectedSessionId "session-fail-exit" -ExpectedTargetPath $targetFailPath

    if ($failedExitState.error -ne "Target exited with code 7") {
        throw "non-zero target exit should record a deterministic error"
    }

    if ($failedExitState.exit_code -ne 7) {
        throw "non-zero target exit should preserve the target exit code in state"
    }

    $failedExitStdout = Read-TextFile -Path $failedExitStdoutPath
    if ($failedExitStdout -notmatch [regex]::Escape("target-fail stdout")) {
        throw "--stdout-file should capture output for failing targets"
    }

    $failedExitStderr = Read-TextFile -Path $failedExitStderrPath
    if ($failedExitStderr -notmatch [regex]::Escape("target-fail stderr")) {
        throw "--stderr-file should capture errors for failing targets"
    }

    $timeoutStatePath = Join-Path $tempRoot "target-sleep-timeout-state.json"
    $timeoutStdoutPath = Join-Path $tempRoot "target-sleep-timeout.stdout.log"
    $timeoutStderrPath = Join-Path $tempRoot "target-sleep-timeout.stderr.log"
    $timeoutResult = Invoke-Launcher -Arguments @(
        "--target-path",
        $targetSleepPath,
        "--session-id",
        "session-timeout",
        "--state-file",
        $timeoutStatePath,
        "--wait-mode",
        "exit",
        "--timeout-seconds",
        "1",
        "--env",
        "MO2_VFS_TEST_EMIT_STREAMS=1",
        "--stdout-file",
        $timeoutStdoutPath,
        "--stderr-file",
        $timeoutStderrPath
    )

    if ($timeoutResult.ExitCode -eq 0) {
        throw "launcher should fail when exit wait mode times out"
    }

    $timeoutState = Read-StateJson -Path $timeoutStatePath
    Assert-JsonCoreFields -State $timeoutState -ExpectedStatus "failed" -ExpectedSessionId "session-timeout" -ExpectedTargetPath $targetSleepPath

    if ($timeoutState.error -ne "Timed out after 1 seconds") {
        throw "timeout should record a deterministic error"
    }

    if ($null -ne $timeoutState.exit_code) {
        throw "timeout failure should not report an exit_code"
    }

    $timeoutStdout = Read-TextFile -Path $timeoutStdoutPath
    if ($timeoutStdout -notmatch [regex]::Escape("target-sleep stdout")) {
        throw "timeout path should preserve redirected stdout"
    }

    $timeoutStderr = Read-TextFile -Path $timeoutStderrPath
    if ($timeoutStderr -notmatch [regex]::Escape("target-sleep stderr")) {
        throw "timeout path should preserve redirected stderr"
    }

    $explicitSpawnedStatePath = Join-Path $tempRoot "target-sleep-explicit-spawned-state.json"
    $explicitSpawnedResult = Invoke-Launcher -Arguments @(
        "--target-path",
        $targetSleepPath,
        "--session-id",
        "session-spawned-explicit",
        "--state-file",
        $explicitSpawnedStatePath,
        "--wait-mode",
        "spawned"
    )

    if ($explicitSpawnedResult.ExitCode -ne 0) {
        throw "launcher should succeed in explicit spawned wait mode: $($explicitSpawnedResult.Output)"
    }

    if (-not [string]::IsNullOrWhiteSpace($explicitSpawnedResult.Output)) {
        throw "explicit spawned mode should write state to --state-file instead of stdout"
    }

    $explicitSpawnedState = Read-StateJson -Path $explicitSpawnedStatePath
    Assert-JsonCoreFields -State $explicitSpawnedState -ExpectedStatus "spawned" -ExpectedSessionId "session-spawned-explicit" -ExpectedTargetPath $targetSleepPath

    if (@($explicitSpawnedState.args).Count -ne 0) {
        throw "explicit spawned state should include an empty args array when no target args are supplied"
    }

    if ($explicitSpawnedState.error -ne $null) {
        throw "successful explicit spawned state should record null error"
    }

    if ($null -ne $explicitSpawnedState.exit_code) {
        throw "explicit spawned state should omit exit_code"
    }

    $spawnedPids += [int]$explicitSpawnedState.pid

    $explicitKernelEntry = @(Read-KernelLogEntries -Path $kernelLogPath | Where-Object {
        $_.command -eq "launch.start" -and
        $_.payload.transport.target_path -eq $targetSleepPath -and
        $_.payload.transport.wait_mode -eq "spawned"
    } | Select-Object -Last 1)
    if ($null -eq $explicitKernelEntry) {
        throw "launcher should hand spawned launches to broker launch.start"
    }

    if ($explicitKernelEntry.session_id -ne "session-spawned-explicit") {
        throw "launcher should preserve the caller session id for spawned broker launches"
    }

    $defaultSpawnedStatePath = Join-Path $tempRoot "target-sleep-default-spawned-state.json"
    $defaultSpawnedResult = Invoke-Launcher -Arguments @(
        "--target-path",
        $targetSleepPath,
        "--session-id",
        "session-spawned-default",
        "--state-file",
        $defaultSpawnedStatePath
    )

    if ($defaultSpawnedResult.ExitCode -ne 0) {
        throw "launcher should succeed when wait mode is omitted: $($defaultSpawnedResult.Output)"
    }

    if (-not [string]::IsNullOrWhiteSpace($defaultSpawnedResult.Output)) {
        throw "default spawned mode should write state to --state-file instead of stdout"
    }

    $defaultSpawnedState = Read-StateJson -Path $defaultSpawnedStatePath
    Assert-JsonCoreFields -State $defaultSpawnedState -ExpectedStatus "spawned" -ExpectedSessionId "session-spawned-default" -ExpectedTargetPath $targetSleepPath

    if (@($defaultSpawnedState.args).Count -ne 0) {
        throw "default spawned state should include an empty args array when no target args are supplied"
    }

    if ($defaultSpawnedState.error -ne $null) {
        throw "successful default spawned state should record null error"
    }

    if ($null -ne $defaultSpawnedState.exit_code) {
        throw "default spawned state should omit exit_code"
    }

    $spawnedPids += [int]$defaultSpawnedState.pid
}
finally {
    foreach ($spawnedPid in $spawnedPids) {
        Stop-Process -Id $spawnedPid -Force -ErrorAction SilentlyContinue
    }

    Remove-Item Env:MO2_CONTROL_PLANE_FAKE_KERNEL_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:MO2_CONTROL_PLANE_FAKE_KERNEL_LOG_PATH -ErrorAction SilentlyContinue

    Remove-Item -Path $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "launcher contract tests: PASS"

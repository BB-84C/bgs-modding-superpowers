$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$cliPath = Join-Path $repoRoot "tools/mo2-control-plane/broker/bin/mo2-cli.ps1"

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

function New-NamedPipeRuntimeFixture {
    param(
        [string]$Name,
        [int]$Mo2Pid,
        [string]$EndpointName
    )

    $root = Join-Path $env:TEMP ("mo2-live-ipc-test-" + $Name + "-" + [guid]::NewGuid().ToString("N"))
    $null = New-Item -ItemType Directory -Path $root -Force

    ([ordered]@{
        schemaVersion = 1
        state = "bootstrap-stale"
        mo2Pid = $Mo2Pid
    } | ConvertTo-Json -Depth 10) | Set-Content -Path (Join-Path $root "status.json")

    ([ordered]@{
        schemaVersion = 1
        transport = "named-pipe"
        endpoint = $EndpointName
    } | ConvertTo-Json -Depth 10) | Set-Content -Path (Join-Path $root "endpoint.json")

    return $root
}

function Remove-RuntimeFixture {
    param(
        [string]$Path
    )

    if (-not [string]::IsNullOrWhiteSpace($Path) -and (Test-Path $Path)) {
        Remove-Item -Path $Path -Recurse -Force
    }
}

$runtimeRoot = $null
$deadProcessRoot = $null
$missingFixtureRoot = $null
$unsupportedTransportRoot = $null
$ipcFixturePath = $null

try {
    $runtimeRoot = New-NamedPipeRuntimeFixture -Name "named-pipe" -Mo2Pid $PID -EndpointName "mo2-control-plane-test"
    $ipcFixturePath = Join-Path $runtimeRoot "fake-ipc-response.json"

    ([ordered]@{
        "system.ping" = [ordered]@{
            ok = $true
            result = [ordered]@{
                status = "ipc-ok"
            }
        }
        "system.capabilities" = [ordered]@{
            ok = $true
            result = [ordered]@{
                commands = @("system.ping", "system.capabilities", "test.synthetic")
            }
        }
    } | ConvertTo-Json -Depth 10) | Set-Content -Path $ipcFixturePath

    $env:MO2_CONTROL_PLANE_FAKE_IPC_RESPONSE_PATH = $ipcFixturePath

    $ping = Invoke-Cli -Arguments @("system", "ping", "--live-root", $runtimeRoot)
    if ($ping.ExitCode -ne 0) {
        throw "system ping with named-pipe discovery should succeed through IPC: $($ping.Output)"
    }

    $pingJson = $ping.Output | ConvertFrom-Json -ErrorAction Stop
    if (-not $pingJson.ok) { throw "system ping with named-pipe discovery should return ok=true" }
    if ($pingJson.result.status -ne "ipc-ok") {
        throw "system ping with named-pipe discovery should surface IPC status instead of bootstrap file state"
    }

    $capabilities = Invoke-Cli -Arguments @("system", "capabilities", "--live-root", $runtimeRoot)
    if ($capabilities.ExitCode -ne 0) {
        throw "system capabilities with named-pipe discovery should succeed through IPC: $($capabilities.Output)"
    }

    $capabilitiesJson = $capabilities.Output | ConvertFrom-Json -ErrorAction Stop
    if (-not $capabilitiesJson.ok) { throw "system capabilities with named-pipe discovery should return ok=true" }
    foreach ($commandName in @("system.ping", "system.capabilities", "session.open", "session.artifacts", "test.synthetic")) {
        if ($capabilitiesJson.result.commands -notcontains $commandName) {
            throw "system capabilities with named-pipe discovery should surface broker-shaped command list including $commandName"
        }
    }

    $deadProcessRoot = New-NamedPipeRuntimeFixture -Name "dead-process" -Mo2Pid 999999 -EndpointName "mo2-control-plane-test"
    $deadProcess = Invoke-Cli -Arguments @("system", "ping", "--live-root", $deadProcessRoot)
    if ($deadProcess.ExitCode -eq 0) {
        throw "system ping with named-pipe discovery should fail closed when status.json points at a dead mo2Pid"
    }

    $deadProcessJson = $deadProcess.Output | ConvertFrom-Json -ErrorAction Stop
    if ($deadProcessJson.ok -ne $false) { throw "dead mo2Pid on named-pipe discovery should return ok=false" }
    if ($deadProcessJson.error.code -ne "transport_error") { throw "dead mo2Pid on named-pipe discovery should return transport_error" }

    $missingFixtureRoot = New-NamedPipeRuntimeFixture -Name "missing-ipc-fixture" -Mo2Pid $PID -EndpointName "mo2-control-plane-test"
    $env:MO2_CONTROL_PLANE_FAKE_IPC_RESPONSE_PATH = Join-Path $missingFixtureRoot "missing-ipc-response.json"
    $missingFixture = Invoke-Cli -Arguments @("system", "ping", "--live-root", $missingFixtureRoot)
    if ($missingFixture.ExitCode -eq 0) {
        throw "system ping with named-pipe discovery should fail closed when the fake IPC fixture is unavailable"
    }

    $missingFixtureJson = $missingFixture.Output | ConvertFrom-Json -ErrorAction Stop
    if ($missingFixtureJson.ok -ne $false) { throw "missing fake IPC fixture should return ok=false" }
    if ($missingFixtureJson.error.code -ne "transport_error") { throw "missing fake IPC fixture should return transport_error" }

    $unsupportedTransportRoot = Join-Path $env:TEMP ("mo2-live-ipc-test-unsupported-transport-" + [guid]::NewGuid().ToString("N"))
    $null = New-Item -ItemType Directory -Path $unsupportedTransportRoot -Force
    ([ordered]@{
        schemaVersion = 1
        state = "ok"
        mo2Pid = $PID
    } | ConvertTo-Json -Depth 10) | Set-Content -Path (Join-Path $unsupportedTransportRoot "status.json")
    ([ordered]@{
        schemaVersion = 1
        methods = @("system.ping", "system.capabilities")
    } | ConvertTo-Json -Depth 10) | Set-Content -Path (Join-Path $unsupportedTransportRoot "capabilities.json")
    ([ordered]@{
        schemaVersion = 1
        transport = "telepathy"
    } | ConvertTo-Json -Depth 10) | Set-Content -Path (Join-Path $unsupportedTransportRoot "endpoint.json")

    $env:MO2_CONTROL_PLANE_FAKE_IPC_RESPONSE_PATH = $ipcFixturePath
    $unsupportedTransport = Invoke-Cli -Arguments @("system", "ping", "--live-root", $unsupportedTransportRoot)
    if ($unsupportedTransport.ExitCode -eq 0) {
        throw "system ping with an unsupported endpoint transport should fail closed"
    }

    $unsupportedTransportJson = $unsupportedTransport.Output | ConvertFrom-Json -ErrorAction Stop
    if ($unsupportedTransportJson.ok -ne $false) { throw "unsupported endpoint transport should return ok=false" }
    if ($unsupportedTransportJson.error.code -ne "transport_error") { throw "unsupported endpoint transport should return transport_error" }

    if ($unsupportedTransportJson.error.message -notmatch [regex]::Escape("Unsupported live bootstrap transport: telepathy")) {
        throw "unsupported endpoint transport should identify the unsupported transport value"
    }

    Write-Host "MO2 live IPC contract checks passed."
}
finally {
    $env:MO2_CONTROL_PLANE_FAKE_IPC_RESPONSE_PATH = $null
    Remove-RuntimeFixture -Path $runtimeRoot
    Remove-RuntimeFixture -Path $deadProcessRoot
    Remove-RuntimeFixture -Path $missingFixtureRoot
    Remove-RuntimeFixture -Path $unsupportedTransportRoot
}

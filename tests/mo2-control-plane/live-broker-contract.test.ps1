$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$cliPath = Join-Path $repoRoot "tools/mo2-control-plane/broker/bin/mo2-cli.ps1"
$fakeKernelResponsePath = Join-Path $PSScriptRoot "fixtures/fake-kernel-response.json"

. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/common.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/protocol.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/live-bootstrap.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/client.ps1")

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

function New-LiveRuntimeFixture {
    param(
        [string]$Name,
        [object]$Status = $null,
        [object]$Capabilities = $null,
        [object]$Endpoint = $null
    )

    $root = Join-Path $env:TEMP ("mo2-live-broker-test-" + $Name + "-" + [guid]::NewGuid().ToString("N"))
    $null = New-Item -ItemType Directory -Path $root -Force

    if ($null -ne $Status) {
        $Status | ConvertTo-Json -Depth 10 | Set-Content -Path (Join-Path $root "status.json")
    }

    if ($null -ne $Capabilities) {
        $Capabilities | ConvertTo-Json -Depth 10 | Set-Content -Path (Join-Path $root "capabilities.json")
    }

    if ($null -ne $Endpoint) {
        $Endpoint | ConvertTo-Json -Depth 10 | Set-Content -Path (Join-Path $root "endpoint.json")
    }

    return $root
}

function Remove-LiveRuntimeFixture {
    param(
        [string]$Path
    )

    if (-not [string]::IsNullOrWhiteSpace($Path) -and (Test-Path $Path)) {
        Remove-Item -Path $Path -Recurse -Force
    }
}

$env:MO2_CONTROL_PLANE_FAKE_RESPONSE_PATH = $fakeKernelResponsePath
$liveProcessId = [int]$PID

$runtimeRoot = $null
$missingCapabilitiesRoot = $null
$malformedStatusRoot = $null
$missingMo2PidRoot = $null
$deadMo2PidRoot = $null
$unsupportedMethodRoot = $null
$unsupportedStatusSchemaRoot = $null
$unsupportedCapabilitiesSchemaRoot = $null
$unsupportedEndpointSchemaRoot = $null

try {
    $runtimeRoot = New-LiveRuntimeFixture -Name "ok" -Status ([ordered]@{
        schemaVersion = 1
        state = "ok"
        mo2Pid = $liveProcessId
    }) -Capabilities ([ordered]@{
        schemaVersion = 1
        methods = @("system.ping", "system.capabilities")
    }) -Endpoint ([ordered]@{
        schemaVersion = 1
        transport = "stdio"
    })

    $livePing = Invoke-Cli -Arguments @("system", "ping", "--live-root", $runtimeRoot)
    if ($livePing.ExitCode -ne 0) {
        throw "system ping with --live-root should succeed: $($livePing.Output)"
    }

    $livePingJson = $livePing.Output | ConvertFrom-Json -ErrorAction Stop
    if (-not $livePingJson.ok) { throw "system ping with --live-root should return ok=true" }
    if ($livePingJson.result.status -ne "ok") { throw "system ping with --live-root should surface the live runtime state" }

    $liveCapabilities = Invoke-Cli -Arguments @("system", "capabilities", "--live-root", $runtimeRoot)
    if ($liveCapabilities.ExitCode -ne 0) {
        throw "system capabilities with --live-root should succeed: $($liveCapabilities.Output)"
    }

    $liveCapabilitiesJson = $liveCapabilities.Output | ConvertFrom-Json -ErrorAction Stop
    if (-not $liveCapabilitiesJson.ok) { throw "system capabilities with --live-root should return ok=true" }
    foreach ($commandName in @("system.ping", "system.capabilities")) {
        if ($liveCapabilitiesJson.result.commands -notcontains $commandName) {
            throw "system capabilities with --live-root should advertise $commandName"
        }
    }

    $profileListRequest = New-Mo2ControlPlaneRequest -SessionId "sess-test" -Command "profile.list" -Payload @{}
    $profileListResponse = Invoke-Mo2ControlPlaneClientRequest -Request $profileListRequest -LiveRoot $runtimeRoot
    if (-not $profileListResponse.ok) {
        throw "client requests outside the live bootstrap system set should ignore -LiveRoot and keep the normal route"
    }

    if ($profileListResponse.result.command -ne "profile.list") {
        throw "non-system client requests should keep the normal primitive route even when -LiveRoot is supplied"
    }

    $missingCapabilitiesRoot = New-LiveRuntimeFixture -Name "missing-capabilities" -Status ([ordered]@{
        schemaVersion = 1
        state = "ok"
        mo2Pid = $liveProcessId
    }) -Endpoint ([ordered]@{
        schemaVersion = 1
        transport = "stdio"
    })

    $missingCapabilities = Invoke-Cli -Arguments @("system", "ping", "--live-root", $missingCapabilitiesRoot)
    if ($missingCapabilities.ExitCode -eq 0) {
        throw "system ping with --live-root should fail closed when capabilities.json is missing"
    }

    $missingCapabilitiesJson = $missingCapabilities.Output | ConvertFrom-Json -ErrorAction Stop
    if ($missingCapabilitiesJson.ok -ne $false) { throw "missing capabilities.json should return ok=false" }
    if ($missingCapabilitiesJson.error.code -ne "transport_error") { throw "missing capabilities.json should return transport_error" }

    $malformedStatusRoot = New-LiveRuntimeFixture -Name "malformed-status" -Status ([ordered]@{
        schemaVersion = 1
    }) -Capabilities ([ordered]@{
        schemaVersion = 1
        methods = @("system.ping", "system.capabilities")
    }) -Endpoint ([ordered]@{
        schemaVersion = 1
        transport = "stdio"
    })

    $malformedStatus = Invoke-Cli -Arguments @("system", "ping", "--live-root", $malformedStatusRoot)
    if ($malformedStatus.ExitCode -eq 0) {
        throw "system ping with --live-root should fail closed when status.json is malformed"
    }

    $malformedStatusJson = $malformedStatus.Output | ConvertFrom-Json -ErrorAction Stop
    if ($malformedStatusJson.ok -ne $false) { throw "malformed status.json should return ok=false" }
    if ($malformedStatusJson.error.code -ne "transport_error") { throw "malformed status.json should return transport_error" }

    $missingMo2PidRoot = New-LiveRuntimeFixture -Name "missing-mo2pid" -Status ([ordered]@{
        schemaVersion = 1
        state = "ok"
    }) -Capabilities ([ordered]@{
        schemaVersion = 1
        methods = @("system.ping", "system.capabilities")
    }) -Endpoint ([ordered]@{
        schemaVersion = 1
        transport = "stdio"
    })

    $missingMo2Pid = Invoke-Cli -Arguments @("system", "ping", "--live-root", $missingMo2PidRoot)
    if ($missingMo2Pid.ExitCode -eq 0) {
        throw "system ping with --live-root should fail closed when status.json is missing mo2Pid"
    }

    $missingMo2PidJson = $missingMo2Pid.Output | ConvertFrom-Json -ErrorAction Stop
    if ($missingMo2PidJson.ok -ne $false) { throw "missing mo2Pid should return ok=false" }
    if ($missingMo2PidJson.error.code -ne "transport_error") { throw "missing mo2Pid should return transport_error" }

    $deadMo2PidRoot = New-LiveRuntimeFixture -Name "dead-mo2pid" -Status ([ordered]@{
        schemaVersion = 1
        state = "ok"
        mo2Pid = 999999
    }) -Capabilities ([ordered]@{
        schemaVersion = 1
        methods = @("system.ping", "system.capabilities")
    }) -Endpoint ([ordered]@{
        schemaVersion = 1
        transport = "stdio"
    })

    $deadMo2Pid = Invoke-Cli -Arguments @("system", "ping", "--live-root", $deadMo2PidRoot)
    if ($deadMo2Pid.ExitCode -eq 0) {
        throw "system ping with --live-root should fail closed when status.json points at a dead mo2Pid"
    }

    $deadMo2PidJson = $deadMo2Pid.Output | ConvertFrom-Json -ErrorAction Stop
    if ($deadMo2PidJson.ok -ne $false) { throw "dead mo2Pid should return ok=false" }
    if ($deadMo2PidJson.error.code -ne "transport_error") { throw "dead mo2Pid should return transport_error" }

    $unsupportedMethodRoot = New-LiveRuntimeFixture -Name "unsupported-method" -Status ([ordered]@{
        schemaVersion = 1
        state = "ok"
        mo2Pid = $liveProcessId
    }) -Capabilities ([ordered]@{
        schemaVersion = 1
        methods = @("system.capabilities")
    }) -Endpoint ([ordered]@{
        schemaVersion = 1
        transport = "stdio"
    })

    $unsupportedMethod = Invoke-Cli -Arguments @("system", "ping", "--live-root", $unsupportedMethodRoot)
    if ($unsupportedMethod.ExitCode -eq 0) {
        throw "system ping with --live-root should fail closed when system.ping is not advertised"
    }

    $unsupportedMethodJson = $unsupportedMethod.Output | ConvertFrom-Json -ErrorAction Stop
    if ($unsupportedMethodJson.ok -ne $false) { throw "missing system.ping advertisement should return ok=false" }
    if ($unsupportedMethodJson.error.code -ne "transport_error") { throw "missing system.ping advertisement should return transport_error" }

    $unsupportedStatusSchemaRoot = New-LiveRuntimeFixture -Name "unsupported-status-schema" -Status ([ordered]@{
        schemaVersion = 2
        state = "ok"
        mo2Pid = $liveProcessId
    }) -Capabilities ([ordered]@{
        schemaVersion = 1
        methods = @("system.ping", "system.capabilities")
    }) -Endpoint ([ordered]@{
        schemaVersion = 1
        transport = "stdio"
    })

    $unsupportedStatusSchema = Invoke-Cli -Arguments @("system", "ping", "--live-root", $unsupportedStatusSchemaRoot)
    if ($unsupportedStatusSchema.ExitCode -eq 0) {
        throw "system ping with --live-root should fail closed on unsupported status.json schemaVersion"
    }

    $unsupportedStatusSchemaJson = $unsupportedStatusSchema.Output | ConvertFrom-Json -ErrorAction Stop
    if ($unsupportedStatusSchemaJson.ok -ne $false) { throw "unsupported status.json schemaVersion should return ok=false" }
    if ($unsupportedStatusSchemaJson.error.code -ne "transport_error") { throw "unsupported status.json schemaVersion should return transport_error" }

    $unsupportedCapabilitiesSchemaRoot = New-LiveRuntimeFixture -Name "unsupported-capabilities-schema" -Status ([ordered]@{
        schemaVersion = 1
        state = "ok"
        mo2Pid = $liveProcessId
    }) -Capabilities ([ordered]@{
        schemaVersion = 2
        methods = @("system.ping", "system.capabilities")
    }) -Endpoint ([ordered]@{
        schemaVersion = 1
        transport = "stdio"
    })

    $unsupportedCapabilitiesSchema = Invoke-Cli -Arguments @("system", "ping", "--live-root", $unsupportedCapabilitiesSchemaRoot)
    if ($unsupportedCapabilitiesSchema.ExitCode -eq 0) {
        throw "system ping with --live-root should fail closed on unsupported capabilities.json schemaVersion"
    }

    $unsupportedCapabilitiesSchemaJson = $unsupportedCapabilitiesSchema.Output | ConvertFrom-Json -ErrorAction Stop
    if ($unsupportedCapabilitiesSchemaJson.ok -ne $false) { throw "unsupported capabilities.json schemaVersion should return ok=false" }
    if ($unsupportedCapabilitiesSchemaJson.error.code -ne "transport_error") { throw "unsupported capabilities.json schemaVersion should return transport_error" }

    $unsupportedEndpointSchemaRoot = New-LiveRuntimeFixture -Name "unsupported-endpoint-schema" -Status ([ordered]@{
        schemaVersion = 1
        state = "ok"
        mo2Pid = $liveProcessId
    }) -Capabilities ([ordered]@{
        schemaVersion = 1
        methods = @("system.ping", "system.capabilities")
    }) -Endpoint ([ordered]@{
        schemaVersion = 2
        transport = "stdio"
    })

    $unsupportedEndpointSchema = Invoke-Cli -Arguments @("system", "ping", "--live-root", $unsupportedEndpointSchemaRoot)
    if ($unsupportedEndpointSchema.ExitCode -eq 0) {
        throw "system ping with --live-root should fail closed on unsupported endpoint.json schemaVersion"
    }

    $unsupportedEndpointSchemaJson = $unsupportedEndpointSchema.Output | ConvertFrom-Json -ErrorAction Stop
    if ($unsupportedEndpointSchemaJson.ok -ne $false) { throw "unsupported endpoint.json schemaVersion should return ok=false" }
    if ($unsupportedEndpointSchemaJson.error.code -ne "transport_error") { throw "unsupported endpoint.json schemaVersion should return transport_error" }

    Write-Host "MO2 live broker contract checks passed."
}
finally {
    Remove-LiveRuntimeFixture -Path $runtimeRoot
    Remove-LiveRuntimeFixture -Path $missingCapabilitiesRoot
    Remove-LiveRuntimeFixture -Path $malformedStatusRoot
    Remove-LiveRuntimeFixture -Path $missingMo2PidRoot
    Remove-LiveRuntimeFixture -Path $deadMo2PidRoot
    Remove-LiveRuntimeFixture -Path $unsupportedMethodRoot
    Remove-LiveRuntimeFixture -Path $unsupportedStatusSchemaRoot
    Remove-LiveRuntimeFixture -Path $unsupportedCapabilitiesSchemaRoot
    Remove-LiveRuntimeFixture -Path $unsupportedEndpointSchemaRoot
}

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$bridgeSourcePath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_agent_control.py"

if (-not (Test-Path $bridgeSourcePath -PathType Leaf)) {
    throw "Missing live bridge source: tools/mo2-control-plane/live-bridge/mo2_agent_control.py"
}

$tempRoot = Join-Path $env:TEMP ("mo2-live-launch-contract-" + [guid]::NewGuid().ToString("N"))
$bridgeCopyPath = Join-Path $tempRoot "mo2_agent_control.py"

try {
    $null = New-Item -ItemType Directory -Path $tempRoot -Force
    Copy-Item -Path $bridgeSourcePath -Destination $bridgeCopyPath -Force

    function Assert-ExactStringSet {
        param(
            [string]$Label,
            [object[]]$Actual,
            [string[]]$Expected
        )

        $actualList = @($Actual | ForEach-Object { [string]$_ })
        $expectedList = @($Expected | ForEach-Object { [string]$_ })

        if ($actualList.Count -ne $expectedList.Count) {
            throw "$Label should contain exactly [$($expectedList -join ', ')], got [$($actualList -join ', ')]"
        }

        foreach ($index in 0..($expectedList.Count - 1)) {
            if ($actualList[$index] -ne $expectedList[$index]) {
                throw "$Label should contain exactly [$($expectedList -join ', ')], got [$($actualList -join ', ')]"
            }
        }
    }

    $pythonScript = @'
import importlib.util
import json
import pathlib
import sys
import types

module_path = pathlib.Path(sys.argv[1])

mobase = types.ModuleType("mobase")

class IPluginTool:
    pass

class VersionInfo:
    def __init__(self, *parts):
        self.parts = parts

mobase.IPluginTool = IPluginTool
mobase.VersionInfo = VersionInfo
sys.modules["mobase"] = mobase

spec = importlib.util.spec_from_file_location("mo2_agent_control", str(module_path))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

handlers = module.build_command_handlers()
request = {
    "protocol_version": "1",
    "request_id": "req-launch-contract",
    "session_id": "sess-launch-contract",
}

capabilities = module.dispatch_transport_request({**request, "method": "system.capabilities"}, handlers)
launch_responses = {
    method_name: module.dispatch_transport_request({**request, "method": method_name, "payload": {}}, handlers)
    for method_name in module.LAUNCH_METHODS
}

registry = module.create_launch_registry()
entry = module.create_launch_registry_entry(
    "launch-contract-id",
    request,
    {
        "target_path": "C:/test/target.exe",
        "args": ["--demo"],
        "cwd": "C:/test",
        "env": {"DEMO": "1"},
    },
)

print(json.dumps({
    "launchMethods": list(module.LAUNCH_METHODS),
    "contracts": module.LAUNCH_COMMAND_CONTRACTS,
    "registryFields": {
        "rootField": module.LAUNCH_REGISTRY_ENTRIES_FIELD,
        "entryFields": list(module.LAUNCH_REGISTRY_ENTRY_FIELDS),
        "statusValues": list(module.LAUNCH_REGISTRY_STATUS_VALUES),
    },
    "capabilities": capabilities,
    "launchResponses": launch_responses,
    "registry": registry,
    "entry": entry,
}))
'@

    $output = & python -c $pythonScript $bridgeCopyPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Importing and probing the live launch contract should succeed: $($output -join "`n")"
    }

    $summary = (($output | ForEach-Object { $_.ToString() }) -join "`n") | ConvertFrom-Json -AsHashtable -ErrorAction Stop

    $expectedLaunchMethods = @("launch.start", "launch.status", "launch.wait", "launch.stop")
    Assert-ExactStringSet -Label "LAUNCH_METHODS" -Actual $summary.launchMethods -Expected $expectedLaunchMethods
    foreach ($methodName in $expectedLaunchMethods) {
        if ($summary.capabilities.result.commands -notcontains $methodName) {
            throw "system.capabilities should advertise $methodName"
        }

        $response = $summary.launchResponses[$methodName]
        if ($response.ok -ne $false) {
            throw "$methodName should fail closed on invalid launch payloads"
        }

        if ($response.error.code -ne "invalid_params") {
            throw "$methodName should report invalid_params when required launch fields are missing"
        }
    }

    $expectedPayloadFields = @{
        "launch.start" = @("target_path", "args", "cwd", "env")
        "launch.status" = @("launch_id")
        "launch.wait" = @("launch_id")
        "launch.stop" = @("launch_id")
    }

    $expectedResultFields = @{
        "launch.start" = @("launch_id", "pid", "status", "started_at", "artifacts")
        "launch.status" = @("launch_id", "pid", "status")
        "launch.wait" = @("launch_id", "pid", "status")
        "launch.stop" = @("launch_id", "pid", "status")
    }

    foreach ($methodName in $expectedLaunchMethods) {
        $contract = $summary.contracts[$methodName]
        if ($null -eq $contract) {
            throw "launch contract should define shape metadata for $methodName"
        }

        Assert-ExactStringSet -Label "$methodName payloadFields" -Actual $contract.payloadFields -Expected $expectedPayloadFields[$methodName]
        Assert-ExactStringSet -Label "$methodName resultFields" -Actual $contract.resultFields -Expected $expectedResultFields[$methodName]
    }

    if ($summary.registryFields.rootField -ne "launches") {
        throw "launch registry root field should be named launches"
    }

    if ($summary.registry.launches.Count -ne 0) {
        throw "new launch registry should start empty"
    }

    $expectedEntryFields = @(
        "launch_id",
        "session_id",
        "target_path",
        "args",
        "cwd",
        "env",
        "pid",
        "process_handle",
        "status",
        "started_at",
        "updated_at",
        "exit_code",
        "artifacts"
    )
    Assert-ExactStringSet -Label "launch registry entry fields" -Actual $summary.registryFields.entryFields -Expected $expectedEntryFields

    $expectedStatusValues = @("pending", "running", "completed", "stopped")
    Assert-ExactStringSet -Label "launch registry status values" -Actual $summary.registryFields.statusValues -Expected $expectedStatusValues

    if ($summary.entry.launch_id -ne "launch-contract-id") {
        throw "launch registry entry should preserve launch_id"
    }

    if ($summary.entry.session_id -ne "sess-launch-contract") {
        throw "launch registry entry should preserve session association"
    }

    if ($summary.entry.target_path -ne "C:/test/target.exe") {
        throw "launch registry entry should preserve target_path"
    }

    if ($summary.entry.args.Count -ne 1 -or $summary.entry.args[0] -ne "--demo") {
        throw "launch registry entry should preserve args"
    }

    if ($summary.entry.cwd -ne "C:/test") {
        throw "launch registry entry should preserve cwd"
    }

    if ($summary.entry.env.DEMO -ne "1") {
        throw "launch registry entry should preserve env"
    }

    if ($summary.entry.pid -ne $null) {
        throw "launch registry entry pid should remain unset until a real launch.start call materializes a process"
    }

    if ($summary.entry.process_handle -ne $null) {
        throw "launch registry entry process_handle should remain unset until a real launch.start call materializes a process"
    }

    if ($summary.entry.status -ne "pending") {
        throw "launch registry entry should still start in pending state before launch.start marks it running"
    }

    if ($summary.entry.started_at -ne $null) {
        throw "launch registry entry should leave started_at unset until a real process has been launched"
    }

    if ([string]::IsNullOrWhiteSpace([string]$summary.entry.updated_at)) {
        throw "launch registry entry should stamp updated_at"
    }

    if ($summary.entry.exit_code -ne $null) {
        throw "launch registry entry exit_code should remain unset until the process exits"
    }

    if ($summary.entry.artifacts.state_file -ne $null) {
        throw "launch registry entry should reserve artifacts.state_file without materializing it yet"
    }

    if ($summary.entry.artifacts.backend -ne $null) {
        throw "launch registry entry should reserve artifacts.backend without materializing it yet"
    }

    Write-Host "MO2 live launch contract checks passed."
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -Path $tempRoot -Recurse -Force
    }
}

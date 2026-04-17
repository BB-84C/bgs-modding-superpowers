$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$bridgeSourcePath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_agent_control.py"

if (-not (Test-Path $bridgeSourcePath -PathType Leaf)) {
    throw "Missing live bridge source: tools/mo2-control-plane/live-bridge/mo2_agent_control.py"
}

$tempRoot = Join-Path $env:TEMP ("mo2-live-system-handler-" + [guid]::NewGuid().ToString("N"))
$bridgeCopyPath = Join-Path $tempRoot "mo2_agent_control.py"

try {
    $null = New-Item -ItemType Directory -Path $tempRoot -Force
    Copy-Item -Path $bridgeSourcePath -Destination $bridgeCopyPath -Force

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
handlers["test.synthetic"] = lambda request: {"ok": True, "result": {"command": request.get("method")}}

request = {
    "protocol_version": "1",
    "request_id": "req-system-handler",
    "session_id": "sess-system-handler",
}

ping_response = module.dispatch_transport_request({**request, "method": "system.ping"}, handlers)
capabilities_response = module.dispatch_transport_request({**request, "method": "system.capabilities"}, handlers)

print(json.dumps({
    "ping": ping_response,
    "capabilities": capabilities_response,
}))
'@

    $output = & python -c $pythonScript $bridgeCopyPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Importing and probing the deployed bridge should succeed: $($output -join "`n")"
    }

    $summary = (($output | ForEach-Object { $_.ToString() }) -join "`n") | ConvertFrom-Json -AsHashtable -ErrorAction Stop

    foreach ($responseName in @("ping", "capabilities")) {
        $response = $summary[$responseName]
        if ($response.protocol_version -ne "1") {
            throw "$responseName should preserve protocol_version in the Python response envelope"
        }

        if ($response.request_id -ne "req-system-handler") {
            throw "$responseName should preserve request_id in the Python response envelope"
        }

        if ($response.session_id -ne "sess-system-handler") {
            throw "$responseName should preserve session_id in the Python response envelope"
        }

        if (-not $response.ok) {
            throw "$responseName should return ok=true in the Python response envelope"
        }

        if ($null -ne $response.error) {
            throw "$responseName should return error=null in the Python response envelope for success"
        }
    }

    if ($summary.ping.result.status -ne "ok") {
        throw "system.ping should return status 'ok' inside the Python response envelope"
    }

    foreach ($methodName in @("system.ping", "system.capabilities", "test.synthetic")) {
        if ($summary.capabilities.result.commands -notcontains $methodName) {
            throw "system.capabilities should advertise $methodName inside the Python response envelope"
        }
    }

    Write-Host "MO2 live system handler envelope checks passed."
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -Path $tempRoot -Recurse -Force
    }
}

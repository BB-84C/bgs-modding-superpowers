$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$bridgeSourcePath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_agent_control.py"

if (-not (Test-Path $bridgeSourcePath -PathType Leaf)) {
    throw "Missing live bridge source: tools/mo2-control-plane/live-bridge/mo2_agent_control.py"
}

$tempRoot = Join-Path $env:TEMP ("mo2-live-transport-runtime-" + [guid]::NewGuid().ToString("N"))
$pluginsRoot = Join-Path $tempRoot "plugins"
$pluginSupportRoot = Join-Path $pluginsRoot "Mo2AgentControl"
$bootstrapRoot = Join-Path $pluginSupportRoot "bootstrap"
$bridgeCopyPath = Join-Path $pluginsRoot "mo2_agent_control.py"

try {
    $null = New-Item -ItemType Directory -Path $bootstrapRoot -Force
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

runtime_root = module.get_runtime_root(module_path)
events = []
recorded = {}

original_bootstrap = getattr(module, "bootstrap_named_pipe_server")

def fake_bootstrap_named_pipe_server(runtime_root_arg, handlers_arg, pipe_name=None):
    root = pathlib.Path(runtime_root_arg)
    events.append("bootstrap")
    recorded["runtimeRoot"] = str(root)
    recorded["handlers"] = sorted(list(handlers_arg.keys()))
    recorded["pipeName"] = pipe_name
    return {
        "transport": getattr(module, "RUNTIME_TRANSPORT", None),
        "endpoint": pipe_name,
        "runtimeRoot": str(root),
        "started": True,
    }

module.bootstrap_named_pipe_server = fake_bootstrap_named_pipe_server

handlers = module.build_command_handlers()
handlers["test.synthetic"] = lambda request: {"ok": True, "result": {"command": request["method"]}}
ping_response = module.dispatch_transport_request({"method": "system.ping"}, handlers)
capabilities_response = module.dispatch_transport_request({"method": "system.capabilities"}, handlers)

plugin = module.createPlugin()
init_result = bool(plugin.init(object()))

summary = {
    "hasBootstrapNamedPipeServer": callable(original_bootstrap),
    "hasDispatchTransportRequest": callable(getattr(module, "dispatch_transport_request", None)),
    "hasBuildCommandHandlers": callable(getattr(module, "build_command_handlers", None)),
    "handlerNames": sorted(list(handlers.keys())),
    "pingResponse": ping_response,
    "capabilitiesResponse": capabilities_response,
    "events": events,
    "recorded": recorded,
    "initResult": init_result,
    "pluginTransport": getattr(plugin, "_transport", None),
    "runtimeRoot": str(runtime_root),
}

print(json.dumps(summary))
'@

    $output = & python -c $pythonScript $bridgeCopyPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Importing and probing the deployed bridge should succeed: $($output -join "`n")"
    }

    $summary = (($output | ForEach-Object { $_.ToString() }) -join "`n") | ConvertFrom-Json -AsHashtable -ErrorAction Stop

    if (-not $summary.hasBootstrapNamedPipeServer) {
        throw "The live bridge should expose bootstrap_named_pipe_server(runtime_root, handlers)"
    }

    if (-not $summary.hasDispatchTransportRequest) {
        throw "The live bridge should expose dispatch_transport_request(request, handlers)"
    }

    if (-not $summary.hasBuildCommandHandlers) {
        throw "The live bridge should expose build_command_handlers() as the command registration point"
    }

    foreach ($methodName in @("system.ping", "system.capabilities", "test.synthetic")) {
        if ($summary.handlerNames -notcontains $methodName) {
            throw "build_command_handlers() should register $methodName"
        }
    }

    if (-not $summary.pingResponse.ok) {
        throw "dispatch_transport_request() should route system.ping to an ok result"
    }

    if ($summary.pingResponse.result.status -ne "ok") {
        throw "dispatch_transport_request() should return status 'ok' for system.ping"
    }

    if (-not $summary.capabilitiesResponse.ok) {
        throw "dispatch_transport_request() should route system.capabilities to an ok result"
    }

    foreach ($methodName in @("system.ping", "system.capabilities", "test.synthetic")) {
        if ($summary.capabilitiesResponse.result.commands -notcontains $methodName) {
            throw "dispatch_transport_request() should surface $methodName from registered handlers"
        }
    }

    if (-not $summary.initResult) {
        throw "Plugin init(organizer) should report success after starting transport skeleton"
    }

    if ($summary.events.Count -ne 1 -or $summary.events[0] -ne "bootstrap") {
        throw "Plugin init(organizer) should start the named-pipe transport skeleton exactly once"
    }

    if ($summary.recorded.runtimeRoot -ne $summary.runtimeRoot) {
        throw "Plugin init(organizer) should bootstrap the named-pipe server for the deployed runtime root"
    }

    foreach ($methodName in @("system.ping", "system.capabilities")) {
        if ($summary.recorded.handlers -notcontains $methodName) {
            throw "Plugin init(organizer) should pass registered handlers to bootstrap_named_pipe_server()"
        }
    }

    if ($summary.pluginTransport.transport -ne "named-pipe") {
        throw "Plugin init(organizer) should retain named-pipe transport metadata on the plugin instance"
    }

    if ($summary.pluginTransport.endpoint -ne $summary.recorded.pipeName) {
        throw "Plugin init(organizer) should retain the instance-specific named-pipe endpoint metadata on the plugin instance"
    }

    if ($summary.pluginTransport.endpoint -notmatch '^mo2-control-plane-') {
        throw "Plugin init(organizer) should use an instance-specific named-pipe endpoint prefix"
    }

    if ($summary.pluginTransport.runtimeRoot -ne $summary.runtimeRoot) {
        throw "Plugin init(organizer) should retain the deployed runtime root in transport metadata"
    }

    if (-not $summary.pluginTransport.started) {
        throw "Plugin init(organizer) should retain a started marker in transport metadata"
    }

    foreach ($forbiddenField in @("handlers", "server")) {
        if ($summary.pluginTransport.ContainsKey($forbiddenField)) {
            throw "Plugin init(organizer) should not retain $forbiddenField in transport metadata"
        }
    }

    Write-Host "MO2 live transport runtime checks passed."
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -Path $tempRoot -Recurse -Force
    }
}

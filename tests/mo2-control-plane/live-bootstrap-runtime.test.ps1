$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$bridgeSourcePath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_agent_control.py"

if (-not (Test-Path $bridgeSourcePath -PathType Leaf)) {
    throw "Missing live bridge source: tools/mo2-control-plane/live-bridge/mo2_agent_control.py"
}

$tempRoot = Join-Path $env:TEMP ("mo2-live-bootstrap-runtime-" + [guid]::NewGuid().ToString("N"))
$pluginsRoot = Join-Path $tempRoot "plugins"
$pluginSupportRoot = Join-Path $pluginsRoot "Mo2AgentControl"
$bootstrapRoot = Join-Path $pluginSupportRoot "bootstrap"
$runtimeRoot = Join-Path $bootstrapRoot "runtime"
$bridgeCopyPath = Join-Path $pluginsRoot "mo2_agent_control.py"

try {
    $null = New-Item -ItemType Directory -Path $bootstrapRoot -Force
    Copy-Item -Path $bridgeSourcePath -Destination $bridgeCopyPath -Force

    $pythonScript = @'
import importlib.util
import json
import os
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
summary = {
    "hasCreatePlugin": hasattr(module, "createPlugin"),
    "pythonPid": os.getpid(),
    "runtimeExistsAfterImport": runtime_root.exists(),
}

if summary["hasCreatePlugin"]:
    plugin = module.createPlugin()
    summary["hasInit"] = callable(getattr(plugin, "init", None))
    if summary["hasInit"]:
        summary["initResult"] = bool(plugin.init(object()))
        summary["runtimeExistsAfterInit"] = runtime_root.exists()
    else:
        summary["runtimeExistsAfterInit"] = runtime_root.exists()
else:
    summary["hasInit"] = False
    summary["runtimeExistsAfterInit"] = runtime_root.exists()

print(json.dumps(summary))
'@

    $output = & python -c $pythonScript $bridgeCopyPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Importing the deployed bridge should succeed: $($output -join "`n")"
    }

    $summary = (($output | ForEach-Object { $_.ToString() }) -join "`n") | ConvertFrom-Json -AsHashtable -ErrorAction Stop

    if (-not $summary.hasCreatePlugin) {
        throw "Importing the deployed bridge should expose createPlugin()"
    }

    if (-not $summary.hasInit) {
        throw "The plugin instance returned by createPlugin() should expose init(organizer)"
    }

    if ($summary.runtimeExistsAfterImport) {
        throw "Importing the deployed bridge should not materialize bootstrap runtime files before plugin initialization"
    }

    if (-not $summary.initResult) {
        throw "Plugin init(organizer) should report success"
    }

    if (-not $summary.runtimeExistsAfterInit) {
        throw "Plugin init(organizer) should materialize bootstrap runtime files"
    }

    foreach ($path in @(
        $runtimeRoot,
        (Join-Path $runtimeRoot "status.json"),
        (Join-Path $runtimeRoot "capabilities.json"),
        (Join-Path $runtimeRoot "endpoint.json")
    )) {
        if (-not (Test-Path $path)) {
            throw "Plugin init(organizer) should materialize bootstrap runtime path: $path"
        }
    }

    $status = Get-Content -Path (Join-Path $runtimeRoot "status.json") -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    if ($status.schemaVersion -ne 1) {
        throw "status.json should publish schemaVersion 1"
    }

    if ($status.state -ne "ok") {
        throw "status.json should publish state 'ok'"
    }

    if ($status.mo2Pid -ne $summary.pythonPid) {
        throw "status.json should publish mo2Pid for the live Python plugin process"
    }

    $capabilities = Get-Content -Path (Join-Path $runtimeRoot "capabilities.json") -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    if ($capabilities.schemaVersion -ne 1) {
        throw "capabilities.json should publish schemaVersion 1"
    }

    foreach ($methodName in @("system.ping", "system.capabilities")) {
        if ($capabilities.methods -notcontains $methodName) {
            throw "capabilities.json should advertise $methodName"
        }
    }

    $endpoint = Get-Content -Path (Join-Path $runtimeRoot "endpoint.json") -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    if ($endpoint.schemaVersion -ne 1) {
        throw "endpoint.json should publish schemaVersion 1"
    }

    if ($endpoint.transport -ne "named-pipe") {
        throw "endpoint.json should publish transport 'named-pipe'"
    }

    if ([string]::IsNullOrWhiteSpace([string]$endpoint.endpoint)) {
        throw "endpoint.json should publish a concrete named-pipe endpoint value"
    }

    Write-Host "MO2 live bootstrap runtime checks passed."
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -Path $tempRoot -Recurse -Force
    }
}

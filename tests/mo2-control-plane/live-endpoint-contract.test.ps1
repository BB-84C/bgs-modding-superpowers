$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$bridgeSourcePath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_agent_control.py"
$readmePath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/README.md"
$liveIntegrationPath = Join-Path $repoRoot "tools/mo2-control-plane/live-integration.md"

foreach ($requiredPath in @($bridgeSourcePath, $readmePath, $liveIntegrationPath)) {
    if (-not (Test-Path $requiredPath -PathType Leaf)) {
        throw "Missing required file: $requiredPath"
    }
}

$bridgeSource = Get-Content -Path $bridgeSourcePath -Raw
$readme = Get-Content -Path $readmePath -Raw
$liveIntegration = Get-Content -Path $liveIntegrationPath -Raw

foreach ($anchor in @(
    @{ Pattern = 'RUNTIME_TRANSPORT\s*=\s*"named-pipe"'; Message = 'must publish named-pipe transport in endpoint.json' },
    @{ Pattern = 'RUNTIME_PIPE_NAME_PREFIX\s*=\s*"mo2-control-plane-"'; Message = 'must use an instance-specific named-pipe prefix instead of a single fixed pipe name' },
    @{ Pattern = 'def\s+get_runtime_pipe_name\(process_id:\s*int\s*\|\s*None\s*=\s*None\)\s*->\s*str'; Message = 'must expose a runtime pipe-name helper for instance-specific discovery' },
    @{ Pattern = 'RUNTIME_ENDPOINT_FIELD\s*=\s*"(?:endpoint|pipeName)"'; Message = 'must lock an endpoint-discovery field name for endpoint.json' },
    @{ Pattern = 'RUNTIME_ENDPOINT_FILE\s*:\s*\(\s*"schemaVersion"\s*,\s*"transport"\s*,\s*RUNTIME_ENDPOINT_FIELD\s*\)'; Message = 'must require endpoint.json to include schemaVersion, transport, and the endpoint-discovery field' },
    @{ Pattern = 'RUNTIME_ENDPOINT_FIELD\s*:\s*get_runtime_pipe_name\('; Message = 'must publish the instance-specific named-pipe discovery value in endpoint.json' },
    @{ Pattern = 'file-bootstrap'; Message = 'must keep file-bootstrap wording in the source contract' },
    @{ Pattern = 'discovery'; Message = 'must describe file-bootstrap as discovery' },
    @{ Pattern = 'liveness'; Message = 'must describe file-bootstrap as liveness' },
    @{ Pattern = 'not\s+as\s+the\s+command\s+transport'; Message = 'must state that file-bootstrap is not the command transport' }
)) {
    if ($bridgeSource -notmatch $anchor.Pattern) {
        throw "tools/mo2-control-plane/live-bridge/mo2_agent_control.py $($anchor.Message)"
    }
}

foreach ($anchor in @(
    @{ Pattern = 'os\.replace\('; Message = 'must atomically replace runtime JSON files' },
    @{ Pattern = 'with_suffix\('; Message = 'must write runtime JSON through a temporary sibling file before replace' }
)) {
    if ($bridgeSource -notmatch $anchor.Pattern) {
        throw "tools/mo2-control-plane/live-bridge/mo2_agent_control.py $($anchor.Message)"
    }
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString("N"))

try {
    $pythonProgram = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonProgram) {
        $pythonProgram = Get-Command py -ErrorAction SilentlyContinue
    }

    if (-not $pythonProgram) {
        throw "Python interpreter not found in PATH"
    }

    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
    $pythonScriptPath = Join-Path $tempRoot "verify_bridge.py"
    $pythonOutputPath = Join-Path $tempRoot "endpoint-check.json"

    @'
import importlib.util
import json
import pathlib
import sys
import types

bridge_source_path = pathlib.Path(sys.argv[1])
runtime_root = pathlib.Path(sys.argv[2])
output_path = pathlib.Path(sys.argv[3])

mobase = types.ModuleType("mobase")

class _IPluginTool:
    pass

class _VersionInfo:
    def __init__(self, *args):
        self.args = args

mobase.IPluginTool = _IPluginTool
mobase.VersionInfo = _VersionInfo
sys.modules["mobase"] = mobase

spec = importlib.util.spec_from_file_location("mo2_agent_control_test", bridge_source_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.publish_runtime_bootstrap(runtime_root)

endpoint_path = runtime_root / module.RUNTIME_ENDPOINT_FILE
with endpoint_path.open("r", encoding="utf-8") as handle:
    endpoint = json.load(handle)

output = {
    "transport": endpoint.get("transport"),
    "endpointField": module.RUNTIME_ENDPOINT_FIELD,
    "endpointValue": endpoint.get(module.RUNTIME_ENDPOINT_FIELD),
    "pipeName111": module.get_runtime_pipe_name(111),
    "pipeName222": module.get_runtime_pipe_name(222),
}

output_path.write_text(json.dumps(output), encoding="utf-8")
'@ | Set-Content -Path $pythonScriptPath -Encoding UTF8

    $pythonOutput = & $pythonProgram.Source $pythonScriptPath $bridgeSourcePath $tempRoot $pythonOutputPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to verify emitted bridge bootstrap payload: $pythonOutput"
    }

    $endpointCheck = Get-Content -Path $pythonOutputPath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    if ($endpointCheck.transport -ne 'named-pipe') {
        throw "endpoint.json should emit transport 'named-pipe'"
    }

    if ($endpointCheck.endpointField -notin @('endpoint', 'pipeName')) {
        throw "endpoint.json should use an endpoint-discovery field name"
    }

    if ([string]::IsNullOrWhiteSpace([string]$endpointCheck.endpointValue)) {
        throw "endpoint.json should emit a non-empty pipe name or endpoint value"
    }

    if ($endpointCheck.pipeName111 -eq $endpointCheck.pipeName222) {
        throw "runtime endpoint discovery should produce distinct pipe names for distinct MO2 process ids"
    }

    if ($endpointCheck.endpointValue -notmatch '^mo2-control-plane-') {
        throw "endpoint.json should emit an instance-specific pipe name prefix"
    }
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -Path $tempRoot -Recurse -Force
    }
}

foreach ($document in @(
    @{ Path = 'tools/mo2-control-plane/live-bridge/README.md'; Content = $readme },
    @{ Path = 'tools/mo2-control-plane/live-integration.md'; Content = $liveIntegration }
)) {
    foreach ($phrase in @(
        'named-pipe',
        'endpoint.json',
        'transport',
        'file-bootstrap',
        'discovery',
        'liveness',
        'not as the command transport',
        'instance-specific'
    )) {
        if ($document.Content -notmatch [regex]::Escape($phrase)) {
            throw "$($document.Path) is missing phrase: $phrase"
        }
    }

    if ($document.Content -notmatch '(?i)(pipe name|endpoint field|endpoint value)') {
        throw "$($document.Path) must describe a pipe name or endpoint field in endpoint.json"
    }
}

foreach ($forbiddenPhrase in @(
    'Real broker read-path check',
    '## Verify Real Broker Read Path',
    '## Verify Real Launch'
)) {
    if ($liveIntegration -match [regex]::Escape($forbiddenPhrase)) {
        throw "tools/mo2-control-plane/live-integration.md should not describe later-slice verification yet: $forbiddenPhrase"
    }
}

Write-Host "MO2 live endpoint discovery contract checks passed."

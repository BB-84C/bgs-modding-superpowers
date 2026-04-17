$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$bridgeSourcePath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_agent_control.py"
$readmePath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/README.md"

if (-not (Test-Path $bridgeSourcePath -PathType Leaf)) {
    throw "Missing live bridge source: tools/mo2-control-plane/live-bridge/mo2_agent_control.py"
}

if (-not (Test-Path $readmePath -PathType Leaf)) {
    throw "Missing live bridge README: tools/mo2-control-plane/live-bridge/README.md"
}

$bridgeSource = Get-Content -Path $bridgeSourcePath -Raw
$readme = Get-Content -Path $readmePath -Raw

foreach ($anchor in @(
    @{ Pattern = 'RUNTIME_STATUS_FILE\s*=\s*"status\.json"'; Message = 'missing runtime filename constant for status.json' },
    @{ Pattern = 'RUNTIME_CAPABILITIES_FILE\s*=\s*"capabilities\.json"'; Message = 'missing runtime filename constant for capabilities.json' },
    @{ Pattern = 'RUNTIME_ENDPOINT_FILE\s*=\s*"endpoint\.json"'; Message = 'missing runtime filename constant for endpoint.json' },
    @{ Pattern = 'def\s+createPlugin\s*\('; Message = 'missing MO2 Python plugin entrypoint createPlugin()' },
    @{ Pattern = 'def\s+init\s*\(\s*self\s*,\s*organizer\s*\)'; Message = 'missing plugin init(organizer) lifecycle hook' },
    @{ Pattern = 'SYSTEM_PING_METHOD\s*=\s*"system\.ping"'; Message = 'missing broker-visible method anchor for system.ping' },
    @{ Pattern = 'SYSTEM_CAPABILITIES_METHOD\s*=\s*"system\.capabilities"'; Message = 'missing broker-visible method anchor for system.capabilities' },
    @{ Pattern = 'MINIMUM_RUNTIME_JSON_FIELDS\s*=\s*\{[\s\S]*?RUNTIME_STATUS_FILE\s*:\s*\(\s*"schemaVersion"\s*,\s*"state"\s*,\s*"mo2Pid"\s*\)'; Message = 'missing minimum JSON-field mapping for status.json via RUNTIME_STATUS_FILE' },
    @{ Pattern = 'MINIMUM_RUNTIME_JSON_FIELDS\s*=\s*\{[\s\S]*?RUNTIME_CAPABILITIES_FILE\s*:\s*\(\s*"schemaVersion"\s*,\s*"methods"\s*\)'; Message = 'missing minimum JSON-field mapping for capabilities.json via RUNTIME_CAPABILITIES_FILE' },
    @{ Pattern = 'MINIMUM_RUNTIME_JSON_FIELDS\s*=\s*\{[\s\S]*?RUNTIME_ENDPOINT_FILE\s*:\s*\(\s*"schemaVersion"\s*,\s*"transport"\s*,\s*RUNTIME_ENDPOINT_FIELD\s*\)'; Message = 'missing minimum JSON-field mapping for endpoint.json via RUNTIME_ENDPOINT_FILE' }
)) {
    if ($bridgeSource -notmatch $anchor.Pattern) {
        throw "tools/mo2-control-plane/live-bridge/mo2_agent_control.py $($anchor.Message)"
    }
}

foreach ($phrase in @(
    'createPlugin()',
    'plugin initialization',
    'status.json',
    'capabilities.json',
    'endpoint.json',
    'mo2Pid',
    'system.ping',
    'system.capabilities',
    'minimum JSON fields',
    'source-level contract only'
)) {
    if ($readme -notmatch [regex]::Escape($phrase)) {
        throw "tools/mo2-control-plane/live-bridge/README.md is missing phrase: $phrase"
    }
}

Write-Host "MO2 live bootstrap contract checks passed."

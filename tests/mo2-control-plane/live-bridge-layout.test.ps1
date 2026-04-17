$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

$requiredPaths = @(
    "tools/mo2-control-plane/live-bridge/README.md",
    "tools/mo2-control-plane/live-bridge/mo2_agent_control.py",
    "tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1"
)

foreach ($path in $requiredPaths) {
    if (-not (Test-Path (Join-Path $repoRoot $path))) {
        throw "Missing live bridge path: $path"
    }
}

$readme = Get-Content -Path (Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/README.md") -Raw
foreach ($phrase in @(
    "live bridge",
    ".artifacts/mo2/plugins/",
    "scaffold-only"
)) {
    if ($readme -notmatch [regex]::Escape($phrase)) {
        throw "tools/mo2-control-plane/live-bridge/README.md is missing phrase: $phrase"
    }
}

$deployScript = Get-Content -Path (Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1") -Raw
foreach ($phrase in @(
    ".artifacts/mo2/plugins/",
    "Mo2AgentControl",
    "scaffold",
    '$pluginTarget',
    'Expected deployment target: $pluginTarget'
)) {
    if ($deployScript -notmatch [regex]::Escape($phrase)) {
        throw "tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1 is missing phrase: $phrase"
    }
}

foreach ($phrase in @(
    '$repoRoot',
    '$sourceRoot',
    '$defaultMo2Root'
)) {
    if ($deployScript -match [regex]::Escape($phrase)) {
        throw "tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1 should not keep unused variable: $phrase"
    }
}

$bridgeSource = Get-Content -Path (Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_agent_control.py") -Raw
foreach ($phrase in @(
    "MO2 live bootstrap bridge",
    ".artifacts/mo2/plugins/",
    ".artifacts/mo2/plugins/mo2_agent_control.py",
    "Mo2AgentControl/bootstrap/runtime"
)) {
    if ($bridgeSource -notmatch [regex]::Escape($phrase)) {
        throw "tools/mo2-control-plane/live-bridge/mo2_agent_control.py is missing phrase: $phrase"
    }
}

foreach ($phrase in @(
    "createPlugin()",
    "plugin initialization"
)) {
    if ($bridgeSource -notmatch [regex]::Escape($phrase)) {
        throw "tools/mo2-control-plane/live-bridge/mo2_agent_control.py is missing phrase: $phrase"
    }
}

if ($bridgeSource -notmatch 'def\s+init\s*\(\s*self\s*,\s*organizer\s*\)') {
    throw "tools/mo2-control-plane/live-bridge/mo2_agent_control.py should expose init(organizer) for real MO2 plugin initialization"
}

Write-Host "MO2 live bridge layout checks passed."

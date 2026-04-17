$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$deployScriptPath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1"

if (-not (Test-Path $deployScriptPath -PathType Leaf)) {
    throw "Missing live bridge deploy helper: tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1"
}

$tempRoot = Join-Path $env:TEMP ("mo2-live-deploy-" + [guid]::NewGuid().ToString("N"))
$mo2Root = Join-Path $tempRoot "ModOrganizer"
$pluginsRoot = Join-Path $mo2Root ".artifacts/mo2/plugins"
$pluginSupportRoot = Join-Path $pluginsRoot "Mo2AgentControl"
$bridgeTargetPath = Join-Path $pluginsRoot "mo2_agent_control.py"
$bootstrapDataRoot = Join-Path $pluginSupportRoot "bootstrap"

try {
    $null = New-Item -ItemType Directory -Path $mo2Root -Force

    & pwsh -NoProfile -File $deployScriptPath -Mo2Root $mo2Root
    if ($LASTEXITCODE -ne 0) {
        throw "deploy-live-bridge.ps1 should succeed for a caller-provided MO2 root"
    }

    if (-not (Test-Path $pluginsRoot -PathType Container)) {
        throw "deploy-live-bridge.ps1 should create the plugin root under .artifacts/mo2/plugins"
    }

    if (-not (Test-Path $pluginSupportRoot -PathType Container)) {
        throw "deploy-live-bridge.ps1 should create the support directory under .artifacts/mo2/plugins/Mo2AgentControl"
    }

    if (-not (Test-Path $bridgeTargetPath -PathType Leaf)) {
        throw "deploy-live-bridge.ps1 should copy mo2_agent_control.py into the plugin root"
    }

    if (-not (Test-Path $bootstrapDataRoot -PathType Container)) {
        throw "deploy-live-bridge.ps1 should create a fixed bootstrap data subdirectory for later runtime files"
    }

    $bridgeTarget = Get-Content -Path $bridgeTargetPath -Raw
    if ($bridgeTarget -notmatch [regex]::Escape('PLUGIN_NAME = "Mo2AgentControl"')) {
        throw "deployed bridge should preserve the live bridge source payload"
    }

    Write-Host "MO2 live deploy contract checks passed."
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -Path $tempRoot -Recurse -Force
    }
}

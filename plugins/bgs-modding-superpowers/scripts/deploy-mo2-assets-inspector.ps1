<#
.SYNOPSIS
Deploys the MO2 Assets Inspector plugin into <MO2_Root>/plugins/.

Copies:
  - tools/mo2-control-plane/live-bridge/mo2_assets_inspector.py
    -> <MO2_Root>/plugins/mo2_assets_inspector.py
  - tools/mo2-control-plane/live-bridge/mo2_assets_inspector/
    -> <MO2_Root>/plugins/Mo2AssetsInspector/
  - tools/mo2-assets-engine/src/mo2_assets_engine/
    -> <MO2_Root>/plugins/Mo2AssetsInspector/vendored/mo2_assets_engine/

MO2 must NOT be running when this script executes (file lock on plugin tree).

.PARAMETER MO2Root
Absolute path to the MO2 install root. Defaults to $env:BGS_MO2_ROOT.
#>
[CmdletBinding()]
param(
    [string]$MO2Root = $env:BGS_MO2_ROOT
)

$ErrorActionPreference = "Stop"

if (-not $MO2Root) {
    throw "MO2Root not provided and `$env:BGS_MO2_ROOT is unset."
}

$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path
$srcEntry = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_assets_inspector.py"
$srcSupport = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_assets_inspector"
$srcEngine = Join-Path $repoRoot "tools/mo2-assets-engine/src/mo2_assets_engine"

$dstPluginsDir = Join-Path $MO2Root "plugins"
$dstEntry = Join-Path $dstPluginsDir "mo2_assets_inspector.py"
$dstSupport = Join-Path $dstPluginsDir "Mo2AssetsInspector"
$dstVendored = Join-Path $dstSupport "vendored/mo2_assets_engine"

if (-not (Test-Path -LiteralPath $dstPluginsDir)) {
    throw "MO2 plugins dir not found at: $dstPluginsDir"
}

Write-Host "Deploying mo2_assets_inspector.py -> $dstEntry"
Copy-Item -LiteralPath $srcEntry -Destination $dstEntry -Force

Write-Host "Deploying support tree -> $dstSupport"
if (Test-Path -LiteralPath $dstSupport) {
    Remove-Item -LiteralPath $dstSupport -Recurse -Force
}
& robocopy $srcSupport $dstSupport /MIR `
    /XD __pycache__ .mypy_cache .pytest_cache .ruff_cache vendored `
    | Out-Null

Write-Host "Vendoring mo2_assets_engine -> $dstVendored"
New-Item -ItemType Directory -Force -Path (Split-Path $dstVendored) | Out-Null
& robocopy $srcEngine $dstVendored /MIR `
    /XD __pycache__ .mypy_cache .pytest_cache .ruff_cache `
    | Out-Null

Write-Host "Deployment complete. Restart MO2 to load the plugin."

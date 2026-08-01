#requires -Version 7.0
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

.PARAMETER DeleteUnmarkedDeployment
Permit one prompted deletion of an existing unmarked managed support tree. Requires
`-Force`; the tree is not marked unless the complete redeploy succeeds.
#>
[CmdletBinding(SupportsShouldProcess, ConfirmImpact='High')]
param(
    [string]$MO2Root = $env:BGS_MO2_ROOT,

    [switch]$DeleteUnmarkedDeployment,

    [switch]$Force
)

$ErrorActionPreference = "Stop"

if (-not $MO2Root) {
    throw "MO2Root not provided and `$env:BGS_MO2_ROOT is unset."
}

$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path
. (Join-Path $PSScriptRoot "lib/Assert-SafeDeleteTarget.ps1")
$MO2Root = [System.IO.Path]::GetFullPath($MO2Root)
$srcEntry = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_assets_inspector.py"
$srcSupport = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_assets_inspector"
$srcEngine = Join-Path $repoRoot "tools/mo2-assets-engine/src/mo2_assets_engine"

$dstPluginsDir = Join-Path $MO2Root "plugins"
$dstEntry = Join-Path $dstPluginsDir "mo2_assets_inspector.py"
$dstSupport = Join-Path $dstPluginsDir "Mo2AssetsInspector"
$dstVendored = Join-Path $dstSupport "vendored/mo2_assets_engine"
$GeneratedMarker = ".bgs-mo2-assets-inspector"

if (-not (Test-Path -LiteralPath $dstPluginsDir)) {
    throw "MO2 plugins dir not found at: $dstPluginsDir"
}
if (-not (Test-Path -LiteralPath (Join-Path $MO2Root "ModOrganizer.exe"))) {
    throw "MO2 installation identity check failed: ModOrganizer.exe not found at '$MO2Root'."
}
$null = Assert-SafeDeleteTarget -Target $dstSupport -RepoRoot $repoRoot -ContainmentRoot $MO2Root
$existingUnmarkedDeployment = (Test-Path -LiteralPath $dstSupport) -and -not (Test-BgsGeneratedMarker -Target $dstSupport -MarkerName $GeneratedMarker)
# Force is non-interactive only for a managed, marked steady-state deployment.
# An unmarked target keeps ConfirmImpact=High so its deletion needs an explicit assent.
if ($Force -and -not $PSBoundParameters.ContainsKey('Confirm') -and -not $existingUnmarkedDeployment) { $ConfirmPreference = 'None' }

Write-Host "Deploying support tree -> $dstSupport"
if (Test-Path -LiteralPath $dstSupport) {
    if (-not (Test-BgsGeneratedMarker -Target $dstSupport -MarkerName $GeneratedMarker)) {
        if (-not $DeleteUnmarkedDeployment) {
            throw "Refusing to delete '$dstSupport': no $GeneratedMarker marker. Use -DeleteUnmarkedDeployment with -Force to request one prompted deletion."
        }
        if (-not $Force) {
            throw "-DeleteUnmarkedDeployment requires -Force and never writes a marker without a deletion attempt."
        }
        Write-Warning "[deploy-mo2-assets-inspector] deleting this unmarked deployment for this run only: $dstSupport"
    }
    Write-SafeDeletePreview -Target $dstSupport
    if (-not $PSCmdlet.ShouldProcess($dstSupport, "Remove managed MO2 Assets Inspector support tree")) {
        return
    }
    Remove-Item -LiteralPath $dstSupport -Recurse -Force
}
if (-not $PSCmdlet.ShouldProcess($dstSupport, "Copy managed MO2 Assets Inspector support tree")) {
    return
}
& robocopy $srcSupport $dstSupport /E `
    /XD __pycache__ .mypy_cache .pytest_cache .ruff_cache vendored `
    | Out-Null
if ($LASTEXITCODE -gt 7) {
    throw "robocopy failed copying MO2 Assets Inspector support tree (exit $LASTEXITCODE)"
}
$global:LASTEXITCODE = 0

Write-Host "Vendoring mo2_assets_engine -> $dstVendored"
New-Item -ItemType Directory -Force -Path (Split-Path $dstVendored) | Out-Null
if (-not $PSCmdlet.ShouldProcess($dstVendored, "Copy managed mo2_assets_engine vendor tree")) {
    return
}
& robocopy $srcEngine $dstVendored /E `
    /XD __pycache__ .mypy_cache .pytest_cache .ruff_cache `
    | Out-Null
if ($LASTEXITCODE -gt 7) {
    throw "robocopy failed copying mo2_assets_engine (exit $LASTEXITCODE)"
}
$global:LASTEXITCODE = 0

Write-Host "Deploying mo2_assets_inspector.py -> $dstEntry"
if (-not $PSCmdlet.ShouldProcess($dstEntry, "Copy MO2 Assets Inspector entrypoint")) {
    return
}
Copy-Item -LiteralPath $srcEntry -Destination $dstEntry -Force
Write-BgsGeneratedMarker -Target $dstSupport -MarkerName $GeneratedMarker -Content "generatedBy=deploy-mo2-assets-inspector; createdAtUtc=$((Get-Date).ToUniversalTime().ToString('o'))"

Write-Host "Deployment complete. Restart MO2 to load the plugin."

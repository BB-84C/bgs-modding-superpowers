<#
.SYNOPSIS
Deploys xEditHookBridge.dll (shipped by bgs-modding-superpowers) next to the
user's xEdit.exe under MO2.

.DESCRIPTION
xEditHookBridge.dll is the GUI-blocker hook DLL owned by bgs-modding-superpowers
(NOT by the xEdit fork). It must be co-located with xEdit.exe at runtime so the
xEdit automation daemon can find and load it.

Run scripts/fetch-xedit-release.ps1 first to land xEdit.exe at
<MO2Root>/tools/xEdit/; then run this script to drop the hook bridge alongside.

.PARAMETER MO2Root
Absolute path to the user's MO2 install root.

.PARAMETER Force
Overwrite an existing xEditHookBridge.dll at the target.

.EXAMPLE
.\scripts\install-xedit-hook-bridge.ps1 -MO2Root "D:\ModOrganizer2"
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$MO2Root,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# --- Validate -------------------------------------------------------------

$resolvedRoot = (Resolve-Path -Path $MO2Root -ErrorAction Stop).Path
$mo2Exe = Join-Path $resolvedRoot "ModOrganizer.exe"
if (-not (Test-Path $mo2Exe -PathType Leaf)) {
    throw "MO2 root does not contain ModOrganizer.exe: $resolvedRoot"
}

# This script lives at <plugin-root>/scripts/
$pluginRoot = (Resolve-Path -Path (Join-Path $PSScriptRoot "..")).Path
$dllSource = Join-Path $pluginRoot "tools\xedit-hook-bridge\dist\xEditHookBridge.dll"

if (-not (Test-Path $dllSource -PathType Leaf)) {
    throw @"
xEditHookBridge.dll not found at $dllSource.
The DLL ships from this plugin's tools/xedit-hook-bridge/dist/ tree. If the
file is missing, your checkout may be incomplete - try a fresh git clone or
re-install the plugin.
"@
}

# --- Deploy ---------------------------------------------------------------

$xeditDir = Join-Path $resolvedRoot "tools\xEdit"
if (-not (Test-Path $xeditDir -PathType Container)) {
    throw @"
xEdit directory not found at $xeditDir.
Run scripts/fetch-xedit-release.ps1 first to land xEdit.exe under
<MO2Root>/tools/xEdit/, then re-run this script.
"@
}

$dllTarget = Join-Path $xeditDir "xEditHookBridge.dll"
if ((Test-Path $dllTarget) -and -not $Force) {
    Write-Host "xEditHookBridge.dll already deployed at:"
    Write-Host "  $dllTarget"
    Write-Host "  (use -Force to overwrite)"
} else {
    Copy-Item -Path $dllSource -Destination $dllTarget -Force
    Write-Host ""
    Write-Host "==========================================================="
    Write-Host "xEditHookBridge.dll deployed"
    Write-Host "==========================================================="
    Write-Host "  Source: $dllSource"
    Write-Host "  Target: $dllTarget"
    Write-Host ""
    Write-Host "[OK] Hook bridge ready. The xEdit automation daemon will load it on next launch." -ForegroundColor Green
}

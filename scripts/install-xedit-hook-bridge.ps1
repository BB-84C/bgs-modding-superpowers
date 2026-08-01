#
# RETIRED 2026-08-01
#
# This installer is superseded by native xeAutomation* in D:\TES5Edit-contrib
# through xEdit.exe -automation-serve. It is retained only as a historical
# artifact; see tools\xedit-hook-bridge\RECOVERY.md. Normal use must not deploy
# xEditHookBridge.dll.
#
<#
.SYNOPSIS
Historical installer for xEditHookBridge.dll.

.DESCRIPTION
The historical deployment behavior below is reachable only with
-IUnderstandThisIsRetired. Normal xEdit automation uses xEdit.exe
-automation-serve and must not deploy this DLL.

.PARAMETER MO2Root
Absolute path to the user's MO2 install root.

.PARAMETER Force
Historical override for an existing target; requires -IUnderstandThisIsRetired.

.PARAMETER IUnderstandThisIsRetired
Explicitly permits the historical deployment behavior for archaeology only.

.EXAMPLE
 .\scripts\install-xedit-hook-bridge.ps1 -MO2Root "D:\ModOrganizer2" -IUnderstandThisIsRetired
#>
param(
    [string]$MO2Root,
    [switch]$Force,
    [switch]$IUnderstandThisIsRetired
)

$ErrorActionPreference = "Stop"

if (-not $IUnderstandThisIsRetired) {
    Write-Host "xEditHookBridge.dll deployment is retired. Use the native xEdit -automation-serve path instead."
    Write-Host "Historical reference: tools\xedit-hook-bridge\RECOVERY.md"
    return
}

if ([string]::IsNullOrWhiteSpace($MO2Root)) {
    throw "-MO2Root is required when using -IUnderstandThisIsRetired."
}

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

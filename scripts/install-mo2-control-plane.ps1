<#
.SYNOPSIS
Deploys the bgs-modding-superpowers MO2 control plane into the user's MO2 install.

.DESCRIPTION
The control plane is the combination of:
  - mo2_agent_control.py  (Python MO2 plugin loader)
  - Mo2AgentControl.dll   (C++ MO2 plugin; built from tools/mo2-control-plane/plugin/src/)
  - broker/bin/mo2-cli.ps1 + broker/lib/ (PowerShell broker for IPC)
  - ModOrganizer.ini lock_gui=false normalization (so MO2 can stay open under agent control)

The C++ DLL is shipped pre-built when present. If the DLL is missing from this
checkout, the installer warns and skips that step; the rest of the deployment
still lands so the Python plugin half can be exercised.

.PARAMETER MO2Root
Absolute path to the user's MO2 install root (the directory containing
ModOrganizer.exe). Required.

.PARAMETER Force
Overwrite any existing deployment files at the target.

.EXAMPLE
.\scripts\install-mo2-control-plane.ps1 -MO2Root "D:\ModOrganizer2"

.EXAMPLE
.\scripts\install-mo2-control-plane.ps1 -MO2Root "D:\ModOrganizer2" -Force
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$MO2Root,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# --- Validate inputs -------------------------------------------------------

$resolvedRoot = (Resolve-Path -Path $MO2Root -ErrorAction Stop).Path
$mo2Exe = Join-Path $resolvedRoot "ModOrganizer.exe"
if (-not (Test-Path $mo2Exe -PathType Leaf)) {
    throw "MO2 root does not contain ModOrganizer.exe: $resolvedRoot"
}

# This script lives at <plugin-root>/scripts/install-mo2-control-plane.ps1
$pluginRoot = (Resolve-Path -Path (Join-Path $PSScriptRoot "..")).Path

Write-Host ""
Write-Host "bgs-modding-superpowers MO2 control plane install"
Write-Host "  Plugin root: $pluginRoot"
Write-Host "  MO2 root:    $resolvedRoot"
Write-Host ""

# --- 1. Deploy Python loader + ModOrganizer.ini lock_gui normalize ---------

$liveBridgeScript = Join-Path $pluginRoot "tools\mo2-control-plane\live-bridge\deploy-live-bridge.ps1"
if (-not (Test-Path $liveBridgeScript -PathType Leaf)) {
    throw "Missing live-bridge deploy script: $liveBridgeScript"
}

Write-Host "[1/3] Deploying Python loader + ModOrganizer.ini normalization..."
& $liveBridgeScript -Mo2Root $resolvedRoot

# --- 2. Deploy C++ MO2 plugin DLL (when available) -------------------------

$dllCandidates = @(
    (Join-Path $pluginRoot "tools\mo2-control-plane\plugin\dist\Mo2AgentControl.dll"),
    (Join-Path $pluginRoot "tools\mo2-control-plane\plugin\build\Mo2AgentControl.dll"),
    (Join-Path $pluginRoot "tools\mo2-control-plane\plugin\bin\Mo2AgentControl.dll")
)
$dllSource = $dllCandidates | Where-Object { Test-Path $_ -PathType Leaf } | Select-Object -First 1
$dllTarget = Join-Path $resolvedRoot "plugins\Mo2AgentControl.dll"

Write-Host ""
Write-Host "[2/3] Deploying Mo2AgentControl.dll..."
if ($dllSource) {
    if ((Test-Path $dllTarget) -and -not $Force) {
        Write-Host "  DLL already deployed at $dllTarget (use -Force to overwrite)"
    } else {
        Copy-Item -Path $dllSource -Destination $dllTarget -Force
        Write-Host "  Deployed: $dllTarget"
    }
} else {
    Write-Warning "  Mo2AgentControl.dll not pre-built in this checkout."
    Write-Warning "  Searched:"
    foreach ($c in $dllCandidates) { Write-Warning "    $c" }
    Write-Warning "  Build the DLL from tools/mo2-control-plane/plugin/ first."
    Write-Warning "  See docs/internal/repo-bootstrap.md for build instructions."
    Write-Warning "  (The Python loader half of the control plane is already deployed.)"
}

# --- 3. Report broker availability -----------------------------------------

$brokerSource = Join-Path $pluginRoot "tools\mo2-control-plane\broker"
Write-Host ""
Write-Host "[3/3] Broker (PowerShell) source location:"
if (Test-Path $brokerSource -PathType Container) {
    Write-Host "  $brokerSource"
    Write-Host "  Broker runs from the plugin checkout; no copy step required."
} else {
    Write-Warning "  Broker directory not found at $brokerSource"
}

# --- Summary ---------------------------------------------------------------

Write-Host ""
Write-Host "==========================================================="
Write-Host "MO2 control plane deployment summary"
Write-Host "==========================================================="
Write-Host "  MO2 root:           $resolvedRoot"
Write-Host "  Python loader:      $(Join-Path $resolvedRoot 'plugins\mo2_agent_control.py')"
Write-Host "  Plugin DLL:         $dllTarget" -NoNewline
if ($dllSource) { Write-Host "" } else { Write-Host "  (NOT DEPLOYED — see warnings above)" }
Write-Host "  Support directory:  $(Join-Path $resolvedRoot 'plugins\Mo2AgentControl\')"
Write-Host "  Broker source:      $brokerSource"
Write-Host ""
Write-Host "[OK] Restart MO2 to load the Mo2AgentControl plugin." -ForegroundColor Green

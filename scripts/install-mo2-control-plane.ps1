<#
.SYNOPSIS
Deploys the bgs-modding-superpowers MO2 control plane into the user's MO2 install.

.DESCRIPTION
The control plane is a Python MO2 plugin plus a PowerShell broker. There is NO
C++ DLL to build or deploy at v0.1.

What this script installs:
  - mo2_agent_control.py  -> <MO2Root>/plugins/  (Python MO2 plugin loader)
  - Mo2AgentControl/      -> <MO2Root>/plugins/  (bootstrap runtime support dir)
  - ModOrganizer.ini lock_gui=false normalization (so MO2 can stay open under
    agent control)

What this script does NOT install:
  - Mo2AgentControl.dll. There is no production C++ MO2 plugin in this repo at
    v0.1. The Python plugin above IS the agent's MO2 integration. A C++ kernel
    skeleton exists under docs/internal/future-c-kernel/ as a design note for
    later perf-critical paths; it is intentionally unbuilt and not deployed.

After this script returns and MO2 is launched (use scripts/start-mo2.ps1), MO2
will load mo2_agent_control.py as a regular Python plugin and start publishing
the agent-control named pipe + bootstrap runtime files.

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

# --- 1. Deploy the Python MO2 plugin + lock_gui normalization --------------

$liveBridgeScript = Join-Path $pluginRoot "tools\mo2-control-plane\live-bridge\deploy-live-bridge.ps1"
if (-not (Test-Path $liveBridgeScript -PathType Leaf)) {
    throw "Missing live-bridge deploy script: $liveBridgeScript"
}

Write-Host "[1/2] Deploying mo2_agent_control.py + ModOrganizer.ini normalization..."
& $liveBridgeScript -Mo2Root $resolvedRoot

# --- 2. Report broker availability (no copy step; runs from plugin checkout)

$brokerSource = Join-Path $pluginRoot "tools\mo2-control-plane\broker"
Write-Host ""
Write-Host "[2/2] Broker (PowerShell) source location:"
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
Write-Host "  Python plugin:      $(Join-Path $resolvedRoot 'plugins\mo2_agent_control.py')"
Write-Host "  Support directory:  $(Join-Path $resolvedRoot 'plugins\Mo2AgentControl\')"
Write-Host "  Broker source:      $brokerSource"
Write-Host ""
Write-Host "[OK] Control plane installed." -ForegroundColor Green
Write-Host "     Next: start MO2 visibly so it loads the Python plugin."
Write-Host "     -> scripts\start-mo2.ps1 -MO2Root `"$resolvedRoot`""
Write-Host "     When MO2 boots, watch for status.json under"
Write-Host "     <MO2Root>\plugins\Mo2AgentControl\bootstrap\runtime\ to confirm the plugin is live."

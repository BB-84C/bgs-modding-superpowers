param(
    [Parameter(Mandatory = $true)]
    [string]$Mo2Root
)

$ErrorActionPreference = "Stop"

$pluginsTarget = ".artifacts/mo2/plugins/"
$pluginTarget = ".artifacts/mo2/plugins/mo2_agent_control.py"
$pluginSupportTarget = ".artifacts/mo2/plugins/Mo2AgentControl/"
$bootstrapSubdirectory = "bootstrap"

$scriptDirectory = Split-Path -Path $PSCommandPath -Parent
$bridgeSourcePath = Join-Path $scriptDirectory "mo2_agent_control.py"
$resolvedMo2Root = (Resolve-Path -Path $Mo2Root).Path
$pluginsDirectory = Join-Path $resolvedMo2Root $pluginsTarget
$pluginSupportDirectory = Join-Path $resolvedMo2Root $pluginSupportTarget
$bootstrapDirectory = Join-Path $pluginSupportDirectory $bootstrapSubdirectory
$bridgeTargetPath = Join-Path $resolvedMo2Root $pluginTarget

if (-not (Test-Path $bridgeSourcePath -PathType Leaf)) {
    throw "Missing live bridge source: $bridgeSourcePath"
}

$null = New-Item -ItemType Directory -Path $pluginsDirectory -Force
$null = New-Item -ItemType Directory -Path $pluginSupportDirectory -Force
$null = New-Item -ItemType Directory -Path $bootstrapDirectory -Force
Copy-Item -Path $bridgeSourcePath -Destination $bridgeTargetPath -Force

Write-Host "MO2 live bridge scaffold"
Write-Host "Expected deployment target: $pluginTarget"
Write-Host "Deployed live bridge to: $bridgeTargetPath"
Write-Host "Prepared support directory: $pluginSupportDirectory"
Write-Host "Prepared bootstrap data directory: $bootstrapDirectory"

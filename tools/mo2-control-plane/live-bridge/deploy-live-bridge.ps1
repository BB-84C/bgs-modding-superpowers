param(
    [Parameter(Mandatory = $true)]
    [string]$Mo2Root
)

$ErrorActionPreference = "Stop"

$pluginsTarget = ".artifacts/mo2/plugins/"
$pluginTarget = ".artifacts/mo2/plugins/mo2_agent_control.py"
$pluginSupportTarget = ".artifacts/mo2/plugins/Mo2AgentControl/"
$bootstrapSubdirectory = "bootstrap"
$modOrganizerIniTarget = ".artifacts/mo2/ModOrganizer.ini"

$scriptDirectory = Split-Path -Path $PSCommandPath -Parent
$bridgeSourcePath = Join-Path $scriptDirectory "mo2_agent_control.py"
$resolvedMo2Root = (Resolve-Path -Path $Mo2Root).Path
$pluginsDirectory = Join-Path $resolvedMo2Root $pluginsTarget
$pluginSupportDirectory = Join-Path $resolvedMo2Root $pluginSupportTarget
$bootstrapDirectory = Join-Path $pluginSupportDirectory $bootstrapSubdirectory
$bridgeTargetPath = Join-Path $resolvedMo2Root $pluginTarget
$modOrganizerIniPath = Join-Path $resolvedMo2Root $modOrganizerIniTarget

function Set-LockGuiFalse {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path $Path -PathType Leaf)) {
        throw "Missing ModOrganizer.ini: $Path"
    }

    $content = Get-Content -Path $Path -Raw
    $settingsMatch = [regex]::Match($content, '(?ms)^\[Settings\]\r?\n(.*?)(?=^\[|\z)')

    if ($settingsMatch.Success) {
        $settingsBody = $settingsMatch.Groups[1].Value
        if ($settingsBody -match '(?m)^lock_gui\s*=.*$') {
            $updatedSettingsBody = [regex]::Replace($settingsBody, '(?m)^lock_gui\s*=.*$', 'lock_gui=false', 1)
        }
        else {
            $updatedSettingsBody = "lock_gui=false`r`n$settingsBody"
        }

        $updatedContent = $content.Substring(0, $settingsMatch.Groups[1].Index) + $updatedSettingsBody + $content.Substring($settingsMatch.Groups[1].Index + $settingsMatch.Groups[1].Length)
    }
    else {
        $trimmedContent = $content.TrimEnd("`r", "`n")
        if ([string]::IsNullOrEmpty($trimmedContent)) {
            $updatedContent = "[Settings]`r`nlock_gui=false`r`n"
        }
        else {
            $updatedContent = $trimmedContent + "`r`n[Settings]`r`nlock_gui=false`r`n"
        }
    }

    Set-Content -Path $Path -Value $updatedContent
}

if (-not (Test-Path $bridgeSourcePath -PathType Leaf)) {
    throw "Missing live bridge source: $bridgeSourcePath"
}

Set-LockGuiFalse -Path $modOrganizerIniPath
$null = New-Item -ItemType Directory -Path $pluginsDirectory -Force
$null = New-Item -ItemType Directory -Path $pluginSupportDirectory -Force
$null = New-Item -ItemType Directory -Path $bootstrapDirectory -Force
Copy-Item -Path $bridgeSourcePath -Destination $bridgeTargetPath -Force

Write-Host "MO2 live bridge scaffold"
Write-Host "Expected deployment target: $pluginTarget"
Write-Host "Deployed live bridge to: $bridgeTargetPath"
Write-Host "Prepared support directory: $pluginSupportDirectory"
Write-Host "Prepared bootstrap data directory: $bootstrapDirectory"
if (Test-Path $modOrganizerIniPath -PathType Leaf) {
    Write-Host "Normalized sandbox GUI lock setting: $modOrganizerIniPath"
}

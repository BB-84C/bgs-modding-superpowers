$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$deployScriptPath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1"

if (-not (Test-Path $deployScriptPath -PathType Leaf)) {
    throw "Missing live bridge deploy helper: tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1"
}

$tempRoot = Join-Path $env:TEMP ("mo2-live-deploy-lock-gui-" + [guid]::NewGuid().ToString("N"))

function New-TestMo2Root {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [switch]$CreateIni
    )

    $root = Join-Path $tempRoot $Name
    $configRoot = Join-Path $root ".artifacts/mo2"
    $iniPath = Join-Path $configRoot "ModOrganizer.ini"
    $pluginsRoot = Join-Path $configRoot "plugins"
    $pluginSupportRoot = Join-Path $pluginsRoot "Mo2AgentControl"
    $bridgeTargetPath = Join-Path $pluginsRoot "mo2_agent_control.py"

    $null = New-Item -ItemType Directory -Path $configRoot -Force

    if ($CreateIni) {
        Set-Content -Path $iniPath -Value @(
            "[Settings]",
            "lock_gui=true",
            "other_setting=kept"
        )
    }

    return @{
        Root = $root
        ConfigRoot = $configRoot
        IniPath = $iniPath
        PluginsRoot = $pluginsRoot
        PluginSupportRoot = $pluginSupportRoot
        BridgeTargetPath = $bridgeTargetPath
    }
}

function Get-IniSectionBody {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Content,

        [Parameter(Mandatory = $true)]
        [string]$SectionName
    )

    $escapedSectionName = [regex]::Escape($SectionName)
    $sectionMatch = [regex]::Match($Content, "(?ms)^\[$escapedSectionName\]\r?\n(.*?)(?=^\[|\z)")
    if (-not $sectionMatch.Success) {
        throw "Missing section [$SectionName] in INI content"
    }

    return $sectionMatch.Groups[1].Value
}

try {
    $rewriteCase = New-TestMo2Root -Name "rewrite-case" -CreateIni

    & pwsh -NoProfile -File $deployScriptPath -Mo2Root $rewriteCase.Root
    if ($LASTEXITCODE -ne 0) {
        throw "deploy-live-bridge.ps1 should succeed for a caller-provided MO2 root"
    }

    $mo2Ini = Get-Content -Path $rewriteCase.IniPath -Raw
    if ($mo2Ini -notmatch '(?m)^lock_gui=false$') {
        throw "deploy-live-bridge.ps1 should normalize lock_gui=false in .artifacts/mo2/ModOrganizer.ini"
    }

    if ($mo2Ini -match '(?m)^lock_gui=true$') {
        throw "deploy-live-bridge.ps1 should replace any existing lock_gui=true value"
    }

    $missingKeyCase = New-TestMo2Root -Name "missing-key-in-settings-case"
    Set-Content -Path $missingKeyCase.IniPath -Value @(
        "[General]",
        "theme=dark",
        "[Settings]",
        "other_setting=kept",
        "[Paths]",
        "base_directory=C:\\Modding"
    )

    & pwsh -NoProfile -File $deployScriptPath -Mo2Root $missingKeyCase.Root
    if ($LASTEXITCODE -ne 0) {
        throw "deploy-live-bridge.ps1 should succeed when [Settings] exists without lock_gui"
    }

    $missingKeyIni = Get-Content -Path $missingKeyCase.IniPath -Raw
    $settingsBody = Get-IniSectionBody -Content $missingKeyIni -SectionName "Settings"
    if ($settingsBody -notmatch '(?m)^lock_gui=false\r?$') {
        throw "deploy-live-bridge.ps1 should insert lock_gui=false inside the [Settings] section"
    }

    $pathsBody = Get-IniSectionBody -Content $missingKeyIni -SectionName "Paths"
    if ($pathsBody -match '(?m)^lock_gui=false\r?$') {
        throw "deploy-live-bridge.ps1 should not append lock_gui=false under the trailing INI section"
    }

    if ($missingKeyIni -notmatch '(?ms)^\[Settings\]\r?\n(?:(?!^\[).*(?:\r?\n))*?lock_gui=false\r?\n(?:(?!^\[).*(?:\r?\n))*?^\[Paths\]') {
        throw "deploy-live-bridge.ps1 should keep lock_gui=false within [Settings] before the next section"
    }

    $missingIniCase = New-TestMo2Root -Name "missing-ini-case"
    $missingIniOutput = & pwsh -NoProfile -File $deployScriptPath -Mo2Root $missingIniCase.Root 2>&1
    if ($LASTEXITCODE -eq 0) {
        throw "deploy-live-bridge.ps1 should fail when .artifacts/mo2/ModOrganizer.ini is missing"
    }

    $missingIniText = ($missingIniOutput | Out-String)
    if ($missingIniText -notmatch 'Missing ModOrganizer\.ini:') {
        throw "deploy-live-bridge.ps1 should report that ModOrganizer.ini is missing"
    }

    if ($missingIniText -notmatch [regex]::Escape($missingIniCase.IniPath)) {
        throw "deploy-live-bridge.ps1 should report a clear missing ModOrganizer.ini error"
    }

    if (Test-Path $missingIniCase.PluginsRoot) {
        throw "deploy-live-bridge.ps1 should not create the plugins directory when ModOrganizer.ini is missing"
    }

    if (Test-Path $missingIniCase.PluginSupportRoot) {
        throw "deploy-live-bridge.ps1 should not create the plugin support directory when ModOrganizer.ini is missing"
    }

    if (Test-Path $missingIniCase.BridgeTargetPath) {
        throw "deploy-live-bridge.ps1 should not copy the bridge artifact when ModOrganizer.ini is missing"
    }

    Write-Host "MO2 live deploy lock_gui regression checks passed."
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -Path $tempRoot -Recurse -Force
    }
}

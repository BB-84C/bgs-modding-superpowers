$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir 'xedit-client.common.ps1')

function Resolve-XeditClientPluginLinesFromValues {
    param(
        [string[]]$PluginLines
    )

    $normalizedPluginLines = @()
    $seenPluginLines = @{}

    foreach ($pluginLine in @($PluginLines)) {
        $trimmedPluginLine = ([string]$pluginLine).Trim()
        if ([string]::IsNullOrWhiteSpace($trimmedPluginLine) -or $trimmedPluginLine.StartsWith('#')) {
            continue
        }

        if (-not $seenPluginLines.ContainsKey($trimmedPluginLine)) {
            $seenPluginLines[$trimmedPluginLine] = $true
            $normalizedPluginLines += $trimmedPluginLine
        }
    }

    if ($normalizedPluginLines.Count -eq 0) {
        throw "Plugin list must contain at least one non-empty entry."
    }

    return $normalizedPluginLines
}

function Resolve-XeditClientPluginLines {
    param([string]$PluginFilePath)

    if ([string]::IsNullOrWhiteSpace($PluginFilePath)) { throw 'Plugin file path is required.' }
    if (-not (Test-Path $PluginFilePath -PathType Leaf)) { throw "Plugin file not found: $PluginFilePath" }
    return Resolve-XeditClientPluginLinesFromValues -PluginLines (Get-Content -Path $PluginFilePath)
}

function Resolve-XeditClientPluginSource {
    param([string]$PluginFilePath, [string]$ProfilePluginFilePath)

    $sourcePluginFilePath = $PluginFilePath
    if ([string]::IsNullOrWhiteSpace($sourcePluginFilePath)) { $sourcePluginFilePath = $ProfilePluginFilePath }
    if ([string]::IsNullOrWhiteSpace($sourcePluginFilePath)) { throw 'A caller or profile plugins file path is required.' }

    return [pscustomobject]@{
        SourcePluginFilePath = $sourcePluginFilePath
        PluginLines = (Resolve-XeditClientPluginLines -PluginFilePath $sourcePluginFilePath)
    }
}

function New-XeditClientSessionPluginsFile {
    param(
        [string]$SessionPath,
        [string[]]$PluginLines
    )

    if ([string]::IsNullOrWhiteSpace($SessionPath)) {
        throw "Session path is required."
    }

    $null = New-Item -ItemType Directory -Path $SessionPath -Force
    $normalizedSessionPath = (Get-Item -Path $SessionPath).FullName
    $normalizedPluginLines = Resolve-XeditClientPluginLinesFromValues -PluginLines $PluginLines

    $pluginsFilePath = Join-Path $normalizedSessionPath 'plugins.txt'
    $temporaryPluginsFilePath = Join-Path $normalizedSessionPath 'plugins.txt.tmp'

    Set-Content -Path $temporaryPluginsFilePath -Value $normalizedPluginLines
    Move-Item -Path $temporaryPluginsFilePath -Destination $pluginsFilePath -Force

    return [pscustomobject]@{
        SessionPath = $normalizedSessionPath
        SessionPluginsFilePath = $pluginsFilePath
        PluginLines = $normalizedPluginLines
    }
}

function New-XeditClientSessionContext {
    param(
        [string[]]$PluginLines
    )

    $sessionGuid = [guid]::NewGuid().ToString('N')
    $sessionId = 'xedit-client-' + $sessionGuid
    $sessionPath = Join-Path (Get-XeditClientSessionBasePath -TempPath $env:TEMP) $sessionGuid
    $pluginsFileContext = New-XeditClientSessionPluginsFile -SessionPath $sessionPath -PluginLines $PluginLines

    return [pscustomobject]@{
        SessionId = $sessionId
        SessionPath = $pluginsFileContext.SessionPath
        SessionPluginsFilePath = $pluginsFileContext.SessionPluginsFilePath
        PluginLines = $pluginsFileContext.PluginLines
        EnvironmentVariables = @{}
    }
}

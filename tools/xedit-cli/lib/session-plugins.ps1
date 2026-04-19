function Resolve-XeditCliPluginLinesFromValues {
    param(
        [string[]]$PluginLines
    )

    $normalizedPluginLines = @()
    $seenPluginLines = @{}

    foreach ($pluginLine in @($PluginLines)) {
        $trimmedPluginLine = ([string]$pluginLine).Trim()
        if ([string]::IsNullOrWhiteSpace($trimmedPluginLine) -or $trimmedPluginLine.StartsWith("#")) {
            continue
        }

        if ($seenPluginLines.ContainsKey($trimmedPluginLine)) {
            continue
        }

        $seenPluginLines[$trimmedPluginLine] = $true
        $normalizedPluginLines += $trimmedPluginLine
    }

    if ($normalizedPluginLines.Count -eq 0) {
        throw "Plugin list must contain at least one non-empty entry."
    }

    return $normalizedPluginLines
}

function Resolve-XeditCliPluginLines {
    param(
        [string]$PluginFilePath
    )

    if ([string]::IsNullOrWhiteSpace($PluginFilePath)) {
        throw "Plugin file path is required."
    }

    if (-not (Test-Path $PluginFilePath -PathType Leaf)) {
        throw "Plugin file not found: $PluginFilePath"
    }

    return Resolve-XeditCliPluginLinesFromValues -PluginLines (Get-Content -Path $PluginFilePath)
}

function Resolve-XeditCliPluginSource {
    param(
        [string]$PluginFilePath,
        [string]$ProfilePluginFilePath
    )

    $sourcePluginFilePath = $PluginFilePath
    if ([string]::IsNullOrWhiteSpace($sourcePluginFilePath)) {
        $sourcePluginFilePath = $ProfilePluginFilePath
    }

    if ([string]::IsNullOrWhiteSpace($sourcePluginFilePath)) {
        throw "A caller or profile plugins file path is required."
    }

    return [pscustomobject]@{
        SourcePluginFilePath = $sourcePluginFilePath
        PluginLines = (Resolve-XeditCliPluginLines -PluginFilePath $sourcePluginFilePath)
    }
}

function New-XeditCliSessionPluginsFile {
    param(
        [string]$SessionPath,
        [string[]]$PluginLines
    )

    if ([string]::IsNullOrWhiteSpace($SessionPath)) {
        throw "Session path is required."
    }

    $null = New-Item -ItemType Directory -Path $SessionPath -Force
    $normalizedSessionPath = (Get-Item -Path $SessionPath).FullName
    $normalizedPluginLines = Resolve-XeditCliPluginLinesFromValues -PluginLines $PluginLines
    $pluginsFilePath = Join-Path $normalizedSessionPath "plugins.txt"
    $temporaryPluginsFilePath = Join-Path $normalizedSessionPath "plugins.txt.tmp"

    Set-Content -Path $temporaryPluginsFilePath -Value $normalizedPluginLines
    Move-Item -Path $temporaryPluginsFilePath -Destination $pluginsFilePath -Force

    return [pscustomobject]@{
        SessionPath = $normalizedSessionPath
        PluginsFilePath = $pluginsFilePath
        PluginLines = $normalizedPluginLines
    }
}

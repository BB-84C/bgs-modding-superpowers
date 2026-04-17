$ErrorActionPreference = "Stop"

function ConvertTo-Mo2VfsProbeOptions {
    param(
        [string[]]$Arguments
    )

    $options = @{}

    for ($index = 0; $index -lt $Arguments.Count; $index++) {
        $token = $Arguments[$index]
        if ($token -ne "--path") {
            throw "Unexpected option: $token"
        }

        if ($index + 1 -ge $Arguments.Count) {
            throw "Missing value for option: $token"
        }

        $options[$token] = $Arguments[$index + 1]
        $index++
    }

    if ([string]::IsNullOrWhiteSpace([string]$options["--path"])) {
        throw "Missing required option: --path"
    }

    return $options
}

$options = ConvertTo-Mo2VfsProbeOptions -Arguments $args
$targetPath = $options["--path"]
$localAppData = $env:LOCALAPPDATA
$pluginsPath = if ([string]::IsNullOrWhiteSpace($localAppData)) {
    $null
}
else {
    Join-Path $localAppData "Fallout4/plugins.txt"
}

$payload = [ordered]@{
    path = $targetPath
    visible = (Test-Path -LiteralPath $targetPath)
    plugins_txt_path = $pluginsPath
    plugins_txt_visible = if ($null -eq $pluginsPath) { $false } else { Test-Path -LiteralPath $pluginsPath -PathType Leaf }
}

[Console]::Out.Write(($payload | ConvertTo-Json -Compress))

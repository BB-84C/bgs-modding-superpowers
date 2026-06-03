$ErrorActionPreference = "Stop"

function ConvertTo-Mo2VfsProbeOptions {
    param(
        [string[]]$Arguments
    )

    $options = @{}

    for ($index = 0; $index -lt $Arguments.Count; $index++) {
        $token = $Arguments[$index]
        switch ($token) {
            "--path" {
                if ($index + 1 -ge $Arguments.Count) {
                    throw "Missing value for option: $token"
                }

                $options[$token] = $Arguments[$index + 1]
                $index++
            }
            "--result-path" {
                if ($index + 1 -ge $Arguments.Count) {
                    throw "Missing value for option: $token"
                }

                $options[$token] = $Arguments[$index + 1]
                $index++
            }
            default {
                throw "Unexpected option: $token"
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace([string]$options["--path"])) {
        throw "Missing required option: --path"
    }

    return $options
}

function Write-Mo2VfsProbeResultFile {
    param(
        [string]$Path,
        [string]$Content
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }

    $parent = Split-Path -Path $Path -Parent
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path -LiteralPath $parent -PathType Container)) {
        $null = New-Item -ItemType Directory -Path $parent -Force
    }

    [System.IO.File]::WriteAllText($Path, $Content)
}

$options = ConvertTo-Mo2VfsProbeOptions -Arguments $args
$targetPath = $options["--path"]
$resultPath = if ($options.ContainsKey("--result-path")) { [string]$options["--result-path"] } else { $null }
$localAppData = $env:LOCALAPPDATA
$pluginsPath = if ([string]::IsNullOrWhiteSpace($localAppData)) {
    $null
}
else {
    Join-Path $localAppData "Fallout4/plugins.txt"
}

$pluginsEntries = if ($null -eq $pluginsPath -or -not (Test-Path -LiteralPath $pluginsPath -PathType Leaf)) {
    @()
}
else {
    @(Get-Content -LiteralPath $pluginsPath | Where-Object {
        -not [string]::IsNullOrWhiteSpace($_) -and -not $_.StartsWith('#')
    })
}

$payload = [ordered]@{
    path = $targetPath
    visible = (Test-Path -LiteralPath $targetPath)
    plugins_txt_path = $pluginsPath
    plugins_txt_visible = if ($null -eq $pluginsPath) { $false } else { Test-Path -LiteralPath $pluginsPath -PathType Leaf }
    plugins_txt_entries = $pluginsEntries
}

$compactJson = $payload | ConvertTo-Json -Compress
Write-Mo2VfsProbeResultFile -Path $resultPath -Content $compactJson
[Console]::Out.Write($compactJson)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path
$probePath = Join-Path $repoRoot "tools/mo2-vfs-launcher/mo2-vfs-probe.ps1"

function Invoke-Probe {
    param(
        [string]$TargetPath,
        [string]$LocalAppDataPath,
        [string]$ResultPath = $null
    )

    $previousLocalAppData = $env:LOCALAPPDATA
    try {
        $env:LOCALAPPDATA = $LocalAppDataPath
        $arguments = @('--path', $TargetPath)
        if (-not [string]::IsNullOrWhiteSpace($ResultPath)) {
            $arguments += @('--result-path', $ResultPath)
        }

        $output = & pwsh -NoProfile -File $probePath @arguments 2>&1

        return [pscustomobject]@{
            ExitCode = $LASTEXITCODE
            Output = ($output | ForEach-Object { $_.ToString() }) -join "`n"
        }
    }
    finally {
        $env:LOCALAPPDATA = $previousLocalAppData
    }
}

$tempRoot = Join-Path $env:TEMP ("mo2-vfs-probe-test-" + [guid]::NewGuid().ToString("N"))
$null = New-Item -ItemType Directory -Path $tempRoot -Force

try {
    $targetPath = Join-Path $tempRoot "visible-under-probe"
    $null = New-Item -ItemType Directory -Path $targetPath -Force

    $localAppDataPath = Join-Path $tempRoot "LocalAppData"
    $pluginsDirectory = Join-Path $localAppDataPath "Fallout4"
    $null = New-Item -ItemType Directory -Path $pluginsDirectory -Force

    $pluginsPath = Join-Path $pluginsDirectory "plugins.txt"
    Set-Content -Path $pluginsPath -Value "*Fallout4.esm"
    $resultPath = Join-Path $tempRoot "probe.result.json"

    $result = Invoke-Probe -TargetPath $targetPath -LocalAppDataPath $localAppDataPath -ResultPath $resultPath
    if ($result.ExitCode -ne 0) {
        throw "probe should succeed when both inspected paths are visible: $($result.Output)"
    }

    if ([string]::IsNullOrWhiteSpace($result.Output)) {
        throw "probe should emit compact JSON to stdout"
    }

    if ($result.Output.Contains("`r") -or $result.Output.Contains("`n")) {
        throw "probe output should stay on one line for evidence capture"
    }

    $payload = $result.Output | ConvertFrom-Json -ErrorAction Stop
    if ($payload.path -ne $targetPath) {
        throw "probe should echo the caller-provided path"
    }

    if ($payload.visible -ne $true) {
        throw "probe should report the caller-provided path as visible"
    }

    if ($payload.plugins_txt_path -ne $pluginsPath) {
        throw "probe should inspect LOCALAPPDATA/Fallout4/plugins.txt"
    }

    if ($payload.plugins_txt_visible -ne $true) {
        throw "probe should report plugins.txt visibility"
    }

    $compactJson = $payload | ConvertTo-Json -Compress
    if ($result.Output -ne $compactJson) {
        throw "probe should emit compact JSON without extra formatting or noise"
    }

    if (-not (Test-Path -Path $resultPath -PathType Leaf)) {
        throw "probe should optionally persist the same compact JSON payload to --result-path"
    }

    $persistedPayload = Get-Content -Path $resultPath -Raw | ConvertFrom-Json -ErrorAction Stop
    if (($persistedPayload | ConvertTo-Json -Compress) -ne $compactJson) {
        throw "probe should persist the same compact JSON payload it writes to stdout"
    }
}
finally {
    Remove-Item -Path $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}

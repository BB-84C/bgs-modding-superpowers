param(
    [int]$Port = 7847,
    [string]$TranslatorHome = $env:BGS_MODDING_SUPERPOWERS_HOME,
    [string]$PythonExe = "",
    [int]$StartupTimeoutSeconds = 30,
    [switch]$SkipStop
)

$ErrorActionPreference = "Stop"

function Resolve-PackageRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Resolve-TranslatorHome {
    param([string]$Value)
    if (-not [string]::IsNullOrWhiteSpace($Value)) {
        return $Value
    }
    return (Join-Path $env:USERPROFILE ".bgs-modding-superpowers")
}

function Resolve-PythonExe {
    param([string]$Value)
    if (-not [string]::IsNullOrWhiteSpace($Value)) {
        $resolved = Resolve-Path -LiteralPath $Value -ErrorAction Stop
        return $resolved.Path
    }

    $probe = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($probe)) {
        return $probe.Trim()
    }

    $fallback = Get-Command python -ErrorAction Stop
    return $fallback.Source
}

function Get-ListenPid {
    param([int]$ListenPort)
    $connection = Get-NetTCPConnection -LocalPort $ListenPort -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $connection) {
        return $null
    }
    return [int]$connection.OwningProcess
}

function Stop-GuiProcess {
    param(
        [string]$TranslatorRoot,
        [int]$TargetPort
    )

    $candidatePids = New-Object System.Collections.Generic.List[int]
    $pidFile = Join-Path $TranslatorRoot "gui.pid"
    $portFile = Join-Path $TranslatorRoot "gui.port"

    if (Test-Path -LiteralPath $pidFile) {
        $pidText = (Get-Content -LiteralPath $pidFile -Raw).Trim()
        $parsedPid = 0
        if ([int]::TryParse($pidText, [ref]$parsedPid) -and $parsedPid -gt 0) {
            $candidatePids.Add($parsedPid)
        }
    }

    if (Test-Path -LiteralPath $portFile) {
        $portText = (Get-Content -LiteralPath $portFile -Raw).Trim()
        $parsedPort = 0
        if ([int]::TryParse($portText, [ref]$parsedPort) -and $parsedPort -gt 0) {
            $portPid = Get-ListenPid -ListenPort $parsedPort
            if ($null -ne $portPid) {
                $candidatePids.Add($portPid)
            }
        }
    }

    $targetPortPid = Get-ListenPid -ListenPort $TargetPort
    if ($null -ne $targetPortPid) {
        $candidatePids.Add($targetPortPid)
    }

    $uniquePids = $candidatePids | Sort-Object -Unique
    foreach ($processId in $uniquePids) {
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($null -ne $process) {
            Write-Host "Stopping GUI process PID $processId ($($process.ProcessName))"
            Stop-Process -Id $processId -Force
        }
    }

    $deadline = (Get-Date).AddSeconds(10)
    while ((Get-Date) -lt $deadline) {
        if ($null -eq (Get-ListenPid -ListenPort $TargetPort)) {
            break
        }
        Start-Sleep -Milliseconds 200
    }

    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $portFile -Force -ErrorAction SilentlyContinue
}

function Wait-Healthz {
    param(
        [int]$TargetPort,
        [int]$TimeoutSeconds,
        [string]$StderrPath
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $url = "http://127.0.0.1:$TargetPort/healthz"
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-RestMethod -Uri $url -TimeoutSec 1
            if ($response.status -eq "ok") {
                return $true
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }

    if (Test-Path -LiteralPath $StderrPath) {
        Write-Host "Last stderr lines:"
        Get-Content -LiteralPath $StderrPath -Tail 40
    }
    return $false
}

$packageRoot = Resolve-PackageRoot
$homeRoot = Resolve-TranslatorHome -Value $TranslatorHome
$translatorRoot = Join-Path $homeRoot "translator"
$logRoot = Join-Path $translatorRoot "logs"
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null

if (-not $SkipStop) {
    Stop-GuiProcess -TranslatorRoot $translatorRoot -TargetPort $Port
}

$resolvedPython = Resolve-PythonExe -Value $PythonExe
$env:BGS_MODDING_SUPERPOWERS_HOME = $homeRoot

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$stdoutPath = Join-Path $logRoot "web-gui-$Port-$stamp.out.log"
$stderrPath = Join-Path $logRoot "web-gui-$Port-$stamp.err.log"
$arguments = @(
    "-m",
    "bgs_translator.web.app",
    "--port",
    [string]$Port,
    "--no-open"
)

Write-Host "Starting Web GUI on http://127.0.0.1:$Port"
Write-Host "Python: $resolvedPython"
Write-Host "Package root: $packageRoot"
Write-Host "Translator home: $homeRoot"

$process = Start-Process `
    -FilePath $resolvedPython `
    -ArgumentList $arguments `
    -WorkingDirectory $packageRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -PassThru

if (-not (Wait-Healthz -TargetPort $Port -TimeoutSeconds $StartupTimeoutSeconds -StderrPath $stderrPath)) {
    throw "Web GUI did not become healthy on port $Port within $StartupTimeoutSeconds seconds. PID: $($process.Id). Logs: $stdoutPath / $stderrPath"
}

$listenPid = Get-ListenPid -ListenPort $Port
Write-Host "Web GUI healthy: http://127.0.0.1:$Port"
Write-Host "Listening PID: $listenPid"
Write-Host "Logs: $stdoutPath / $stderrPath"

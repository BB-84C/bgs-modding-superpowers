$ErrorActionPreference = "Stop"

function Invoke-XeditClientAutomationCall {
    param(
        [string]$XeditExecutablePath,
        [int]$XeditPid,
        [string]$RequestPath,
        [string]$ResponsePath,
        [int]$TimeoutSeconds = 30
    )

    if (Test-Path $ResponsePath -PathType Leaf) { Remove-Item -Path $ResponsePath -Force }

    $startInfo = @{
        FilePath = $XeditExecutablePath
        ArgumentList = @(
            ('-automation-call-pid:' + $XeditPid),
            ('-automation-call-request:' + $RequestPath),
            ('-automation-call-response:' + $ResponsePath)
        )
        PassThru = $true
        WindowStyle = 'Hidden'
    }

    $process = Start-Process @startInfo
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        throw "Timed out waiting for automation-call response after $TimeoutSeconds seconds"
    }
    if (-not (Test-Path $ResponsePath -PathType Leaf)) {
        throw "Automation call response was not created: $ResponsePath"
    }
    return Get-Content -Path $ResponsePath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
}

function Wait-XeditClientAutomationReady {
    param([string]$XeditExecutablePath, [int]$XeditPid, [string]$SessionPath, [int]$TimeoutSeconds = 30)
    $requestPath = Join-Path $SessionPath 'ready.request.json'
    $responsePath = Join-Path $SessionPath 'ready.response.json'
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Set-Content -Path $requestPath -Value '{"command":"system.describe","args":{}}'
        try {
            $response = Invoke-XeditClientAutomationCall -XeditExecutablePath $XeditExecutablePath -XeditPid $XeditPid -RequestPath $requestPath -ResponsePath $responsePath -TimeoutSeconds 5
            if ($response.ok -eq $true) { return $response }
        } catch {
        }
        Start-Sleep -Milliseconds 500
    }
    throw 'Timed out waiting for native xEdit automation readiness'
}

function Invoke-XeditClientAutomationCallCommand {
    param([string[]]$Arguments)

    try {
        $options = ConvertTo-XeditClientOptionMap -Arguments $Arguments -AllowedNames @('--xedit-pid', '--request-file', '--response-file', '--timeout-seconds')
        $missing = @()
        foreach ($name in @('--xedit-pid', '--request-file', '--response-file', '--timeout-seconds')) {
            if (-not $options.ContainsKey($name)) { $missing += $name }
        }
        if ($missing.Count -gt 0) { Write-Host "Missing required options: $($missing -join ', ')"; return 1 }

        $xeditPid = ConvertTo-XeditClientProcessId -ProcessId $options['--xedit-pid']
        if ($null -eq $xeditPid) { Write-Host "Invalid xEdit PID: $($options['--xedit-pid'])"; return 1 }
        $timeoutSeconds = ConvertTo-XeditClientPositiveIntValue -Value $options['--timeout-seconds']
        if ($null -eq $timeoutSeconds) { Write-Host "Invalid timeout seconds: $($options['--timeout-seconds'])"; return 1 }

        $requestPath = [string]$options['--request-file']
        $responsePath = [string]$options['--response-file']
        if ([string]::IsNullOrWhiteSpace($requestPath)) { Write-Host 'Request file path must be non-empty'; return 1 }
        if ([string]::IsNullOrWhiteSpace($responsePath)) { Write-Host 'Response file path must be non-empty'; return 1 }
        if (-not (Test-Path $requestPath -PathType Leaf)) { Write-Host "Request file does not exist: $requestPath"; return 1 }

        $responseParent = Split-Path -Path $responsePath -Parent
        if (-not [string]::IsNullOrWhiteSpace($responseParent) -and -not (Test-Path $responseParent -PathType Container)) {
            $null = New-Item -ItemType Directory -Path $responseParent -Force
        }

        $processInfo = Get-XeditClientProcessById -ProcessId $xeditPid
        if ($null -eq $processInfo) { Write-Host "xEdit PID is not running: $xeditPid"; return 1 }
        if (-not (Test-XeditClientProcessLooksLikeXedit -Process $processInfo)) { Write-Host "Process is not an xEdit instance: $xeditPid"; return 1 }
        $xeditExecutablePath = [string]$processInfo.ExecutablePath

        $null = Invoke-XeditClientAutomationCall -XeditExecutablePath $xeditExecutablePath -XeditPid $xeditPid -RequestPath $requestPath -ResponsePath $responsePath -TimeoutSeconds $timeoutSeconds

        Write-Host 'automation call'
        Write-Host 'status: ok'
        Write-Host "xedit-pid: $xeditPid"
        Write-Host "xedit-executable-path: $xeditExecutablePath"
        Write-Host "request-file: $requestPath"
        Write-Host "response-file: $responsePath"
        return 0
    }
    catch {
        Write-Host $_.Exception.Message
        return 1
    }
}

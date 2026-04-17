function Get-ProcessFromPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $resolvedPath = [System.IO.Path]::GetFullPath($Path)

    @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $null -ne $_.Path -and [System.StringComparer]::OrdinalIgnoreCase.Equals($_.Path, $resolvedPath)
    })
}

function Stop-SandboxMo2FromPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [int]$TimeoutSeconds = 30,
        [int]$PollIntervalMilliseconds = 500
    )

    foreach ($sandboxMo2Process in @(Get-ProcessFromPath -Path $Path)) {
        Stop-Process -Id $sandboxMo2Process.Id -Force -ErrorAction SilentlyContinue
    }

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-ProcessFromPath -Path $Path).Count -gt 0) {
        if ((Get-Date) -ge $deadline) {
            throw "Timed out waiting for sandbox MO2 to exit: $Path"
        }

        Start-Sleep -Milliseconds $PollIntervalMilliseconds
    }
}

function New-SandboxHarnessMutexName {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $normalizedPath = [System.IO.Path]::GetFullPath($Path).ToLowerInvariant()
    $hashBytes = [System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes($normalizedPath))
    $hash = [System.BitConverter]::ToString($hashBytes).Replace('-', '')
    return "Global\Mo2ControlPlaneLiveIpc_$hash"
}

function Enter-SandboxHarnessLock {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [int]$TimeoutSeconds = 30
    )

    $mutexName = New-SandboxHarnessMutexName -Path $Path
    $createdNew = $false
    $mutex = [System.Threading.Mutex]::new($false, $mutexName, [ref]$createdNew)

    try {
        $hasHandle = $mutex.WaitOne([TimeSpan]::FromSeconds($TimeoutSeconds))
    }
    catch [System.Threading.AbandonedMutexException] {
        $hasHandle = $true
    }

    if (-not $hasHandle) {
        $mutex.Dispose()
        throw "Timed out waiting for the live MO2 sandbox harness lock: $Path"
    }

    return $mutex
}

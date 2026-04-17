param(
    [Parameter(Mandatory = $true)]
    [string]$Command,

    [Parameter(Mandatory = $true)]
    [string]$SessionId,

    [string]$LaunchId,

    [string]$StateFile,

    [string]$PayloadFile
)

$ErrorActionPreference = "Stop"

$launchStatePath = $StateFile
if ([string]::IsNullOrWhiteSpace($launchStatePath)) {
    throw "StateFile is required"
}

$payload = @{}
if (-not [string]::IsNullOrWhiteSpace($PayloadFile)) {
    $payload = Get-Content -Path $PayloadFile -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
}

function Write-LaunchLog {
    param(
        [hashtable]$Entry
    )

    if ([string]::IsNullOrWhiteSpace($env:MO2_CONTROL_PLANE_FAKE_KERNEL_LOG_PATH)) {
        return
    }

    $directory = Split-Path -Parent $env:MO2_CONTROL_PLANE_FAKE_KERNEL_LOG_PATH
    if (-not (Test-Path $directory -PathType Container)) {
        $null = New-Item -ItemType Directory -Path $directory -Force
    }

    Add-Content -Path $env:MO2_CONTROL_PLANE_FAKE_KERNEL_LOG_PATH -Value ($Entry | ConvertTo-Json -Depth 10 -Compress)
}

function Write-LaunchState {
    param(
        [hashtable]$State
    )

    $directory = Split-Path -Parent $launchStatePath
    if (-not (Test-Path $directory -PathType Container)) {
        $null = New-Item -ItemType Directory -Path $directory -Force
    }

    $State | ConvertTo-Json -Depth 10 | Set-Content -Path $launchStatePath
}

function Read-LaunchState {
    if (-not (Test-Path $launchStatePath -PathType Leaf)) {
        throw "Launch state file not found: $launchStatePath"
    }

    return Get-Content -Path $launchStatePath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
}

function Wait-TransportProcess {
    param(
        [int]$ProcessId
    )

    try {
        $process = [System.Diagnostics.Process]::GetProcessById($ProcessId)
    }
    catch {
        return $null
    }

    $process.WaitForExit()
    return $process.ExitCode
}

function Complete-RunningState {
    param(
        [hashtable]$State
    )

    if ($State.status -ne "running" -or $null -eq $State.pid) {
        return $State
    }

    if ($null -ne $State.transport -and $null -ne $State.transport.fake_wait_until_utc) {
        $deadline = [datetime]::Parse([string]$State.transport.fake_wait_until_utc)
        $remaining = [int][math]::Ceiling(($deadline - (Get-Date).ToUniversalTime()).TotalMilliseconds)
        if ($remaining -gt 0) {
            Start-Sleep -Milliseconds $remaining
        }

        $exitCode = if ($null -eq $State.transport.fake_exit_code) { 0 } else { [int]$State.transport.fake_exit_code }
        $State.exit_code = $exitCode
        if ($exitCode -eq 0) {
            $State.status = "completed"
            $State.error = $null
        }
        else {
            $State.status = "failed"
            $State.error = "Target exited with code $exitCode"
        }

        Write-LaunchState -State $State
        return $State
    }

    $exitCode = Wait-TransportProcess -ProcessId ([int]$State.pid)
    if ($null -eq $exitCode) {
        return $State
    }

    $State.exit_code = $exitCode
    if ($exitCode -eq 0) {
        $State.status = "completed"
        $State.error = $null
    }
    else {
        $State.status = "failed"
        $State.error = "Target exited with code $exitCode"
    }

    Write-LaunchState -State $State
    return $State
}

function Start-TransportProcess {
    param(
        [hashtable]$Transport
    )

    $targetPath = [string]$Transport.target_path
    if ([string]::IsNullOrWhiteSpace($targetPath) -or -not (Test-Path $targetPath -PathType Leaf)) {
        throw "Fake kernel transport target_path does not exist: $targetPath"
    }

    $targetArgs = @()
    if ($null -ne $Transport.args) {
        $targetArgs = @($Transport.args)
    }

    $stdoutFile = [string]$Transport.stdout_file
    $stderrFile = [string]$Transport.stderr_file
    $timeoutSeconds = if ($null -eq $Transport.timeout_seconds) { $null } else { [int]$Transport.timeout_seconds }
    $waitMode = [string]$Transport.wait_mode
    $environment = @{}
    if ($null -ne $Transport.env) {
        $environment = [hashtable]$Transport.env
    }

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.UseShellExecute = $false
    $startInfo.WorkingDirectory = Split-Path -Path $targetPath -Parent
    $startInfo.RedirectStandardOutput = -not [string]::IsNullOrWhiteSpace($stdoutFile)
    $startInfo.RedirectStandardError = -not [string]::IsNullOrWhiteSpace($stderrFile)

    if ([System.IO.Path]::GetExtension($targetPath).ToLowerInvariant() -eq ".ps1") {
        $startInfo.FileName = "pwsh"
        $startInfo.ArgumentList.Add("-NoProfile")
        $startInfo.ArgumentList.Add("-File")
        $startInfo.ArgumentList.Add($targetPath)
    }
    else {
        $startInfo.FileName = $targetPath
    }

    foreach ($targetArg in $targetArgs) {
        $startInfo.ArgumentList.Add([string]$targetArg)
    }

    foreach ($name in $environment.Keys) {
        $startInfo.Environment[[string]$name] = [string]$environment[$name]
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $null = $process.Start()

    $stdoutTask = $null
    $stderrTask = $null
    if ($startInfo.RedirectStandardOutput) {
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    }

    if ($startInfo.RedirectStandardError) {
        $stderrTask = $process.StandardError.ReadToEndAsync()
    }

    $state = [ordered]@{
        launch_id = if ([string]::IsNullOrWhiteSpace($LaunchId)) { "launch-" + [guid]::NewGuid().ToString("N") } else { $LaunchId }
        pid = $process.Id
        status = "running"
        artifacts = [ordered]@{
            state_file = $launchStatePath
        }
        transport = [ordered]@{
            target_path = $targetPath
            args = $targetArgs
            wait_mode = $waitMode
            stdout_file = $stdoutFile
            stderr_file = $stderrFile
            timeout_seconds = $timeoutSeconds
            fake_wait_until_utc = if ($waitMode -eq "spawned" -and $null -ne $Transport.fake_wait_milliseconds) { (Get-Date).ToUniversalTime().AddMilliseconds([int]$Transport.fake_wait_milliseconds).ToString("o") } else { $null }
            fake_exit_code = if ($waitMode -eq "spawned" -and $null -ne $Transport.fake_exit_code) { [int]$Transport.fake_exit_code } else { $null }
        }
        error = $null
        exit_code = $null
    }

    if ($waitMode -eq "exit") {
        $timedOut = $false
        if ($null -ne $timeoutSeconds) {
            $timedOut = -not $process.WaitForExit($timeoutSeconds * 1000)
            if ($timedOut) {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
                $null = $process.WaitForExit(5000)
            }
        }
        else {
            $process.WaitForExit()
        }

        if ($null -ne $stdoutTask) {
            [System.IO.File]::WriteAllText($stdoutFile, $stdoutTask.GetAwaiter().GetResult())
        }

        if ($null -ne $stderrTask) {
            [System.IO.File]::WriteAllText($stderrFile, $stderrTask.GetAwaiter().GetResult())
        }

        if ($timedOut) {
            $state.status = "failed"
            $state.error = "Timed out after $timeoutSeconds seconds"
        }
        else {
            $state.exit_code = $process.ExitCode
            if ($process.ExitCode -eq 0) {
                $state.status = "completed"
            }
            else {
                $state.status = "failed"
                $state.error = "Target exited with code $($process.ExitCode)"
            }
        }
    }

    Write-LaunchState -State $state
    return $state
}

switch ($Command) {
    "launch.start" {
        if ($payload.ContainsKey("transport")) {
            $state = Start-TransportProcess -Transport ([hashtable]$payload.transport)
        }
        else {
            $state = [ordered]@{
                launch_id = if ([string]::IsNullOrWhiteSpace($LaunchId)) { "launch-" + [guid]::NewGuid().ToString("N") } else { $LaunchId }
                pid = 4242
                status = "running"
                artifacts = [ordered]@{
                    state_file = $launchStatePath
                }
            }

            Write-LaunchState -State $state
        }

        Write-LaunchLog -Entry ([ordered]@{
            command = $Command
            session_id = $SessionId
            launch_id = $state.launch_id
            payload = $payload
        })
        $state | ConvertTo-Json -Depth 10 -Compress
        break
    }
    "launch.status" {
        $state = Read-LaunchState
        Write-LaunchLog -Entry ([ordered]@{
            command = $Command
            session_id = $SessionId
            launch_id = $state.launch_id
            payload = $payload
        })
        $state | ConvertTo-Json -Depth 10 -Compress
        break
    }
    "launch.wait" {
        $state = Complete-RunningState -State (Read-LaunchState)
        Write-LaunchLog -Entry ([ordered]@{
            command = $Command
            session_id = $SessionId
            launch_id = $state.launch_id
            payload = $payload
        })
        $state | ConvertTo-Json -Depth 10 -Compress
        break
    }
    "launch.stop" {
        $state = Read-LaunchState
        $state.status = "stopped"
        Write-LaunchState -State $state
        Write-LaunchLog -Entry ([ordered]@{
            command = $Command
            session_id = $SessionId
            launch_id = $state.launch_id
            payload = $payload
        })
        $state | ConvertTo-Json -Depth 10 -Compress
        break
    }
    default {
        throw "Unsupported fake kernel command: $Command"
    }
}

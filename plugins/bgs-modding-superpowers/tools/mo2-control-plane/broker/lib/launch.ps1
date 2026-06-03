function New-Mo2ControlPlaneLaunchId {
    return "launch-" + [guid]::NewGuid().ToString("N")
}

function Assert-Mo2ControlPlaneLaunchSessionId {
    param(
        [string]$SessionId
    )

    if ([string]::IsNullOrWhiteSpace($SessionId) -or $SessionId -match '[\\/]' -or $SessionId -eq '.' -or $SessionId -eq '..') {
        throw "Invalid launch session id: $SessionId"
    }

    return $SessionId
}

function Get-Mo2ControlPlaneLaunchesRootForLaunchSession {
    param(
        [string]$SessionId
    )

    $validatedSessionId = Assert-Mo2ControlPlaneLaunchSessionId -SessionId $SessionId
    return Join-Path (Join-Path (Get-Mo2ControlPlaneRoot) $validatedSessionId) "launches"
}

function Get-Mo2ControlPlaneLaunchStateFile {
    param(
        [string]$SessionId,
        [string]$LaunchId
    )

    return Join-Path (Get-Mo2ControlPlaneLaunchesRootForLaunchSession -SessionId $SessionId) ("{0}.json" -f $LaunchId)
}

function Test-Mo2ControlPlaneFakeKernelAvailable {
    $kernelPath = $env:MO2_CONTROL_PLANE_FAKE_KERNEL_PATH
    return -not [string]::IsNullOrWhiteSpace($kernelPath) -and (Test-Path $kernelPath -PathType Leaf)
}

function Test-Mo2ControlPlaneTransportPayload {
    param(
        [hashtable]$Request
    )

    return $Request.command -eq "launch.start" -and $Request.payload -is [System.Collections.IDictionary] -and $Request.payload.Contains("transport")
}

function Read-Mo2ControlPlaneLaunchStateFile {
    param(
        [string]$StateFile
    )

    if ([string]::IsNullOrWhiteSpace($StateFile) -or -not (Test-Path $StateFile -PathType Leaf)) {
        throw "Launch state file not found: $StateFile"
    }

    return Get-Content -Path $StateFile -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
}

function Write-Mo2ControlPlaneLaunchStateFile {
    param(
        [string]$StateFile,
        [hashtable]$State
    )

    $directory = Split-Path -Parent $StateFile
    if (-not (Test-Path $directory -PathType Container)) {
        $null = New-Item -ItemType Directory -Path $directory -Force
    }

    $State | ConvertTo-Json -Depth 10 | Set-Content -Path $StateFile
}

function Write-Mo2ControlPlaneTransportOutputFile {
    param(
        [string]$Path,
        [string]$Content
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }

    $directory = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($directory) -and -not (Test-Path $directory -PathType Container)) {
        $null = New-Item -ItemType Directory -Path $directory -Force
    }

    [System.IO.File]::WriteAllText($Path, $Content)
}

function Wait-Mo2ControlPlaneTransportProcess {
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

function Complete-Mo2ControlPlaneRunningState {
    param(
        [hashtable]$State,
        [string]$StateFile
    )

    if ($State.status -ne 'running' -or $null -eq $State.pid) {
        return $State
    }

    $exitCode = Wait-Mo2ControlPlaneTransportProcess -ProcessId ([int]$State.pid)
    if ($null -eq $exitCode) {
        return $State
    }

    $State.exit_code = $exitCode
    if ($exitCode -eq 0) {
        $State.status = 'completed'
        $State.error = $null
    }
    else {
        $State.status = 'failed'
        $State.error = "Target exited with code $exitCode"
    }

    Write-Mo2ControlPlaneLaunchStateFile -StateFile $StateFile -State $State
    return $State
}

function Start-Mo2ControlPlaneLocalTransport {
    param(
        [string]$LaunchId,
        [string]$StateFile,
        [hashtable]$Transport
    )

    $targetPath = [string]$Transport.target_path
    if ([string]::IsNullOrWhiteSpace($targetPath) -or -not (Test-Path $targetPath -PathType Leaf)) {
        throw "Launch transport target_path does not exist: $targetPath"
    }

    $targetArguments = if ($null -eq $Transport.args) { @() } else { @($Transport.args) }
    $environment = if ($null -eq $Transport.env) { @{} } else { [hashtable]$Transport.env }
    $waitMode = [string]$Transport.wait_mode
    $stdoutFile = [string]$Transport.stdout_file
    $stderrFile = [string]$Transport.stderr_file
    $timeoutSeconds = if ($null -eq $Transport.timeout_seconds) { $null } else { [int]$Transport.timeout_seconds }

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.UseShellExecute = $false
    $startInfo.WorkingDirectory = Split-Path -Path $targetPath -Parent
    $startInfo.RedirectStandardOutput = -not [string]::IsNullOrWhiteSpace($stdoutFile)
    $startInfo.RedirectStandardError = -not [string]::IsNullOrWhiteSpace($stderrFile)

    if ([System.IO.Path]::GetExtension($targetPath).ToLowerInvariant() -eq '.ps1') {
        $startInfo.FileName = 'pwsh'
        $startInfo.ArgumentList.Add('-NoProfile')
        $startInfo.ArgumentList.Add('-File')
        $startInfo.ArgumentList.Add($targetPath)
    }
    else {
        $startInfo.FileName = $targetPath
    }

    foreach ($targetArgument in $targetArguments) {
        $startInfo.ArgumentList.Add([string]$targetArgument)
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
        launch_id = $LaunchId
        pid = $process.Id
        status = 'running'
        artifacts = [ordered]@{
            state_file = $StateFile
        }
        transport = [ordered]@{
            target_path = $targetPath
            args = $targetArguments
            wait_mode = $waitMode
            stdout_file = $stdoutFile
            stderr_file = $stderrFile
            timeout_seconds = $timeoutSeconds
        }
        error = $null
        exit_code = $null
    }

    if ($waitMode -eq 'exit') {
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
            Write-Mo2ControlPlaneTransportOutputFile -Path $stdoutFile -Content $stdoutTask.GetAwaiter().GetResult()
        }

        if ($null -ne $stderrTask) {
            Write-Mo2ControlPlaneTransportOutputFile -Path $stderrFile -Content $stderrTask.GetAwaiter().GetResult()
        }

        if ($timedOut) {
            $state.status = 'failed'
            $state.error = "Timed out after $timeoutSeconds seconds"
        }
        else {
            $state.exit_code = $process.ExitCode
            if ($process.ExitCode -eq 0) {
                $state.status = 'completed'
            }
            else {
                $state.status = 'failed'
                $state.error = "Target exited with code $($process.ExitCode)"
            }
        }
    }

    Write-Mo2ControlPlaneLaunchStateFile -StateFile $StateFile -State $state
    return $state
}

function Invoke-Mo2ControlPlaneLocalLaunchCommand {
    param(
        [hashtable]$Request
    )

    $sessionId = [string]$Request.session_id
    $launchId = if ($Request.command -eq 'launch.start') {
        New-Mo2ControlPlaneLaunchId
    }
    else {
        [string]$Request.payload.launch_id
    }

    if ($Request.command -ne 'launch.start' -and [string]::IsNullOrWhiteSpace($launchId)) {
        throw "Missing launch id for $($Request.command)"
    }

    $stateFile = Get-Mo2ControlPlaneLaunchStateFile -SessionId $sessionId -LaunchId $launchId
    switch ($Request.command) {
        'launch.start' {
            $transport = [hashtable]$Request.payload.transport
            $state = Start-Mo2ControlPlaneLocalTransport -LaunchId $launchId -StateFile $stateFile -Transport $transport
            return ConvertTo-Mo2ControlPlaneLaunchStateResult -InputObject $state -SessionId $sessionId -LaunchId $launchId -StateFile $stateFile
        }
        'launch.status' {
            $state = Read-Mo2ControlPlaneLaunchStateFile -StateFile $stateFile
            return ConvertTo-Mo2ControlPlaneLaunchStateResult -InputObject $state -SessionId $sessionId -LaunchId $launchId -StateFile $stateFile
        }
        'launch.wait' {
            $state = Complete-Mo2ControlPlaneRunningState -State (Read-Mo2ControlPlaneLaunchStateFile -StateFile $stateFile) -StateFile $stateFile
            return ConvertTo-Mo2ControlPlaneLaunchStateResult -InputObject $state -SessionId $sessionId -LaunchId $launchId -StateFile $stateFile
        }
        'launch.stop' {
            $state = Read-Mo2ControlPlaneLaunchStateFile -StateFile $stateFile
            if ($state.status -eq 'running' -and $null -ne $state.pid) {
                Stop-Process -Id ([int]$state.pid) -Force -ErrorAction SilentlyContinue
                $state.status = 'stopped'
                Write-Mo2ControlPlaneLaunchStateFile -StateFile $stateFile -State $state
            }

            return ConvertTo-Mo2ControlPlaneLaunchStateResult -InputObject $state -SessionId $sessionId -LaunchId $launchId -StateFile $stateFile
        }
        default {
            throw "Unsupported launch command: $($Request.command)"
        }
    }
}

function ConvertTo-Mo2ControlPlaneLaunchStateResult {
    param(
        [object]$InputObject,
        [string]$SessionId,
        [string]$LaunchId,
        [string]$StateFile
    )

    $resolvedLaunchId = if ([string]::IsNullOrWhiteSpace($InputObject.launch_id)) {
        $LaunchId
    }
    else {
        [string]$InputObject.launch_id
    }

    $resolvedStateFile = $StateFile
    if ($null -ne $InputObject.artifacts -and -not [string]::IsNullOrWhiteSpace($InputObject.artifacts.state_file)) {
        $resolvedStateFile = [string]$InputObject.artifacts.state_file
    }

    if ([string]::IsNullOrWhiteSpace($resolvedStateFile) -and -not [string]::IsNullOrWhiteSpace($resolvedLaunchId)) {
        $resolvedStateFile = Get-Mo2ControlPlaneLaunchStateFile -SessionId $SessionId -LaunchId $resolvedLaunchId
    }

    return [ordered]@{
        launch_id = $resolvedLaunchId
        pid = if ($null -eq $InputObject.pid) { $null } else { [int]$InputObject.pid }
        status = [string]$InputObject.status
        artifacts = [ordered]@{
            state_file = $resolvedStateFile
        }
    }
}

function Invoke-Mo2ControlPlaneFakeKernelLaunchCommand {
    param(
        [hashtable]$Request
    )

    $sessionId = [string]$Request.session_id
    $launchId = if ($Request.command -eq "launch.start") {
        New-Mo2ControlPlaneLaunchId
    }
    else {
        [string]$Request.payload.launch_id
    }

    if ($Request.command -ne "launch.start" -and [string]::IsNullOrWhiteSpace($launchId)) {
        throw "Missing launch id for $($Request.command)"
    }

    $stateFile = Get-Mo2ControlPlaneLaunchStateFile -SessionId $sessionId -LaunchId $launchId

    $payloadFile = $null
    try {
        if ($null -ne $Request.payload) {
            $payloadFile = Join-Path $env:TEMP ("mo2-control-plane-payload-" + [guid]::NewGuid().ToString("N") + ".json")
            $Request.payload | ConvertTo-Json -Depth 10 | Set-Content -Path $payloadFile
        }

        $kernelArguments = @(
            "-NoProfile",
            "-File",
            $env:MO2_CONTROL_PLANE_FAKE_KERNEL_PATH,
            "-Command",
            $Request.command,
            "-SessionId",
            $sessionId,
            "-LaunchId",
            $launchId,
            "-StateFile",
            $stateFile
        )

        if (-not [string]::IsNullOrWhiteSpace($payloadFile)) {
            $kernelArguments += @("-PayloadFile", $payloadFile)
        }

        $kernelOutput = & pwsh @kernelArguments 2>&1
        if ($LASTEXITCODE -ne 0) {
            $message = ($kernelOutput | ForEach-Object { $_.ToString() }) -join "`n"
            throw "Fake kernel launch transport failed: $message"
        }

        $result = (($kernelOutput | ForEach-Object { $_.ToString() }) -join "`n") | ConvertFrom-Json -AsHashtable -ErrorAction Stop
        return ConvertTo-Mo2ControlPlaneLaunchStateResult -InputObject $result -SessionId $sessionId -LaunchId $launchId -StateFile $stateFile
    }
    finally {
        if (-not [string]::IsNullOrWhiteSpace($payloadFile)) {
            Remove-Item -Path $payloadFile -Force -ErrorAction SilentlyContinue
        }
    }
}

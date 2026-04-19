$ErrorActionPreference = "Stop"

function ConvertTo-Mo2VfsLauncherOptions {
    param(
        [string[]]$Arguments
    )

    $options = @{
        "--target-arg" = @()
        "--env" = @()
    }

    for ($index = 0; $index -lt $Arguments.Count; $index++) {
        $token = $Arguments[$index]
        if (-not $token.StartsWith("--")) {
            throw "Unexpected argument: $token"
        }

        if ($index + 1 -ge $Arguments.Count) {
            throw "Missing value for option: $token"
        }

        $value = $Arguments[$index + 1]
        switch ($token) {
            "--target-arg" {
                $options[$token] += $value
            }
            "--env" {
                $options[$token] += $value
            }
            "--target-path" {
                $options[$token] = $value
            }
            "--session-id" {
                $options[$token] = $value
            }
            "--state-file" {
                $options[$token] = $value
            }
            "--wait-mode" {
                $options[$token] = $value
            }
            "--transport-mode" {
                $options[$token] = $value
            }
            "--stdout-file" {
                $options[$token] = $value
            }
            "--stderr-file" {
                $options[$token] = $value
            }
            "--timeout-seconds" {
                $options[$token] = $value
            }
            default {
                throw "Unexpected option: $token"
            }
        }

        $index++
    }

    return $options
}

function Test-Mo2VfsLauncherRequiredOptions {
    param(
        [hashtable]$Options,
        [string[]]$Names
    )

    $missing = @()
    foreach ($name in $Names) {
        if (-not $Options.ContainsKey($name) -or [string]::IsNullOrWhiteSpace([string]$Options[$name])) {
            $missing += $name
        }
    }

    if ($missing.Count -gt 0) {
        throw "Missing required options: $($missing -join ', ')"
    }

    return $true
}

function ConvertTo-Mo2VfsLauncherEnvironment {
    param(
        [string[]]$Values
    )

    $environment = @{}
    foreach ($entry in $Values) {
        $separatorIndex = $entry.IndexOf("=")
        if ($separatorIndex -le 0) {
            throw "Invalid --env value: $entry"
        }

        $name = $entry.Substring(0, $separatorIndex)
        $value = $entry.Substring($separatorIndex + 1)
        $environment[$name] = $value
    }

    return $environment
}

function Get-Mo2VfsLauncherProcessEnvironment {
    $environment = @{}
    foreach ($entry in [System.Environment]::GetEnvironmentVariables().GetEnumerator()) {
        $environment[[string]$entry.Key] = [string]$entry.Value
    }

    return $environment
}

function Get-Mo2VfsLauncherTransportMode {
    param(
        [hashtable]$Options
    )

    if ($Options.ContainsKey("--transport-mode") -and -not [string]::IsNullOrWhiteSpace([string]$Options["--transport-mode"])) {
        return [string]$Options["--transport-mode"]
    }

    return 'broker'
}

function Write-Mo2VfsLauncherState {
    param(
        [string]$StateFile,
        [object]$State
    )

    if ([string]::IsNullOrWhiteSpace($StateFile)) {
        return
    }

    $parent = Split-Path -Path $StateFile -Parent
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path $parent)) {
        $null = New-Item -ItemType Directory -Path $parent -Force
    }

    $State | ConvertTo-Json -Depth 4 | Set-Content -Path $StateFile
}

function Resolve-Mo2VfsLauncherOutputPath {
    param(
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $null
    }

    $parent = Split-Path -Path $Path -Parent
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path $parent)) {
        $null = New-Item -ItemType Directory -Path $parent -Force
    }

    return $Path
}

function Write-Mo2VfsLauncherOutputFile {
    param(
        [string]$Path,
        [string]$Content
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }

    [System.IO.File]::WriteAllText($Path, $Content)
}

function Read-Mo2VfsLauncherJsonFile {
    param(
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path $Path -PathType Leaf)) {
        throw "Expected JSON file to exist: $Path"
    }

    return Get-Content -Path $Path -Raw | ConvertFrom-Json -ErrorAction Stop
}

function New-Mo2VfsLauncherState {
    param(
        [string]$Status,
        [string]$SessionId,
        [Nullable[int]]$StatePid,
        [string]$TargetPath,
        [string[]]$Arguments,
        [string]$Error = $null,
        [Nullable[int]]$ExitCode = $null
    )

    $state = [ordered]@{
        status = $Status
        session_id = $SessionId
        pid = if ($null -eq $StatePid) { $null } else { [int]$StatePid }
        target_path = $TargetPath
        args = $Arguments
        error = if ($PSBoundParameters.ContainsKey("Error")) { $Error } else { $null }
    }

    if ($null -ne $ExitCode) {
        $state.exit_code = [int]$ExitCode
    }

    return $state
}

$script:Mo2VfsLauncherBrokerAvailable = $true
$script:Mo2VfsLauncherBrokerLibRoot = Join-Path $PSScriptRoot "..\mo2-control-plane\broker\lib"
$script:Mo2VfsLauncherBrokerLibFiles = @(
    "common.ps1",
    "protocol.ps1",
    "session.ps1",
    "launch.ps1",
    "client.ps1"
)

foreach ($fileName in $script:Mo2VfsLauncherBrokerLibFiles) {
    $path = Join-Path $script:Mo2VfsLauncherBrokerLibRoot $fileName
    if (-not (Test-Path $path -PathType Leaf)) {
        $script:Mo2VfsLauncherBrokerAvailable = $false
        break
    }
}

if ($script:Mo2VfsLauncherBrokerAvailable) {
    foreach ($fileName in $script:Mo2VfsLauncherBrokerLibFiles) {
        . (Join-Path $script:Mo2VfsLauncherBrokerLibRoot $fileName)
    }
}

function Invoke-Mo2VfsLauncherBrokerTransport {
    param(
        [string]$TargetPath,
        [string]$SessionId,
        [string[]]$TargetArguments,
        [hashtable]$Environment,
        [string]$WaitMode,
        [string]$StdoutFile,
        [string]$StderrFile,
        [Nullable[int]]$TimeoutSeconds
    )

    if (-not $script:Mo2VfsLauncherBrokerAvailable) {
        throw "Broker launch functions are unavailable"
    }

    $transport = [ordered]@{
        target_path = $TargetPath
        args = $TargetArguments
        env = $Environment
        wait_mode = $WaitMode
    }

    if (-not [string]::IsNullOrWhiteSpace($StdoutFile)) {
        $transport.stdout_file = $StdoutFile
    }

    if (-not [string]::IsNullOrWhiteSpace($StderrFile)) {
        $transport.stderr_file = $StderrFile
    }

    if ($null -ne $TimeoutSeconds) {
        $transport.timeout_seconds = $TimeoutSeconds
    }

    $startRequest = New-Mo2ControlPlaneRequest -SessionId $SessionId -Command "launch.start" -Payload ([ordered]@{
        transport = $transport
    })
    $startResponse = Invoke-Mo2ControlPlaneClientRequest -Request $startRequest
    if (-not $startResponse.ok) {
        throw "Broker launch.start failed: $($startResponse.error.message)"
    }

    $launchResult = $startResponse.result
    $transportState = Read-Mo2VfsLauncherJsonFile -Path $launchResult.artifacts.state_file
    if ($WaitMode -eq "exit" -and [string]$transportState.status -eq "running") {
        $waitRequest = New-Mo2ControlPlaneRequest -SessionId $SessionId -Command "launch.wait" -Payload ([ordered]@{
            launch_id = $launchResult.launch_id
        })
        $waitResponse = Invoke-Mo2ControlPlaneClientRequest -Request $waitRequest
        if (-not $waitResponse.ok) {
            throw "Broker launch.wait failed: $($waitResponse.error.message)"
        }

        $transportState = Read-Mo2VfsLauncherJsonFile -Path $waitResponse.result.artifacts.state_file
    }

    $processId = if ($null -eq $transportState.pid) { $launchResult.pid } else { [int]$transportState.pid }
    if ($WaitMode -eq "spawned") {
        if ([string]$transportState.status -eq "failed") {
            return [pscustomobject]@{
                State = (New-Mo2VfsLauncherState -Status "failed" -SessionId $SessionId -StatePid $processId -TargetPath $TargetPath -Arguments $TargetArguments -Error ([string]$transportState.error) -ExitCode $(if ($null -ne $transportState.exit_code) { [int]$transportState.exit_code } else { $null }))
                ExitCode = if ($null -ne $transportState.exit_code) { [int]$transportState.exit_code } else { 1 }
            }
        }

        return [pscustomobject]@{
            State = (New-Mo2VfsLauncherState -Status "spawned" -SessionId $SessionId -StatePid $processId -TargetPath $TargetPath -Arguments $TargetArguments)
            ExitCode = 0
        }
    }

    if ([string]$transportState.status -eq "completed") {
        $exitCode = if ($null -ne $transportState.exit_code) { [int]$transportState.exit_code } else { 0 }
        return [pscustomobject]@{
            State = (New-Mo2VfsLauncherState -Status "exited" -SessionId $SessionId -StatePid $processId -TargetPath $TargetPath -Arguments $TargetArguments -ExitCode $exitCode)
            ExitCode = $exitCode
        }
    }

    $failedExitCode = if ($null -ne $transportState.exit_code) { [int]$transportState.exit_code } else { $null }
    return [pscustomobject]@{
        State = (New-Mo2VfsLauncherState -Status "failed" -SessionId $SessionId -StatePid $processId -TargetPath $TargetPath -Arguments $TargetArguments -Error ([string]$transportState.error) -ExitCode $failedExitCode)
        ExitCode = if ($null -ne $failedExitCode) { $failedExitCode } else { 1 }
    }
}

function Invoke-Mo2VfsLauncherDirectChildTransport {
    param(
        [string]$TargetPath,
        [string]$SessionId,
        [string[]]$TargetArguments,
        [hashtable]$Environment,
        [string]$WaitMode,
        [string]$StdoutFile,
        [string]$StderrFile,
        [Nullable[int]]$TimeoutSeconds
    )

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.UseShellExecute = $false
    $startInfo.WorkingDirectory = Split-Path -Path $TargetPath -Parent
    $startInfo.RedirectStandardOutput = -not [string]::IsNullOrWhiteSpace($StdoutFile)
    $startInfo.RedirectStandardError = -not [string]::IsNullOrWhiteSpace($StderrFile)

    if ([System.IO.Path]::GetExtension($TargetPath).ToLowerInvariant() -eq '.ps1') {
        $startInfo.FileName = 'pwsh'
        $null = $startInfo.ArgumentList.Add('-NoProfile')
        $null = $startInfo.ArgumentList.Add('-File')
        $null = $startInfo.ArgumentList.Add($TargetPath)
    }
    else {
        $startInfo.FileName = $TargetPath
    }

    foreach ($targetArgument in $TargetArguments) {
        $null = $startInfo.ArgumentList.Add([string]$targetArgument)
    }

    foreach ($name in $Environment.Keys) {
        $startInfo.Environment[[string]$name] = [string]$Environment[$name]
    }

    $process = New-Object System.Diagnostics.Process
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

    if ($WaitMode -eq 'spawned') {
        return [pscustomobject]@{
            State = (New-Mo2VfsLauncherState -Status 'spawned' -SessionId $SessionId -StatePid $process.Id -TargetPath $TargetPath -Arguments $TargetArguments)
            ExitCode = 0
        }
    }

    $timedOut = $false
    if ($null -ne $TimeoutSeconds) {
        $timedOut = -not $process.WaitForExit($TimeoutSeconds * 1000)
        if ($timedOut) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            $null = $process.WaitForExit(5000)
        }
    }
    else {
        $process.WaitForExit()
    }

    if ($null -ne $stdoutTask) {
        Write-Mo2VfsLauncherOutputFile -Path $StdoutFile -Content $stdoutTask.GetAwaiter().GetResult()
    }

    if ($null -ne $stderrTask) {
        Write-Mo2VfsLauncherOutputFile -Path $StderrFile -Content $stderrTask.GetAwaiter().GetResult()
    }

    if ($timedOut) {
        return [pscustomobject]@{
            State = (New-Mo2VfsLauncherState -Status 'failed' -SessionId $SessionId -StatePid $process.Id -TargetPath $TargetPath -Arguments $TargetArguments -Error ("Timed out after {0} seconds" -f $TimeoutSeconds))
            ExitCode = 1
        }
    }

    $exitCode = $process.ExitCode
    if ($exitCode -eq 0) {
        return [pscustomobject]@{
            State = (New-Mo2VfsLauncherState -Status 'exited' -SessionId $SessionId -StatePid $process.Id -TargetPath $TargetPath -Arguments $TargetArguments -ExitCode $exitCode)
            ExitCode = 0
        }
    }

    return [pscustomobject]@{
        State = (New-Mo2VfsLauncherState -Status 'failed' -SessionId $SessionId -StatePid $process.Id -TargetPath $TargetPath -Arguments $TargetArguments -Error ("Target exited with code {0}" -f $exitCode) -ExitCode $exitCode)
        ExitCode = $exitCode
    }
}

function Get-Mo2VfsLauncherTimeoutSeconds {
    param(
        [hashtable]$Options
    )

    if (-not $Options.ContainsKey("--timeout-seconds")) {
        return $null
    }

    $timeoutSeconds = 0
    if (-not [int]::TryParse([string]$Options["--timeout-seconds"], [ref]$timeoutSeconds) -or $timeoutSeconds -le 0) {
        throw "Invalid --timeout-seconds: $($Options["--timeout-seconds"]). Expected a positive integer."
    }

    return $timeoutSeconds
}

$options = $null
$targetPath = $null
$sessionId = $null
$stateFile = $null
$waitMode = "spawned"
$targetArguments = @()

try {
    $options = ConvertTo-Mo2VfsLauncherOptions -Arguments $args

    if ($options.ContainsKey("--target-path")) {
        $targetPath = $options["--target-path"]
    }

    if ($options.ContainsKey("--session-id")) {
        $sessionId = $options["--session-id"]
    }

    if ($options.ContainsKey("--state-file")) {
        $stateFile = $options["--state-file"]
    }

    Test-Mo2VfsLauncherRequiredOptions -Options $options -Names @("--target-path", "--session-id", "--state-file") | Out-Null

    if ($options.ContainsKey("--wait-mode")) {
        $waitMode = $options["--wait-mode"]
    }

    if (@("spawned", "exit") -notcontains $waitMode) {
        throw "Invalid --wait-mode: $waitMode. Supported wait modes: spawned, exit"
    }

    if ($waitMode -eq "spawned" -and ($options.ContainsKey("--stdout-file") -or $options.ContainsKey("--stderr-file"))) {
        throw "--stdout-file and --stderr-file are only supported when --wait-mode=exit"
    }

    if (-not (Test-Path $targetPath -PathType Leaf)) {
        throw "Target path does not exist: $targetPath"
    }

    $targetPath = (Resolve-Path $targetPath).Path
    $targetArguments = @($options["--target-arg"])
    $environment = Get-Mo2VfsLauncherProcessEnvironment
    foreach ($entry in (ConvertTo-Mo2VfsLauncherEnvironment -Values $options["--env"]).GetEnumerator()) {
        $environment[[string]$entry.Key] = [string]$entry.Value
    }
    $stdoutFile = Resolve-Mo2VfsLauncherOutputPath -Path $options["--stdout-file"]
    $stderrFile = Resolve-Mo2VfsLauncherOutputPath -Path $options["--stderr-file"]
    $timeoutSeconds = Get-Mo2VfsLauncherTimeoutSeconds -Options $options

    $transportMode = Get-Mo2VfsLauncherTransportMode -Options $options
    if (@('broker', 'direct-child') -notcontains $transportMode) {
        throw "Invalid --transport-mode: $transportMode. Supported transport modes: broker, direct-child"
    }

    if ($transportMode -eq 'direct-child') {
        $transportResult = Invoke-Mo2VfsLauncherDirectChildTransport -TargetPath $targetPath -SessionId $sessionId -TargetArguments $targetArguments -Environment $environment -WaitMode $waitMode -StdoutFile $stdoutFile -StderrFile $stderrFile -TimeoutSeconds $timeoutSeconds
    }
    else {
        if (-not $script:Mo2VfsLauncherBrokerAvailable) {
            throw "Broker launch functions are unavailable"
        }

        $transportResult = Invoke-Mo2VfsLauncherBrokerTransport -TargetPath $targetPath -SessionId $sessionId -TargetArguments $targetArguments -Environment $environment -WaitMode $waitMode -StdoutFile $stdoutFile -StderrFile $stderrFile -TimeoutSeconds $timeoutSeconds
    }

    Write-Mo2VfsLauncherState -StateFile $stateFile -State $transportResult.State
    exit $transportResult.ExitCode
}
catch {
    $message = $_.Exception.Message
    if (-not [string]::IsNullOrWhiteSpace($stateFile)) {
        $failureState = New-Mo2VfsLauncherState -Status "failed" -SessionId $sessionId -StatePid $null -TargetPath $targetPath -Arguments $targetArguments -Error $message

        Write-Mo2VfsLauncherState -StateFile $stateFile -State $failureState
    }

    Write-Host $message
    exit 1
}

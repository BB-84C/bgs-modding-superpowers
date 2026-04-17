$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$bridgeSourcePath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_agent_control.py"
$cliPath = Join-Path $repoRoot "tools/mo2-control-plane/broker/bin/mo2-cli.ps1"

. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/common.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/protocol.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/ipc-client.ps1")

function Wait-ForHarnessSummary {
    param(
        [System.Management.Automation.Job]$Job,
        [int]$TimeoutSeconds = 10
    )

    $nonJsonOutput = @()
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $records = @(Receive-Job -Job $Job -Keep -ErrorAction SilentlyContinue)
        foreach ($record in $records) {
            $text = $record.ToString()
            if ([string]::IsNullOrWhiteSpace($text)) {
                continue
            }

            try {
                return $text | ConvertFrom-Json -AsHashtable -ErrorAction Stop
            }
            catch {
                if ($nonJsonOutput -notcontains $text) {
                    $nonJsonOutput += $text
                }
            }
        }

        if ($Job.State -in @("Failed", "Completed", "Stopped")) {
            $records = @(Receive-Job -Job $Job -Keep -ErrorAction SilentlyContinue | ForEach-Object { $_.ToString() })
            $message = if ($records.Count -gt 0) { $records -join "`n" } elseif ($nonJsonOutput.Count -gt 0) { $nonJsonOutput -join "`n" } else { "job ended before readiness" }
            throw "Python harness terminated before readiness: $message"
        }

        Start-Sleep -Milliseconds 100
    }

    throw "Timed out waiting for Python harness summary from background job"
}

function Invoke-Cli {
    param(
        [string[]]$Arguments
    )

    $output = & pwsh -NoProfile -File $cliPath @Arguments 2>&1

    return [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = ($output | ForEach-Object { $_.ToString() }) -join "`n"
    }
}

function Send-MalformedNamedPipeFrame {
    param(
        [string]$PipeName,
        [string]$Frame = '{"method":'
    )

    $client = $null
    $writer = $null
    $reader = $null

    try {
        $client = [System.IO.Pipes.NamedPipeClientStream]::new(
            ".",
            $PipeName,
            [System.IO.Pipes.PipeDirection]::InOut,
            [System.IO.Pipes.PipeOptions]::None
        )
        $client.Connect(5000)

        $utf8 = [System.Text.UTF8Encoding]::new($false)
        $writer = [System.IO.StreamWriter]::new($client, $utf8, 1024, $true)
        $writer.NewLine = "`n"
        $writer.AutoFlush = $true
        $reader = [System.IO.StreamReader]::new($client, $utf8, $false, 1024, $true)

        $writer.WriteLine($Frame)
        return $reader.ReadLine()
    }
    finally {
        if ($null -ne $reader) {
            try {
                $reader.Dispose()
            }
            catch {
            }
        }

        if ($null -ne $writer) {
            try {
                $writer.Dispose()
            }
            catch {
            }
        }

        if ($null -ne $client) {
            try {
                $client.Dispose()
            }
            catch {
            }
        }
    }
}

if (-not (Test-Path $bridgeSourcePath -PathType Leaf)) {
    throw "Missing live bridge source: tools/mo2-control-plane/live-bridge/mo2_agent_control.py"
}

if (-not (Test-Path $cliPath -PathType Leaf)) {
    throw "Missing broker CLI: tools/mo2-control-plane/broker/bin/mo2-cli.ps1"
}

$tempRoot = Join-Path $env:TEMP ("mo2-live-ipc-runtime-" + [guid]::NewGuid().ToString("N"))
$runtimeRoot = Join-Path $tempRoot "runtime"
$harnessScriptPath = Join-Path $tempRoot "named-pipe-harness.py"
$pipeName = "mo2-control-plane-runtime-" + [guid]::NewGuid().ToString("N")
$harnessJob = $null
$originalFakeFixturePath = $env:MO2_CONTROL_PLANE_FAKE_IPC_RESPONSE_PATH

try {
    $null = New-Item -ItemType Directory -Path $runtimeRoot -Force
    Remove-Item Env:MO2_CONTROL_PLANE_FAKE_IPC_RESPONSE_PATH -ErrorAction SilentlyContinue

    $pythonScript = @'
import importlib.util
import json
import pathlib
import sys
import time
import types

module_path = pathlib.Path(sys.argv[1])
runtime_root = pathlib.Path(sys.argv[2])
pipe_name = sys.argv[3]

mobase = types.ModuleType("mobase")

class IPluginTool:
    pass

class VersionInfo:
    def __init__(self, *parts):
        self.parts = parts

mobase.IPluginTool = IPluginTool
mobase.VersionInfo = VersionInfo
sys.modules["mobase"] = mobase

spec = importlib.util.spec_from_file_location("mo2_agent_control", str(module_path))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

module.RUNTIME_PIPE_NAME_OVERRIDE = pipe_name
published_root = module.publish_runtime_bootstrap(runtime_root)
transport = module.start_transport(published_root)

print(json.dumps({
    "runtimeRoot": str(published_root),
    "transport": transport.get("transport"),
    "endpoint": transport.get("endpoint"),
    "started": bool(transport.get("started")),
}))
sys.stdout.flush()

while True:
    time.sleep(0.25)
'@

    Set-Content -Path $harnessScriptPath -Value $pythonScript -Encoding UTF8

    $harnessJob = Start-Job -ArgumentList $harnessScriptPath, $bridgeSourcePath, $runtimeRoot, $pipeName -ScriptBlock {
        param($scriptPath, $bridgePath, $runtimePath, $runtimePipeName)
        & python -u $scriptPath $bridgePath $runtimePath $runtimePipeName 2>&1
    }

    $summary = Wait-ForHarnessSummary -Job $harnessJob

    if ($summary.transport -ne "named-pipe") {
        throw "Python live bridge harness should report named-pipe transport"
    }

    if ($summary.endpoint -ne $pipeName) {
        throw "Python live bridge harness should expose the concrete named-pipe endpoint"
    }

    if (-not $summary.started) {
        throw "Python live bridge harness should report a started transport"
    }

    $malformedResponseLine = Send-MalformedNamedPipeFrame -PipeName $pipeName
    if ([string]::IsNullOrWhiteSpace($malformedResponseLine)) {
        throw "Malformed named-pipe input should return a structured error response"
    }

    $malformedResponse = $malformedResponseLine | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    if ($malformedResponse.ok -ne $false) {
        throw "Malformed named-pipe input should return ok=false"
    }

    if ($malformedResponse.error.code -ne "invalid_request") {
        throw "Malformed named-pipe input should return invalid_request"
    }

    $endpoint = [ordered]@{
        transport = "named-pipe"
        endpoint = $pipeName
    }

    $request = New-Mo2ControlPlaneRequest -SessionId $null -Command "system.ping" -Payload @{}
    $response = Invoke-Mo2ControlPlaneNamedPipeRequest -Request $request -Endpoint $endpoint
    if (-not $response.ok) {
        throw "Named-pipe IPC client should return ok=true for system.ping against the local harness"
    }

    if ($response.result.status -ne "ok") {
        throw "Named-pipe IPC client should surface status 'ok' from the local harness"
    }

    $cliResponse = Invoke-Cli -Arguments @("system", "ping", "--live-root", $runtimeRoot)
    if ($cliResponse.ExitCode -ne 0) {
        throw "system ping with --live-root should succeed through the local named-pipe harness: $($cliResponse.Output)"
    }

    $cliJson = $cliResponse.Output | ConvertFrom-Json -ErrorAction Stop
    if (-not $cliJson.ok) {
        throw "system ping with --live-root should return ok=true through the local named-pipe harness"
    }

    if ($cliJson.result.status -ne "ok") {
        throw "system ping with --live-root should surface status 'ok' from the local named-pipe harness"
    }

    Write-Host "MO2 live IPC runtime checks passed."
}
finally {
    $env:MO2_CONTROL_PLANE_FAKE_IPC_RESPONSE_PATH = $originalFakeFixturePath

    if ($null -ne $harnessJob) {
        Stop-Job -Job $harnessJob -ErrorAction SilentlyContinue
        Remove-Job -Job $harnessJob -Force -ErrorAction SilentlyContinue
    }

    if (Test-Path $tempRoot) {
        Remove-Item -Path $tempRoot -Recurse -Force
    }
}

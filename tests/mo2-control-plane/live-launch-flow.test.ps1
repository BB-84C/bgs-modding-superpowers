$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$bridgeSourcePath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_agent_control.py"

. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/common.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/protocol.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/session.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/launch.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/ipc-client.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/live-bootstrap.ps1")
. (Join-Path $repoRoot "tools/mo2-control-plane/broker/lib/client.ps1")

function Wait-ForHarnessSummary {
    param(
        [System.Management.Automation.Job]$Job,
        [int]$TimeoutSeconds = 10
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $nonJsonOutput = @()
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

function New-LiveLaunchRequest {
    param(
        [string]$SessionId,
        [string]$Command,
        [string]$TargetPath,
        [string[]]$Arguments = @()
    )

    return New-Mo2ControlPlaneRequest -SessionId $SessionId -Command $Command -Payload ([ordered]@{
        transport = [ordered]@{
            target_path = $TargetPath
            args = $Arguments
            cwd = (Split-Path -Path $TargetPath -Parent)
            env = [ordered]@{}
        }
    })
}

function Start-LiveClientRequestJob {
    param(
        [string]$RepoRoot,
        [string]$LiveRoot,
        [hashtable]$Request
    )

    $requestJson = $Request | ConvertTo-Json -Compress -Depth 10
    return Start-Job -ArgumentList $RepoRoot, $LiveRoot, $requestJson -ScriptBlock {
        param($jobRepoRoot, $jobLiveRoot, $jobRequestJson)

        . (Join-Path $jobRepoRoot "tools/mo2-control-plane/broker/lib/common.ps1")
        . (Join-Path $jobRepoRoot "tools/mo2-control-plane/broker/lib/protocol.ps1")
        . (Join-Path $jobRepoRoot "tools/mo2-control-plane/broker/lib/session.ps1")
        . (Join-Path $jobRepoRoot "tools/mo2-control-plane/broker/lib/launch.ps1")
        . (Join-Path $jobRepoRoot "tools/mo2-control-plane/broker/lib/ipc-client.ps1")
        . (Join-Path $jobRepoRoot "tools/mo2-control-plane/broker/lib/live-bootstrap.ps1")
        . (Join-Path $jobRepoRoot "tools/mo2-control-plane/broker/lib/client.ps1")

        $request = $jobRequestJson | ConvertFrom-Json -AsHashtable -ErrorAction Stop
        $response = Invoke-Mo2ControlPlaneClientRequest -LiveRoot $jobLiveRoot -Request $request
        $response | ConvertTo-Json -Compress -Depth 10
    }
}

function Receive-LiveClientRequestJob {
    param(
        [System.Management.Automation.Job]$Job
    )

    $output = @(Receive-Job -Job $Job -Wait -ErrorAction Stop)
    if ($output.Count -ne 1) {
        throw "Expected exactly one JSON response from background client job"
    }

    return ($output[0].ToString() | ConvertFrom-Json -AsHashtable -ErrorAction Stop)
}

if (-not (Test-Path $bridgeSourcePath -PathType Leaf)) {
    throw "Missing live bridge source: tools/mo2-control-plane/live-bridge/mo2_agent_control.py"
}

$tempRoot = Join-Path $env:TEMP ("mo2-live-launch-flow-" + [guid]::NewGuid().ToString("N"))
$runtimeRoot = Join-Path $tempRoot "runtime"
$harnessScriptPath = Join-Path $tempRoot "launch-harness.py"
$pipeName = "mo2-control-plane-launch-" + [guid]::NewGuid().ToString("N")
$harnessJob = $null

try {
    $organizerFailureHarness = @'
import importlib.util
import json
import pathlib
import sys
import types

module_path = pathlib.Path(sys.argv[1])

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

subprocess_calls = []

class FakeProcess:
    pid = 9001

    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0

class ExplodingOrganizer:
    def startApplication(self, target_path, args, cwd, profile=""):
        raise RuntimeError("organizer launch exploded")

def fake_start_subprocess_launch(payload):
    subprocess_calls.append(dict(payload))
    return FakeProcess()

module.start_subprocess_launch = fake_start_subprocess_launch

request = {
    "protocol_version": "1",
    "request_id": "req-organizer-failure",
    "session_id": "sess-organizer-failure",
    "method": "launch.start",
    "payload": {
        "transport": {
            "target_path": "C:/ModOrganizer/fake.exe",
            "args": ["--through-organizer"],
            "cwd": "C:/ModOrganizer",
            "env": {},
        }
    },
}

response = module.dispatch_transport_request(
    request,
    module.build_command_handlers(
        organizer=ExplodingOrganizer(),
        main_thread_pump=module.MainThreadCallPump(),
    ),
)

print(json.dumps({
    "response": response,
    "subprocessCalls": subprocess_calls,
}))
'@

    $organizerFailureOutput = & python -c $organizerFailureHarness $bridgeSourcePath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Organizer runtime failure harness should execute cleanly: $($organizerFailureOutput -join "`n")"
    }

    $organizerFailureSummary = (($organizerFailureOutput | ForEach-Object { $_.ToString() }) -join "`n") | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    if ($organizerFailureSummary.response.ok) {
        throw "Organizer-backed launch should return an explicit error when organizer.startApplication fails at runtime"
    }

    if ($organizerFailureSummary.subprocessCalls.Count -ne 0) {
        throw "Organizer-backed launch should not silently fall back to raw subprocess launch after organizer.startApplication runs and fails"
    }

    if ($organizerFailureSummary.response.error.message -notmatch "organizer launch exploded") {
        throw "Organizer-backed launch runtime failures should surface the organizer error instead of hiding it behind fallback"
    }

    $registryCleanupHarness = @'
import importlib.util
import json
import pathlib
import sys
import types

module_path = pathlib.Path(sys.argv[1])

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

class FakeProcess:
    _next_pid = 6100

    def __init__(self, wait_exit_code=0):
        self.pid = FakeProcess._next_pid
        FakeProcess._next_pid += 1
        self._wait_exit_code = wait_exit_code
        self._poll_result = None
        self.terminated = False

    def poll(self):
        return self._poll_result

    def wait(self, timeout=None):
        if self.terminated:
            self._poll_result = 1
        else:
            self._poll_result = self._wait_exit_code
        return self._poll_result

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.terminated = True

created_processes = []

def fake_start_subprocess_launch(payload):
    process = FakeProcess(wait_exit_code=0)
    created_processes.append(process)
    return process

module.start_subprocess_launch = fake_start_subprocess_launch
launch_registry = module.create_launch_registry()

completed_request = {
    "session_id": "sess-registry-completed",
    "payload": {
        "transport": {
            "target_path": "C:/terminal-completed.cmd",
            "args": [],
            "cwd": "C:/",
            "env": {},
        }
    },
}
completed_start = module.handle_launch_start(completed_request, launch_registry)
completed_result = module.handle_launch_wait(
    {
        "payload": {"launch_id": completed_start["launch_id"]},
    },
    launch_registry,
)
completed_entry = launch_registry[module.LAUNCH_REGISTRY_ENTRIES_FIELD][completed_start["launch_id"]]

stopped_request = {
    "session_id": "sess-registry-stopped",
    "payload": {
        "transport": {
            "target_path": "C:/terminal-stopped.cmd",
            "args": [],
            "cwd": "C:/",
            "env": {},
        }
    },
}
stopped_start = module.handle_launch_start(stopped_request, launch_registry)
stopped_result = module.handle_launch_stop(
    {
        "payload": {"launch_id": stopped_start["launch_id"]},
    },
    launch_registry,
)
stopped_entry = launch_registry[module.LAUNCH_REGISTRY_ENTRIES_FIELD][stopped_start["launch_id"]]

print(json.dumps({
    "completed": {
        "result": completed_result,
        "entry": {
            "status": completed_entry["status"],
            "exit_code": completed_entry["exit_code"],
            "process_handle": completed_entry["process_handle"],
        },
    },
    "stopped": {
        "result": stopped_result,
        "entry": {
            "status": stopped_entry["status"],
            "exit_code": stopped_entry["exit_code"],
            "process_handle": stopped_entry["process_handle"],
        },
    },
}))
'@

    $registryCleanupOutput = & python -c $registryCleanupHarness $bridgeSourcePath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Launch registry cleanup harness should execute cleanly: $($registryCleanupOutput -join "`n")"
    }

    $registryCleanupSummary = (($registryCleanupOutput | ForEach-Object { $_.ToString() }) -join "`n") | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    if ($registryCleanupSummary.completed.result.status -ne "completed") {
        throw "Completed terminal launches should report completed state in the cleanup harness"
    }

    if ($registryCleanupSummary.completed.entry.process_handle -ne $null) {
        throw "Completed terminal launches should clear process_handle from the in-memory registry"
    }

    if ($registryCleanupSummary.stopped.result.status -ne "stopped") {
        throw "Stopped terminal launches should report stopped state in the cleanup harness"
    }

    if ($registryCleanupSummary.stopped.entry.process_handle -ne $null) {
        throw "Stopped terminal launches should clear process_handle from the in-memory registry"
    }

    $retentionHarness = @'
import importlib.util
import json
import pathlib
import sys
import types

module_path = pathlib.Path(sys.argv[1])

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

class FakeProcess:
    _next_pid = 7100

    def __init__(self, wait_exit_code=0):
        self.pid = FakeProcess._next_pid
        FakeProcess._next_pid += 1
        self._wait_exit_code = wait_exit_code
        self._poll_result = None

    def poll(self):
        return self._poll_result

    def wait(self, timeout=None):
        self._poll_result = self._wait_exit_code
        return self._poll_result

def fake_start_subprocess_launch(payload):
    return FakeProcess(wait_exit_code=0)

def get_closure_var(function, name):
    if function.__closure__ is None:
        raise RuntimeError(f"{function.__name__} does not expose closure variables")

    closure = dict(zip(function.__code__.co_freevars, [cell.cell_contents for cell in function.__closure__]))
    if name not in closure:
        raise RuntimeError(f"Missing closure variable: {name}")

    return closure[name]

module.start_subprocess_launch = fake_start_subprocess_launch
handlers = module.build_command_handlers()
launch_start_handler = handlers[module.LAUNCH_START_METHOD]
handle_launch_request = get_closure_var(launch_start_handler, "handle_launch_request")
launch_registry = get_closure_var(handle_launch_request, "launch_registry")
launch_entry_locks = get_closure_var(handle_launch_request, "launch_entry_locks")

retention_limit = int(module.TERMINAL_LAUNCH_RETENTION_LIMIT)
launch_ids = []
for index in range(retention_limit + 2):
    start_response = module.dispatch_transport_request(
        {
            "protocol_version": "1",
            "request_id": f"req-retention-{index}",
            "session_id": f"sess-retention-{index}",
            "method": "launch.start",
            "payload": {
                "transport": {
                    "target_path": f"C:/terminal-retention-{index}.cmd",
                    "args": [],
                    "cwd": "C:/",
                    "env": {},
                }
            },
        },
        handlers,
    )
    launch_id = start_response["result"]["launch_id"]
    launch_ids.append(launch_id)
    module.dispatch_transport_request(
        {
            "protocol_version": "1",
            "request_id": f"req-retention-wait-{index}",
            "session_id": f"sess-retention-{index}",
            "method": "launch.wait",
            "payload": {"launch_id": launch_id},
        },
        handlers,
    )

launch_entries = launch_registry[module.LAUNCH_REGISTRY_ENTRIES_FIELD]
retained_ids = list(launch_entries.keys())

print(json.dumps({
    "retentionLimit": retention_limit,
    "createdLaunchIds": launch_ids,
    "retainedLaunchIds": retained_ids,
    "retainedLockIds": list(launch_entry_locks.keys()),
}))
'@

    $retentionOutput = & python -c $retentionHarness $bridgeSourcePath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Launch retention harness should execute cleanly: $($retentionOutput -join "`n")"
    }

    $retentionSummary = (($retentionOutput | ForEach-Object { $_.ToString() }) -join "`n") | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    $retentionLimit = [int]$retentionSummary.retentionLimit
    $createdLaunchIds = @($retentionSummary.createdLaunchIds)
    $retainedLaunchIds = @($retentionSummary.retainedLaunchIds)
    $retainedLockIds = @($retentionSummary.retainedLockIds)

    if ($retainedLaunchIds.Count -ne $retentionLimit) {
        throw "Completed/stopped terminal launches should retain only $retentionLimit entries, got $($retainedLaunchIds.Count)"
    }

    if ($retainedLockIds.Count -ne $retentionLimit) {
        throw "Completed/stopped terminal launches should retain only $retentionLimit coordination locks, got $($retainedLockIds.Count)"
    }

    if ($retainedLaunchIds -contains $createdLaunchIds[0] -or $retainedLaunchIds -contains $createdLaunchIds[1]) {
        throw "Oldest completed terminal launches should be pruned once retention is exceeded"
    }

    $expectedRetainedLaunchIds = @($createdLaunchIds | Select-Object -Last $retentionLimit)
    if (($retainedLaunchIds -join "|") -ne ($expectedRetainedLaunchIds -join "|")) {
        throw "Recent completed terminal launches should remain after pruning the oldest entries"
    }

    if (($retainedLockIds -join "|") -ne ($expectedRetainedLaunchIds -join "|")) {
        throw "Per-launch coordination locks should be pruned alongside the oldest terminal launches"
    }

    $threadSafeHarnessScript = @'
import importlib.util
import json
import pathlib
import sys
import threading
import time
import types

module_path = pathlib.Path(sys.argv[1])

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

main_thread_id = threading.get_ident()
organizer_calls = []

class FakeOrganizer:
    def startApplication(self, target_path, args, cwd, profile=""):
        organizer_calls.append({
            "thread_id": threading.get_ident(),
            "target_path": target_path,
            "args": list(args),
            "cwd": cwd,
            "profile": profile,
        })
        if threading.get_ident() != main_thread_id:
            raise RuntimeError("startApplication must run on the main thread")
        return 4242

pump = module.MainThreadCallPump()
handlers = module.build_command_handlers(
    organizer=FakeOrganizer(),
    main_thread_pump=pump,
)

request = {
    "protocol_version": "1",
    "request_id": "req-threadsafe-launch",
    "session_id": "sess-threadsafe-launch",
    "method": "launch.start",
    "payload": {
        "transport": {
            "target_path": "C:/ModOrganizer/fake.exe",
            "args": ["--through-organizer"],
            "cwd": "C:/ModOrganizer",
            "env": {},
        }
    },
}

response_holder = {}

def dispatch_request():
    response_holder["response"] = module.dispatch_transport_request(request, handlers)

worker = threading.Thread(target=dispatch_request, name="named-pipe-worker")
worker.start()

deadline = time.time() + 2.0
while pump.pending_count() == 0 and time.time() < deadline:
    time.sleep(0.01)

if pump.pending_count() != 1:
    raise RuntimeError(f"expected one queued organizer launch, got {pump.pending_count()}")

if organizer_calls:
    raise RuntimeError("organizer launch should not execute before the main-thread pump runs")

if not worker.is_alive():
    raise RuntimeError("background dispatch should wait for the queued launch to be pumped")

if not pump.pump_once(timeout_seconds=0.1):
    raise RuntimeError("main-thread pump should execute the queued organizer launch")

worker.join(timeout=2.0)
if worker.is_alive():
    raise RuntimeError("background dispatch should finish after the main-thread pump runs")

response = response_holder.get("response")
if response is None:
    raise RuntimeError("thread-safe launch harness should capture a transport response")

print(json.dumps({
    "mainThreadId": main_thread_id,
    "queuedBeforePump": True,
    "organizerCalls": organizer_calls,
    "response": response,
}))
'@

    $threadSafeOutput = & python -c $threadSafeHarnessScript $bridgeSourcePath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Organizer-backed launch marshalling harness should pass: $($threadSafeOutput -join "`n")"
    }

    $threadSafeSummary = (($threadSafeOutput | ForEach-Object { $_.ToString() }) -join "`n") | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    if (-not $threadSafeSummary.queuedBeforePump) {
        throw "Organizer-backed launch marshalling harness should prove the request queued before pumping"
    }

    if ($threadSafeSummary.organizerCalls.Count -ne 1) {
        throw "Organizer-backed launch marshalling harness should execute exactly one organizer launch"
    }

    if ($threadSafeSummary.organizerCalls[0].thread_id -ne $threadSafeSummary.mainThreadId) {
        throw "Organizer-backed launch marshalling harness should run organizer.startApplication on the Python main thread"
    }

    if (-not $threadSafeSummary.response.ok) {
        throw "Organizer-backed launch marshalling harness should return ok=true after the main-thread pump runs"
    }

    if ($threadSafeSummary.response.result.pid -ne 4242) {
        throw "Organizer-backed launch marshalling harness should return the organizer launch pid"
    }

    $null = New-Item -ItemType Directory -Path $runtimeRoot -Force

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
        throw "Python live launch harness should report named-pipe transport"
    }

    $sessionId = "sess-live-launch-" + [guid]::NewGuid().ToString("N")
    $cmdPath = if (-not [string]::IsNullOrWhiteSpace($env:ComSpec)) { $env:ComSpec } else { Join-Path $env:WINDIR "System32\cmd.exe" }

    $waitStart = Invoke-Mo2ControlPlaneClientRequest -Request (New-LiveLaunchRequest -SessionId $sessionId -Command "launch.start" -TargetPath $cmdPath -Arguments @("/c", "exit 0")) -LiveRoot $runtimeRoot
    if (-not $waitStart.ok) {
        throw "launch.start with --live-root should succeed through the Python transport: $($waitStart.error.message)"
    }

    if ([string]::IsNullOrWhiteSpace([string]$waitStart.result.launch_id)) {
        throw "launch.start through the Python transport should return launch_id"
    }

    if ($waitStart.result.pid -le 0) {
        throw "launch.start through the Python transport should return a real pid"
    }

    if ([string]::IsNullOrWhiteSpace([string]$waitStart.result.status)) {
        throw "launch.start through the Python transport should return status"
    }

    if ([string]::IsNullOrWhiteSpace([string]$waitStart.result.started_at)) {
        throw "launch.start through the Python transport should surface started_at from the live transport"
    }

    $blockedStart = Invoke-Mo2ControlPlaneClientRequest -Request (New-LiveLaunchRequest -SessionId $sessionId -Command "launch.start" -TargetPath $cmdPath -Arguments @("/c", "ping -n 6 127.0.0.1 >nul")) -LiveRoot $runtimeRoot
    if (-not $blockedStart.ok) {
        throw "long-lived launch.start for transport concurrency should succeed through the Python transport"
    }

    $waitJob = Start-LiveClientRequestJob -RepoRoot $repoRoot -LiveRoot $runtimeRoot -Request (New-Mo2ControlPlaneRequest -SessionId $sessionId -Command "launch.wait" -Payload @{ launch_id = $blockedStart.result.launch_id })
    $stopJob = $null
    try {
        Start-Sleep -Milliseconds 250
        $stopJob = Start-LiveClientRequestJob -RepoRoot $repoRoot -LiveRoot $runtimeRoot -Request (New-Mo2ControlPlaneRequest -SessionId $sessionId -Command "launch.stop" -Payload @{ launch_id = $blockedStart.result.launch_id })
        if (-not (Wait-Job -Job $stopJob -Timeout 2)) {
            throw "A blocked launch.wait should not prevent launch.stop for the same launch_id from completing"
        }

        $concurrentStop = Receive-LiveClientRequestJob -Job $stopJob
        if (-not $concurrentStop.ok) {
            throw "Concurrent launch.stop should still succeed while another client is blocked in launch.wait"
        }

        if ($concurrentStop.result.status -ne "stopped") {
            throw "Concurrent launch.stop should report stopped while launch.wait is blocked on the same launch"
        }

        $concurrentWait = Receive-LiveClientRequestJob -Job $waitJob
        if (-not $concurrentWait.ok) {
            throw "launch.wait should still complete successfully after concurrent launch.stop passes"
        }

        if ($concurrentWait.result.status -ne "stopped") {
            throw "launch.wait should preserve stopped state when launch.stop wins during the wait"
        }
    }
    finally {
        if ($null -ne $stopJob) {
            Remove-Job -Job $stopJob -Force -ErrorAction SilentlyContinue
        }

        if ($null -ne $waitJob) {
            Remove-Job -Job $waitJob -Force -ErrorAction SilentlyContinue
        }
    }

    $waitStatus = Invoke-Mo2ControlPlaneClientRequest -LiveRoot $runtimeRoot -Request (New-Mo2ControlPlaneRequest -SessionId $sessionId -Command "launch.status" -Payload @{ launch_id = $waitStart.result.launch_id })
    if (-not $waitStatus.ok) {
        throw "launch.status with --live-root should succeed through the Python transport"
    }

    if ($waitStatus.result.launch_id -ne $waitStart.result.launch_id) {
        throw "launch.status through the Python transport should keep launch_id stable"
    }

    $waitResult = Invoke-Mo2ControlPlaneClientRequest -LiveRoot $runtimeRoot -Request (New-Mo2ControlPlaneRequest -SessionId $sessionId -Command "launch.wait" -Payload @{ launch_id = $waitStart.result.launch_id })
    if (-not $waitResult.ok) {
        throw "launch.wait with --live-root should succeed through the Python transport"
    }

    if ($waitResult.result.status -ne "completed") {
        throw "launch.wait through the Python transport should report completed for cmd.exe /c exit 0"
    }

    if ($waitResult.result.exit_code -ne 0) {
        throw "launch.wait through the Python transport should return the real exit_code for cmd.exe /c exit 0"
    }

    $stopStart = Invoke-Mo2ControlPlaneClientRequest -Request (New-LiveLaunchRequest -SessionId $sessionId -Command "launch.start" -TargetPath $cmdPath -Arguments @("/c", "ping -n 30 127.0.0.1 >nul")) -LiveRoot $runtimeRoot
    if (-not $stopStart.ok) {
        throw "long-lived launch.start with --live-root should succeed through the Python transport"
    }

    Start-Sleep -Milliseconds 250

    $stopStatus = Invoke-Mo2ControlPlaneClientRequest -LiveRoot $runtimeRoot -Request (New-Mo2ControlPlaneRequest -SessionId $sessionId -Command "launch.status" -Payload @{ launch_id = $stopStart.result.launch_id })
    if (-not $stopStatus.ok) {
        throw "launch.status for a long-lived target should succeed through the Python transport"
    }

    if ($stopStatus.result.status -ne "running") {
        throw "launch.status through the Python transport should report a tracked long-lived target as running before stop"
    }

    $stopResult = Invoke-Mo2ControlPlaneClientRequest -LiveRoot $runtimeRoot -Request (New-Mo2ControlPlaneRequest -SessionId $sessionId -Command "launch.stop" -Payload @{ launch_id = $stopStart.result.launch_id })
    if (-not $stopResult.ok) {
        throw "launch.stop with --live-root should succeed through the Python transport"
    }

    if ($stopResult.result.status -ne "stopped") {
        throw "launch.stop through the Python transport should report stopped for a long-lived harmless target"
    }

    Write-Host "MO2 live launch flow checks passed."
}
finally {
    if ($null -ne $harnessJob) {
        Stop-Job -Job $harnessJob -ErrorAction SilentlyContinue
        Remove-Job -Job $harnessJob -Force -ErrorAction SilentlyContinue
    }

    if (Test-Path $tempRoot) {
        Remove-Item -Path $tempRoot -Recurse -Force
    }
}

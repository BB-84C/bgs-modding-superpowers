# MO2 GUI Blocker Auto-Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the two known MO2 GUI blockers by disabling `lock_gui` in the sandbox configuration and adding a whitelisted in-process dialog watcher inside the `Mo2AgentControl` live bridge.

**Architecture:** Keep the fix inside MO2. Normalize the checked-in and deployed MO2 settings so the GUI does not enter the lock blocker path, then extend `mo2_agent_control.py` with Qt dialog matching, exact-button auto-handling, and runtime blocker-event logging for the two approved dialogs only. Verify the behavior with narrow Python-harness tests plus a live sandbox regression for raw `ModOrganizer.exe ... run ...` launches.

**Tech Stack:** PowerShell, Python, MO2 Python plugin (`mobase`), PyQt5/PyQt6, named-pipe control-plane runtime, real `.artifacts/mo2` sandbox tests

**Operator note:** Do not create git commits during execution unless the user explicitly asks for them.

---

## File Structure

- `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`
  - add blocker-event runtime artifacts
  - add strict whitelist matcher for the two approved dialogs
  - add Qt widget scanning and exact-button handling
  - add dialog-fingerprint dedupe so repeated ignored/failed dialogs are not logged every timer tick and the same dialog is handled at most once per appearance
  - install a second main-thread timer for dialog scanning
- `tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1`
  - normalize MO2 sandbox settings during bridge deployment
  - ensure `lock_gui=false` is enforced on deploy
- `.artifacts/mo2/ModOrganizer.ini`
  - change the checked-in sandbox default from `lock_gui=true` to `lock_gui=false`
- `tests/mo2-control-plane/live-dialog-blocker-runtime.test.ps1`
  - unit-style PowerShell/Python harness for blocker matching, logging, fake dialog handling, and negative cases
- `tests/mo2-control-plane/deploy-live-bridge.test.ps1`
  - deployment regression proving bridge deployment rewrites `lock_gui=false` in a temporary MO2 root
- `tests/mo2-control-plane/live-cli-run-real.test.ps1`
  - real sandbox regression proving a raw `ModOrganizer.exe -p Default run -e OpenCodeVfsLauncher -a ...` launch returns while a long-running child stays alive and that blocker handling is recorded
- `tests/mo2-control-plane/live-bootstrap-real.test.ps1`
  - strengthen existing live bootstrap verification with an explicit `lock_gui=false` assertion
- `tools/mo2-control-plane/live-bridge/README.md`
  - document the blocker watcher and blocker-events runtime log
- `tools/mo2-control-plane/live-integration.md`
  - document that raw MO2 CLI launches now rely on internal blocker auto-handling instead of human clicks

## Task 1: Add blocker matching and runtime-log helpers

**Files:**
- Create: `tests/mo2-control-plane/live-dialog-blocker-runtime.test.ps1`
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`

- [ ] **Step 1: Write the failing runtime helper test**

Add `tests/mo2-control-plane/live-dialog-blocker-runtime.test.ps1` with a Python harness that imports `mo2_agent_control.py`, stubs `mobase`, and expects new blocker helper symbols to exist and behave deterministically.

```powershell
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$bridgeSourcePath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_agent_control.py"

$harness = @'
import importlib.util
import json
import pathlib
import sys
import tempfile
import types

module_path = pathlib.Path(sys.argv[1])
runtime_root = pathlib.Path(tempfile.mkdtemp(prefix="mo2-blocker-runtime-"))

mobase = types.ModuleType("mobase")
class IPluginTool: pass
class VersionInfo:
    def __init__(self, *parts):
        self.parts = parts
mobase.IPluginTool = IPluginTool
mobase.VersionInfo = VersionInfo
sys.modules["mobase"] = mobase

spec = importlib.util.spec_from_file_location("mo2_agent_control", str(module_path))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

unlock_match = module.match_blocker_dialog(
    "ModOrganizer",
    "Mod Organizer is locked while the application is running.\nxEdit.exe (68944)",
    ["Unlock"],
)
exit_match = module.match_blocker_dialog(
    "ModOrganizer",
    "Mod Organizer is waiting on an application to close before exiting.\nxEdit.exe (44992)",
    ["Exit Now", "Cancel"],
)
ignored_match = module.match_blocker_dialog(
    "ModOrganizer",
    "Unexpected confirmation dialog",
    ["OK"],
)

module.append_blocker_event(
    runtime_root,
    {
        "type": "unlock",
        "result": "handled",
        "source": "global-dialog-watcher",
        "dialog_title": "ModOrganizer",
    },
)

events_path = runtime_root / module.BLOCKER_EVENTS_FILE
print(json.dumps({
    "unlockMatch": unlock_match,
    "exitMatch": exit_match,
    "ignoredMatch": ignored_match,
    "eventsPathExists": events_path.exists(),
    "eventLine": events_path.read_text(encoding="utf-8").strip() if events_path.exists() else "",
}))
'@

$output = & python -c $harness $bridgeSourcePath 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Runtime helper harness failed: $($output -join "`n")"
}

$summary = (($output | ForEach-Object { $_.ToString() }) -join "`n") | ConvertFrom-Json -ErrorAction Stop
if ($summary.unlockMatch.type -ne 'unlock') { throw 'Expected unlock blocker match.' }
if ($summary.exitMatch.type -ne 'exit-now') { throw 'Expected exit-now blocker match.' }
if ($null -ne $summary.ignoredMatch) { throw 'Unexpected dialogs should not match.' }
if (-not $summary.eventsPathExists) { throw 'Expected blocker event log to be created.' }
if ($summary.eventLine -notmatch '"type": "unlock"') { throw 'Expected blocker event log to contain unlock event JSON.' }

Write-Host "MO2 live dialog blocker runtime helper checks passed."
```

- [ ] **Step 2: Run the new test and verify it fails first**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-control-plane/live-dialog-blocker-runtime.test.ps1
```

Expected: FAIL because `match_blocker_dialog`, `append_blocker_event`, and `BLOCKER_EVENTS_FILE` do not exist yet.

- [ ] **Step 3: Implement the minimal helper surface in `mo2_agent_control.py`**

Add the blocker artifact constant and pure helper functions near the existing runtime/bootstrap constants so they can be tested without Qt widgets.

```python
BLOCKER_EVENTS_FILE = "blocker-events.jsonl"

KNOWN_BLOCKER_DIALOGS = (
    {
        "type": "unlock",
        "titleContains": ("ModOrganizer", "Mod Organizer"),
        "textContains": ("Mod Organizer is locked while the application is running",),
        "buttons": ("Unlock",),
        "actionButton": "Unlock",
    },
    {
        "type": "exit-now",
        "titleContains": ("ModOrganizer", "Mod Organizer"),
        "textContains": ("Mod Organizer is waiting on an application to close before exiting",),
        "buttons": ("Exit Now", "Cancel"),
        "actionButton": "Exit Now",
    },
)


def get_blocker_events_path(runtime_root: str | Path | None = None) -> Path:
    root = Path(runtime_root) if runtime_root is not None else get_runtime_root()
    root.mkdir(parents=True, exist_ok=True)
    return root / BLOCKER_EVENTS_FILE


def match_blocker_dialog(title: str, text: str, buttons: list[str]) -> dict[str, object] | None:
    normalized_title = title or ""
    normalized_text = text or ""
    normalized_buttons = tuple(str(button) for button in buttons)
    for spec in KNOWN_BLOCKER_DIALOGS:
        if not any(fragment in normalized_title for fragment in spec["titleContains"]):
            continue
        if not all(fragment in normalized_text for fragment in spec["textContains"]):
            continue
        if not all(button in normalized_buttons for button in spec["buttons"]):
            continue
        return dict(spec)
    return None


def append_blocker_event(runtime_root: str | Path | None, event: dict[str, object]) -> None:
    events_path = get_blocker_events_path(runtime_root)
    payload = dict(event)
    payload.setdefault("ts", utc_now_timestamp())
    with events_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: Re-run the helper test and verify it passes**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-control-plane/live-dialog-blocker-runtime.test.ps1
```

Expected: PASS with `MO2 live dialog blocker runtime helper checks passed.`

## Task 2: Add the Qt dialog watcher and negative-case coverage

**Files:**
- Modify: `tests/mo2-control-plane/live-dialog-blocker-runtime.test.ps1`
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`

- [ ] **Step 1: Extend the runtime harness with fake dialog handling tests**

Append a second harness section that constructs fake dialog/button objects and verifies the watcher clicks only the whitelisted button, records a handled event, ignores unknown dialog candidates, and logs the same unchanged unknown dialog only once.

```powershell
$dialogHarness = @'
import importlib.util
import json
import pathlib
import sys
import tempfile
import types

module_path = pathlib.Path(sys.argv[1])
runtime_root = pathlib.Path(tempfile.mkdtemp(prefix="mo2-blocker-dialog-"))

mobase = types.ModuleType("mobase")
class IPluginTool: pass
class VersionInfo:
    def __init__(self, *parts):
        self.parts = parts
mobase.IPluginTool = IPluginTool
mobase.VersionInfo = VersionInfo
sys.modules["mobase"] = mobase

spec = importlib.util.spec_from_file_location("mo2_agent_control", str(module_path))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class FakeButton:
    def __init__(self, text):
        self._text = text
        self.clicked = 0
    def text(self):
        return self._text
    def click(self):
        self.clicked += 1

class FakeDialog:
    def __init__(self, title, text, buttons):
        self._title = title
        self._text = text
        self._buttons = buttons
    def windowTitle(self):
        return self._title
    def text(self):
        return self._text
    def buttons(self):
        return self._buttons

unlock_button = FakeButton("Unlock")
unlock_dialog = FakeDialog(
    "ModOrganizer",
    "Mod Organizer is locked while the application is running.\nxEdit.exe (68944)",
    [unlock_button],
)
unknown_button = FakeButton("OK")
unknown_dialog = FakeDialog("ModOrganizer", "Unexpected confirmation dialog", [unknown_button])

unlock_handled = module.handle_known_blocker_dialog(unlock_dialog, runtime_root)
unknown_handled = module.handle_known_blocker_dialog(unknown_dialog, runtime_root)
unknown_handled_again = module.handle_known_blocker_dialog(unknown_dialog, runtime_root)
events_text = (runtime_root / module.BLOCKER_EVENTS_FILE).read_text(encoding="utf-8")

print(json.dumps({
    "unlockHandled": unlock_handled,
    "unlockClicks": unlock_button.clicked,
    "unknownHandled": unknown_handled,
    "unknownHandledAgain": unknown_handled_again,
    "unknownClicks": unknown_button.clicked,
    "eventsText": events_text,
}))
'@
```

Add assertions:

```powershell
$dialogOutput = & python -c $dialogHarness $bridgeSourcePath 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Dialog harness failed: $($dialogOutput -join "`n")"
}

$dialogSummary = (($dialogOutput | ForEach-Object { $_.ToString() }) -join "`n") | ConvertFrom-Json -ErrorAction Stop
if (-not $dialogSummary.unlockHandled) { throw 'Expected whitelist dialog to be handled.' }
if ($dialogSummary.unlockClicks -ne 1) { throw 'Expected Unlock button to be clicked once.' }
if ($dialogSummary.unknownHandled) { throw 'Unknown dialog must not be handled.' }
if ($dialogSummary.unknownHandledAgain) { throw 'Unknown dialog must stay unhandled on repeat scan.' }
if ($dialogSummary.unknownClicks -ne 0) { throw 'Unknown dialog button must not be clicked.' }
if ($dialogSummary.eventsText -notmatch '"result": "handled"') { throw 'Expected handled blocker event in runtime log.' }
if ($dialogSummary.eventsText -notmatch '"result": "ignored"') { throw 'Expected ignored blocker event for unknown dialog.' }
if (([regex]::Matches($dialogSummary.eventsText, '"result": "ignored"')).Count -ne 1) { throw 'Expected ignored blocker event to be logged only once per unchanged dialog.' }
```

- [ ] **Step 2: Run the extended runtime harness and verify it fails**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-control-plane/live-dialog-blocker-runtime.test.ps1
```

Expected: FAIL because `handle_known_blocker_dialog` does not exist yet.

- [ ] **Step 3: Implement dialog extraction, button lookup, watcher scan, and init wiring**

Extend `mo2_agent_control.py` with Qt widget imports and the watcher surface.

```python
def import_qt_widgets_module():
    for module_name in ("PyQt6.QtWidgets", "PyQt5.QtWidgets"):
        try:
            module = __import__(module_name, fromlist=["QApplication", "QDialog", "QMessageBox", "QAbstractButton"])
        except ImportError:
            continue
        if hasattr(module, "QApplication"):
            return module
    raise RuntimeError("Dialog blocker handling requires PyQt5/PyQt6 QtWidgets")


def extract_dialog_snapshot(dialog) -> dict[str, object]:
    title = dialog.windowTitle() if hasattr(dialog, "windowTitle") else ""
    text = dialog.text() if hasattr(dialog, "text") else ""
    buttons = []
    if hasattr(dialog, "buttons"):
        buttons = [button.text() for button in dialog.buttons()]
    return {"title": str(title), "text": str(text), "buttons": [str(button) for button in buttons]}


def find_button_by_text(dialog, expected_text: str):
    if not hasattr(dialog, "buttons"):
        return None
    for button in dialog.buttons():
        if str(button.text()) == expected_text:
            return button
    return None


def is_dialog_candidate(dialog) -> bool:
    return hasattr(dialog, "windowTitle") and hasattr(dialog, "text") and hasattr(dialog, "buttons")


def build_dialog_fingerprint(snapshot: dict[str, object]) -> str:
    return json.dumps({
        "title": snapshot["title"],
        "text": snapshot["text"],
        "buttons": snapshot["buttons"],
    }, ensure_ascii=False, sort_keys=True)


def handle_known_blocker_dialog(dialog, runtime_root: str | Path | None = None) -> bool:
    if not is_dialog_candidate(dialog):
        return False

    snapshot = extract_dialog_snapshot(dialog)
    fingerprint = build_dialog_fingerprint(snapshot)
    watcher_state = getattr(handle_known_blocker_dialog, "_seen_fingerprints", set())
    if fingerprint in watcher_state:
        return False

    spec = match_blocker_dialog(snapshot["title"], snapshot["text"], snapshot["buttons"])
    if spec is None:
        append_blocker_event(runtime_root, {
            "type": "ignored",
            "result": "ignored",
            "source": "global-dialog-watcher",
            "dialog_title": snapshot["title"],
            "buttons": snapshot["buttons"],
        })
        watcher_state.add(fingerprint)
        handle_known_blocker_dialog._seen_fingerprints = watcher_state
        return False

    button = find_button_by_text(dialog, spec["actionButton"])
    if button is None:
        append_blocker_event(runtime_root, {
            "type": spec["type"],
            "result": "failed",
            "source": "global-dialog-watcher",
            "dialog_title": snapshot["title"],
            "buttons": snapshot["buttons"],
        })
        watcher_state.add(fingerprint)
        handle_known_blocker_dialog._seen_fingerprints = watcher_state
        return False

    button.click()
    append_blocker_event(runtime_root, {
        "type": spec["type"],
        "result": "handled",
        "source": "global-dialog-watcher",
        "dialog_title": snapshot["title"],
        "buttons": snapshot["buttons"],
    })
    watcher_state.add(fingerprint)
    handle_known_blocker_dialog._seen_fingerprints = watcher_state
    return True


def scan_for_known_blocker_dialogs(runtime_root: str | Path | None = None) -> int:
    qt_widgets = import_qt_widgets_module()
    application = qt_widgets.QApplication.instance()
    if application is None:
        return 0
    handled = 0
    for widget in application.topLevelWidgets():
        if not is_dialog_candidate(widget):
            continue
        if handle_known_blocker_dialog(widget, runtime_root):
            handled += 1
    return handled


def install_blocker_watcher_timer(runtime_root: str | Path | None = None, interval_ms: int = 100):
    qt_core = import_qt_core_module()
    application = qt_core.QCoreApplication.instance()
    timer = qt_core.QTimer(application) if application is not None else qt_core.QTimer()
    timer.setInterval(interval_ms)
    timer.timeout.connect(lambda: scan_for_known_blocker_dialogs(runtime_root))
    timer.start()
    return timer
```

Update plugin init so the timer is installed when MO2 loads the plugin:

```python
class Mo2AgentControlPlugin(mobase.IPluginTool):
    def __init__(self) -> None:
        super().__init__()
        self._organizer = None
        self._main_thread_pump = None
        self._main_thread_timer = None
        self._blocker_watcher_timer = None
        self._transport = None

    def init(self, organizer) -> bool:
        self._organizer = organizer
        self._main_thread_pump = MainThreadCallPump()
        self._main_thread_timer = install_main_thread_pump_timer(self._main_thread_pump)
        runtime_root = publish_runtime_bootstrap()
        self._blocker_watcher_timer = install_blocker_watcher_timer(runtime_root)
        self._transport = start_transport(
            runtime_root,
            organizer=organizer,
            main_thread_pump=self._main_thread_pump,
        )
        return True
```

- [ ] **Step 4: Re-run the runtime harness and verify it passes**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-control-plane/live-dialog-blocker-runtime.test.ps1
```

Expected: PASS with runtime helper and fake-dialog coverage complete.

## Task 3: Normalize `lock_gui=false` in the sandbox and deployment flow

**Files:**
- Create: `tests/mo2-control-plane/deploy-live-bridge.test.ps1`
- Modify: `tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1`
- Modify: `.artifacts/mo2/ModOrganizer.ini`
- Modify: `tests/mo2-control-plane/live-bootstrap-real.test.ps1`

- [ ] **Step 1: Write the failing deploy regression test**

Create `tests/mo2-control-plane/deploy-live-bridge.test.ps1` with a temporary fake MO2 root that contains a minimal `ModOrganizer.ini` starting with `lock_gui=true`, then run the deploy script and assert the setting flips to `false`.

```powershell
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$deployScriptPath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1"
$tempRoot = Join-Path $env:TEMP ("mo2-deploy-" + [guid]::NewGuid().ToString("N"))
$sandboxRoot = Join-Path $tempRoot ".artifacts\mo2"
$pluginsRoot = Join-Path $sandboxRoot "plugins"
$iniPath = Join-Path $sandboxRoot "ModOrganizer.ini"

$null = New-Item -ItemType Directory -Path $pluginsRoot -Force
Set-Content -Path $iniPath -Value @"
[Settings]
lock_gui=true
center_dialogs=false
"@

& pwsh -NoProfile -File $deployScriptPath -Mo2Root $tempRoot
if ($LASTEXITCODE -ne 0) {
    throw 'Deploy live bridge should succeed against a temporary MO2 root.'
}

$iniContent = Get-Content -Path $iniPath -Raw
if ($iniContent -notmatch '(?m)^lock_gui=false\s*$') {
    throw 'Deploy live bridge should normalize lock_gui=false.'
}

Write-Host 'MO2 live bridge deploy checks passed.'
```

- [ ] **Step 2: Run the deploy test and verify it fails first**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-control-plane/deploy-live-bridge.test.ps1
```

Expected: FAIL because the deploy script currently copies the bridge but does not rewrite `ModOrganizer.ini`.

- [ ] **Step 3: Implement settings normalization and update the checked-in sandbox default**

Add a helper to `deploy-live-bridge.ps1` and invoke it after copying the bridge.

```powershell
function Set-Mo2IniBooleanValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$IniPath,
        [Parameter(Mandatory = $true)]
        [string]$Key,
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    if (-not (Test-Path $IniPath -PathType Leaf)) {
        return
    }

    $content = Get-Content -Path $IniPath -Raw
    if ($content -match "(?m)^$([regex]::Escape($Key))=") {
        $content = [regex]::Replace($content, "(?m)^$([regex]::Escape($Key))=.*$", "$Key=$Value")
    }
    else {
        $content = $content.TrimEnd() + [Environment]::NewLine + "$Key=$Value" + [Environment]::NewLine
    }

    Set-Content -Path $IniPath -Value $content
}

$modOrganizerIniPath = Join-Path $resolvedMo2Root ".artifacts/mo2/ModOrganizer.ini"
Set-Mo2IniBooleanValue -IniPath $modOrganizerIniPath -Key "lock_gui" -Value "false"
```

Update the tracked sandbox config too:

```ini
[Settings]
...
lock_gui=false
archive_parsing_experimental=false
```

Strengthen `tests/mo2-control-plane/live-bootstrap-real.test.ps1` with an explicit assertion:

```powershell
$modOrganizerIniPath = Join-Path $liveMo2Root "ModOrganizer.ini"
$modOrganizerIni = Get-Content -Path $modOrganizerIniPath -Raw
if ($modOrganizerIni -notmatch '(?m)^lock_gui=false\s*$') {
    throw 'The live MO2 sandbox must keep lock_gui=false to avoid the GUI lock blocker.'
}
```

- [ ] **Step 4: Re-run deploy coverage and verify it passes**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-control-plane/deploy-live-bridge.test.ps1
```

Expected: PASS with `MO2 live bridge deploy checks passed.`

## Task 4: Add the raw MO2 CLI real regression for the exit blocker

**Files:**
- Create: `tests/mo2-control-plane/live-cli-run-real.test.ps1`
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py` (only if the first real run exposes integration gaps)

- [ ] **Step 1: Write the failing live regression test**

Create `tests/mo2-control-plane/live-cli-run-real.test.ps1` that deploys the bridge into the real sandbox, restarts MO2, launches a long-running child through the existing `OpenCodeVfsLauncher` executable entry, and asserts that the MO2 CLI process returns while the child is still alive and that `blocker-events.jsonl` records an `exit-now` handling event.

```powershell
param(
    [switch]$AllowLiveSandbox,
    [switch]$RestartMo2,
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$liveMo2Root = 'D:\awesome-bgs-mod-master\.artifacts\mo2'
$mo2ExecutablePath = Join-Path $liveMo2Root 'ModOrganizer.exe'
$runtimeRoot = Join-Path $liveMo2Root 'plugins\Mo2AgentControl\bootstrap\runtime'
$blockerEventsPath = Join-Path $runtimeRoot 'blocker-events.jsonl'
$deployScriptPath = Join-Path $repoRoot 'tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1'

. (Join-Path $PSScriptRoot 'live-sandbox.ps1')

if (-not $AllowLiveSandbox) {
    throw 'This real harness touches D:\awesome-bgs-mod-master\.artifacts\mo2. Re-run with -AllowLiveSandbox to opt in.'
}

$sandboxHarnessMutex = Enter-SandboxHarnessLock -Path $mo2ExecutablePath -TimeoutSeconds $TimeoutSeconds
$tempRoot = Join-Path $env:TEMP ('mo2-cli-run-real-' + [guid]::NewGuid().ToString('N'))

try {
    & pwsh -NoProfile -File $deployScriptPath -Mo2Root $repoRoot
    if ($LASTEXITCODE -ne 0) { throw 'Deploying the live bridge should succeed.' }

    if ($RestartMo2) {
        Stop-SandboxMo2FromPath -Path $mo2ExecutablePath -TimeoutSeconds $TimeoutSeconds
        $null = Start-Process -FilePath $mo2ExecutablePath -PassThru
    }

    $null = New-Item -ItemType Directory -Path $tempRoot -Force
    $longScriptPath = Join-Path $tempRoot 'sleepy.cmd'
    $statePath = Join-Path $tempRoot 'state.json'
    Set-Content -Path $longScriptPath -Encoding ASCII -Value @"
@echo off
ping -n 30 127.0.0.1 >nul
exit /b 0
"@

    Remove-Item -Path $blockerEventsPath -Force -ErrorAction SilentlyContinue
    $arguments = '--target-path "' + $env:ComSpec + '" --target-arg /c --target-arg "' + $longScriptPath + '" --session-id cli-real --state-file "' + $statePath + '" --wait-mode spawned --transport-mode direct-child'
    $cli = Start-Process -FilePath $mo2ExecutablePath -ArgumentList @('-p', 'Default', 'run', '-e', 'OpenCodeVfsLauncher', '-a', $arguments) -PassThru

    if (-not $cli.WaitForExit($TimeoutSeconds * 1000)) {
        throw 'Raw ModOrganizer.exe run invocation should return instead of hanging behind the exit blocker.'
    }

    if (-not (Test-Path $blockerEventsPath -PathType Leaf)) {
        throw 'Expected blocker-events.jsonl after raw CLI run.'
    }

    $events = Get-Content -Path $blockerEventsPath
    if ($events -notmatch '"type": "exit-now"') {
        throw 'Expected exit-now blocker handling to be recorded for the raw CLI run.'
    }

    Write-Host 'MO2 live CLI run blocker regression checks passed.'
}
finally {
    if ($null -ne $sandboxHarnessMutex) {
        $sandboxHarnessMutex.ReleaseMutex()
        $sandboxHarnessMutex.Dispose()
    }
}
```

- [ ] **Step 2: Run the live regression and verify it fails first**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-control-plane/live-cli-run-real.test.ps1 -AllowLiveSandbox -RestartMo2
```

Expected: FAIL on current behavior because the raw MO2 CLI run hangs or exits without any blocker handling evidence.

- [ ] **Step 3: Fix any integration gaps exposed by the real run**

If the watcher logic from Task 2 needs integration adjustments after the first real run, make them in `mo2_agent_control.py` without broadening the whitelist. Keep the change narrow:

```python
def scan_for_known_blocker_dialogs(runtime_root: str | Path | None = None) -> int:
    qt_widgets = import_qt_widgets_module()
    application = qt_widgets.QApplication.instance()
    if application is None:
        return 0

    handled = 0
    for widget in application.topLevelWidgets():
        if not is_dialog_candidate(widget):
            continue
        if handle_known_blocker_dialog(widget, runtime_root):
            handled += 1
    return handled
```

If needed, also enrich the event payload with parsed process info from the dialog text, but do not widen the matching rules.

- [ ] **Step 4: Re-run the live regression until it passes**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-control-plane/live-cli-run-real.test.ps1 -AllowLiveSandbox -RestartMo2
```

Expected: PASS with `MO2 live CLI run blocker regression checks passed.`

## Task 5: Update docs and lock the new behavior in the text surface

**Files:**
- Modify: `tools/mo2-control-plane/live-bridge/README.md`
- Modify: `tools/mo2-control-plane/live-integration.md`

- [ ] **Step 1: Document the blocker watcher and runtime artifact**

Add a short section to `tools/mo2-control-plane/live-bridge/README.md` explaining the two handled dialogs and the blocker log path.

```markdown
## GUI blocker auto-handling

The live bridge now auto-handles two known MO2 GUI blockers from inside the MO2 process:

- `Mod Organizer is locked while the application is running.` -> `Unlock`
- `Mod Organizer is waiting on an application to close before exiting.` -> `Exit Now`

Each handling attempt is recorded to `.artifacts/mo2/plugins/Mo2AgentControl/bootstrap/runtime/blocker-events.jsonl`.

The watcher is a strict whitelist. Unknown dialogs are logged and left alone.
```

- [ ] **Step 2: Document the effect on raw MO2 CLI launches**

Add a short note to `tools/mo2-control-plane/live-integration.md` near the launch discussion.

```markdown
Raw `ModOrganizer.exe -p <profile> run ...` launches now rely on the MO2-internal blocker watcher to consume the known `Exit Now` and `Unlock` blockers without human clicks. The runtime blocker log under `.artifacts/mo2/plugins/Mo2AgentControl/bootstrap/runtime/blocker-events.jsonl` is the evidence source when diagnosing these flows.
```

- [ ] **Step 3: Run the targeted test set and verify everything is green**

Run:

```powershell
pwsh -NoProfile -File tests/mo2-control-plane/live-dialog-blocker-runtime.test.ps1
pwsh -NoProfile -File tests/mo2-control-plane/deploy-live-bridge.test.ps1
pwsh -NoProfile -File tests/mo2-control-plane/live-bootstrap-real.test.ps1 -AllowLiveSandbox -DeployBridge -RestartMo2
pwsh -NoProfile -File tests/mo2-control-plane/live-cli-run-real.test.ps1 -AllowLiveSandbox -RestartMo2
```

Expected:

- runtime harness passes
- deploy regression passes
- live bootstrap still passes with `lock_gui=false`
- raw MO2 CLI run regression passes with blocker handling evidence

- [ ] **Step 4: Manual smoke-check the original xEdit path**

Run the original user-facing command once as a final manual smoke check:

```powershell
& "D:\awesome-bgs-mod-master\.artifacts\mo2\ModOrganizer.exe" -p Default run -e "OpenCode xEdit Automation Serve"
```

Expected: the command should no longer hang behind the known MO2 blockers, and any auto-handled blocker should appear in `blocker-events.jsonl`.

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$modulePath = Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_agent_control.py"
$runtimeRoot = Join-Path $env:TEMP ("mo2-blocker-runtime-test-" + [guid]::NewGuid().ToString("N"))

try {
    New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null

    $pythonCode = @'
import json
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path
import importlib.util

module_path = Path(sys.argv[1])
runtime_root = Path(sys.argv[2])

if runtime_root.exists():
    shutil.rmtree(runtime_root)
runtime_root.mkdir(parents=True, exist_ok=True)

if not hasattr(__import__("ctypes"), "WinDLL"):
    import ctypes
    ctypes.WinDLL = lambda *args, **kwargs: types.SimpleNamespace()

mobase = types.ModuleType("mobase")
mobase.IPluginTool = type("IPluginTool", (), {})
mobase.VersionInfo = lambda *args, **kwargs: (args, kwargs)
sys.modules["mobase"] = mobase

import ctypes

class _Kernel32Stub:
    def __getattr__(self, name):
        return types.SimpleNamespace(argtypes=None, restype=None)

ctypes.WinDLL = lambda *args, **kwargs: _Kernel32Stub()

spec = importlib.util.spec_from_file_location("mo2_agent_control_under_test", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

unlock = module.match_blocker_dialog(
    "ModOrganizer",
    "Mod Organizer is locked while the application is running.\nxEdit.exe (68944)",
    ["Unlock"],
)
assert unlock is not None, "expected unlock blocker dialog match"
assert unlock["type"] == "unlock", unlock

unlock_crlf = module.match_blocker_dialog(
    "ModOrganizer",
    "Mod Organizer is locked while the application is running.\r\nxEdit.exe (68944)",
    ["Unlock"],
)
assert unlock_crlf is not None, "expected CRLF unlock blocker dialog match"
assert unlock_crlf["type"] == "unlock", unlock_crlf

exit_now = module.match_blocker_dialog(
    "ModOrganizer",
    "Mod Organizer is waiting on an application to close before exiting.\nxEdit.exe (44992)",
    ["Exit Now", "Cancel"],
)
assert exit_now is not None, "expected exit blocker dialog match"
assert exit_now["type"] == "exit-now", exit_now

exit_now_crlf = module.match_blocker_dialog(
    "ModOrganizer",
    "Mod Organizer is waiting on an application to close before exiting.\r\nxEdit.exe (44992)",
    ["Exit Now", "Cancel"],
)
assert exit_now_crlf is not None, "expected CRLF exit blocker dialog match"
assert exit_now_crlf["type"] == "exit-now", exit_now_crlf

unexpected = module.match_blocker_dialog(
    "Unexpected",
    "Something else happened",
    ["OK"],
)
assert unexpected is None, unexpected


class FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)


class FakeTimer:
    def __init__(self, parent=None):
        self.parent = parent
        self.interval = None
        self.started = False
        self.timeout = FakeSignal()

    def setInterval(self, interval):
        self.interval = interval

    def start(self):
        self.started = True


class FakeApplication:
    _instance = None

    def __init__(self, widgets=None):
        self._widgets = list(widgets or [])
        FakeApplication._instance = self

    @classmethod
    def instance(cls):
        return cls._instance

    def topLevelWidgets(self):
        return list(self._widgets)

    def setTopLevelWidgets(self, widgets):
        self._widgets = list(widgets)


class FakeDialog:
    def __init__(self, title, text, buttons, *, visible=True):
        self._title = title
        self._text = text
        self._buttons = list(buttons)
        self._visible = visible

    def isVisible(self):
        return self._visible

    def windowTitle(self):
        return self._title

    def text(self):
        return self._text

    def findChildren(self, cls):
        if cls is FakePushButton:
            return list(self._buttons)
        return []


class MissingTextDialog(FakeDialog):
    def __getattribute__(self, name):
        if name == "text":
            raise AttributeError("text")
        return super().__getattribute__(name)


class FakePushButton:
    def __init__(self, text):
        self._text = text
        self.click_count = 0

    def text(self):
        return self._text

    def click(self):
        self.click_count += 1


class NonDialogWidget:
    def isVisible(self):
        return True


fake_qtwidgets = types.SimpleNamespace(
    QApplication=FakeApplication,
    QDialog=FakeDialog,
    QPushButton=FakePushButton,
)

module.import_qt_widgets_module = lambda: fake_qtwidgets

unlock_button = FakePushButton("Unlock")
unlock_dialog = FakeDialog(
    "ModOrganizer",
    "Mod Organizer is locked while the application is running.\nxEdit.exe (68944)",
    [unlock_button],
)
unknown_ok_button = FakePushButton("OK")
unknown_dialog = FakeDialog(
    "ModOrganizer",
    "Completely different dialog text",
    [unknown_ok_button],
)
missing_text_dialog = MissingTextDialog(
    "ModOrganizer",
    "This text should never be read",
    [FakePushButton("Unlock")],
)

application = FakeApplication([NonDialogWidget(), unlock_dialog, unknown_dialog])

handled_count = module.scan_for_known_blocker_dialogs(runtime_root)
assert handled_count == 1, handled_count
assert unlock_button.click_count == 1, unlock_button.click_count

handled_count_repeat = module.scan_for_known_blocker_dialogs(runtime_root)
assert handled_count_repeat == 0, handled_count_repeat
assert unlock_button.click_count == 1, unlock_button.click_count

application.setTopLevelWidgets([unknown_dialog])
unknown_first = module.scan_for_known_blocker_dialogs(runtime_root)
unknown_second = module.scan_for_known_blocker_dialogs(runtime_root)
assert unknown_first == 0, unknown_first
assert unknown_second == 0, unknown_second

application.setTopLevelWidgets([missing_text_dialog])
missing_text_result = module.scan_for_known_blocker_dialogs(runtime_root)
assert missing_text_result == 0, missing_text_result

application.setTopLevelWidgets([])
application.setTopLevelWidgets([unlock_dialog])
handled_count_reappeared = module.scan_for_known_blocker_dialogs(runtime_root)
assert handled_count_reappeared == 1, handled_count_reappeared
assert unlock_button.click_count == 2, unlock_button.click_count

event = {
    "type": "unlock",
    "title": "ModOrganizer",
    "buttons": ["Unlock"],
    "result": "handled",
}
module.append_blocker_event(runtime_root, event)

events_path = runtime_root / "blocker-events.jsonl"
assert events_path.exists(), "expected blocker-events.jsonl to be created"
lines = events_path.read_text(encoding="utf-8").strip().splitlines()
assert len(lines) == 4, lines
first_record = json.loads(lines[0])
assert first_record["type"] == "unlock", first_record
assert first_record["title"] == "ModOrganizer", first_record
assert first_record["buttons"] == ["Unlock"], first_record
assert first_record["result"] == "handled", first_record

second_record = json.loads(lines[1])
assert second_record["type"] == "ignored", second_record
assert second_record["title"] == "ModOrganizer", second_record
assert second_record["text"] == "Completely different dialog text", second_record
assert second_record["buttons"] == ["OK"], second_record
assert second_record["result"] == "ignored", second_record
assert second_record["source"] == "candidate-dialog", second_record

third_record = json.loads(lines[2])
assert third_record["type"] == "unlock", third_record
assert third_record["title"] == "ModOrganizer", third_record
assert third_record["buttons"] == ["Unlock"], third_record
assert third_record["result"] == "handled", third_record

fourth_record = json.loads(lines[3])
assert fourth_record["type"] == "unlock", fourth_record
assert fourth_record["title"] == "ModOrganizer", fourth_record
assert fourth_record["buttons"] == ["Unlock"], fourth_record
assert fourth_record["result"] == "handled", fourth_record

print("MO2 live dialog blocker runtime checks passed.")
'@

    $output = & python -c $pythonCode $modulePath $runtimeRoot 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ((($output | ForEach-Object { $_.ToString() }) -join "`n"))
    }

    Write-Host (($output | ForEach-Object { $_.ToString() }) -join "`n")
}
finally {
    if (Test-Path $runtimeRoot) {
        Remove-Item -Path $runtimeRoot -Recurse -Force
    }
}

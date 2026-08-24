"""Regression tests for the Windows plugin file picker and its browser client."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


def test_windows_file_picker_startupinfo_requests_normal_visibility(
    tmp_path: Path, monkeypatch
) -> None:
    if os.name != "nt":
        pytest.skip("Windows startup visibility is only available on Windows")
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    startupinfo = web_app._windows_dialog_startupinfo()

    assert startupinfo is not None
    assert startupinfo.dwFlags & subprocess.STARTF_USESHOWWINDOW
    assert startupinfo.wShowWindow == 1  # Win32 SW_SHOWNORMAL


def test_windows_file_picker_uses_visible_utf8_process_and_accepts_chinese_path(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    selected_path = r"D:\模组\中文插件.esm"
    completed = SimpleNamespace(
        returncode=0,
        stdout=json.dumps(
            {"path": selected_path, "canceled": False}, ensure_ascii=False
        ),
        stderr=None,
    )
    startupinfo = object()
    invocation: dict[str, object] = {}

    def fake_run(command, **kwargs):
        invocation["command"] = command
        invocation.update(kwargs)
        return completed

    monkeypatch.setattr(
        web_app, "_windows_dialog_startupinfo", lambda: startupinfo, raising=False
    )
    monkeypatch.setattr(web_app.subprocess, "run", fake_run)

    result = web_app._select_plugin_file()

    assert result == {"path": selected_path, "canceled": False}
    assert invocation["encoding"] == "utf-8"
    assert invocation["errors"] == "replace"
    assert invocation["startupinfo"] is startupinfo
    command = invocation["command"]
    assert isinstance(command, list)
    script = command[-1]
    assert "[Console]::OutputEncoding" in script
    assert "$OutputEncoding" in script
    assert "$owner.TopMost = $true" in script
    assert "FormStartPosition]::CenterScreen" in script
    assert "$dialog.ShowDialog($owner)" in script


def test_windows_file_picker_timeout_becomes_json_500(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="powershell", timeout=300)

    monkeypatch.setattr(web_app.subprocess, "run", raise_timeout)
    client = TestClient(web_app.fastapi_app, raise_server_exceptions=False)
    response = client.post(
        "/api/projects/select-plugin-file",
        headers={"Authorization": f"Bearer {ensure_shared_secret()}"},
        json={"current_path": ""},
    )

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Windows 文件选择器等待响应超时。"}


def test_windows_file_picker_missing_output_becomes_json_500(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    client = TestClient(web_app.fastapi_app, raise_server_exceptions=False)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}
    for stdout in (None, ""):
        monkeypatch.setattr(
            web_app.subprocess,
            "run",
            lambda *args, _stdout=stdout, **kwargs: SimpleNamespace(
                returncode=0, stdout=_stdout, stderr=None
            ),
        )
        response = client.post(
            "/api/projects/select-plugin-file",
            headers=headers,
            json={"current_path": ""},
        )

        assert response.status_code == 500
        assert response.json() == {
            "detail": "Windows 文件选择器没有返回可读取的结果。"
        }


def test_windows_file_picker_rejects_non_object_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    monkeypatch.setattr(
        web_app.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout='["not", "an", "object"]', stderr=""
        ),
    )

    with pytest.raises(web_app.HTTPException) as exc_info:
        web_app._select_plugin_file()

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Windows 文件选择器返回的结果格式无效。"


def test_windows_file_picker_rejects_replacement_character_path(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    monkeypatch.setattr(
        web_app.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"path": "D:\\模组\\损坏\ufffd插件.esm", "canceled": False}),
            stderr="",
        ),
    )
    client = TestClient(web_app.fastapi_app, raise_server_exceptions=False)

    response = client.post(
        "/api/projects/select-plugin-file",
        headers={"Authorization": f"Bearer {ensure_shared_secret()}"},
        json={"current_path": ""},
    )

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Windows 文件选择器返回的路径编码无效。"}


def test_project_api_reports_plain_text_errors_without_json_parse_leak(
    tmp_path: Path, monkeypatch
) -> None:
    if shutil.which("node") is None:
        pytest.skip("Node.js is required for the browser helper behavior test")
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    script = web_app._project_script(None)
    start = script.index("async function api(")
    end = script.index("function setStatus", start)
    api_source = script[start:end]
    node_program = f"""
global.fetch = async (path) => ({{
  ok: path !== '/error',
  status: path === '/error' ? 500 : 200,
  text: async () => path === '/error' ? 'backend exploded' : '<html>not json</html>',
}});
{api_source}
Promise.all([
  api('/error').then(() => null, error => error.message),
  api('/success').then(() => null, error => error.message),
]).then(messages => process.stdout.write(JSON.stringify(messages)));
"""
    completed = subprocess.run(
        ["node", "-e", node_program],
        capture_output=True,
        check=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )

    messages = json.loads(completed.stdout)
    assert messages[0] == "backend exploded"
    assert "无法解析" in messages[1]
    assert "HTTP 200" in messages[1]
    assert all("Unexpected token" not in message for message in messages)

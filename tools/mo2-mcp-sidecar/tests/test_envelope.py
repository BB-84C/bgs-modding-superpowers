"""Unit tests for envelope.py (no subprocess; uses StringIO streams)."""
import io
import json

from mo2_mcp_sidecar.envelope import register_method, run_stdio_loop, _METHODS


def setup_function():
    _METHODS.clear()


def test_ready_signal_emitted_before_processing():
    stdin = io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 1,
                                     "method": "system.echo", "params": {"x": 1}}) + "\n")
    stdout = io.StringIO()
    stderr = io.StringIO()
    register_method("system.echo", lambda p: p)
    run_stdio_loop(stdin, stdout, stderr, exit_on_eof=True)

    lines = [line for line in stdout.getvalue().split("\n") if line]
    assert json.loads(lines[0]) == {"ready": True}
    assert json.loads(lines[1])["result"] == {"x": 1}


def test_invalid_json_returns_parse_error():
    stdin = io.StringIO("not json\n")
    stdout = io.StringIO()
    run_stdio_loop(stdin, stdout, io.StringIO(), exit_on_eof=True)
    lines = [line for line in stdout.getvalue().split("\n") if line]
    err = json.loads(lines[1])
    assert err["error"]["code"] == -32700


def test_unknown_method_returns_minus_32601():
    stdin = io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "nope"}) + "\n")
    stdout = io.StringIO()
    run_stdio_loop(stdin, stdout, io.StringIO(), exit_on_eof=True)
    lines = [line for line in stdout.getvalue().split("\n") if line]
    err = json.loads(lines[1])
    assert err["error"]["code"] == -32601


def test_handler_exception_returns_minus_32603():
    def boom(_p):
        raise ValueError("boom")
    register_method("system.boom", boom)
    stdin = io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "system.boom"}) + "\n")
    stdout = io.StringIO()
    run_stdio_loop(stdin, stdout, io.StringIO(), exit_on_eof=True)
    lines = [line for line in stdout.getvalue().split("\n") if line]
    err = json.loads(lines[1])
    assert err["error"]["code"] == -32603
    assert "boom" in err["error"]["message"]

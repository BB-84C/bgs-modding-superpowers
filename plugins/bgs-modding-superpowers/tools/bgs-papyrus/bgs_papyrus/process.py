import subprocess
from dataclasses import dataclass


@dataclass
class ProcResult:
    returncode: int
    stdout: str
    stderr: str


def run_tool(argv, cwd=None, timeout=120) -> ProcResult:
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return ProcResult(p.returncode, p.stdout, p.stderr)
    except subprocess.TimeoutExpired as e:
        return ProcResult(-1, e.stdout or "", (e.stderr or "") + "\n[timeout]")

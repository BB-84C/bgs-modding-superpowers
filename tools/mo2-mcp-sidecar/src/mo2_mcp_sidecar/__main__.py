"""MO2 MCP sidecar entry point. Args + register methods + run stdio loop."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .envelope import register_method, run_stdio_loop


def _echo_handler(params: dict) -> dict:
    return params


def main() -> int:
    parser = argparse.ArgumentParser(description="MO2 MCP sidecar")
    parser.add_argument("--mods-root", required=True, type=Path)
    parser.add_argument("--profile-dir", required=False, type=Path, default=None)
    parser.add_argument("--game", required=True,
                        choices=["FALLOUT4", "SKYRIM_SE", "SKYRIM_LE",
                                 "STARFIELD", "OBLIVION", "FALLOUT_NV"])
    args = parser.parse_args()

    # Later tasks (S1b 25-29) register their methods here (assets/world/fomod/archive/install)
    register_method("system.echo", _echo_handler)

    run_stdio_loop(sys.stdin, sys.stdout, sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

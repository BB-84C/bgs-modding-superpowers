"""MO2 MCP sidecar entry point."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .envelope import register_method, run_stdio_loop
from .world import WorldCache
from . import archive as _archive
from . import assets as _assets
from . import fomod as _fomod


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

    # Build the shared WorldCache (P-B7: game in, P-F10: lock inside cache)
    cache = WorldCache(mods_root=args.mods_root, game=args.game)

    # Wire methods
    register_method("system.echo", _echo_handler)
    _assets.init_assets(cache)
    _assets.register()
    _fomod.register()
    _archive.register()

    # Later tasks (P-B6 install.conflict_preview, install.stage_fomod) register here

    run_stdio_loop(sys.stdin, sys.stdout, sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

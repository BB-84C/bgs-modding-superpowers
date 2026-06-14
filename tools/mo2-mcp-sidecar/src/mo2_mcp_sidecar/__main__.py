"""MO2 MCP sidecar entry point.

Accepts --mods-root, --profile-dir (optional), --game (required per PLAN-PATCH P-B7).
Emits {"ready": true} on stdout, then runs JSON-RPC stdio loop.
Later S1b tasks (24-29) register actual JSON-RPC methods; this skeleton emits
ready signal then handles only system.echo for smoke testing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="MO2 MCP sidecar")
    parser.add_argument("--mods-root", required=True, type=Path,
                        help="Absolute path to MO2 mods/ directory")
    parser.add_argument("--profile-dir", required=False, type=Path, default=None,
                        help="Absolute path to active profile directory")
    parser.add_argument("--game", required=True,
                        choices=["FALLOUT4", "SKYRIM_SE", "SKYRIM_LE",
                                 "STARFIELD", "OBLIVION", "FALLOUT_NV"],
                        help="Game enum value (per PLAN-PATCH P-B7)")
    args = parser.parse_args()

    sys.stdout.write(json.dumps({"ready": True}) + "\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps({
                "jsonrpc": "2.0", "id": None,
                "error": {"code": -32700, "message": "parse error"},
            }) + "\n")
            sys.stdout.flush()
            continue

        method = req.get("method", "")
        id_ = req.get("id")
        if method == "system.echo":
            sys.stdout.write(json.dumps({
                "jsonrpc": "2.0", "id": id_, "result": req.get("params", {}),
            }) + "\n")
        else:
            sys.stdout.write(json.dumps({
                "jsonrpc": "2.0", "id": id_,
                "error": {"code": -32601, "message": f"method not found: {method}"},
            }) + "\n")
        sys.stdout.flush()

    return 0


if __name__ == "__main__":
    sys.exit(main())

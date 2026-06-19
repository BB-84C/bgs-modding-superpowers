from __future__ import annotations

import os
from pathlib import Path

from . import detect, process, safety
from .games import Game
from .model import Envelope


CHAMPOLLION_NOT_FOUND_MESSAGE = (
    "Champollion not found; install it to ~/.bgs-modding-superpowers/tools/champollion/ "
    "or set BGS_PAPYRUS_CHAMPOLLION"
)


def build_champollion_argv(
    champollion,
    source,
    out,
    *,
    recursive=False,
    threaded=False,
    print_info=False,
) -> list[str]:
    argv = [str(champollion), str(source), "-p", str(out)]
    if recursive:
        argv.append("-r")
    if threaded:
        argv.append("-t")
    if print_info:
        argv.append("-i")
    return argv


def decompile_run(
    game,
    source,
    out,
    *,
    backend="champollion",
    sf_syntax_fix=None,
    recursive=False,
    threaded=False,
    timeout=300,
    allow_game_data=False,
) -> Envelope:
    if safety.is_protected_game_path(out) and not allow_game_data:
        return Envelope(
            ok=False,
            command="decompile",
            error={
                "code": "refused_game_data_write",
                "message": "Refusing to write into a game Data directory; output to an MO2 mod overlay (<MO2_Root>/mods/<mod>/Scripts/) instead, or pass --allow-game-data.",
            },
        )

    game = Game(game)
    backend = backend.lower()
    if backend != "champollion":
        return Envelope(
            ok=False,
            command="decompile",
            error={"code": "backend_not_found", "message": f"Unsupported decompile backend: {backend}"},
        )

    champollion = os.environ.get("BGS_PAPYRUS_CHAMPOLLION")
    if not champollion:
        champollion = detect.detect_game(game).champollion
    if not champollion:
        return Envelope(
            ok=False,
            command="decompile",
            error={"code": "champollion_not_found", "message": CHAMPOLLION_NOT_FOUND_MESSAGE},
        )

    argv = build_champollion_argv(
        champollion,
        source,
        out,
        recursive=recursive,
        threaded=threaded,
    )
    before = _snapshot_outputs(out, "*.psc")
    result = process.run_tool(argv, timeout=timeout)
    produced = _fresh_outputs(out, "*.psc", before)
    fixed: list[str] = []
    should_fix_starfield = (game == Game.STARFIELD) if sf_syntax_fix is None else bool(sf_syntax_fix)
    if should_fix_starfield:
        from . import starfield_syntax

        for path_text in produced:
            path = Path(path_text)
            original = path.read_text(encoding="utf-8", errors="replace")
            updated = starfield_syntax.fix(original)
            if updated != original:
                path.write_text(updated, encoding="utf-8")
                fixed.append(path_text)

    success = result.returncode == 0 and bool(produced)
    data = {
        "backend": "champollion",
        "source": str(source),
        "output_dir": str(out),
        "produced": produced,
        "fixed": fixed,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    if success:
        error = None
    elif result.returncode == 0:
        error = {"code": "decompile_produced_no_psc", "message": "Champollion returned success but produced no fresh .psc output."}
    else:
        error = {"code": "decompile_failed", "message": "Champollion decompile failed."}
    return Envelope(
        ok=success,
        command="decompile",
        data=data,
        error=error,
    )


def _produced_psc(out) -> list[str]:
    out_path = Path(out)
    if not out_path.exists():
        return []
    return sorted(str(path) for path in out_path.rglob("*.psc"))


def _snapshot_outputs(out, pattern: str) -> dict[str, int]:
    out_path = Path(out)
    if not out_path.exists():
        return {}
    snapshot: dict[str, int] = {}
    for path in out_path.rglob(pattern):
        try:
            snapshot[str(path)] = path.stat().st_mtime_ns
        except OSError:
            continue
    return snapshot


def _fresh_outputs(out, pattern: str, before: dict[str, int]) -> list[str]:
    out_path = Path(out)
    if not out_path.exists():
        return []
    fresh: list[str] = []
    for path in out_path.rglob(pattern):
        key = str(path)
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            continue
        if key not in before or mtime > before[key]:
            fresh.append(str(path))
    return sorted(fresh)

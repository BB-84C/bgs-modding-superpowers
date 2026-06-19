from __future__ import annotations

import re
from pathlib import Path

from . import detect, process, safety
from .games import Game, default_imports
from .model import Envelope


def build_ck_argv(
    compiler,
    source,
    flags,
    imports,
    out,
    *,
    all_=False,
    optimize=False,
    release=False,
    final=False,
) -> list[str]:
    argv = [str(compiler), str(source)]
    if flags:
        argv.append(f"-flags={flags}")
    if imports:
        argv.append(f"-import={';'.join(str(path) for path in imports)}")
    argv.append(f"-output={out}")
    if all_:
        argv.append("-all")
    if optimize:
        argv.append("-optimize")
    if release:
        argv.append("-release")
    if final:
        argv.append("-final")
    return argv


def build_caprica_argv(caprica, source, imports, out, *, game=None, flags=None) -> list[str]:
    argv = [str(caprica), str(source)]
    for import_dir in imports or []:
        argv.extend(["-i", str(import_dir)])
    argv.extend(["-o", str(out)])
    if game:
        argv.extend(["-g", game.value if isinstance(game, Game) else str(game)])
    if flags:
        argv.extend(["-f", str(flags)])
    return argv


def build_russo_argv(russo, source, imports, out, *, optimize=False) -> list[str]:
    argv = [str(russo), str(source), "-o", str(out)]
    for import_dir in imports or []:
        argv.extend(["-h", str(import_dir)])
    if optimize:
        argv.append("-O")
    return argv


def compile_run(
    game,
    source,
    out,
    *,
    backend="auto",
    imports=None,
    flags=None,
    all_=False,
    optimize=False,
    release=False,
    final=False,
    timeout=300,
    allow_game_data=False,
) -> Envelope:
    if safety.is_protected_game_path(out) and not allow_game_data:
        return _error(
            "refused_game_data_write",
            "Refusing to write into a game Data directory; output to an MO2 mod overlay (<MO2_Root>/mods/<mod>/Scripts/) instead, or pass --allow-game-data.",
        )

    game = Game(game)
    backend = backend.lower()
    toolchain = detect.detect_game(game)

    resolved, compiler = _resolve_backend(game, toolchain, backend)
    if not resolved or not compiler:
        return _error(
            "backend_not_found",
            f"No Papyrus compiler backend available for {game.value} (requested {backend})",
        )

    if game == Game.STARFIELD and resolved != "ck" and backend != "caprica":
        return _error(
            "starfield_guard_requires_ck",
            "Starfield Guard scripts require the official Creation Kit Papyrus compiler; use backend='caprica' only as an explicit override.",
        )

    flags = flags if flags is not None else toolchain.flags_file
    imports = list(imports) if imports is not None else _default_import_paths(game, toolchain)

    if resolved == "ck":
        if not flags:
            return _error(
                "flags_file_not_found",
                f"Could not locate Papyrus flags file for {game.value}; pass flags= explicitly.",
            )
        argv = build_ck_argv(
            compiler,
            source,
            flags,
            imports,
            out,
            all_=all_,
            optimize=optimize,
            release=release,
            final=final,
        )
    elif resolved == "caprica":
        argv = build_caprica_argv(compiler, source, imports, out, game=game, flags=flags)
    else:
        argv = build_russo_argv(compiler, source, imports, out, optimize=optimize)

    before = _snapshot_outputs(out, "*.pex")
    result = process.run_tool(argv, timeout=timeout)
    produced = _fresh_outputs(out, "*.pex", before)
    errors = _parse_errors(result.stdout, result.stderr)
    expected = _expected_pex_names(source, all_=all_)
    produced_expected = produced if expected is None else [path for path in produced if Path(path).name.lower() in expected]
    success = result.returncode == 0 and bool(produced_expected)
    data = {
        "backend": resolved,
        "compiler": compiler,
        "source": str(source),
        "output_dir": str(out),
        "produced": produced,
        "errors": errors,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    if success:
        error = None
    elif result.returncode == 0:
        error = {"code": "compile_produced_no_pex", "message": "Papyrus compiler returned success but produced no fresh expected .pex output."}
    else:
        error = {"code": "compile_failed", "message": "Papyrus compile failed or produced no .pex output."}
    return Envelope(
        ok=success,
        command="compile",
        data=data,
        error=error,
    )


def _resolve_backend(game: Game, toolchain: detect.ToolchainInfo, backend: str) -> tuple[str | None, str | None]:
    if backend == "auto":
        if toolchain.ck_compiler:
            return "ck", toolchain.ck_compiler
        if toolchain.caprica:
            return "caprica", toolchain.caprica
        if game in {Game.SKYRIMLE, Game.SKYRIMSE} and toolchain.russo:
            return "russo", toolchain.russo
        return None, None
    if backend == "ck":
        return ("ck", toolchain.ck_compiler) if toolchain.ck_compiler else (None, None)
    if backend == "caprica":
        return ("caprica", toolchain.caprica) if toolchain.caprica else (None, None)
    if backend == "russo":
        if game not in {Game.SKYRIMLE, Game.SKYRIMSE}:
            return None, None
        return ("russo", toolchain.russo) if toolchain.russo else (None, None)
    return None, None


def _default_import_paths(game: Game, toolchain: detect.ToolchainInfo) -> list[str]:
    root = _game_root(toolchain, game)
    if not root:
        return []
    return [str(root / Path(*relative.split("/"))) for relative in default_imports(game)]


def _game_root(toolchain: detect.ToolchainInfo, game: Game) -> Path | None:
    if toolchain.ck_compiler:
        root = detect._game_root_from_compiler(game, Path(toolchain.ck_compiler))
        if root:
            return root
    if toolchain.flags_file:
        return Path(toolchain.flags_file).parents[3]
    return None


def _produced_pex(out) -> list[str]:
    out_path = Path(out)
    if not out_path.exists():
        return []
    return sorted(str(path) for path in out_path.rglob("*.pex"))


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


def _expected_pex_names(source, *, all_: bool) -> set[str] | None:
    source_path = Path(source)
    if not all_ and source_path.suffix.lower() == ".psc":
        return {f"{source_path.stem}.pex".lower()}
    return None


def _parse_errors(stdout: str, stderr: str) -> list[dict]:
    errors: list[dict] = []
    pattern = re.compile(r"^(?P<script>.+?)\((?P<line>\d+),(?P<col>\d+)\):\s*(?P<message>.*)$")
    for line in (stdout + "\n" + stderr).splitlines():
        text = line.strip()
        if not text:
            continue
        match = pattern.match(text)
        if match:
            errors.append(
                {
                    "script": match.group("script"),
                    "line": int(match.group("line")),
                    "message": match.group("message"),
                }
            )
        elif "error" in text.lower():
            errors.append({"script": None, "line": None, "message": text})
    return errors


def _error(code: str, message: str) -> Envelope:
    return Envelope(ok=False, command="compile", error={"code": code, "message": message})

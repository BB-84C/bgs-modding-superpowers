from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from bgs_papyrus.games import Game, ck_compiler_subpaths, flags_file, steam_dir_name


@dataclass
class ToolchainInfo:
    game: str
    ck_compiler: str | None = None
    ck_version: str | None = None
    flags_file: str | None = None
    caprica: str | None = None
    russo: str | None = None
    champollion: str | None = None
    source: str | None = None


def detect_game(game: Game) -> ToolchainInfo:
    ck_compiler, source = _detect_ck_compiler(game)
    game_root = _game_root_from_compiler(game, ck_compiler) if ck_compiler else None
    community = _detect_community_backends()
    return ToolchainInfo(
        game=game.value,
        ck_compiler=str(ck_compiler) if ck_compiler else None,
        ck_version=None,
        flags_file=_detect_flags_file(game, game_root),
        caprica=community["caprica"],
        russo=community["russo"],
        champollion=community["champollion"],
        source=source,
    )


def _detect_ck_compiler(game: Game) -> tuple[Path | None, str | None]:
    env_compiler = os.environ.get(f"BGS_PAPYRUS_CK_{game.name}")
    if env_compiler:
        path = Path(env_compiler)
        if path.exists():
            return path, "env"

    env_root = os.environ.get(f"BGS_{game.name}_PATH")
    if env_root:
        found = _find_compiler_under_root(game, Path(env_root))
        if found:
            return found, "env"

    for library in _steam_library_roots():
        root = library / "steamapps" / "common" / steam_dir_name(game)
        found = _find_compiler_under_root(game, root)
        if found:
            return found, "steam"

    return None, None


def _find_compiler_under_root(game: Game, root: Path) -> Path | None:
    for subpath in ck_compiler_subpaths(game):
        candidate = root / Path(*subpath.split("/"))
        if candidate.exists():
            return candidate
    return None


def _game_root_from_compiler(game: Game, compiler: Path) -> Path | None:
    normalized_compiler = compiler.resolve(strict=False)
    for subpath in ck_compiler_subpaths(game):
        parts = Path(*subpath.split("/")).parts
        suffix = Path(*normalized_compiler.parts[-len(parts) :])
        if _same_path_text(suffix, Path(*parts)):
            return normalized_compiler.parents[len(parts) - 1]
    return None


def _detect_flags_file(game: Game, game_root: Path | None) -> str | None:
    if not game_root:
        return None
    candidate = game_root / "Data" / "Scripts" / "Source" / flags_file(game)
    return str(candidate) if candidate.exists() else None


def _detect_community_backends() -> dict[str, str | None]:
    root = Path.home() / ".bgs-modding-superpowers" / "tools"
    caprica = root / "caprica" / "Caprica.exe"
    champollion = root / "champollion" / "Champollion.exe"
    russo_root = root / "papyrus-compiler"
    return {
        "caprica": str(caprica) if caprica.exists() else None,
        "russo": str(russo_root) if russo_root.exists() else None,
        "champollion": str(champollion) if champollion.exists() else None,
    }


def _steam_library_roots() -> list[Path]:
    steam_root = _steam_root()
    roots: list[Path] = []
    if steam_root:
        roots.append(steam_root)
        libraryfolders = steam_root / "steamapps" / "libraryfolders.vdf"
        if libraryfolders.exists():
            try:
                text = libraryfolders.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            roots.extend(Path(path) for path in _parse_library_paths(text))
    return _dedupe_paths(roots)


def _steam_root() -> Path | None:
    if sys.platform == "win32":
        registry_path = _windows_steam_path()
        if registry_path:
            return registry_path
        program_files_x86 = os.environ.get("ProgramFiles(x86)")
        if program_files_x86:
            return Path(program_files_x86) / "Steam"
        return None

    candidates = [Path.home() / ".steam" / "steam", Path.home() / ".local" / "share" / "Steam"]
    return next((candidate for candidate in candidates if candidate.exists()), candidates[0])


def _windows_steam_path() -> Path | None:
    try:
        import winreg
    except ImportError:
        return None

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _ = winreg.QueryValueEx(key, "SteamPath")
    except OSError:
        return None
    return Path(str(value)) if value else None


def _parse_library_paths(text: str) -> list[str]:
    paths = []
    for match in re.finditer(r'"path"\s+"((?:\\.|[^"])*)"', text):
        raw = match.group(1)
        paths.append(raw.replace("\\\\", "\\"))
    return paths


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = os.path.normcase(os.path.normpath(str(path)))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def _same_path_text(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left).replace("/", "\\")) == os.path.normcase(
        str(right).replace("/", "\\")
    )

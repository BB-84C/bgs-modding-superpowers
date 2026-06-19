from importlib import metadata

from .games import Game, flags_file
from .model import Envelope


def _version() -> str:
    try:
        return metadata.version("bgs-papyrus")
    except metadata.PackageNotFoundError:
        return "0.1.0"


def run() -> Envelope:
    games = ["skyrimle", "skyrimse", "fallout4", "starfield"]
    descriptor = {
        "tool": "bgs-papyrus",
        "version": _version(),
        "games": games,
        "subcommands": [
            {"name": "detect-toolchain", "args": ["--game"]},
            {
                "name": "compile",
                "args": [
                    "source",
                    "--game",
                    "--out",
                    "--import",
                    "--backend",
                    "--flags",
                    "--optimize",
                    "--release",
                    "--final",
                    "--all",
                ],
            },
            {
                "name": "decompile",
                "args": [
                    "source",
                    "--game",
                    "--out",
                    "--backend",
                    "--sf-syntax-fix",
                    "--no-sf-syntax-fix",
                    "--recursive",
                    "--threaded",
                ],
            },
            {"name": "capabilities", "args": ["--json"]},
        ],
        "backends": {
            "compile": ["ck", "caprica", "russo"],
            "decompile": ["champollion"],
        },
        "flags_files": {
            "skyrimle": flags_file(Game.SKYRIMLE),
            "skyrimse": flags_file(Game.SKYRIMSE),
            "fallout4": flags_file(Game.FALLOUT4),
            "starfield": flags_file(Game.STARFIELD),
        },
        "starfield_decompile": "champollion + sf-syntax-fix (validated-gated; unproven constructs left as UNVERIFIED)",
        "notes": [
            "Official CK PapyrusCompiler.exe must be user-installed (Bethesda EULA forbids redistribution); bgs-papyrus detects + drives it.",
            "Champollion must be installed to ~/.bgs-modding-superpowers/tools/champollion/ or set BGS_PAPYRUS_CHAMPOLLION.",
        ],
    }
    return Envelope(ok=True, command="capabilities", data=descriptor)

from enum import Enum


class Game(str, Enum):
    SKYRIMLE = "SkyrimLE"
    SKYRIMSE = "SkyrimSE"
    FALLOUT4 = "Fallout4"
    STARFIELD = "Starfield"


def flags_file(game: Game) -> str:
    if game in {Game.SKYRIMLE, Game.SKYRIMSE}:
        return "TESV_Papyrus_Flags.flg"
    if game == Game.FALLOUT4:
        return "Institute_Papyrus_Flags.flg"
    if game == Game.STARFIELD:
        return "Starfield_Papyrus_Flags.flg"
    raise ValueError(f"Unsupported game: {game}")


def ck_compiler_subpaths(game: Game) -> list[str]:
    if game == Game.STARFIELD:
        return [
            "Tools/Papyrus Compiler/PapyrusCompiler.exe",
            "Papyrus Compiler/PapyrusCompiler.exe",
        ]
    if game in {Game.SKYRIMLE, Game.SKYRIMSE, Game.FALLOUT4}:
        return ["Papyrus Compiler/PapyrusCompiler.exe"]
    raise ValueError(f"Unsupported game: {game}")


def steam_dir_name(game: Game) -> str:
    names = {
        Game.SKYRIMLE: "Skyrim",
        Game.SKYRIMSE: "Skyrim Special Edition",
        Game.FALLOUT4: "Fallout 4",
        Game.STARFIELD: "Starfield",
    }
    try:
        return names[game]
    except KeyError as e:
        raise ValueError(f"Unsupported game: {game}") from e


def default_imports(game: Game) -> list[str]:
    imports = {
        Game.SKYRIMLE: ["Data/Scripts/Source"],
        Game.SKYRIMSE: ["Data/Scripts/Source", "Data/Source/Scripts"],
        Game.FALLOUT4: [
            "Data/Scripts/Source/User",
            "Data/Scripts/Source/Base",
            "Data/Scripts/Source",
        ],
        Game.STARFIELD: ["Data/Scripts/Source"],
    }
    try:
        return imports[game]
    except KeyError as e:
        raise ValueError(f"Unsupported game: {game}") from e

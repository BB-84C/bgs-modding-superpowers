from bgs_papyrus.games import Game, flags_file


def test_starfield_flags_file():
    assert flags_file(Game.STARFIELD) == "Starfield_Papyrus_Flags.flg"


def test_fo4_flags_file():
    assert flags_file(Game.FALLOUT4) == "Institute_Papyrus_Flags.flg"


def test_sse_flags_file():
    assert flags_file(Game.SKYRIMSE) == "TESV_Papyrus_Flags.flg"


def test_starfield_compiler_subpaths_include_tools_segment():
    from bgs_papyrus.games import ck_compiler_subpaths

    paths = ck_compiler_subpaths(Game.STARFIELD)
    assert any("Tools/Papyrus Compiler/PapyrusCompiler.exe" in p.replace("\\", "/") for p in paths)

def test_env_override_finds_starfield_compiler(tmp_path, monkeypatch):
    from bgs_papyrus import detect
    from bgs_papyrus.games import Game

    root = tmp_path / "Starfield"
    comp = root / "Tools" / "Papyrus Compiler" / "PapyrusCompiler.exe"
    comp.parent.mkdir(parents=True)
    comp.write_text("x")
    flg = root / "Data" / "Scripts" / "Source" / "Starfield_Papyrus_Flags.flg"
    flg.parent.mkdir(parents=True)
    flg.write_text("x")
    monkeypatch.setenv("BGS_STARFIELD_PATH", str(root))

    info = detect.detect_game(Game.STARFIELD)

    assert info.ck_compiler == str(comp)
    assert info.flags_file == str(flg)
    assert info.source == "env"


def test_parse_libraryfolders_extracts_paths():
    from bgs_papyrus.detect import _parse_library_paths

    sample = '"libraryfolders"\n{\n  "0"\n  {\n    "path"  "C:\\\\Program Files (x86)\\\\Steam"\n  }\n  "1"\n  {\n    "path"  "D:\\\\SteamLibrary"\n  }\n}'

    paths = _parse_library_paths(sample)

    assert any(p.replace("\\", "/").endswith("SteamLibrary") for p in paths)

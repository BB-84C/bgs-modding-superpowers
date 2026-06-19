from bgs_papyrus.detect import ToolchainInfo
from bgs_papyrus.games import Game


def test_ck_batch_argv():
    from bgs_papyrus.compile import build_ck_argv

    argv = build_ck_argv(
        compiler=r"C:\SF\Tools\Papyrus Compiler\PapyrusCompiler.exe",
        source=r"C:\mod\scripts",
        flags=r"C:\SF\Data\Scripts\Source\Starfield_Papyrus_Flags.flg",
        imports=[r"C:\SF\Data\Scripts\Source", r"C:\base\src"],
        out=r"C:\out",
        all_=True,
        optimize=True,
    )

    assert argv[0].endswith("PapyrusCompiler.exe")
    assert r"C:\mod\scripts" in argv
    assert "-flags=C:\\SF\\Data\\Scripts\\Source\\Starfield_Papyrus_Flags.flg" in argv
    assert "-import=C:\\SF\\Data\\Scripts\\Source;C:\\base\\src" in argv
    assert "-output=C:\\out" in argv
    assert "-all" in argv and "-optimize" in argv


def test_starfield_auto_requires_ck_for_guard_scripts(monkeypatch, tmp_path):
    from bgs_papyrus import compile as compile_mod

    def fake_detect_game(game):
        return ToolchainInfo(
            game=game.value,
            ck_compiler=None,
            flags_file=None,
            caprica=r"C:\tools\Caprica.exe",
            russo=None,
            source="test",
        )

    monkeypatch.setattr(compile_mod.detect, "detect_game", fake_detect_game)

    env = compile_mod.compile_run(
        Game.STARFIELD,
        source=str(tmp_path / "GuardScript.psc"),
        out=str(tmp_path / "out"),
        backend="auto",
    )

    assert env.ok is False
    assert env.error["code"] == "starfield_guard_requires_ck"

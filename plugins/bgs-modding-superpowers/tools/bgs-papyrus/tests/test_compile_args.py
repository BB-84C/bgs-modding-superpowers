from bgs_papyrus.detect import ToolchainInfo
from bgs_papyrus.games import Game
from bgs_papyrus.process import ProcResult


def _fake_toolchain(game):
    return ToolchainInfo(
        game=game.value,
        ck_compiler=r"C:\Tools\PapyrusCompiler.exe",
        flags_file=r"C:\Game\Data\Scripts\Source\Starfield_Papyrus_Flags.flg",
        caprica=None,
        russo=None,
        source="test",
    )


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


def test_compile_run_rejects_returncode_zero_without_fresh_expected_pex(monkeypatch, tmp_path):
    from bgs_papyrus import compile as compile_mod

    source = tmp_path / "FreshScript.psc"
    source.write_text("ScriptName FreshScript")
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(compile_mod.detect, "detect_game", _fake_toolchain)
    monkeypatch.setattr(compile_mod.process, "run_tool", lambda argv, timeout=300: ProcResult(0, "", ""))

    env = compile_mod.compile_run(Game.STARFIELD, source=str(source), out=str(out), backend="ck", imports=[])

    assert env.ok is False
    assert env.error["code"] == "compile_produced_no_pex"
    assert env.data["produced"] == []


def test_compile_run_rejects_stale_expected_pex(monkeypatch, tmp_path):
    from bgs_papyrus import compile as compile_mod

    source = tmp_path / "FreshScript.psc"
    source.write_text("ScriptName FreshScript")
    out = tmp_path / "out"
    out.mkdir()
    (out / "FreshScript.pex").write_text("stale")
    monkeypatch.setattr(compile_mod.detect, "detect_game", _fake_toolchain)
    monkeypatch.setattr(compile_mod.process, "run_tool", lambda argv, timeout=300: ProcResult(0, "", ""))

    env = compile_mod.compile_run(Game.STARFIELD, source=str(source), out=str(out), backend="ck", imports=[])

    assert env.ok is False
    assert env.error["code"] == "compile_produced_no_pex"
    assert env.data["produced"] == []


def test_compile_run_accepts_fresh_expected_pex(monkeypatch, tmp_path):
    from bgs_papyrus import compile as compile_mod

    source = tmp_path / "FreshScript.psc"
    source.write_text("ScriptName FreshScript")
    out = tmp_path / "out"
    out.mkdir()

    def fake_run(argv, timeout=300):
        (out / "FreshScript.pex").write_text("compiled")
        return ProcResult(0, "", "")

    monkeypatch.setattr(compile_mod.detect, "detect_game", _fake_toolchain)
    monkeypatch.setattr(compile_mod.process, "run_tool", fake_run)

    env = compile_mod.compile_run(Game.STARFIELD, source=str(source), out=str(out), backend="ck", imports=[])

    assert env.ok is True
    assert env.error is None
    assert env.data["produced"] == [str(out / "FreshScript.pex")]


def test_compile_run_refuses_game_data_output_without_override(tmp_path):
    from bgs_papyrus import compile as compile_mod

    out = tmp_path / "steamapps" / "common" / "Game" / "Data" / "Scripts"

    env = compile_mod.compile_run(Game.FALLOUT4, source=str(tmp_path / "Script.psc"), out=str(out))

    assert env.ok is False
    assert env.error["code"] == "refused_game_data_write"


def test_compile_run_allow_game_data_bypasses_refusal(monkeypatch, tmp_path):
    from bgs_papyrus import compile as compile_mod

    out = tmp_path / "steamapps" / "common" / "Game" / "Data" / "Scripts"
    monkeypatch.setattr(compile_mod.detect, "detect_game", lambda game: ToolchainInfo(game=game.value, source="test"))

    env = compile_mod.compile_run(
        Game.FALLOUT4,
        source=str(tmp_path / "Script.psc"),
        out=str(out),
        allow_game_data=True,
    )

    assert env.error["code"] != "refused_game_data_write"

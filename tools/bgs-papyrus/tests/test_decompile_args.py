from bgs_papyrus.detect import ToolchainInfo
from bgs_papyrus.games import Game
from bgs_papyrus.process import ProcResult


def test_champollion_argv_uses_real_cli_flags():
    from bgs_papyrus.decompile import build_champollion_argv

    argv = build_champollion_argv(
        "C:/t/Champollion.exe",
        "C:/in",
        "C:/out",
        recursive=True,
        threaded=True,
    )

    assert argv == ["C:/t/Champollion.exe", "C:/in", "-p", "C:/out", "-r", "-t"]


def test_decompile_run_reports_missing_champollion(monkeypatch, tmp_path):
    from bgs_papyrus import decompile as decompile_mod

    def fake_detect_game(game):
        return ToolchainInfo(
            game=game.value,
            champollion=None,
            source="test",
        )

    monkeypatch.delenv("BGS_PAPYRUS_CHAMPOLLION", raising=False)
    monkeypatch.setattr(decompile_mod.detect, "detect_game", fake_detect_game)

    env = decompile_mod.decompile_run(
        Game.STARFIELD,
        source=str(tmp_path / "input"),
        out=str(tmp_path / "out"),
    )

    assert env.ok is False
    assert env.error["code"] == "champollion_not_found"


def test_decompile_run_rejects_returncode_zero_without_fresh_psc(monkeypatch, tmp_path):
    from bgs_papyrus import decompile as decompile_mod

    def fake_detect_game(game):
        return ToolchainInfo(game=game.value, champollion=r"C:\tools\Champollion.exe", source="test")

    monkeypatch.delenv("BGS_PAPYRUS_CHAMPOLLION", raising=False)
    monkeypatch.setattr(decompile_mod.detect, "detect_game", fake_detect_game)
    monkeypatch.setattr(decompile_mod.process, "run_tool", lambda argv, timeout=300: ProcResult(0, "", ""))

    env = decompile_mod.decompile_run(Game.FALLOUT4, source=str(tmp_path / "input.pex"), out=str(tmp_path / "out"))

    assert env.ok is False
    assert env.error["code"] == "decompile_produced_no_psc"
    assert env.data["produced"] == []


def test_decompile_run_rejects_stale_psc(monkeypatch, tmp_path):
    from bgs_papyrus import decompile as decompile_mod

    out = tmp_path / "out"
    out.mkdir()
    (out / "input.psc").write_text("stale")

    def fake_detect_game(game):
        return ToolchainInfo(game=game.value, champollion=r"C:\tools\Champollion.exe", source="test")

    monkeypatch.delenv("BGS_PAPYRUS_CHAMPOLLION", raising=False)
    monkeypatch.setattr(decompile_mod.detect, "detect_game", fake_detect_game)
    monkeypatch.setattr(decompile_mod.process, "run_tool", lambda argv, timeout=300: ProcResult(0, "", ""))

    env = decompile_mod.decompile_run(Game.FALLOUT4, source=str(tmp_path / "input.pex"), out=str(out))

    assert env.ok is False
    assert env.error["code"] == "decompile_produced_no_psc"
    assert env.data["produced"] == []


def test_decompile_run_accepts_fresh_psc(monkeypatch, tmp_path):
    from bgs_papyrus import decompile as decompile_mod

    out = tmp_path / "out"

    def fake_detect_game(game):
        return ToolchainInfo(game=game.value, champollion=r"C:\tools\Champollion.exe", source="test")

    def fake_run(argv, timeout=300):
        out.mkdir(parents=True, exist_ok=True)
        (out / "input.psc").write_text("ScriptName Input")
        return ProcResult(0, "", "")

    monkeypatch.delenv("BGS_PAPYRUS_CHAMPOLLION", raising=False)
    monkeypatch.setattr(decompile_mod.detect, "detect_game", fake_detect_game)
    monkeypatch.setattr(decompile_mod.process, "run_tool", fake_run)

    env = decompile_mod.decompile_run(Game.FALLOUT4, source=str(tmp_path / "input.pex"), out=str(out))

    assert env.ok is True
    assert env.error is None
    assert env.data["produced"] == [str(out / "input.psc")]


def test_decompile_run_refuses_game_data_output_without_override(tmp_path):
    from bgs_papyrus import decompile as decompile_mod

    out = tmp_path / "Stock Game" / "Fallout 4" / "Data" / "Scripts"

    env = decompile_mod.decompile_run(Game.FALLOUT4, source=str(tmp_path / "input.pex"), out=str(out))

    assert env.ok is False
    assert env.error["code"] == "refused_game_data_write"


def test_decompile_run_allow_game_data_bypasses_refusal(monkeypatch, tmp_path):
    from bgs_papyrus import decompile as decompile_mod

    out = tmp_path / "Stock Game" / "Fallout 4" / "Data" / "Scripts"
    monkeypatch.setattr(decompile_mod.detect, "detect_game", lambda game: ToolchainInfo(game=game.value, source="test"))

    env = decompile_mod.decompile_run(
        Game.FALLOUT4,
        source=str(tmp_path / "input.pex"),
        out=str(out),
        allow_game_data=True,
    )

    assert env.error["code"] != "refused_game_data_write"

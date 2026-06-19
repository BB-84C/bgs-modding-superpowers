from bgs_papyrus.detect import ToolchainInfo
from bgs_papyrus.games import Game


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

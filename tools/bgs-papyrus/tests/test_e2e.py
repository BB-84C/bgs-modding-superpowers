import os
from pathlib import Path

import pytest

from bgs_papyrus import compile as compile_mod
from bgs_papyrus.games import Game


STARFIELD_ROOT = Path(r"D:\SteamLibrary\steamapps\common\Starfield")
CHRONOMARK_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / ".opencode"
    / "artifacts"
    / "archive-papyrus-tools"
    / "fixtures"
    / "starfield-chronomark"
)
EXPECTED_PEX = ["UCW_MainQuestScript.pex", "UCW_PlayerAliasScript.pex"]
PEX_MAGIC = 0xFA57C0DE


def _starfield_compiler() -> Path:
    return Path(
        os.environ.get(
            "BGS_PAPYRUS_CK_STARFIELD",
            STARFIELD_ROOT / "Tools" / "Papyrus Compiler" / "PapyrusCompiler.exe",
        )
    )


def _pex_header(path: Path) -> dict[str, object]:
    header = path.read_bytes()[:8]
    return {
        "magic": int.from_bytes(header[:4], "little"),
        "version": tuple(header[4:6]),
        "game_id": int.from_bytes(header[6:8], "little"),
    }


@pytest.mark.e2e
def test_compile_real_starfield_chronomark_sources_with_official_ck(tmp_path):
    compiler = _starfield_compiler()
    if not compiler.exists():
        pytest.skip(f"Starfield Creation Kit Papyrus compiler not found: {compiler}")
    if not CHRONOMARK_FIXTURE.exists():
        pytest.skip(f"Chronomark Starfield fixture not found: {CHRONOMARK_FIXTURE}")

    source_dir = CHRONOMARK_FIXTURE / "Source"
    flags = STARFIELD_ROOT / "Data" / "Scripts" / "Source" / "Starfield_Papyrus_Flags.flg"
    imports = [
        source_dir,
        STARFIELD_ROOT / "Data" / "Scripts" / "Source",
        STARFIELD_ROOT / "Tools" / "ContentResources" / "Scripts" / "Source",
    ]

    env = compile_mod.compile_run(
        Game.STARFIELD,
        source=str(source_dir),
        out=str(tmp_path),
        backend="ck",
        imports=[str(path) for path in imports],
        flags=str(flags),
        all_=True,
        timeout=300,
    )

    assert env.ok is True, env.to_json()
    for filename in EXPECTED_PEX:
        produced = tmp_path / filename
        original = CHRONOMARK_FIXTURE / filename

        assert produced.exists(), env.to_json()
        assert produced.stat().st_size > 0

        produced_header = _pex_header(produced)
        original_header = _pex_header(original)
        assert produced_header["magic"] == PEX_MAGIC
        assert produced_header["version"] == original_header["version"]
        assert produced_header["game_id"] == original_header["game_id"]

import os
import re
import zipfile
from difflib import SequenceMatcher
from pathlib import Path

import pytest

from bgs_papyrus import compile as compile_mod, decompile as decompile_mod, detect
from bgs_papyrus.games import Game


STARFIELD_ROOT = Path(r"D:\SteamLibrary\steamapps\common\Starfield")
FALLOUT4_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Fallout 4")
FALLOUT4_BASE_ZIP = FALLOUT4_ROOT / "Data" / "Scripts" / "Source" / "Base" / "Base.zip"
FALLOUT4_COMPILE_SOURCE = "BoSResQuestScript.psc"
CHRONOMARK_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / ".opencode"
    / "artifacts"
    / "archive-papyrus-tools"
    / "fixtures"
    / "starfield-chronomark"
)
EXPECTED_PEX = ["UCW_MainQuestScript.pex", "UCW_PlayerAliasScript.pex"]
EXPECTED_PSC = ["UCW_MainQuestScript.psc", "UCW_PlayerAliasScript.psc"]
P10A_COMPILE_OUT = (
    Path(__file__).resolve().parents[3]
    / ".opencode"
    / "artifacts"
    / "archive-papyrus-tools"
    / "acceptance"
    / "P10a-starfield-compile-out"
)
PEX_MAGIC = 0xFA57C0DE


def _starfield_compiler() -> Path:
    return Path(
        os.environ.get(
            "BGS_PAPYRUS_CK_STARFIELD",
            STARFIELD_ROOT / "Tools" / "Papyrus Compiler" / "PapyrusCompiler.exe",
        )
    )


def _fallout4_toolchain() -> detect.ToolchainInfo:
    return detect.detect_game(Game.FALLOUT4)


def _pex_header(path: Path) -> dict[str, object]:
    header = path.read_bytes()[:8]
    return {
        "magic": int.from_bytes(header[:4], "little"),
        "version": tuple(header[4:6]),
        "game_id": int.from_bytes(header[6:8], "little"),
    }


def _extract_fo4_base_source(out: Path) -> Path:
    with zipfile.ZipFile(FALLOUT4_BASE_ZIP) as archive:
        archive.extractall(out)
    return out


def _champollion() -> Path:
    path = os.environ.get("BGS_PAPYRUS_CHAMPOLLION") or detect.detect_game(Game.STARFIELD).champollion
    return Path(path) if path else Path("__missing_champollion__")


def _flags() -> Path:
    return STARFIELD_ROOT / "Data" / "Scripts" / "Source" / "Starfield_Papyrus_Flags.flg"


def _imports(*extra: Path) -> list[str]:
    return [
        *(str(path) for path in extra),
        str(STARFIELD_ROOT / "Data" / "Scripts" / "Source"),
        str(STARFIELD_ROOT / "Tools" / "ContentResources" / "Scripts" / "Source"),
    ]


def _without_comments(text: str) -> str:
    return "\n".join(re.sub(r";.*", "", line) for line in text.splitlines())


def _normalized_source(text: str) -> str:
    text = _without_comments(text)
    text = re.sub(r"\{.*?\}", " ", text, flags=re.DOTALL)
    return re.sub(r"\s+", " ", text).strip().lower()


def _symbols(text: str) -> dict[str, set[str]]:
    text = _without_comments(text)
    return {
        "script": {match.lower() for match in re.findall(r"(?im)^\s*scriptname\s+(\w+)", text)},
        "functions": {
            match.lower()
            for match in re.findall(r"(?im)^\s*(?:\w+\s+)?function\s+(\w+)\s*\(", text)
        },
        "events": {match.lower() for match in re.findall(r"(?im)^\s*event\s+([\w.]+)\s*\(", text)},
        "properties": {
            match.lower() for match in re.findall(r"(?im)^\s*\w+\s+property\s+(\w+)\b", text)
        },
    }


@pytest.mark.e2e
def test_compile_real_fallout4_base_source_with_official_ck(tmp_path):
    toolchain = _fallout4_toolchain()
    compiler = Path(toolchain.ck_compiler) if toolchain.ck_compiler else Path("__missing_fallout4_compiler__")
    if not compiler.exists():
        pytest.skip(f"Fallout 4 Creation Kit Papyrus compiler not found: {compiler}")
    if not FALLOUT4_BASE_ZIP.exists():
        pytest.skip(f"Fallout 4 Base.zip source archive not found: {FALLOUT4_BASE_ZIP}")

    source_dir = _extract_fo4_base_source(tmp_path / "fo4-base-source")
    source = source_dir / FALLOUT4_COMPILE_SOURCE
    flags = source_dir / "Institute_Papyrus_Flags.flg"
    if not source.exists():
        pytest.skip(f"Fallout 4 compile fixture source not found in Base.zip: {FALLOUT4_COMPILE_SOURCE}")
    if not flags.exists():
        pytest.skip(f"Fallout 4 Papyrus flags not found in Base.zip: {flags}")

    env = compile_mod.compile_run(
        Game.FALLOUT4,
        source=str(source),
        out=str(tmp_path / "compiled"),
        backend="ck",
        imports=[str(source_dir)],
        flags=str(flags),
        timeout=300,
    )

    produced = tmp_path / "compiled" / "BoSResQuestScript.pex"
    assert env.ok is True, env.to_json()
    assert produced.exists(), env.to_json()
    header = _pex_header(produced)
    assert header["magic"] == PEX_MAGIC
    assert header["version"] == (3, 9)
    assert header["game_id"] == 2


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


@pytest.mark.e2e
def test_decompile_real_starfield_chronomark_round_trips_to_recompiled_pex(tmp_path):
    champollion = _champollion()
    if not champollion.exists():
        pytest.skip(f"Champollion not found: {champollion}")
    if not CHRONOMARK_FIXTURE.exists():
        pytest.skip(f"Chronomark Starfield fixture not found: {CHRONOMARK_FIXTURE}")
    if not P10A_COMPILE_OUT.exists():
        pytest.skip(f"P10a Starfield compiled output not found: {P10A_COMPILE_OUT}")

    original_dec = tmp_path / "original-dec"
    recompiled_dec = tmp_path / "recompiled-dec"
    original_env = decompile_mod.decompile_run(
        Game.STARFIELD,
        source=str(CHRONOMARK_FIXTURE),
        out=str(original_dec),
        recursive=True,
    )
    recompiled_env = decompile_mod.decompile_run(
        Game.STARFIELD,
        source=str(P10A_COMPILE_OUT),
        out=str(recompiled_dec),
        recursive=True,
    )

    assert original_env.ok is True, original_env.to_json()
    assert recompiled_env.ok is True, recompiled_env.to_json()
    for filename in EXPECTED_PSC:
        hand_source = (CHRONOMARK_FIXTURE / "Source" / filename).read_text(encoding="utf-8", errors="replace")
        original_source = (original_dec / filename).read_text(encoding="utf-8", errors="replace")
        recompiled_source = (recompiled_dec / filename).read_text(encoding="utf-8", errors="replace")

        assert _symbols(original_source) == _symbols(hand_source)
        assert SequenceMatcher(None, _normalized_source(hand_source), _normalized_source(original_source)).ratio() > 0.90
        assert _normalized_source(recompiled_source) == _normalized_source(original_source)


@pytest.mark.e2e
def test_starfield_guard_syntax_fix_recompiled_with_official_ck(tmp_path):
    compiler = _starfield_compiler()
    champollion = _champollion()
    flags = _flags()
    if not compiler.exists():
        pytest.skip(f"Starfield Creation Kit Papyrus compiler not found: {compiler}")
    if not champollion.exists():
        pytest.skip(f"Champollion not found: {champollion}")
    if not flags.exists():
        pytest.skip(f"Starfield Papyrus flags not found: {flags}")

    vanilla_source = STARFIELD_ROOT / "Data" / "Scripts" / "Source" / "CCT_Enviro_BehaviorScript.psc"
    if not vanilla_source.exists():
        pytest.skip(f"Vanilla guard source not found: {vanilla_source}")

    vanilla_pex = tmp_path / "vanilla-pex"
    fixed_dec = tmp_path / "fixed-dec"
    recompiled = tmp_path / "recompiled"
    compile_env = compile_mod.compile_run(
        Game.STARFIELD,
        source=str(vanilla_source),
        out=str(vanilla_pex),
        backend="ck",
        imports=_imports(),
        flags=str(flags),
        timeout=300,
    )
    decompile_env = decompile_mod.decompile_run(
        Game.STARFIELD,
        source=str(vanilla_pex),
        out=str(fixed_dec),
        recursive=True,
    )
    recompile_env = compile_mod.compile_run(
        Game.STARFIELD,
        source=str(fixed_dec / "CCT_Enviro_BehaviorScript.psc"),
        out=str(recompiled),
        backend="ck",
        imports=_imports(fixed_dec),
        flags=str(flags),
        timeout=300,
    )

    assert compile_env.ok is True, compile_env.to_json()
    assert decompile_env.ok is True, decompile_env.to_json()
    assert decompile_env.data and decompile_env.data["fixed"]
    fixed_text = (fixed_dec / "CCT_Enviro_BehaviorScript.psc").read_text(encoding="utf-8", errors="replace")
    assert "Guard abilityGuard ProtectsFunctionLogic" in fixed_text
    assert "LockGuard abilityGuard" in fixed_text
    assert "EndLockGuard" in fixed_text
    assert recompile_env.ok is True, recompile_env.to_json()

# bgs-papyrus — Architecture

**Goal:** A Python CLI that compiles (PSC->PEX) and decompiles (PEX->PSC) Papyrus for Skyrim LE/SE-AE, Fallout 4, and Starfield, by detecting and driving the user-installed official CK `PapyrusCompiler.exe` (compile) and Champollion + a CK-grounded Starfield syntax post-processor (decompile), with community fallbacks.

**Grounding (real-world evidence):**
- Flags-file matrix: `fireundubh/pyro` `pyro/Constants.py` (`FlagsName`: FO4=`Institute_Papyrus_Flags.flg`, SF1=`Starfield_Papyrus_Flags.flg`, SSE/TES5=`TESV_Papyrus_Flags.flg`).
- Wrapper pattern + CK-vs-russo fallback: `SpookyPirate/spookys-automod-toolkit` `PapyrusCompilerWrapper.cs`.
- Compile flag syntax: Champollion `Test/compile.cmd` (`PapyrusCompiler.exe <in> -f=<flg> -i=<import> -o=<out> -keepasm`), plus `-output=`/`-import=`/`-flags=`/`-optimize`/`-all` long forms.
- Starfield PEX/language deltas + Guard syntax discrepancy: `.opencode/artifacts/archive-papyrus-tools/multi-lens/INTEGRATED-FINDINGS.md` §3.
- Compiler can NOT be shipped (Bethesda CK EULA). Detect + drive only.

## Package layout (mirrors tools/bgs-translator/)

```
tools/bgs-papyrus/
  pyproject.toml
  bgs_papyrus/
    __init__.py
    cli.py               # argparse dispatch; --json everywhere; exit codes
    model.py             # Envelope dataclass -> JSON
    games.py             # Game enum + flags-file matrix + game path patterns
    process.py           # subprocess runner: argv, cwd, timeout, capture, returncode
    detect.py            # locate CK compiler / Caprica / russo / Champollion per game
    compile.py           # build compile argv + run (CK primary, Caprica/russo fallback)
    decompile.py         # build Champollion argv + run + optional SF post-process
    starfield_syntax.py  # CK-grounded Guard/access-modifier post-processor (PEX->PSC fixups)
    caps.py              # capabilities self-description
  tests/
    test_games.py
    test_detect.py
    test_compile_args.py     # assert constructed argv WITHOUT a real compiler
    test_decompile_args.py
    test_starfield_syntax.py # post-processor unit tests on snippet fixtures
    test_cli.py              # argparse + envelope shape
    test_e2e.py              # @pytest.mark.e2e real CK round-trip; skipped if no CK
  README.md
  USER-GUIDE.en.md
  USER-GUIDE.zh-cn.md
  CHANGELOG.md
```

`pyproject.toml`: package `bgs-papyrus`, entry point `bgs-papyrus = "bgs_papyrus.cli:main"`, Python `>=3.11`, deps minimal (stdlib only + optionally `vdf` for Steam library parsing; prefer a tiny hand parser to avoid the dep). dev: `pytest`.

## CLI surface (capabilities)

All commands accept `--json`. Exit 0 ok, 1 handled error (envelope emitted), 2 usage.

```
bgs-papyrus detect-toolchain [--game <game>]
    # report: CK compiler path+version, flags file, Caprica, russo-2025, Champollion; per game
bgs-papyrus compile <src.psc | src-dir> --game <game>
    [--out <dir>] [--import <dir> ...] [--backend ck|caprica|russo|auto]
    [--flags <flg-path>] [--optimize] [--release] [--final] [--all]
bgs-papyrus decompile <file.pex | pex-dir> --game <game>
    [--out <dir>] [--backend champollion] [--sf-syntax-fix/--no-sf-syntax-fix]
bgs-papyrus capabilities
```

`<game>`: `skyrimle | skyrimse | fallout4 | starfield` (games.py `Game`).

## Game matrix (games.py)

| Game | flags file | CK compiler subpath | default decompile fix |
|---|---|---|---|
| skyrimle / skyrimse | `TESV_Papyrus_Flags.flg` | `<root>/Papyrus Compiler/PapyrusCompiler.exe` | none |
| fallout4 | `Institute_Papyrus_Flags.flg` | `<root>/Papyrus Compiler/PapyrusCompiler.exe` | none |
| starfield | `Starfield_Papyrus_Flags.flg` | `<root>/Papyrus Compiler/PapyrusCompiler.exe` | `--sf-syntax-fix` ON |

Default import dirs per game (from `blu3mania/npp-papyrus` + pyro):
- SSE: `Data/Scripts/Source`, `Data/Source/Scripts`
- FO4: `Data/Scripts/Source/User`, `Data/Scripts/Source/Base`, `Data/Scripts/Source`
- Starfield: `Data/Scripts/Source` (+ user dirs)

## Toolchain detection (detect.py)

Resolution order per game, first hit wins, recorded in `detect-toolchain` output:
1. Env override: `BGS_<GAME>_PATH` (game root) / `BGS_PAPYRUS_CK_<GAME>` (direct compiler path).
2. Steam: parse `<Steam>/steamapps/libraryfolders.vdf` for library roots, look for `steamapps/common/<GameDir>/Papyrus Compiler/PapyrusCompiler.exe`. Steam root from registry `HKCU\Software\Valve\Steam\SteamPath` (Windows) or `~/.steam`/`~/.local/share/Steam` (Linux).
3. Community backends in `~/.bgs-modding-superpowers/tools/`: `caprica/Caprica.exe`, `papyrus-compiler/` (russo-2025), `champollion/Champollion.exe`.

`detect-toolchain --json` emits, per game: `{ ck_compiler: path|null, ck_version: str|null, flags_file: path|null, caprica: path|null, russo: path|null, champollion: path|null }`. Version probing: run `PapyrusCompiler.exe` with no args / `-?` and parse the banner (best-effort; null if unparseable).

## Compile (compile.py)

Backend selection (`--backend auto` default):
- `auto`: prefer CK compiler if detected (authoritative, only reliable Starfield-Guard path). Else Caprica (Skyrim/FO4, and Starfield WITHOUT Guard). Else russo-2025 (Skyrim only).
- Starfield + Guard scripts: `auto` requires CK; if only Caprica available, emit `code: "starfield_guard_requires_ck"` warning and refuse (don't silently miscompile) unless `--backend caprica` is explicit.

CK argv (grounded in compile.cmd + SpookyPirate wrapper):
```
PapyrusCompiler.exe <source-or-folder>
    -flags=<flags-file>
    -import=<dir1>;<dir2>;...     # semicolon-joined, single flag
    -output=<out-dir>
    [-all]                        # when source is a folder (batch)
    [-optimize] [-release] [-final]
```
Batch = pass a folder + `-all`. Success = returncode 0 AND expected `.pex` exists in `-output`. Capture stdout/stderr; parse per-script error lines into structured `errors[]`.

Caprica argv: `Caprica.exe <src> -i <import> -o <out> [-f <flags>] [-g <game>]` (verify exact Caprica flags in task; Caprica uses `-g`/game + auto Starfield flags per `main_options.cpp`).

russo-2025 argv: `<src> -o <out> -h <import> [-O]` (Skyrim only).

## Decompile (decompile.py + starfield_syntax.py)

Champollion drives PEX->PSC. Argv (verify exact in task; Champollion CLI is `Champollion [options] <pex|dir>` with output-dir + recursive flags). Batch = pass a directory.

**Starfield syntax fix pipeline:**
1. Run Champollion -> raw `.psc` (Champollion emits guessed `Guard/EndGuard`/`TryGuard` per its own README disclaimer).
2. If `--sf-syntax-fix` (default ON for `--game starfield`): run `starfield_syntax.fix(psc_text)` to rewrite guessed constructs to official syntax (per OpenPapyrus grammar: `Guard` definitions, `LockGuard/EndLockGuard`, `TryLockGuard/EndTryLockGuard`, access modifiers `Private/Protected/Internal/SelfOnly`, `RequiresGuard(...)`, `ProtectsFunctionLogic`).
3. Mark every rewritten span with a `; bgs-papyrus: sf-syntax-fix applied` comment for auditability.

**The post-processor's correctness is established by round-trip, not by trusting our guess:** decompile a vanilla Starfield `.pex` -> fix -> recompile with the OFFICIAL CK compiler -> if it compiles clean and the re-emitted `.pex` is structurally equivalent, the fix is correct for that construct. The post-processor is built construct-by-construct against this oracle (see acceptance). Anything not yet round-trip-validated is left as Champollion's output + a `; UNVERIFIED sf-syntax` marker rather than a confident-but-wrong rewrite.

## JSON contract (model.py)

```python
@dataclass
class Envelope:
    ok: bool
    tool: str = "bgs-papyrus"
    command: str = ""
    data: dict | None = None
    error: dict | None = None   # {"code": str, "message": str}
```
`compile`/`decompile` data: `{ backend, source, output_dir, produced: [paths], errors: [ {script, line, message} ], skipped: [...] }`.

## Acceptance (semantic E2E — binding)

Unit (`pytest`, no real tools): argv construction (`test_compile_args`/`test_decompile_args`), game matrix, detection logic against a faked dir tree, Starfield post-processor on snippet fixtures.

Semantic E2E (`tests/test_e2e.py`, `@pytest.mark.e2e`, skipped when CK absent): against a real CK install (env `BGS_STARFIELD_PATH` etc.).
1. **Compile**: compile a known vanilla `.psc` via our CLI with the official CK compiler; assert `.pex` produced + non-empty.
2. **Decompile round-trip (Skyrim/FO4)**: decompile a vanilla `.pex` via Champollion; recompile the `.psc` via CK; assert re-emitted `.pex` is produced.
3. **Starfield Guard round-trip (the hard one)**: take a real vanilla Starfield `.pex` that uses Guards (extract from `Starfield - Misc.ba2` via `bgs-archive`); decompile + `--sf-syntax-fix`; recompile via official Starfield CK compiler; assert clean compile. This is THE acceptance gate for Starfield decompile correctness.
4. Record evidence under `.opencode/artifacts/archive-papyrus-tools/acceptance/`.

`returncode 0` / `ok:true` alone is never acceptance — the produced `.pex`/`.psc` must be inspected/round-tripped.

## Distribution

- `tools/bgs-papyrus/` materialized into the plugin tree by `build-portable-plugin.ps1` (exclude `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `*.egg-info`, `build`, `dist`, `.venv`) — same exclude set as bgs-translator.
- Community backends (Caprica, Champollion incl. the SF-fixed fork build if/when it lands, russo-2025) are downloaded on demand into `~/.bgs-modding-superpowers/tools/` (GitHub Release assets), NOT committed. The official CK compiler is always user-supplied (EULA).
- `skills/using-bgs-papyrus/SKILL.md` + bootstrap table row.

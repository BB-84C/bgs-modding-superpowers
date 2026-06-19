# bgs-papyrus — Task Stream

> Execute with `subagent-driven-development`. Run commands with `workdir = tools/bgs-papyrus`. Most logic is unit-testable WITHOUT a real compiler by asserting constructed argv; real compile/decompile is gated behind `@pytest.mark.e2e` (binding acceptance, run manually against a real CK).

---

## Task P1: Python scaffold + CLI skeleton
**Files:** Create `tools/bgs-papyrus/pyproject.toml`, `bgs_papyrus/__init__.py`, `bgs_papyrus/cli.py`, `tests/test_cli.py`

- [ ] **Step 1: pyproject.toml**
```toml
[project]
name = "bgs-papyrus"
version = "0.1.0"
description = "Agent-native Papyrus compile/decompile CLI for Skyrim, Fallout 4, Starfield"
requires-python = ">=3.11"
dependencies = []
[project.scripts]
bgs-papyrus = "bgs_papyrus.cli:main"
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
[tool.pytest.ini_options]
markers = ["e2e: requires a real Creation Kit install"]
```

- [ ] **Step 2: Failing test** — `tests/test_cli.py`
```python
import json, subprocess, sys
def run(*args):
    return subprocess.run([sys.executable, "-m", "bgs_papyrus.cli", *args],
                          capture_output=True, text=True)
def test_capabilities_json_envelope():
    r = run("capabilities", "--json")
    assert r.returncode == 0
    env = json.loads(r.stdout)
    assert env["ok"] is True and env["tool"] == "bgs-papyrus"
```

- [ ] **Step 3: Run, expect FAIL** — `python -m pytest tests/test_cli.py`.

- [ ] **Step 4: Write `bgs_papyrus/cli.py`** (argparse with subparsers `detect-toolchain|compile|decompile|capabilities`, global `--json`, dispatch to module `run()` funcs, `main()` sets exit code; stub non-caps commands to emit an ok envelope for now).
```python
import argparse, sys
from . import caps, model

def main(argv=None):
    p = argparse.ArgumentParser(prog="bgs-papyrus")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("capabilities")
    # compile/decompile/detect-toolchain parsers added in later tasks
    args = p.parse_args(argv)
    try:
        if args.command == "capabilities":
            env = caps.run()
        else:
            env = model.Envelope(ok=True, command=args.command, data={})
        print(env.to_json() if args.json else env.human())
        return 0
    except Exception as e:  # replaced by typed handling in later tasks
        env = model.Envelope(ok=False, command=getattr(args, "command", ""),
                             error={"code": "internal", "message": str(e)})
        print(env.to_json() if args.json else env.human(), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5:** Create minimal `model.py` (Envelope with `to_json`/`human`) and `caps.py` (`run()` returns ok envelope) so it imports.
- [ ] **Step 6: Run, expect PASS.**
- [ ] **Step 7: Commit** — `git add tools/bgs-papyrus && git commit -m "feat(bgs-papyrus): python scaffold + CLI skeleton"`

---

## Task P2: model.py + games.py (matrix)
**Files:** `bgs_papyrus/model.py` (finalize), `bgs_papyrus/games.py`, `tests/test_games.py`

- [ ] **Step 1: Failing test** — `tests/test_games.py`
```python
from bgs_papyrus.games import Game, flags_file, default_imports
def test_starfield_flags_file():
    assert flags_file(Game.STARFIELD) == "Starfield_Papyrus_Flags.flg"
def test_fo4_flags_file():
    assert flags_file(Game.FALLOUT4) == "Institute_Papyrus_Flags.flg"
def test_sse_flags_file():
    assert flags_file(Game.SKYRIMSE) == "TESV_Papyrus_Flags.flg"
```
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implement `games.py`** — `Game` enum (`SKYRIMLE, SKYRIMSE, FALLOUT4, STARFIELD`), `flags_file()` (matrix from `01-architecture.md`), `default_imports()`, `ck_compiler_subpaths()` returning a LIST per game: `["Papyrus Compiler/PapyrusCompiler.exe"]` for Skyrim/FO4; `["Tools/Papyrus Compiler/PapyrusCompiler.exe", "Papyrus Compiler/PapyrusCompiler.exe"]` for Starfield (CONFIRMED: real Starfield path has the `Tools/` segment), `steam_dir_name()` (`"Skyrim Special Edition"`, `"Fallout 4"`, `"Starfield"`). Finalize `model.py` Envelope.
- [ ] **Step 4: PASS.**  **Step 5: Commit.**

---

## Task P3: process.py (subprocess runner)
**Files:** `bgs_papyrus/process.py`, `tests/test_process.py`
- [ ] **Step 1: Failing test**: `run_tool(["python","-c","print(42)"], timeout=10)` returns `(returncode=0, stdout contains "42")`.
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implement** — `run_tool(argv, cwd=None, timeout=120) -> ProcResult(returncode, stdout, stderr)` via `subprocess.run(..., capture_output=True, text=True, timeout=...)`; handle `TimeoutExpired` -> ProcResult(returncode=-1, ...). Use `Start`-safe arg list (no shell).
- [ ] **Step 4: PASS.**  **Step 5: Commit.**

---

## Task P4: detect.py (toolchain detection)
**Files:** `bgs_papyrus/detect.py`, `tests/test_detect.py`
- [ ] **Step 1: Failing test** — build a fake game tree in tmp_path with `Papyrus Compiler/PapyrusCompiler.exe` + flags file; set `BGS_STARFIELD_PATH` env to it; assert `detect_game(Game.STARFIELD)` finds `ck_compiler` and `flags_file`.
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implement** — resolution order from `01-architecture.md` §detection: env override -> Steam `libraryfolders.vdf` scan -> `~/.bgs-modding-superpowers/tools/` community backends. Return a `ToolchainInfo` dataclass per game. Steam vdf parse = small regex/line parser for `"path"  "<dir>"` entries (no external dep).
- [ ] **Step 4: PASS.**  **Step 5: Commit.**

---

## Task P5: compile.py argv + run
**Files:** `bgs_papyrus/compile.py`, `tests/test_compile_args.py`
- [ ] **Step 1: Failing test** — assert constructed argv WITHOUT running a compiler:
```python
from bgs_papyrus.compile import build_ck_argv
def test_ck_batch_argv():
    argv = build_ck_argv(
        compiler=r"C:\SF\Papyrus Compiler\PapyrusCompiler.exe",
        source=r"C:\mod\scripts", flags=r"C:\SF\...\Starfield_Papyrus_Flags.flg",
        imports=[r"C:\SF\Data\Scripts\Source"], out=r"C:\out",
        all_=True, optimize=True, release=False, final=False)
    assert argv[0].endswith("PapyrusCompiler.exe")
    assert r"C:\mod\scripts" in argv
    assert "-flags=" + r"C:\SF\...\Starfield_Papyrus_Flags.flg" in argv
    assert "-import=" + r"C:\SF\Data\Scripts\Source" in argv
    assert "-output=" + r"C:\out" in argv
    assert "-all" in argv and "-optimize" in argv
```
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implement `build_ck_argv`** (semicolon-join multiple imports into one `-import=` per cheat evidence), `build_caprica_argv`, `build_russo_argv`, plus `compile_run(args)` that: resolves backend via `detect`, refuses Starfield+Guard on non-CK (`code: "starfield_guard_requires_ck"`), runs via `process.run_tool`, verifies expected `.pex` exists, parses error lines into `errors[]`, returns Envelope.
- [ ] **Step 4: PASS** (`test_compile_args` — no real compiler needed).
- [ ] **Step 5: Commit.**

---

## Task P6: decompile.py argv + run
**Files:** `bgs_papyrus/decompile.py`, `tests/test_decompile_args.py`
- [ ] **Step 1: VERIFY Champollion CLI first** — fetch `Orvid/Champollion` README / `--help` to confirm exact flags (output dir, recursive, psc-vs-asm). Record the confirmed flags in a comment. (Do NOT invent; Champollion's arg names must be real.)
- [ ] **Step 2: Failing test** — assert `build_champollion_argv(champ, source, out, recursive=True)` produces the confirmed real flags.
- [ ] **Step 3: FAIL.**
- [ ] **Step 4: Implement** `build_champollion_argv` + `decompile_run(args)` that runs Champollion, then (if `--sf-syntax-fix`) pipes each produced `.psc` through `starfield_syntax.fix` (Task P7), returns Envelope with `produced` + `fixed` lists.
- [ ] **Step 5: PASS.**  **Step 6: Commit.**

---

## Task P7: starfield_syntax.py (CK-grounded post-processor)
**Files:** `bgs_papyrus/starfield_syntax.py`, `tests/test_starfield_syntax.py`
- [ ] **Step 1: Failing test** on snippet fixtures — given a `.psc` snippet containing Champollion's guessed `Guard`/`EndGuard` block, `fix(text)` returns text using the official `LockGuard`/`EndLockGuard` form AND inserts a `; bgs-papyrus: sf-syntax-fix applied` audit marker. Start with ONLY the constructs already round-trip-validated; leave others untouched + `; UNVERIFIED sf-syntax` marked.
```python
from bgs_papyrus.starfield_syntax import fix
def test_guard_block_rewrite():
    src = "Guard myGuard\n; ...\nEndGuard\n"
    out = fix(src)
    assert "LockGuard" in out or "; UNVERIFIED sf-syntax" in out
    assert "sf-syntax-fix applied" in out or "UNVERIFIED" in out
```
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implement** `fix(psc_text) -> str` as an ordered set of construct rewrites, each gated by a `VALIDATED` flag. Per INTEGRATED-FINDINGS §3, target official forms: `LockGuard/EndLockGuard`, `TryLockGuard/ElseTryLockGuard/EndTryLockGuard`, access modifiers, `RequiresGuard(...)`, `ProtectsFunctionLogic`, `SelfOnly`. Anything not yet VALIDATED stays as-is + `; UNVERIFIED sf-syntax` marker — NEVER emit a confident-but-unproven rewrite (memory/10).
- [ ] **Step 4: PASS.**  **Step 5: Commit.**
- [ ] **NOTE:** each construct flips to `VALIDATED=True` only after the Task P10 round-trip proves it recompiles via the official Starfield CK compiler. This task ships the framework + the constructs validated so far; the rest stay UNVERIFIED until the E2E oracle confirms them.

---

## Task P8: capabilities (finalize)
**Files:** `bgs_papyrus/caps.py`, `tests/test_caps.py`
- [ ] **Step 1: Failing test**: `capabilities --json` -> `data.games` contains `starfield`; `data.backends.compile` lists `ck/caprica/russo`; `data.starfield_decompile == "champollion+sf-syntax-fix"`.
- [ ] **Step 2: FAIL.**  **Step 3: Implement** static descriptor (games, subcommands+args, backends, flags-file matrix, the "CK must be user-installed; not shipped" note).
- [ ] **Step 4: PASS.**  **Step 5: Commit.**

---

## Task P9: detect-toolchain command + full CLI wiring
**Files:** edit `bgs_papyrus/cli.py`, `tests/test_cli.py`
- [ ] **Step 1: Failing test**: `detect-toolchain --game starfield --json` against a faked env tree returns `data.ck_compiler` non-null.
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implement** — add `detect-toolchain`, `compile`, `decompile` subparsers with all args from `01-architecture.md`; wire to `detect.run`/`compile.compile_run`/`decompile.decompile_run`; typed error -> envelope + exit 1.
- [ ] **Step 4: PASS.**  **Step 5: Commit.**

---

## Task P10: semantic E2E real CK round-trip (BINDING acceptance)
**Files:** `tests/test_e2e.py` (`@pytest.mark.e2e`)
- [ ] **Step 1: Write E2E tests** (skip if `BGS_STARFIELD_PATH`/CK absent):
  - compile a known vanilla `.psc` via CLI -> assert `.pex` produced.
  - Skyrim/FO4: decompile vanilla `.pex` -> recompile via CK -> assert `.pex` produced.
  - **Starfield Guard round-trip**: use `bgs-archive extract` to pull a Guard-using vanilla `.pex` from `Starfield - Misc.ba2`; decompile + `--sf-syntax-fix`; recompile via official Starfield CK compiler; assert clean compile.
- [ ] **Step 2: Run manually** with a real CK: `python -m pytest -m e2e -v`.
- [ ] **Step 3: For each Starfield construct that round-trips clean, flip its `VALIDATED` flag in `starfield_syntax.py`** and re-run. Record before/after in `.opencode/artifacts/archive-papyrus-tools/acceptance/`.
- [ ] **Step 4: Commit** test + the validated post-processor constructs.

---

## Task P11: README + USER-GUIDE + skill + materialize
**Files:** `tools/bgs-papyrus/README.md`, `USER-GUIDE.en.md`, `USER-GUIDE.zh-cn.md`, `CHANGELOG.md`, `skills/using-bgs-papyrus/SKILL.md`, edit `scripts/build-portable-plugin.ps1`, edit `skills/using-bgs-modding-superpowers/SKILL.md`
- [ ] **Step 1:** README + bilingual USER-GUIDE (detect-toolchain first; CK must be installed from Steam; compile/decompile examples; Starfield Guard caveat + the round-trip-validation honesty).
- [ ] **Step 2:** `using-bgs-papyrus` skill (when to use; `detect-toolchain` first; route to `bgs-archive` to extract vanilla scripts; hard rule: compiled output goes to an MO2 overlay, never game Data; Starfield decompile is best-effort + audit-marked).
- [ ] **Step 3:** Add `tools/bgs-papyrus/` to `build-portable-plugin.ps1` materialize set with the bgs-translator exclude list; add `using-bgs-papyrus` row to bootstrap table.
- [ ] **Step 4:** Run materialize; verify.
- [ ] **Step 5:** Two commits (source+skill; then materialized).

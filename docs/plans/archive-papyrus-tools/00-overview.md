# Archive + Papyrus Agent-Native CLI Tools — Plan Overview

> **For agentic workers:** REQUIRED SUB-SKILL: use `subagent-driven-development` (recommended) or `executing-plans` to implement task-by-task. Steps use checkbox (`- [ ]`) syntax. This is the OVERVIEW; the executable task plans live in `bgs-archive/` and `bgs-papyrus/` under this directory.

**Goal:** Ship two standalone, agent-native CLI tools — `bgs-archive` (BA2/BSA unpack/pack) and `bgs-papyrus` (Papyrus PSC<->PEX compile/decompile) — each with a companion `using-*` skill, no MCP surface.

**Architecture:** Two independent subsystems with no shared code.
- `bgs-archive` = Rust CLI on the `ba2` crate (0BSD). Source in-tree at `tools/bgs-archive/`; compiled binary shipped via GitHub Release + sha256-verified download (same pattern as KB packs / xEdit).
- `bgs-papyrus` = Python CLI (mirrors `tools/bgs-translator/` layout). Detects + drives the user-installed official CK `PapyrusCompiler.exe` (pyro model) for compile; drives Champollion + a CK-grounded Starfield syntax post-processor for decompile. No compiler binaries shipped (CK EULA forbids redistribution).

**Tech Stack:** Rust (clap, ba2, serde_json) for archive; Python 3.11+ (argparse/click, subprocess, pydantic) for papyrus. Both emit machine-readable JSON and expose a `capabilities` self-description subcommand.

---

## Scope split (why two plans)

These are independent subsystems (different languages, backends, no shared code), so per `writing-plans` they are **two separate executable plans**, each producing working software on its own:

| Plan dir | Tool | Lang | Backend | Ships binary? |
|---|---|---|---|---|
| `bgs-archive/` | `bgs-archive` | Rust | `ba2` crate (in-process) | Yes — own binary via GitHub Release |
| `bgs-papyrus/` | `bgs-papyrus` | Python | drives external exes (CK compiler, Caprica, Champollion) | No — detects/downloads user-supplied or community exes |

Each plan can land + be reviewed independently. They share this branch (`feat/archive-papyrus-cli-tools`) because they are one construction wave, but commit in separate task streams.

## Locked design decisions (settled with user 2026-06-18)

1. **Archive language**: Rust CLI on `ba2` crate. Source in tree; binary via Release (NOT committed to plugin tree).
2. **Papyrus language**: Python (mirrors `tools/bgs-translator/`).
3. **Papyrus compile backend**: detect + drive official per-game CK `PapyrusCompiler.exe` (pyro-proven pattern); Caprica/russo-2025 as non-Guard fallback. CK binary user-installed, never shipped (EULA).
4. **Starfield decompile**: Champollion as PEX backend + **Python-layer CK-grounded syntax post-processor first** (rewrite Champollion's guessed `Guard/EndGuard` -> official `LockGuard/EndLockGuard/...`, validated by official-CK round-trip). Fork Champollion's C++ emit code **only if** text post-processing proves structurally insufficient.
5. **No MCP** for either tool. CLI + `using-*` skill only.
6. **Distribution**: both tools materialized into `plugins/bgs-modding-superpowers/tools/` via `scripts/build-portable-plugin.ps1` (source/docs/skill only; Rust compiled binary stays out of git, fetched from Release into `~/.bgs-modding-superpowers/tools/<tool>/<version>/`).

## Format / version substrate (from recon — see references)

### BA2/BSA matrix (bgs-archive must cover)
| Game | Container | Version | Compression |
|---|---|---|---|
| Oblivion | BSA | v103 | zlib |
| FO3 / NV | BSA | v104 | zlib |
| Skyrim LE | BSA | v104 | zlib |
| Skyrim SE/AE | BSA | v105 | LZ4 frame |
| FO4 1.10.163 | BA2 | v1 (GNRL+DX10) | zlib |
| FO4 Next-Gen | BA2 | v7 / v8 | zlib |
| FO76 | BA2 | v1 | zlib |
| Starfield | BA2 | v2 (GNRL) / v3 (DX10) | v2 zlib, v3 LZ4 block |
| Starfield GNMF | BA2 GNMF | (PS5) | n/a — OUT OF SCOPE (metadata-only) |

### Papyrus matrix (bgs-papyrus must cover)
Only Skyrim LE/SE-AE + FO4 + Starfield have Papyrus. FO3/NV/Oblivion use GECK/Gamebryo — NOT in scope for this tool.
| Game | PEX gameId/ver | Compile flags file | Compile backend | Decompile |
|---|---|---|---|---|
| Skyrim LE/SE/AE | 1 / 3.1-3.2 | `TESV_Papyrus_Flags.flg` | CK compiler / Caprica | Champollion (mature) |
| Fallout 4 | 2 / 3.9 | `Institute_Papyrus_Flags.flg` | CK compiler / Caprica | Champollion |
| Starfield | 4 / 3.12 (+ Guard table, opcodes 0x30/0x31/0x32) | `Starfield_Papyrus_Flags.flg` | **official Starfield CK compiler only** (Caprica = non-Guard fallback) | Champollion + CK-grounded post-processor |

## Acceptance philosophy (binding — memory/10)

Neither tool is "done" on `cargo test` / `pytest` green alone. Semantic E2E required:

- **bgs-archive**: open REAL game archives (FO4/Starfield/Skyrim from the harness or `.artifacts/bgs-mod-plugins/` samples), confirm correct auto-detect of family/version, then prove extraction via **structural validity** (extracted files have valid format magic — DDS/NIF/PEX/BGSM — and sizes consistent with `list`; this also proves decompression correctness since a botched decompress fails magic) PLUS **self-consistency round-trip** (extract → repack with our own tool → re-extract → byte-identical via SHA256). NO external byte-compare oracle is used — the only mature reference tool here (BSArchPro) is GUI-only and hangs bash, and no CLI archive oracle is available. `ok:true` envelope alone is NOT acceptance — inspect extracted bytes.
- **bgs-papyrus**: round-trip REAL scripts. Compile a known `.psc` with the official CK compiler via our CLI, confirm the `.pex` is produced + loadable; decompile a vanilla `.pex` and (for Starfield) recompile the post-processed `.psc` with the official CK compiler and byte/structure-compare the resulting `.pex`. Starfield Guard correctness is validated by this round-trip, not by trusting Champollion's guessed syntax.

## Distribution / build integration

- Source trees: `tools/bgs-archive/` (Rust crate), `tools/bgs-papyrus/` (Python package).
- `scripts/build-portable-plugin.ps1` extended to materialize both into `plugins/bgs-modding-superpowers/tools/` (with Rust/Python dev-cache excludes). Two-commit shape (source, then materialized) per repo convention.
- Skills: `skills/using-bgs-archive/SKILL.md`, `skills/using-bgs-papyrus/SKILL.md`; both registered in the `using-bgs-modding-superpowers` bootstrap skill table.
- bgs-archive binary: GitHub Release `bgs-archive-vX.Y.Z` (per-platform), downloaded + sha256-verified into `~/.bgs-modding-superpowers/tools/bgs-archive/<version>/` on first use (or by setup skill).

## References (recon substrate — read before implementing)

- `.opencode/artifacts/archive-papyrus-tools/multi-lens/INTEGRATED-FINDINGS.md` — full format matrix + backend survey + sources.
- `.opencode/artifacts/archive-papyrus-tools/ba2-api-cheatsheet.md` — exact `ba2 = "3.0.1"` API surface (grounds every Rust code step).
- Real-world compiler-invocation evidence: pyro (`fireundubh/pyro` Constants.py flags matrix), SpookyPirate/spookys-automod-toolkit (`PapyrusCompilerWrapper.cs` wrapper pattern), Champollion `Test/compile.cmd` (flag syntax).

## Plan index

1. `bgs-archive/01-architecture.md` — Rust CLI design, ba2 wiring, CLI surface, distribution, acceptance.
2. `bgs-archive/02-tasks.md` — bite-sized TDD task stream.
3. `bgs-papyrus/01-architecture.md` — Python CLI design, CK detect/drive, Champollion + Starfield post-processor, distribution, acceptance.
4. `bgs-papyrus/02-tasks.md` — bite-sized TDD task stream.

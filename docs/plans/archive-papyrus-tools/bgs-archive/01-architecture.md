# bgs-archive — Architecture

**Goal:** A Rust CLI that unpacks and packs BA2/BSA archives across Oblivion, FO3/NV, Skyrim LE/SE-AE, FO4 (incl. Next-Gen), FO76, and Starfield, with stable machine-readable JSON output, wrapping the `ba2` crate (v3.0.1, 0BSD).

**Grounding:** every `ba2` call traces to `.opencode/artifacts/archive-papyrus-tools/ba2-api-cheatsheet.md`. Do not invent `ba2` signatures.

## Crate layout

```
tools/bgs-archive/
  Cargo.toml
  src/
    main.rs        # clap dispatch -> command modules; sets process exit code
    cli.rs         # clap derive structs (Cli, Command enum, per-command args)
    error.rs       # AppError (thiserror) wrapping ba2::{tes3,tes4,fo4}::Error + io + json
    model.rs       # serde Serialize output structs (Envelope, EntryInfo, ArchiveInfo, ...)
    game.rs        # Game enum + mapping to ba2 fo4/tes4 Version/Format/CompressionFormat
    archive.rs     # AnyArchive + open_any() (guess_format dispatch), entry iteration
    cmd_info.rs    # `info`
    cmd_list.rs    # `list`
    cmd_extract.rs # `extract`
    cmd_pack.rs    # `pack`
    cmd_caps.rs    # `capabilities`
  tests/
    fixtures.rs        # builds tiny in-memory archives via ba2 for round-trip unit tests
    cli_roundtrip.rs   # assert_cmd integration: pack->list->extract round-trip
    real_archive.rs    # #[ignore] semantic E2E against real game archives (env-gated paths)
```

Dependencies (Cargo.toml):
- `ba2 = "3.0.1"`
- `clap = { version = "4", features = ["derive"] }`
- `serde = { version = "1", features = ["derive"] }`, `serde_json = "1"`
- `thiserror = "1"`
- `anyhow = "1"` (main only)
- `walkdir = "2"` (pack: enumerate input dir)
- `globset = "0.4"` (extract/list `--filter`)
- dev: `assert_cmd = "2"`, `predicates = "3"`, `tempfile = "3"`

## CLI surface (capabilities)

All commands accept `--json` (machine envelope) and default to human text. Exit code 0 = ok, 1 = handled error (envelope still emitted with `--json`), 2 = usage error.

```
bgs-archive info    <archive>                                  # detected family/version/format/compression/entry-count
bgs-archive list    <archive> [--filter <glob>] [--long]       # entries: path, size, compressed
bgs-archive extract <archive> [--out <dir>] [--filter <glob>] [--flatten]
bgs-archive pack    <input-dir> <out-archive> --game <game>
                    [--format gnrl|dx10] [--compress zip|lz4|none] [--strings] [--bsa-types <list>]
bgs-archive capabilities                                       # self-describe: games, formats, subcommands, ba2 version
bgs-archive --version | --help
```

`<game>` (game.rs `Game` enum, `clap::ValueEnum`):
`morrowind | oblivion | fallout3 | falloutnv | skyrimle | skyrimse | fallout4 | fallout4ng | fallout76 | starfield`

Game -> ba2 mapping (grounded in cheat-sheet §3/§4/§5):
| Game | Module | Version | Default Format | Default Compression |
|---|---|---|---|---|
| morrowind | tes3 | (none) | n/a | none |
| oblivion | tes4 | `Version::TES4` (v103) | n/a | zlib (flag) |
| fallout3 / falloutnv | tes4 | `Version::FO3` (v104) | n/a | zlib |
| skyrimle | tes4 | `Version::TES5` (v104) | n/a | zlib |
| skyrimse | tes4 | `Version::SSE` (v105) | n/a | lz4 |
| fallout4 | fo4 | `Version::v1` | GNRL | Zip |
| fallout4ng | fo4 | `Version::v7` | GNRL | Zip |
| fallout76 | fo4 | `Version::v1` | GNRL | Zip (level FO76) |
| starfield | fo4 | `Version::v2` (GNRL) / `v3` (DX10) | GNRL | Zip (GNRL) / LZ4 (DX10) |

## JSON output contract (model.rs)

```rust
#[derive(Serialize)]
pub struct Envelope<T> {
    pub ok: bool,
    pub tool: &'static str,        // "bgs-archive"
    pub command: &'static str,     // "info" | "list" | ...
    pub data: Option<T>,
    pub error: Option<ErrEnvelope>,
}
#[derive(Serialize)]
pub struct ErrEnvelope { pub code: String, pub message: String }

#[derive(Serialize)]
pub struct ArchiveInfo {
    pub path: String,
    pub family: String,            // "tes3" | "tes4" | "fo4"
    pub version: Option<u32>,      // 103/104/105 | 1/2/3/7/8
    pub format: Option<String>,    // "GNRL" | "DX10" | "GNMF" (fo4 only)
    pub compression: Option<String>,
    pub entry_count: usize,
}
#[derive(Serialize)]
pub struct EntryInfo { pub path: String, pub size: u64, pub compressed: bool }
```

`capabilities` emits a static descriptor: tool version, `ba2` version `3.0.1`, supported games list, supported subcommands with arg schemas, and the read/write coverage matrix (write currently: tes3, tes4 all versions, fo4 GNRL all versions; DX10/GNMF pack = read-only until DX10 task lands).

## Auto-detect dispatch (archive.rs)

Use `ba2::guess_format` then branch (cheat-sheet §2/§6). Reader returns `(Archive, ArchiveOptions)` for tes4/fo4 (metadata preserved for extraction), bare `Archive` for tes3.

```rust
pub enum AnyArchive {
    Tes3(ba2::tes3::Archive<'static>),
    Tes4(ba2::tes4::Archive<'static>, ba2::tes4::ArchiveOptions),
    Fo4 (ba2::fo4::Archive<'static>,  ba2::fo4::ArchiveOptions),
}
pub fn open_any(path: &Path) -> Result<AnyArchive, AppError>;
```

Extraction reuses the preserved `ArchiveOptions` via `meta.into()` to build per-file write options (cheat-sheet §3/§4 verbatim extract examples).

## Coverage boundaries (documented in `capabilities` + README)

- **Read/extract**: all families incl. fo4 DX10 textures + Starfield (uses preserved metadata; no DDS transcoding needed to dump bytes).
- **Pack**: tes3, tes4 (v103/104/105), fo4 GNRL (v1/v2/v7/v8). 
- **DX10/GNMF pack = deferred** (Task A-DX10, gated on resolving `fo4::DX10Header` field layout, marked UNVERIFIED in cheat-sheet §8). Until then `pack --format dx10` returns `code: "unsupported_dx10_pack"` with a clear message.
- Starfield GNMF (PS5) is out of scope entirely.

## Acceptance (semantic E2E — binding)

Unit (`cargo test`): in-memory round-trip per family (build archive via ba2 -> write to temp -> read back -> assert payload bytes equal). Proves wiring, NOT real-format fidelity.

Semantic E2E (`tests/real_archive.rs`, `#[ignore]`, run explicitly): against real game archives.
1. Locate a real archive (env `BGS_ARCHIVE_TEST_BA2` / a known harness path).
2. `bgs-archive extract` a known entry; byte-compare against the same entry extracted by **BSArch.exe** (reference oracle from the xEdit tree) — proves our reader matches the canonical tool.
3. `bgs-archive pack` the extracted tree back into a new archive, re-extract, byte-compare payloads — proves write fidelity.
4. For Starfield: repeat with a real Starfield `.ba2` (v2 GNRL) to prove v2 coverage.

`ok:true` is never sufficient; the byte-compare is the acceptance signal.

## Distribution

- `cargo build --release` -> `bgs-archive(.exe)`.
- CI/maintainer publishes per-platform binaries to GitHub Release `bgs-archive-vX.Y.Z`.
- First-run/setup downloads + sha256-verifies into `~/.bgs-modding-superpowers/tools/bgs-archive/<version>/`.
- `scripts/build-portable-plugin.ps1` materializes `tools/bgs-archive/` SOURCE (+ README + skill) into the plugin tree, excluding `target/`, `Cargo.lock` optional. The compiled binary is NOT committed.

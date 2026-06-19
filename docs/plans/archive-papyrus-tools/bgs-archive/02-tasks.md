# bgs-archive — Task Stream

> Execute with `subagent-driven-development`. All `ba2` code is grounded in `.opencode/artifacts/archive-papyrus-tools/ba2-api-cheatsheet.md`. Run all commands with `workdir = tools/bgs-archive`.

---

## Task A1: Cargo scaffold + clap skeleton

**Files:** Create `tools/bgs-archive/Cargo.toml`, `tools/bgs-archive/src/main.rs`, `tools/bgs-archive/src/cli.rs`, `tools/bgs-archive/tests/cli_smoke.rs`

- [ ] **Step 1: Write Cargo.toml**
```toml
[package]
name = "bgs-archive"
version = "0.1.0"
edition = "2021"
license = "MIT"
description = "Agent-native BA2/BSA unpack/pack CLI for Bethesda games"

[dependencies]
ba2 = "3.0.1"
clap = { version = "4", features = ["derive"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
thiserror = "1"
anyhow = "1"
walkdir = "2"
globset = "0.4"

[dev-dependencies]
assert_cmd = "2"
predicates = "3"
tempfile = "3"
```

- [ ] **Step 2: Write failing smoke test** — `tests/cli_smoke.rs`
```rust
use assert_cmd::Command;

#[test]
fn prints_version() {
    Command::cargo_bin("bgs-archive").unwrap()
        .arg("--version")
        .assert().success()
        .stdout(predicates::str::contains("bgs-archive"));
}
```

- [ ] **Step 3: Run, expect FAIL** — `cargo test --test cli_smoke` -> fails (no bin).

- [ ] **Step 4: Write `src/cli.rs`**
```rust
use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(name = "bgs-archive", version, about = "BA2/BSA unpack/pack for Bethesda games")]
pub struct Cli {
    #[arg(long, global = true)] pub json: bool,
    #[command(subcommand)] pub command: Command,
}

#[derive(Subcommand)]
pub enum Command {
    Info    { archive: std::path::PathBuf },
    List    { archive: std::path::PathBuf, #[arg(long)] filter: Option<String>, #[arg(long)] long: bool },
    Extract { archive: std::path::PathBuf, #[arg(long)] out: Option<std::path::PathBuf>, #[arg(long)] filter: Option<String>, #[arg(long)] flatten: bool },
    Pack    { input_dir: std::path::PathBuf, out_archive: std::path::PathBuf,
              #[arg(long, value_enum)] game: crate::game::Game,
              #[arg(long, value_enum, default_value_t = crate::game::PackFormat::Gnrl)] format: crate::game::PackFormat,
              #[arg(long, value_enum)] compress: Option<crate::game::Compress>,
              #[arg(long)] strings: bool },
    Capabilities,
}
```

- [ ] **Step 5: Write `src/main.rs` (dispatch stub)**
```rust
mod cli; mod game; mod model; mod error; mod archive;
mod cmd_info; mod cmd_list; mod cmd_extract; mod cmd_pack; mod cmd_caps;
use clap::Parser;

fn main() {
    let cli = cli::Cli::parse();
    let code = match run(&cli) {
        Ok(()) => 0,
        Err(e) => { error::emit(&e, cli.json); 1 }
    };
    std::process::exit(code);
}

fn run(cli: &cli::Cli) -> Result<(), error::AppError> {
    match &cli.command {
        cli::Command::Info { archive } => cmd_info::run(archive, cli.json),
        cli::Command::List { archive, filter, long } => cmd_list::run(archive, filter.as_deref(), *long, cli.json),
        cli::Command::Extract { archive, out, filter, flatten } => cmd_extract::run(archive, out.as_deref(), filter.as_deref(), *flatten, cli.json),
        cli::Command::Pack { input_dir, out_archive, game, format, compress, strings } =>
            cmd_pack::run(input_dir, out_archive, *game, *format, *compress, *strings, cli.json),
        cli::Command::Capabilities => cmd_caps::run(cli.json),
    }
}
```
(Modules referenced are created in later tasks; until then stub each `cmd_*::run` to `Ok(())` and `game`/`model`/`error`/`archive` minimally so it compiles — implement fully in their tasks.)

- [ ] **Step 6: Run, expect PASS** — `cargo test --test cli_smoke`.
- [ ] **Step 7: Commit** — `git add tools/bgs-archive && git commit -m "feat(bgs-archive): cargo scaffold + clap CLI skeleton"`

---

## Task A2: error.rs + model.rs

**Files:** Create `src/error.rs`, `src/model.rs`

- [ ] **Step 1: Write `src/error.rs`**
```rust
use thiserror::Error;

#[derive(Error, Debug)]
pub enum AppError {
    #[error("io error: {0}")] Io(#[from] std::io::Error),
    #[error("tes3 archive error: {0}")] Tes3(#[from] ba2::tes3::Error),
    #[error("tes4 archive error: {0}")] Tes4(#[from] ba2::tes4::Error),
    #[error("fo4 archive error: {0}")] Fo4(#[from] ba2::fo4::Error),
    #[error("unsupported: {0}")] Unsupported(String),
    #[error("not found: {0}")] NotFound(String),
    #[error("json error: {0}")] Json(#[from] serde_json::Error),
}
impl AppError {
    pub fn code(&self) -> &'static str {
        match self {
            AppError::Io(_) => "io_error",
            AppError::Tes3(_) | AppError::Tes4(_) | AppError::Fo4(_) => "archive_error",
            AppError::Unsupported(_) => "unsupported",
            AppError::NotFound(_) => "not_found",
            AppError::Json(_) => "json_error",
        }
    }
}
pub fn emit(e: &AppError, json: bool) {
    if json {
        let env = crate::model::Envelope::<()>::err(e.code(), &e.to_string(), "");
        println!("{}", serde_json::to_string(&env).unwrap());
    } else {
        eprintln!("error [{}]: {}", e.code(), e);
    }
}
```

- [ ] **Step 2: Write `src/model.rs`** (the Envelope + info structs from `01-architecture.md` §JSON contract). Add constructors:
```rust
use serde::Serialize;
#[derive(Serialize)]
pub struct Envelope<T> { pub ok: bool, pub tool: &'static str, pub command: &'static str,
    pub data: Option<T>, pub error: Option<ErrEnvelope> }
#[derive(Serialize)]
pub struct ErrEnvelope { pub code: String, pub message: String }
impl<T: Serialize> Envelope<T> {
    pub fn ok(command: &'static str, data: T) -> Self {
        Self { ok: true, tool: "bgs-archive", command, data: Some(data), error: None }
    }
    pub fn err(code: &str, message: &str, command: &'static str) -> Self {
        Self { ok: false, tool: "bgs-archive", command, data: None,
            error: Some(ErrEnvelope { code: code.into(), message: message.into() }) }
    }
}
#[derive(Serialize)] pub struct ArchiveInfo { pub path: String, pub family: String, pub version: Option<u32>, pub format: Option<String>, pub compression: Option<String>, pub entry_count: usize }
#[derive(Serialize)] pub struct EntryInfo { pub path: String, pub size: u64, pub compressed: bool }
```
- [ ] **Step 3: `cargo build`** -> compiles.
- [ ] **Step 4: Commit** — `git commit -am "feat(bgs-archive): error + JSON model"`

---

## Task A3: game.rs mapping (unit tested)

**Files:** Create `src/game.rs`, test inline.

- [ ] **Step 1: Write failing unit test** (inline `#[cfg(test)]` in game.rs)
```rust
#[test]
fn starfield_maps_to_fo4_v2_gnrl() {
    let g = Game::Starfield;
    assert_eq!(g.family(), Family::Fo4);
    assert_eq!(g.fo4_version(), Some(ba2::fo4::Version::v2));
}
#[test]
fn skyrimse_maps_to_tes4_v105() {
    assert_eq!(Game::Skyrimse.tes4_version(), Some(ba2::tes4::Version::v105));
}
```
- [ ] **Step 2: Run, expect FAIL** — `cargo test game`.
- [ ] **Step 3: Implement `src/game.rs`** — `Game`, `PackFormat`, `Compress` `ValueEnum`s + `Family` + mapping per `01-architecture.md` table (TES4 aliases v103/104/105; fo4 v1/v2/v7; defaults). Map `PackFormat::{Gnrl,Dx10}` -> `ba2::fo4::Format`, `Compress::{Zip,Lz4,None}` -> `ba2::fo4::CompressionFormat`.
- [ ] **Step 4: Run, expect PASS** — `cargo test game`.
- [ ] **Step 5: Commit** — `git commit -am "feat(bgs-archive): game->ba2 version/format mapping"`

---

## Task A4: archive.rs open_any (auto-detect)

**Files:** Create `src/archive.rs`, `tests/fixtures.rs`

- [ ] **Step 1: Write failing test** — `tests/fixtures.rs` builds an in-memory fo4 GNRL archive (cheat-sheet §3 write example), writes to temp, then `bgs_archive::archive::open_any(path)` returns `AnyArchive::Fo4`.
```rust
// build via ba2, write temp .ba2, then:
let a = bgs_archive::archive::open_any(tmp.path()).unwrap();
assert!(matches!(a, bgs_archive::archive::AnyArchive::Fo4(..)));
```
(Expose modules via `src/lib.rs` re-export so tests can call them; add `[lib]` + `[[bin]]` to Cargo.toml.)
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement `src/archive.rs`** — `AnyArchive` enum + `open_any` using `ba2::guess_format` on a `BufReader`, branch to `tes3/tes4/fo4 ::Archive::read(path)` (cheat-sheet §6 skeleton). Add `entries(&self) -> Vec<EntryInfo>` that iterates each family's archive (fo4: `archive.iter()` keys; tes4: nested directory/file iter; tes3: `archive.iter()`), reporting path/size/compressed.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git commit -am "feat(bgs-archive): auto-detect open_any + entry iteration"`

---

## Task A5: cmd_info

**Files:** Create `src/cmd_info.rs`
- [ ] **Step 1: Failing test** (in `tests/fixtures.rs`): run `bgs-archive info <tmp.ba2> --json`, assert `data.family == "fo4"`, `data.version == 2` for a v2 archive.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** — `open_any`, derive `ArchiveInfo` (family string, version from `meta.version() as u32`, format/compression for fo4 from `meta.format()`/`meta.compression_format()`), print `Envelope::ok("info", info)` as JSON or human table.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit.**

---

## Task A6: cmd_list (+ --filter glob)
**Files:** `src/cmd_list.rs`
- [ ] **Step 1: Failing test**: pack a 2-file fixture, `list --json` returns 2 entries; `list --filter "*.txt"` returns 1.
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implement** — `open_any().entries()`, optional `globset::Glob` filter on entry path, emit `Vec<EntryInfo>`.
- [ ] **Step 4: PASS.**  **Step 5: Commit.**

---

## Task A7: cmd_extract
**Files:** `src/cmd_extract.rs`
- [ ] **Step 1: Failing test**: pack fixture with `dir/hello.txt` containing `b"Hello world!\n"`, extract to temp dir, assert extracted file bytes equal the original.
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implement** — `open_any`; for each entry (optionally glob-filtered): build output path under `--out` (preserve archive-internal path unless `--flatten`), create parent dirs, open file handle, call `file.write(&mut dst, &options)` where `options` is `meta.into()` per family (fo4 `FileWriteOptions`, tes4 `FileCompressionOptions`, tes3 no options) — cheat-sheet §3/§4/§5 verbatim extract examples. Emit count + output dir.
- [ ] **Step 4: PASS.**  **Step 5: Commit.**

---

## Task A8: cmd_pack (tes3 / tes4 / fo4 GNRL)
**Files:** `src/cmd_pack.rs`
- [ ] **Step 1: Failing test**: create a temp input dir with `sub/a.txt` + `b.bin`; `pack --game fallout4`; reopen result; assert both entries present with correct payloads.
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implement** — `walkdir` the input dir; compute archive-internal key from relative path (forward slashes; Starfield requires `/`). Branch by `game.family()`:
  - fo4: build `ba2::fo4::File` from `Chunk::from_decompressed(bytes)`, insert under `ArchiveKey::from(rel_bytes)`, build `ArchiveOptions::builder().format(..).version(game.fo4_version()).compression_format(..).strings(true).build()`, `archive.write(&mut out, &opts)` (cheat-sheet §3). **`.strings(true)` is MANDATORY** — verified in A4: FO4 only writes the file-name string table when `strings()` is true; without it `extract`/`list` cannot recover entry paths (they fall back to `<hash:...>`). The `--strings`/`strings: bool` CLI flag should DEFAULT to true for fo4 packing; only set false for size-optimized hash-only archives where the caller knows names aren't needed.
  - tes4: build `Directory`/`File::from_decompressed`, group by top-level dir into `ArchiveKey`, `ArchiveOptions::builder().types(..).version(game.tes4_version()).build()` (cheat-sheet §4).
  - tes3: `File` from bytes, `archive.write(&mut out)` no options (cheat-sheet §5).
  - `--format dx10` -> return `AppError::Unsupported("dx10_pack")` for now (Task A-DX10).
- [ ] **Step 4: PASS.**  **Step 5: Commit.**

---

## Task A9: cmd_caps (self-description)
**Files:** `src/cmd_caps.rs`
- [ ] **Step 1: Failing test**: `capabilities --json` -> `data.ba2_version == "3.0.1"`, `data.games` contains `"starfield"`, `data.write_support.dx10 == false`.
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implement** — static descriptor struct (tool version, ba2 version, games[], subcommands[] with arg names, read/write coverage matrix).
- [ ] **Step 4: PASS.**  **Step 5: Commit.**

---

## Task A10: integration round-trip
**Files:** `tests/cli_roundtrip.rs` (assert_cmd)
- [ ] **Step 1: Write test**: input dir -> `pack --game starfield` -> `list --json` (assert entries) -> `extract` -> byte-compare payloads. Repeat for `--game skyrimse` (tes4 v105) and `--game fallout4` (fo4 v1).
- [ ] **Step 2: Run; fix any wiring until PASS.**
- [ ] **Step 3: Commit.**

---

## Task A11: semantic E2E vs real archives (BINDING acceptance) — CLI-only, no GUI oracle
**Files:** `tests/real_archive.rs` (`#[ignore]`) + `scripts/run-a11-real-archive-acceptance.ps1`
> NOTE: the original plan called for a BSArch.exe byte-compare oracle. That was abandoned — the only BSArch on this machine is the GUI `BSArchPro.exe`, which hangs bash; no CLI archive oracle exists. The acceptance is therefore tool-free: structural validity + self-consistency round-trip (catches the same decompression/fidelity bug classes an external oracle would).
- [ ] **Step 1: Write `#[ignore]` test / pwsh harness** reading real fixture paths; for each fixture: `info`/`list` (assert family/version), `extract`, then **structural-validate** each extracted file (format magic by extension + size consistent with `list`).
- [ ] **Step 2: Self-consistency round-trip**: repack the extracted tree with our own tool, re-extract, assert byte-identical (SHA256) to the first extraction.
- [ ] **Step 3: Run manually** against a real FO4 BA2 + a real Skyrim BSA from `.opencode/artifacts/archive-papyrus-tools/fixtures/`.
- [ ] **Step 4: Record evidence** under `.opencode/artifacts/archive-papyrus-tools/acceptance/` (structural + SHA256 round-trip verdict). This is the acceptance gate, not `cargo test` alone.
- [ ] **Step 5: Commit** the test/harness (evidence dir is git-ignored artifact). NEVER launch a GUI tool.

---

## Task A-DX10 (deferred / stretch): DX10 texture pack
- [ ] Re-fetch `fo4::DX10Header` / `fo4::GNMFHeader` field layout (cheat-sheet §8 UNVERIFIED) before any code.
- [ ] Parse input `.dds` header -> populate `FileHeader::DX10(DX10Header{..})`, slice mips into `Chunk`s with `mips` ranges, write with `Format::DX10`. Gate behind a passing real-DX10 self-consistency round-trip (extract → repack → re-extract byte-identical) + DDS structural validation (valid `DDS ` magic + header dimensions preserved). No external GUI oracle.

---

## Task A12: README + skill + materialize
**Files:** `tools/bgs-archive/README.md`, `skills/using-bgs-archive/SKILL.md`, edit `scripts/build-portable-plugin.ps1`, edit `skills/using-bgs-modding-superpowers/SKILL.md`
- [ ] **Step 1:** Write README (install via Release download, subcommands, JSON contract, coverage matrix, the BA2/BSA version table).
- [ ] **Step 2:** Write `using-bgs-archive` skill (when to use, the `capabilities`-first pattern, every subcommand with an example, hard rule: never write into game Data, route pack output as MO2 overlay).
- [ ] **Step 3:** Add `tools/bgs-archive/` (source only; exclude `target/`) to `build-portable-plugin.ps1` materialize set; add `using-bgs-archive` row to the bootstrap skill table.
- [ ] **Step 4:** Run `pwsh scripts/build-portable-plugin.ps1 -OutputDir plugins -PluginName bgs-modding-superpowers -McpPathStrategy relative -Force`; verify materialized tree.
- [ ] **Step 5:** Two commits (source+skill; then materialized plugin tree) per repo convention.

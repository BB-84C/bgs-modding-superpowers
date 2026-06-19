# bgs-papyrus

`bgs-papyrus` is an agent-native CLI for Papyrus source and bytecode work. It detects the local Papyrus toolchain, compiles `.psc` to `.pex` through the user-installed Creation Kit compiler, and decompiles `.pex` to `.psc` through Champollion.

It does not ship Bethesda tools. The official Creation Kit and `PapyrusCompiler.exe` must be installed by the user from Steam. `bgs-papyrus` detects those tools and drives them from a repeatable command-line surface.

## Install

Development checkout:

```powershell
cd D:\awesome-bgs-mod-master\tools\bgs-papyrus
pipx install -e .
bgs-papyrus capabilities --json
```

If you run from source without installing:

```powershell
cd D:\awesome-bgs-mod-master\tools\bgs-papyrus
python -m bgs_papyrus.cli --json capabilities
```

## Game and flags-file matrix

| Game argument | Papyrus support | Official flags file | Compiler path notes |
|---|---:|---|---|
| `skyrimle` | yes | `TESV_Papyrus_Flags.flg` | CK compiler under the game folder's `Papyrus Compiler\PapyrusCompiler.exe`. |
| `skyrimse` | yes | `TESV_Papyrus_Flags.flg` | CK compiler under the game folder's `Papyrus Compiler\PapyrusCompiler.exe`. |
| `fallout4` | yes | `Institute_Papyrus_Flags.flg` | CK compiler under the game folder's `Papyrus Compiler\PapyrusCompiler.exe`. |
| `starfield` | yes | `Starfield_Papyrus_Flags.flg` | CK compiler is normally under `<Starfield>\Tools\Papyrus Compiler\PapyrusCompiler.exe`. |

Fallout 3, Fallout: New Vegas, and Oblivion do not use Papyrus and are out of scope for this tool.

## Detect-first pattern

Start every workflow by asking the live tool what it can see:

```powershell
bgs-papyrus capabilities --json
bgs-papyrus detect-toolchain --json --game starfield
```

Example JSON shape:

```json
{"ok":true,"tool":"bgs-papyrus","command":"detect-toolchain","data":{"game":"Starfield","compiler":{"found":true,"path":"D:\\SteamLibrary\\steamapps\\common\\Starfield\\Tools\\Papyrus Compiler\\PapyrusCompiler.exe"}},"error":null}
```

If detection cannot find the Creation Kit compiler, install the relevant Creation Kit from Steam or pass explicit paths where the CLI supports them. Do not copy Bethesda compiler files into this repository or into the plugin tree.

## Commands

Run `bgs-papyrus --help` and `<subcommand> --help` for the live option surface. Add `--json` to any command for an agent-readable envelope.

### `capabilities`

Report supported games, subcommands, compile/decompile backends, flags files, and Starfield syntax handling.

```powershell
bgs-papyrus capabilities --json
```

Example JSON shape:

```json
{"ok":true,"tool":"bgs-papyrus","command":"capabilities","data":{"games":["skyrimle","skyrimse","fallout4","starfield"],"backends":{"compile":["ck","caprica","russo"],"decompile":["champollion"]}},"error":null}
```

### `detect-toolchain [--game G]`

Find the installed compiler and decompiler tools.

```powershell
bgs-papyrus detect-toolchain --json --game fallout4
bgs-papyrus detect-toolchain --json
```

### `compile <src> --game G`

Compile one script or, with `--all`, compile all scripts in a directory. The default backend is `auto`, which prefers the official Creation Kit compiler when available. `caprica` and `russo` are non-Guard fallbacks; they are not the validated Starfield Guard path.

```powershell
bgs-papyrus compile "D:\work\Scripts\Source\MyQuestScript.psc" --json --game starfield --out "D:\work\out" --import "D:\work\Scripts\Source"
```

Useful options:

- `--out <dir>`: output directory for `.pex` files.
- `--import <dir>`: additional source import directory. Repeat for multiple imports.
- `--backend ck|caprica|russo|auto`: compiler backend.
- `--flags <file>`: explicit flags file.
- `--optimize`, `--release`, `--final`, `--all`: passed through to the compiler path where supported.

When the compiled `.pex` is game-local content, write it to an MO2 mod overlay such as `<MO2_Root>\mods\My Script Patch\Scripts\`. Never write it directly to the game's `Data` folder.

### `decompile <src> --game G`

Decompile `.pex` bytecode to `.psc` source through Champollion.

```powershell
bgs-papyrus decompile "D:\mods\Example\Scripts\MyQuestScript.pex" --json --game starfield --out "D:\work\decompiled"
```

Useful options:

- `--out <dir>`: output directory for decompiled `.psc` files.
- `--recursive`: decompile a directory tree.
- `--threaded`: ask Champollion to use threaded decompile where supported.
- `--sf-syntax-fix` / `--no-sf-syntax-fix`: enable or disable Starfield syntax post-processing.

Champollion is detected, not auto-downloaded. Install `Champollion.exe` at `~/.bgs-modding-superpowers/tools/champollion/Champollion.exe`, or set `BGS_PAPYRUS_CHAMPOLLION` to an existing executable.

One PowerShell install shape for Champollion v1.3.2 from `Orvid/Champollion` releases:

```powershell
$root = "$HOME\.bgs-modding-superpowers\tools\champollion"; New-Item -ItemType Directory -Force -Path $root | Out-Null; $zip = Join-Path $root "Champollion.v1.3.2.zip"; Invoke-WebRequest "https://github.com/Orvid/Champollion/releases/download/v1.3.2/Champollion.v1.3.2.zip" -OutFile $zip; Expand-Archive -Force $zip $root
```

## Starfield Guard syntax

Champollion v1.3.2 guesses Starfield Guard syntax as `Guard ... EndGuard` and `TryGuard ... EndGuard`. The official Creation Kit syntax is different. For Starfield decompile output, `bgs-papyrus` applies a validation-gated `starfield_syntax` post-process:

| Champollion guess | Official Starfield syntax |
|---|---|
| `Guard ... EndGuard` | `LockGuard ... EndLockGuard` |
| `TryGuard ... EndGuard` | `TryLockGuard ... EndTryLockGuard` |

This rewrite is empirically grounded and recompile-validated against the real Starfield Creation Kit. Constructs that are not proved should remain explicit instead of being silently rewritten.

## Known limitation

Champollion v1.3.2 has unrelated decompile bugs, including remote-event casts, that can prevent some complex vanilla scripts from recompiling cleanly. Decompiled output is a strong starting point, not a guarantee that every upstream Champollion construct is immediately publishable. The Starfield Guard post-processor is validated; these remaining gaps are upstream Champollion limitations and may need manual fixup.

## Verified coverage

- CLI unit suite: 26 tests passed in the implementation track.
- Real Starfield compile: Chronomark fixture scripts compiled through the official CK compiler.
- Compile readback: generated `.pex` files matched the original CK output by byte size for the verified fixture.
- Real Starfield decompile: Champollion decompile plus Guard syntax post-processing was recompile-validated through the official CK compiler.

## License

MIT. Authored by BB-84C as part of `bgs-modding-superpowers`.

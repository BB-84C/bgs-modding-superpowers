# bgs-archive

`bgs-archive` is an agent-native BA2/BSA inspection, extraction, and packing CLI for Bethesda Game Studios archives. It is designed for modpack automation: detect archive family/version, list entries, extract assets, pack supported archive families, and return machine-readable JSON envelopes for agent workflows.

## Install

Release binary:

```powershell
# Download the GitHub Release asset named bgs-archive-vX.Y.Z for your platform,
# verify its SHA256, then place it under the tool cache.
$version = "vX.Y.Z"
$toolRoot = "$env:USERPROFILE\.bgs-modding-superpowers\tools\bgs-archive\$version"
New-Item -ItemType Directory -Force -Path $toolRoot | Out-Null
# Copy the verified bgs-archive.exe into $toolRoot.
```

Binary is distributed via GitHub Release `bgs-archive-vX.Y.Z` (download + sha256-verify into `~/.bgs-modding-superpowers/tools/bgs-archive/<version>/`); or build from source with `cargo build --release`.

Development checkout:

```powershell
cd D:\awesome-bgs-mod-master\tools\bgs-archive
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
cargo build --release
target\release\bgs-archive.exe capabilities --json
```

## Archive family matrix

| Games | Container | Versions detected/read | Compression notes |
|---|---|---:|---|
| Morrowind | BSA / TES3 family | n/a | Uncompressed TES3 BSA entries. |
| Oblivion | BSA / TES4 family | v103 | zlib-style BSA compression metadata. |
| Fallout 3, Fallout: New Vegas, Skyrim LE | BSA / TES4 family | v104 | zlib-style BSA compression metadata. |
| Skyrim SE / AE | BSA / TES4 family | v105 | LZ4-style BSA compression metadata. |
| Fallout 4 | BA2 / FO4 family | v1 GNRL/DX10 | Zip or LZ4 as reported by the BA2 header. |
| Fallout 4 Next-Gen | BA2 / FO4 family | v7/v8 GNRL/DX10/GNMF | Read/extract supported; pack emits GNRL only. |
| Fallout 76 | BA2 / FO4 family | v1 GNRL/DX10 | Zip or LZ4 as reported by the BA2 header. |
| Starfield | BA2 / FO4 family | v2 GNRL, v3 DX10 | Read/extract supported; pack emits GNRL v2 only. |

## Commands

Run `bgs-archive --help` or any subcommand's `--help` for the live option surface. Add `--json` to any command for an agent-readable envelope. Writes into detected game `Data` directories are refused by default; use an MO2 mod overlay, or pass the global `--allow-game-data` override deliberately.

### `info`

Detect archive family, version, format, compression, and entry count.

```powershell
bgs-archive --json info "D:\mods\Example - Main.ba2"
```

Example JSON shape:

```json
{"ok":true,"tool":"bgs-archive","command":"info","data":{"path":"D:\\mods\\Example - Main.ba2","family":"fo4","version":1,"format":"GNRL","compression":"Zip","entry_count":42},"error":null}
```

### `list`

List archive entries. Use `--filter` with a glob and `--long` for sizes and compression flags.

```powershell
bgs-archive --json list "D:\mods\Example - Main.ba2" --filter "textures/**/*.dds" --long
```

Example JSON shape:

```json
{"ok":true,"tool":"bgs-archive","command":"list","data":[{"path":"textures/example/diffuse.dds","size":4096,"compressed":true}],"error":null}
```

### `extract`

Extract all entries or a filtered subset. Use `--flatten` only for deliberate flat-output workflows. `--out` is guarded against direct writes into game `Data` directories unless `--allow-game-data` is passed.

```powershell
bgs-archive --json extract "D:\mods\Example - Main.ba2" --out "D:\work\extract" --filter "meshes/**/*.nif"
```

Example JSON shape:

```json
{"ok":true,"tool":"bgs-archive","command":"extract","data":{"output_dir":"D:\\work\\extract","extracted_count":1,"paths":["meshes/example/static.nif"]},"error":null}
```

### `pack`

Pack a directory into a supported BSA/BA2 output. Pack outputs should go into an MO2 mod overlay, not into a game `Data` folder; protected game `Data` outputs are refused unless `--allow-game-data` is passed.

```powershell
$overlay = "D:\ModOrganizer\mods\My Packed Assets"
bgs-archive --json pack "$overlay\source-assets" "$overlay\Data\MyPackedAssets - Main.ba2" --game fallout4 --format gnrl --compress zip
```

Example JSON shape:

```json
{"ok":true,"tool":"bgs-archive","command":"pack","data":{"out_archive":"D:\\ModOrganizer\\mods\\My Packed Assets\\Data\\MyPackedAssets - Main.ba2","family":"fo4","version":1,"entry_count":12},"error":null}
```

### `capabilities`

Query the live binary before choosing a game/format combination.

```powershell
bgs-archive --json capabilities
# Alias:
bgs-archive --json caps
```

Example JSON shape:

```json
{"ok":true,"tool":"bgs-archive","command":"capabilities","data":{"tool":"bgs-archive","version":"0.1.0","ba2_version":"3.0.1","games":["morrowind","oblivion","fallout3","falloutnv","skyrimle","skyrimse","fallout4","fallout4ng","fallout76","starfield"],"write_support":{"tes3":true,"tes4":true,"fo4_gnrl":true,"dx10":false,"gnmf":false},"read_support":{"all_families":true}},"error":null}
```

## JSON envelope contract

Every `--json` command writes one JSON object to stdout:

```json
{
  "ok": true,
  "tool": "bgs-archive",
  "command": "info",
  "data": {},
  "error": null
}
```

Failures keep the same envelope shape where the CLI can classify the failure:

```json
{
  "ok": false,
  "tool": "bgs-archive",
  "command": "pack",
  "data": null,
  "error": { "code": "unsupported", "message": "dx10_pack not yet supported (Task A-DX10)" }
}
```

Agents should branch on `ok`, then inspect `data` or `error.code`; do not parse human text.

## Coverage

| Family / format | Read | Extract | Pack/write |
|---|---:|---:|---:|
| TES3 / Morrowind BSA | yes | yes | yes |
| TES4 BSA v103 | yes | yes | yes |
| TES4 BSA v104 | yes | yes | yes |
| TES4 BSA v105 | yes | yes | yes |
| FO4-family BA2 GNRL v1 | yes | yes | yes |
| FO4-family BA2 GNRL v2 | yes | yes | yes |
| FO4-family BA2 GNRL v7/v8 | yes | yes | yes |
| FO4-family BA2 DX10 | yes | yes | no |
| FO4-family BA2 GNMF | yes | yes | no |

DX10/GNMF packing is intentionally unsupported in this version and returns an `unsupported` error. Extract works for those archive formats.

## Testing status

Real-archive read, format detection, JSON command smoke tests, and self-consistency pack/list/extract round-trips are verified in the acceptance evidence. The real-archive gate is structural validity (magic bytes, size, metadata, entry list) plus self-consistency extraction/repack/re-extraction on staged archives; there is no external byte-compare oracle in this environment because BSArchPro/BSAArchivePro is GUI-only here. Large-compressed-entry decompression relies on the upstream `ba2` crate.

## License

MIT. Authored by BB-84C as part of `bgs-modding-superpowers`.

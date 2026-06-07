# 02 — Parser and Coverage

## Architectural split

Bethesda's plugin format family splits at one boundary: **Morrowind (TES3) vs everything else (TES4-family)**. These have fundamentally different binary structures.

We implement two parsers:
- `parsers/tes3.py` — Morrowind only
- `parsers/tes4_family.py` — Oblivion, FO3, FNV, Skyrim LE/SE/AE/VR, FO4/VR, FO76, Starfield

Per-game schema modules under `parsers/schemas/` register subrecord typing tables. The TES4-family walker is one generic record/group walker; the per-game schema tells it which subrecords contain translatable strings.

---

## 1. TES4-family parser (`parsers/tes4_family.py`)

### 1.1 Format overview

The TES4-family format (Oblivion 2006 onward):

```
+--------------------------------+
| TES4 record (file header)      |
|   header signature             |
|   form version                 |
|   flags (incl. Localized bit)  |
|   masters list                 |
|   ...                          |
+--------------------------------+
| GRUP 1                         |
|   header (size includes self)  |
|   contained records...         |
|     RECORD                     |
|       header (24 bytes)        |
|       subrecords...            |
|         SUBRECORD              |
|           header (6 bytes:     |
|             type + uint16 size)|
|           data                 |
|         SUBRECORD              |
|         ...                    |
|     RECORD                     |
|   nested GRUPs (cells, etc.)   |
+--------------------------------+
| GRUP 2                         |
| ...                            |
+--------------------------------+
```

### 1.2 Critical TES4-family details

- **GRUP header size includes the header itself**. Walking past GRUP requires reading 4 more bytes than the size suggests if the implementation isn't careful.
- **Record header is 24 bytes**: type (4), data size (4), flags (4), formid (4), version control (4), form version (2), version control 2 (2).
- **Subrecord header is 6 bytes**: type (4) + uint16 size.
- **`XXXX` overflow**: when a subrecord size exceeds 65535 bytes, the subrecord is preceded by an `XXXX` record carrying a uint32 size in its data; the next subrecord's uint16 size is ignored. Common in FO4/Starfield with large scripts and complex VMAD.
- **Compressed records**: flag `0x40000` indicates the record's data is zlib-deflated. Decompress before walking subrecords.
- **ESL flag**: `0x0200` on TES4 header indicates light plugin. FormIDs are restricted to `0xFExxxYYY` where `xxx` is install-specific (per Skyrim Creation Club).
- **Localized flag**: `0x80` on TES4 header indicates the plugin uses external STRINGS files; `lstring`-typed subrecords contain a 4-byte string ID instead of an inline zstring.

### 1.3 The walker

```python
class TES4FamilyWalker:
    def __init__(self, plugin_path: Path, schema: GameSchema):
        self.f = open(plugin_path, "rb")  # mmap for large plugins
        self.schema = schema
        self.is_localized = False  # set by header parser
        self.masters = []          # set by header parser
        self.eslified = False      # set by header parser
        
    def walk(self) -> Iterator[Record]:
        # 1. Parse TES4 header
        self._parse_tes4_header()
        # 2. Walk top-level GRUPs
        while not self._eof():
            yield from self._walk_grup()
    
    def _walk_grup(self) -> Iterator[Record]:
        grup_type, grup_size, grup_label = self._read_grup_header()
        end = self.f.tell() + grup_size - 24  # header is 24 bytes
        while self.f.tell() < end:
            sig = self._peek_signature()
            if sig == b"GRUP":
                yield from self._walk_grup()
            else:
                yield self._read_record()
    
    def _read_record(self) -> Record:
        sig, data_size, flags, formid, vc1, fv, vc2 = self._read_record_header()
        data = self.f.read(data_size)
        if flags & 0x40000:
            data = zlib.decompress(data)
        subrecords = self._parse_subrecords(data)
        return Record(sig, formid, flags, fv, subrecords)
    
    def _parse_subrecords(self, data: bytes) -> list[Subrecord]:
        # Handle XXXX overflow, per-game schema typing
        ...
```

### 1.4 cpTranslate-flagged subrecord extraction

For each Record yielded, the schema module tells us which subrecord fields are translatable:

```python
class GameSchema(Protocol):
    name: str  # "Skyrim SE", "Fallout 4", etc.
    
    def get_translatable_subrecords(self, record_sig: str) -> list[TranslatableField]:
        """For a given record sig, return the list of cpTranslate-flagged subrecord fields."""
        ...
    
@dataclass(frozen=True)
class TranslatableField:
    subrecord_sig: str    # "FULL", "DESC", etc.
    list_index: int       # 0=STRINGS, 1=DLSTRINGS, 2=ILSTRINGS
    multi_value: bool     # True if subrecord can repeat (e.g. ITXT in MESG, NNAM in QUST)
    byte_budget: int      # per-field engine limit (default 65520; smaller for specific fields)
    notes: str            # human-readable note (e.g. "voice-linked")
```

The extractor calls `schema.get_translatable_subrecords(record.sig)` for each record; iterates over matching subrecords; produces `TranslationUnit` per field instance.

---

## 2. TES3 parser (`parsers/tes3.py`)

### 2.1 Format overview

Morrowind plugins are fundamentally different:

```
+--------------------------------+
| TES3 record (file header)      |
|   "TES3" signature             |
|   dataSize (uint32)            |
|   unused (4)                   |
|   flags (4)                    |
|   subrecords (HEDR, MAST, ...) |
+--------------------------------+
| RECORD 1 (no GRUPs!)           |
|   type (4 bytes)               |
|   dataSize (uint32)            |
|   unused (4)                   |
|   flags (4)                    |
|   subrecords...                |
|     SUBRECORD                  |
|       type (4)                 |
|       size (uint32)            |  ← uint32, not uint16
|       data                     |
+--------------------------------+
| RECORD 2                       |
| ...                            |
+--------------------------------+
```

Key differences from TES4:
- No GRUP records; flat record sequence after TES3 header
- Subrecord size is `uint32`, not `uint16`. No XXXX overflow scheme.
- No FormID. Records are identified by their `NAME` subrecord (typically the editor ID).
- No compression at the record level.
- No localized STRINGS files. All translatable text is inline.
- `DELE` subrecord marks a record for deletion (not a header flag).

### 2.2 The walker

```python
class TES3Walker:
    def __init__(self, plugin_path: Path, schema: MorrowindSchema):
        self.f = open(plugin_path, "rb")
        self.schema = schema
    
    def walk(self) -> Iterator[Record]:
        self._parse_tes3_header()
        while not self._eof():
            yield self._read_record()
    
    def _read_record(self) -> Record:
        sig, data_size, _, flags = self._read_record_header()
        data = self.f.read(data_size)
        subrecords = self._parse_subrecords_tes3(data)
        # Morrowind: identity via NAME subrecord
        name = next((s.data.decode("windows-1252") for s in subrecords if s.sig == "NAME"), None)
        return Record(sig=sig, identity=name, flags=flags, subrecords=subrecords)
```

### 2.3 Morrowind translatable inventory

Morrowind's schema (`parsers/schemas/morrowind.py`) is significantly different. Translatable fields are typically `FNAM` (Name), `DESC` (Description), `BNAM` (dialog response), and INFO-record text fields.

Mapping `TranslatableField` to Morrowind doesn't use `list_index` 0/1/2 (no STRINGS family). We use `list_index = 0` as a placeholder and document in the schema that Morrowind output is inline.

---

## 3. Per-game schema modules

Each game has a schema module under `parsers/schemas/`. The module:
1. Imports `cpTranslate`-flagged subrecord data from a YAML manifest (machine-generated from xEdit's `wbDefinitions<GAME>.pas`)
2. Provides per-record-sig translation field lookups
3. Knows per-game form version ranges (for game detection)

### 3.1 cpTranslate slice extraction

Source: xEdit's `wbDefinitions<GAME>.pas` files under `https://github.com/TES5Edit/TES5Edit/tree/master/`.

A one-time extraction script (`scripts/extract_cptranslate.py`) processes each `.pas` file and emits a YAML manifest:

```yaml
# parsers/schemas/data/skyrim_se.yaml
game: SkyrimSE
form_version_range: [43, 44]

records:
  WEAP:
    FULL:
      list_index: 0
      byte_budget: 65520
      multi_value: false
    DESC:
      list_index: 1
      byte_budget: 65520
      multi_value: false
  
  ARMO:
    FULL: { list_index: 0, byte_budget: 65520, multi_value: false }
    DESC: { list_index: 1, byte_budget: 65520, multi_value: false }
  
  INFO:
    NAM1: { list_index: 2, byte_budget: 65520, multi_value: false, notes: "voice-linked" }
    RNAM: { list_index: 0, byte_budget: 512, multi_value: false }
  
  # ... 40+ more records
```

### 3.2 Schema module API

```python
# parsers/schemas/skyrim_se.py
from .base import GameSchema, TranslatableField, load_yaml_manifest

_MANIFEST = load_yaml_manifest(Path(__file__).parent / "data" / "skyrim_se.yaml")

class SkyrimSESchema(GameSchema):
    name = "SkyrimSE"
    form_version_range = (43, 44)
    
    def get_translatable_subrecords(self, record_sig: str) -> list[TranslatableField]:
        return _MANIFEST.records.get(record_sig, [])
    
    def detect_from_form_version(self, fv: int) -> bool:
        return self.form_version_range[0] <= fv <= self.form_version_range[1]
```

### 3.3 Coverage scope per game

We port the cpTranslate slice for the **same** record signatures across games where they appear (FULL, DESC, NAM1, etc.) plus per-game variants:

| Game | Record types covered (target) | Source |
|---|---|---|
| Oblivion | ~30 records, ~50 fields | xEdit `wbDefinitionsTES4.pas` |
| Fallout 3 | ~40 records | `wbDefinitionsFO3.pas` |
| Fallout NV | ~40 records | `wbDefinitionsFNV.pas` |
| Skyrim LE | ~42 records, ~80 fields | `wbDefinitionsTES5.pas` |
| Skyrim SE/AE/VR | Same as LE + ESL handling | `wbDefinitionsTES5.pas` (no separate file) |
| Fallout 4 / VR | ~50 records | `wbDefinitionsFO4.pas` |
| Fallout 76 | ~50 records | `wbDefinitionsFO76.pas` (note: may need contrib branch) |
| Starfield | ~50 records | `wbDefinitionsSF1.pas` |
| Morrowind | ~25 records, ~40 fields | `wbDefinitionsTES3.pas` |

Coverage gaps (record types with translatable fields that don't make it into the initial slice) are tracked in `14-open-questions.md`. They become extension work driven by user-reported translation misses.

### 3.4 Cross-reference with bethkit

bethkit (the Rust library we considered as a dependency and rejected) has a similar but shallower SSE schema. Its source-of-truth is also xEdit's `wbDefinitions`. We do not use bethkit, but we can use its YAML/JSON schema dumps as **cross-check** for our extraction script — if our slice and bethkit's slice disagree for SSE, that's a bug to investigate.

---

## 4. ESL FormID compaction

ESL-flagged plugins (Skyrim SE and beyond) have a restricted FormID space:
- TES4 header flag `0x0200` set
- All non-master FormIDs use the high byte `0xFE` (or similar marker per game)
- Mid-byte slot is install-specific (Creation Club ordering, etc.)

Implications for translation:
- **The FormID is install-specific**. Same plugin on two users' installs may have different FormIDs for the same record.
- Our SST merge key (`sanitize_formid(formid)`, `rhash`, signature, field, index) sanitizes the high byte, so the low 24 bits are stable across installs **as long as ESL slot assignment doesn't reshuffle**.
- xTranslator handles this by preferring EditorID-based matching (rHash from EditorID) over FormID matching. We follow suit.

Per user direction: we do not attempt best-effort alignment across ESL FormID compaction changes. If a mod author changes ESL slot assignment between versions, users should re-translate.

---

## 5. Form version detection

When `xtl project init` runs without explicit `--game`, the tool can attempt detection:

```python
def detect_game_from_form_version(fv: int) -> str | None:
    candidates = []
    for schema_cls in ALL_SCHEMAS:
        if schema_cls.detect_from_form_version(fv):
            candidates.append(schema_cls.name)
    if len(candidates) == 1:
        return candidates[0]
    return None  # ambiguous; user must specify
```

Form version ranges (from Bethesda format research):

| Game | Form version range |
|---|---|
| Skyrim LE | 43 |
| Skyrim SE/AE/VR | 43-44 |
| Fallout 4 / VR | 131 |
| Fallout 76 | 131+ (overlapping FO4) |
| Starfield | 552-576 |
| Oblivion | (no form version field; detected by TES4 header signature) |
| Fallout 3 | (no form version field) |
| Fallout NV | (no form version field) |
| Morrowind | (TES3 header signature; entirely different) |

For ambiguous cases (FO4 vs FO76 overlap, SSE vs SE/AE/VR), tool requires explicit `--game`.

---

## 6. Cache and rescan

### 6.1 Initial parse

On `xtl project init`:
1. Open source plugin
2. Walk → list of Records
3. Extract → list of TranslationUnits
4. Write `sources/<plugin>.cache.bin` (pickle of TranslationUnit list)
5. Write `sources/<plugin>.cache.toml`:
   ```toml
   plugin_sha256 = "..."
   parser_version = "1.0.0"
   schema_version = "skyrim_se-1.0.0"
   extracted_units = 642
   extracted_at = ...
   ```
6. Insert TranslationUnits into `memory.sqlite` with status `untranslated`

### 6.2 Rescan after mod update

On `xtl project rescan`:
1. Recompute plugin SHA256
2. If matches cache.toml: cache hit, no rescan needed
3. If differs: re-walk, re-extract
4. Compute diff against existing memory.sqlite by `(plugin, formid, signature, field, index)` natural key:
   - **Same source**: no change
   - **Different source**: mark existing entry as `incompleteTrans` (partial translation per xTranslator convention)
   - **New entry**: insert with `untranslated`
   - **Removed entry**: keep with `oldData` (orphan) per `bKeepOldData=true` default

Memory.sqlite is not destroyed; orphan preservation is the default.

### 6.3 Parser version change

If `parser_version` in code differs from cache.toml:
- Invalidate cache.bin
- Re-extract from scratch
- Re-merge into memory.sqlite by natural key (preserving translations)

---

## 7. Edge cases and known unknowns

### 7.1 BSA-packed plugins (not in scope)

Plugins inside BSA/BA2 archives are not directly handled. User must extract first (or use xTranslator's BSA tools). This is a future extension.

### 7.2 Master file resolution

We do NOT load masters during parse. The plugin's own translatable content is what we extract; references to master content (e.g., NPC overrides referring to a master-defined name) are not resolved.

If a user wants to translate master-defined names, they translate the master directly.

### 7.3 Form version 0 / unspecified

Some plugins (especially older mods) have form version 0. We treat as compatible with the lowest range of the detected game family.

### 7.4 Encoding mismatches in source plugins

A plugin authored in CP1252 with non-ASCII characters in source text (German, French) decoded as UTF-8 → mojibake.

The TES4 walker tries primary encoding first (per game/locale chain in `04-ai-pipeline.md` §encoding table), falls back to secondary on UTF-8 decode error. Decoded source goes into `TranslationUnit.source` as a valid Python str.

If both fail (rare; usually corrupt plugin), the entry is flagged with `lockedTrans` and `notes: "decode_error"`. User can inspect in xTranslator separately.

---

## 8. Test fixture

The user-provided test fixture: `D:\Starfield MO2\mods\adwryos-cc\adwryos.esm` (~600 translatable entries across diverse signatures).

Tests against this fixture (per `11-acceptance-and-spikes.md` §3) verify:
- Walk completes without parser errors
- Expected signature counts (per signature: WEAP, ARMO, INFO, BOOK, etc.)
- Extracted TranslationUnit count matches xTranslator's view of the same file (cross-tool consistency check)
- cpTranslate-flagged subrecord routing matches xTranslator's `listIndex` assignments

Reference SSTs from `D:\SteamLibrary\steamapps\common\Starfield\Tools\xTranslator-313-1-4-5-alpha-1694868294\_xTranslator\UserDictionaries\Starfield\` provide the diff target for SST emit round-trip tests.

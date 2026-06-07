# 03 — SST Output Spec

The `.sst` file is `bgs-translator`'s **only** deliverable. xTranslator's mature GUI (or ESP-ESM Translator for Morrowind/Oblivion/FO3) consumes it, the user clicks Finalize, the ship-ready mod comes out the other side.

This document is the byte-level spec for what we emit and the conventions for naming, multi-language emission, and dual-GUI workflow.

---

## 1. Binary format (SSU9 / v8)

We **emit** SSU9 (header magic `"SSU9"` = `0x39 0x55 0x53 0x53` on disk reading LE = `0x39555353`). We **read** any version v1..v8 (`SSU2` through `SSU9`) for the rare case of consuming user-supplied dictionaries.

Source: ported from `xTranslator/TESVT_SSTFunc.pas` (`SaveSSTFile` / `loadSstEdit`) and `TESVT_typedef.pas` (`rEspPointerLite`). Confirmed against xTranslator v1.6.0.

### 1.1 File layout (overall)

```
+--------------------------------------------------+
| HEADER                                           |
|   [4]  magic = "SSU9" (0x39 0x55 0x53 0x53)     |
|   [1]  reserved flag byte = 0                    |
+--------------------------------------------------+
| MASTER LIST TABLE                                |
|   [4]  count : Int32 LE                          |
|   for each master:                               |
|     [4]  byte_size : Int32 LE                    |
|     [byte_size]  filename : UTF-16LE             |
+--------------------------------------------------+
| COLAB LABEL TABLE                                |
|   [4]  count : Int32 LE                          |
|   for each colab label:                          |
|     [4]  colabId : Int32 LE                      |
|     [4]  byte_size : Int32 LE                    |
|     [byte_size]  label : UTF-16LE                |
+--------------------------------------------------+
| ENTRIES (until EOF)                              |
|   one entry per translatable string              |
+--------------------------------------------------+
```

All integers little-endian. Strings are UTF-16LE, no BOM, no NUL terminator, byte-length-prefixed.

No compression, no checksum, no footer.

### 1.2 Entry layout

```
[1]   listIndex : Byte             0 = STRINGS, 1 = DLSTRINGS, 2 = ILSTRINGS
[24]  data : rEspPointerLite       see §1.3
[1]   colabId : Byte               0 if not using collaboration features
[4]   sParams : UInt32 LE          status flag bitset, see §1.5
[4]   src_size : Int32 LE          byte count, NOT char count
[src_size]  source : UTF-16LE
[4]   dst_size : Int32 LE
[dst_size]  destination : UTF-16LE
```

### 1.3 `rEspPointerLite` (24 bytes, packed)

```
[4]  strId : Int32 LE          Bethesda localized string ID (for localized plugins), 0 otherwise
[4]  formID : UInt32 LE        FormID (high byte is master index; cleared via sanitizeFormID before hashing)
[4]  rName : 4×AnsiChar        record sig, e.g. "WEAP"
[4]  fName : 4×AnsiChar        subrecord sig, e.g. "FULL"
[2]  index : UInt16 LE         sub-index inside multi-value subrecord, 0 if not applicable
[2]  indexMax : UInt16 LE      total count of sub-items, 0 if not applicable
[4]  rHash : UInt32 LE         stringHash(editorID) or stringHash('[xxxxxxxx]') — see §1.4
```

### 1.4 `stringHash` and `sanitizeFormID`

Two helper functions ported from xTranslator. **These must be bit-exact** or our SST will not match xTranslator's internal lookup. See `11-acceptance-and-spikes.md` §2 for the hex-dump verification spike.

**`sanitizeFormID(formID: int) -> int`** — strips the master-index high byte:

```python
def sanitize_formid(formid: int) -> int:
    return formid & 0x00FFFFFF
```

(Inferred from usage pattern; verify against hex dump of v1.6.0 SST.)

**`stringHash(s: str) -> int`** — xTranslator's per-string hash. Algorithm body lives in `TESVT_Const.pas` implementation; the implementation section was truncated in the research fetch and needs direct source extraction. See spike §2.

**`rHash` value rule**:
- If the record has an EditorID: `rHash = stringHash(editorID)`
- If the record has no EditorID (typically `INFO:NAM1`): `rHash = stringHash('[' + lowercase_8hex(sanitize_formid(formID)) + ']')`

### 1.5 `sParams` status flag bitset

Bits 0..7 (rest must be 0). On disk: `UInt32 LE`. Per xTranslator typedef comment "(size = size of cardinal)". See spike §2 for hex-dump confirmation of 4-byte vs 1-byte representation.

| Bit | Flag | Meaning |
|---|---|---|
| 0 | `translated` | Auto-applied from dictionary/SST without modification (white in xTranslator UI) |
| 1 | `lockedTrans` | Hard-locked: VMAD lock, pexNoTrans, or manual lock (yellow) |
| 2 | `incompleteTrans` | Partial / needs review (pink) — used for source-string-changed entries |
| 3 | `validated` | User-confirmed (blue) — NOT persisted by xTranslator's writer (stripped on save) |
| 4 | (deprecated) | Reserved, do not set |
| 5 | (deprecated) | Reserved, do not set |
| 6 | `oldData` | Orphan: entry was in dictionary but not in current plugin; preserved for round-trip |
| 7 | `pending` | Not-translated entry with collab ID, forced-save |

**Our writer's emit policy**:
- `translated` only → entry was successfully LLM-translated and validated
- `lockedTrans` → entry was pre-skipped (mask stage or heuristic) or explicitly locked by user
- `incompleteTrans` → entry exhausted retry budget; needs manual review in xTranslator
- `oldData` → orphan from a previous version of this mod that no longer exists in current source; we preserve it (configurable)
- `pending`, `validated`, `deprecated*` → never set by our writer

---

## 2. Filename convention

Per xTranslator's `getSSTFileName` logic in `TESVT_SSTFunc.pas`:

```
<plugin-basename>_<source-lang>_<target-lang>.sst
```

Examples:
- `adwryos_english_chinese.sst`
- `requiem_english_french.sst`
- `myskyrimmod_english_zhcn.sst` (if user prefers ISO-style)

Lang slugs we use (driven by `target_lang` in project.toml, normalized for filename):

| Source `target_lang` value | Filename slug |
|---|---|
| `en` | `english` |
| `fr` | `french` |
| `de` | `german` |
| `it` | `italian` |
| `es` | `spanish` |
| `pl` | `polish` |
| `ru` | `russian` |
| `cs` | `czech` |
| `ja` | `japanese` |
| `zh-cn` | `chinese` |

Lang slug mapping is hardcoded for the 10 languages xTranslator's `_xTranslator\UserDictionaries\<Game>\` convention uses. Other locales fall back to raw `<lang>` value.

---

## 3. Starfield 9-fill (default ON for `game = starfield`)

### 3.1 Why this exists

Per `ebkarlson404/CreationKitAuditTool` documentation: from Starfield CK 1.15.222 onward, if a localized plugin ships with missing `.STRINGS / .DLSTRINGS / .ILSTRINGS` for any of the 9 supported languages, players running Starfield in that language see literal "string not found" placeholder text where translated content should be. The engine does **not** fall back to English.

xTranslator's Finalize step is **single-language per invocation** (confirmed via E1 research lane). It will not auto-generate the other 8 language outputs. The community workaround is "manually run Finalize 9 times, dump English text into the 8 non-translation slots." This is a documented footgun.

### 3.2 What we do

For Starfield projects with `starfield_dummy_fill = true` in `project.toml` (default: true):

`xtl project export --format sst` emits **9 SST files**:

| Slot | Content |
|---|---|
| `<plugin>_english_<target>.sst` | Real translation (e.g. `adwryos_english_chinese.sst`) |
| `<plugin>_english_english.sst` | Dummy: dest = source verbatim |
| `<plugin>_english_french.sst` | Dummy: dest = source verbatim |
| `<plugin>_english_german.sst` | Dummy |
| `<plugin>_english_italian.sst` | Dummy |
| `<plugin>_english_spanish.sst` | Dummy |
| `<plugin>_english_polish.sst` | Dummy |
| `<plugin>_english_brazilianportuguese.sst` | Dummy |
| `<plugin>_english_japanese.sst` | Dummy |

User then opens each in xTranslator and clicks Finalize. The result is 9 `Starfield-locale` `.STRINGS / .DLSTRINGS / .ILSTRINGS` triplets in their MO2 overlay mod.

The dummy files copy the source string verbatim into the `destination` field with status `translated`. xTranslator treats them as fully translated; Finalize emits English text into the non-target STRINGS slots; the engine resolves to English text in those locales (gracefully degraded, not crashed).

### 3.3 Opting out

```toml
# in project.toml
starfield_dummy_fill = false
```

Or CLI: `xtl project init ... --no-starfield-dummy-fill`.

When disabled, `xtl project export` emits only the requested SST. A `WARNING` log line + Tk dialog explains: "Disabling dummy-fill means non-Chinese Starfield players will see 'string not found' in your mod. Make sure you handle this manually."

### 3.4 Non-Starfield games

For other games, default is `starfield_dummy_fill = false` (not applicable). Engine fallback semantics differ across games and xTranslator's single-language Finalize is fine without dummy-fill.

---

## 4. Dual-GUI terminal workflow

The user finalizes in one of two GUIs depending on game:

| Game | Recommended terminal GUI | Why |
|---|---|---|
| Skyrim LE | xTranslator (`tesvTranslator`) | Native support |
| Skyrim SE/AE/VR | xTranslator (`sseTranslator`) | Native support |
| Fallout NV | xTranslator (`fonvTranslator`) | Native support |
| Fallout 4 / VR | xTranslator (`fo4Translator`) | Native support |
| Fallout 76 | xTranslator (`f76Translator`) | Native support |
| Starfield | xTranslator (`sfTranslator`) | Native support |
| Morrowind | ESP-ESM Translator 4 | xTranslator does not cover TES3 |
| Oblivion | ESP-ESM Translator 4 | xTranslator does not cover TES4 baseline |
| Fallout 3 | ESP-ESM Translator 4 | xTranslator does not cover FO3 (FNV-mode workaround is fragile) |

ESP-ESM Translator v3.10+ reads xTranslator `.sst` natively. Per ESP-ESM Translator changelog: "The tool can now open last version of dictionnary file from xTranslator (by McGuffin)." Cross-tool community reference (2game.info): "お互いに問題なく使用できる共通ファイルは.sstファイルのみとなります。"

A single PRD spike (per `11-acceptance-and-spikes.md` §1) confirms ESP-ESM Translator correctly resolves TES3 record/subrecord signatures via an emitted Morrowind SST.

---

## 5. SST reader (consuming user-supplied dictionaries)

We may need to read existing user SST files for two reasons:
- Migration: user wants to seed a new project's memory from an existing translation
- Cross-tool diff testing (acceptance §3)

Reader strategy:
- Accept any version 2..8 (`SSU2` through `SSU9`)
- Use the version-keyed branching in `loadSstEdit` (Pascal) as the reference
- Older versions are missing fields (no rName before v5, no colabId before v6, no colabLabel table before v7, no masterList before v8). For our use, we treat missing fields as defaults: `rName = ''`, `colabId = 0`, empty masterList.

Reader is **not** load-bearing — we are primarily a writer. Reader is convenience.

---

## 6. SST writer emit checklist

When emitting an SST (per pseudocode):

```python
def write_sst(path: Path, units: list[TranslatedUnit], 
              source_lang: str, target_lang: str,
              master_list: list[str]) -> None:
    with open(path, "wb") as f:
        # Header
        f.write(b"\x39\x55\x53\x53")  # "SSU9"
        f.write(b"\x00")               # reserved flag

        # Master list table
        write_u32_le(f, len(master_list))
        for master in master_list:
            payload = master.encode("utf-16-le")
            write_u32_le(f, len(payload))
            f.write(payload)

        # Colab label table (empty for now)
        write_u32_le(f, 0)

        # Entries
        for tu in units:
            f.write(bytes([tu.list_index]))
            write_resp_pointer_lite(f, tu)
            f.write(b"\x00")  # colabId
            write_u32_le(f, tu.s_params)  # 4-byte sParams
            src = tu.source.encode("utf-16-le")
            write_u32_le(f, len(src))
            f.write(src)
            dst = tu.dest.encode("utf-16-le")
            write_u32_le(f, len(dst))
            f.write(dst)
```

`write_resp_pointer_lite(f, tu)`:

```python
def write_resp_pointer_lite(f, tu):
    write_i32_le(f, tu.strid)
    write_u32_le(f, tu.formid)            # ORIGINAL formid, NOT sanitized (sanitize is for hash only)
    f.write(tu.signature.encode("ascii")) # 4 bytes (must be exactly 4-char sig)
    f.write(tu.field.encode("ascii"))     # 4 bytes
    write_u16_le(f, tu.index)
    write_u16_le(f, tu.index_max)
    write_u32_le(f, tu.rhash)
```

**Validation in writer**:
- `signature` and `field` MUST be exactly 4 ASCII bytes (pad with `\x00` if a sig is somehow shorter — should not happen in practice)
- `source` and `dest` MUST encode cleanly to UTF-16LE; if not, raise before opening file
- `rhash` MUST be precomputed; writer does not call `stringHash` itself (separation of concerns)

---

## 7. XML sidecar (optional)

If user passes `--also-xml` to `xtl project export`, we additionally emit `<plugin>_<src>_<tgt>.xml` per xTranslator's `SSTXMLRessources` schema:

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<SSTXMLRessources>
  <Params>
    <Addon>adwryos.esm</Addon>
    <Source>en</Source>
    <Dest>zh-cn</Dest>
    <Version>2</Version>
  </Params>
  <Content>
    <String List="0" sID="0001A2" Partial="1">
      <EDID>SomeEditorID</EDID>
      <REC id="3" idMax="5">WEAP:FULL</REC>
      <Source>Iron Sword</Source>
      <Dest>铁剑</Dest>
    </String>
    <!-- ... -->
  </Content>
</SSTXMLRessources>
```

XML rendering rules per xTranslator's `TESVT_XMLFunc.pas:XMLExportbase` (research lane 1):
- `List` attribute = 0/1/2 mapping to STRINGS/DLSTRINGS/ILSTRINGS
- `sID` = 6-char hex of localized string ID (only when current mode includes strings)
- `Partial` attribute = "1" for `incompleteTrans`, "2" for `lockedTrans`. Absent = `translated`
- `REC` element text = `format("%.4s:%.4s", rname, fname)`
- `REC@id` and `REC@idMax` present only when `indexMax > 0`
- `EDID` text = real EditorID; when missing, encoded as `[xxxxxxxx]` (8-char lowercase hex of FormID)

XML is **lossy** vs SST (no orphan preservation, no colabId, no masterList). Use only for debugging or cross-tool composition.

---

## 8. Compatibility note (xTranslator version)

We emit SSU9, which is xTranslator v1.6.0 (October 2024) and later. Pre-v1.6.0 installs may not read it.

When `xtl project export` runs, we check the user's xTranslator install if discoverable (via the `_xTranslator/UserDictionaries/<Game>/` path traversal). If the user's xTranslator version is older than v1.6.0, we emit a `WARNING` log line and Tk dialog: "Your xTranslator is version X. Recommended: upgrade to v1.6.0+ for SSU9 SST compatibility, or pin our emitter to SSU8."

`xtl config set sst_version SSU8` (or earlier) overrides — at the cost of losing the masterList feature, but with broader install compatibility.

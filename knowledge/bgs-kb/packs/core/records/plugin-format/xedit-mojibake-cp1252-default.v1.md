---
id: plugin-format.xedit-mojibake-cp1252-default.v1
title: xEdit reads non-localized plugin strings as Windows-1252 and mangles UTF-8 mods
kind: gotcha
domains: [plugin-format, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: "xEdit historically decoded inline `FULL`/`DESC` bytes as Windows-1252, mangling UTF-8 community translations (CN/JP/RU/KR) into mojibake in both GUI and automation JSON. **Fixed in xEdit 4.1.6r5+** (commit `9ff67861` on the BB-84C `automation-4.1.6` branch, pushed and released 2026-06-12): translatable inline strings now run through a strict RFC 3629 UTF-8 autodetect before falling back to CP-1252, and `system.capabilities.supports.stringDecoding.translatableInlineUtf8Autodetect: true` is the runtime probe. For agents still running an older xEdit, the per-plugin workaround is a `<plugin>.cpoverride` sidecar containing `utf-8`."
  confidence: verified-project-doc
queryKeys: [encoding, mojibake, UTF-8, Windows-1252, CP-1252, Chinese, Japanese, Russian, Korean, localization, translation, fullName, EDID, FULL field, "è\"é‚¦", wbEncoding, wbEncodingTrans, cpoverride]
severity: high
sources:
  - kind: project-internal-doc
    ref: .opencode/artifacts/xedit-mcp/acceptance/batch2/manual-parity/fo4-WRLD-0000003C/README.md
    sectionPath: Encoding observation
  - kind: project-internal-doc
    ref: .opencode/artifacts/xedit-mcp/acceptance/batch2/manual-parity/fo4-WRLD-0000003C/mcp-envelope-read.json
    sectionPath: winningOverride.object.fullName_mojibake
lastReviewed: "2026-06-12"
schemaVersion: 1
---

# xEdit reads non-localized plugin strings as Windows-1252 and mangles UTF-8 mods

## Symptom

The automation envelope (or the xEdit GUI itself) shows obviously broken characters in the FULL / DESC fields of community-translated mods. Typical pattern for Chinese: `è"é‚¦`, `é"™è‚‰`, `å…¬å…¬åœ¨` —— Latin letters with diacritics followed by curly quotes and pipe-like punctuation.

The mojibake is identical in the xEdit GUI conflict view and in the automation daemon JSON response. This is a useful anti-hallucination signal: the daemon is faithfully transmitting what xEdit reads. The bug is upstream of both, in the plugin-string decoder.

## Mechanism

xEdit Core sets two global encoding defaults at startup:

- `wbEncoding := wbMBCSEncoding(1252)` — non-translatable identifiers (EditorID, signatures)
- `wbEncodingTrans := wbEncoding` — translatable strings (FULL, DESC, etc.)

Non-localized ESMs (the common case for community translations) flow `FULL`/`DESC` reads through `TwbStringDef.ToStringNative`, which calls `bsdGetEncoding(aElement).GetString(rawBytes)`. With no per-file `.cpoverride` sidecar and no `<cp:XXXX>` marker in the file's SNAM description, the chain falls to the global CP-1252 default. UTF-8 byte sequences such as `E8 81 94 E9 82 A6` (the Chinese `联邦`) get interpreted as Windows-1252 codepoints (`è` + invisible U+0081 + `"` + `é` + `‚` + `¦`), and that wrong UnicodeString is what both the GUI and the JSON serializer emit.

Bethesda's own localized FO4 STRINGS files go through a different path (`wbLocalizationHandler.GetValue` → STRINGS file with per-language encoding) and are not affected. The bug is specifically about **inline** translatable strings in **non-localized** community ESMs.

## How to detect

- Mojibake pattern: any string containing diacritic Latin letters (`è é ê ä ö` etc.) followed by curly quotes (`" ' " '`) or low single quotes (`‚`) is almost certainly UTF-8 read as CP-1252.
- Confirm by dumping the raw bytes from the plugin (any hex viewer) and checking whether they form a valid UTF-8 sequence. UTF-8 multi-byte starts must be `C0`-`FD` followed by `80`-`BF` continuation bytes.
- The mojibake renders identically in `xedit_inspect_conflicts` / `xedit_read_record` envelopes and in xEdit's own GUI conflict view —— if both agree, the bug is upstream of automation.

## Upstream fix status (RESOLVED 2026-06-12)

**Fixed in xEdit 4.1.6r5+**, on the BB-84C `automation-4.1.6` branch:

- `9ff67861` — `feat(core): UTF-8 inline autodetect for translatable subrecords (r5)`
- `14e4d62a` — `feat(automation): supports.stringDecoding capability + r5 What's New`
- `e151fabe` — `docs: Phase 14 r5 UTF-8 inline-decode closeout in ROADMAP`

The fix adds a strict RFC 3629 UTF-8 validator at `Core/wbInterface.pas:16522` for elements flagged `dfTranslatable`. Seven defense layers ensure CP-1252 strings are not misread as UTF-8: RFC 3629 strict, overlong tightening, surrogate rejection, noncharacter rejection (BMP + supplementary plane), C1 control rejection, ASCII bypass, leading-BOM strip. Explicit per-file overrides (`.cpoverride` sidecar, SNAM `<cp:XXXX>` marker, per-def encoding override) still suppress autodetect via a latched `flHasExplicitEncodingOverride` boolean.

The fix also bumps `contractVersion` to `0.12` and adds a `supports.stringDecoding` block to `system.capabilities` for runtime probing.

### Runtime probe for downstream tooling

```text
xedit_call({ command: "system.capabilities", args: {} })

→ data.contractVersion === "0.12"
→ data.supports.stringDecoding.translatableInlineUtf8Autodetect === true
→ data.supports.stringDecoding.defenseLayers includes "rfc3629-strict"
→ data.supports.stringDecoding.activeFallbackEncoding (typically "1252 (ANSI - Latin I)")
→ data.supports.stringDecoding.readWriteAsymmetry === "read-autodetects-write-uses-bsdGetEncoding"
```

The write path was intentionally NOT changed (writes still use `bsdGetEncoding`), so do not assume round-trip preservation of newly-typed UTF-8 strings without explicit testing. The capability surface discloses this asymmetry.

### CLI flags shipped with the fix

- `-cp:<encoding>` / `-cp-trans:<encoding>` — sets the translatable-string fallback encoding at startup (defaults to CP-1252).
- `-cp-general:<encoding>` — sets the non-translatable fallback (EditorID etc.).
- Accepted values include `utf-8` / `utf8` / `65001` / `1252` / `936` / `932` / `1251` / any Windows codepage number. Note: `cp1252`-style prefixes are NOT accepted by `wbMBCSEncoding`; use the bare codepage number.

## Workarounds for older xEdit (pre-r5)

For agents and operators still on xEdit 4.1.6r4 or earlier (no autodetect; CP-1252 default still applies):

Either:
- Drop a sidecar `<plugin>.cpoverride` next to the offending ESM with the single line `utf-8` (or `65001`). xEdit's `TwbFile` reads the sidecar at load time and sets `flEncodingTrans` to UTF-8 for just that file.
- Or edit the file's SNAM description in xEdit to include `<cp:utf-8>` somewhere in the text. Same effect, but mutates the plugin.

The sidecar approach is preferred because it does not modify the plugin and survives mod-manager re-deployments. After r5 these per-file overrides keep working (latched `flHasExplicitEncodingOverride` suppresses the autodetect) but are usually unnecessary — UTF-8 is detected automatically.

## What NOT to do

- Do not "fix" mojibake in the TS MCP adapter or in downstream consumers. The daemon faithfully transmits what xEdit reads; patching downstream would introduce a second encoding-translation layer that hides the upstream bug and breaks legitimate CP-1252 strings.
- Do not bulk-edit the plugin to re-encode FULL strings to CP-1252. The file is already correct UTF-8; the bug is in the reader.
- Do not rely on Bethesda's STRINGS file encoding table (`wbEncodingForLanguage`) for community ESMs. That table only applies when `IsLocalized = True`, which non-localized community translations are not.

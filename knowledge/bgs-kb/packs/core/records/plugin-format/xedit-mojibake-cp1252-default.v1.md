---
id: plugin-format.xedit-mojibake-cp1252-default.v1
title: xEdit reads non-localized plugin strings as Windows-1252 and mangles UTF-8 mods
kind: gotcha
domains: [plugin-format, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: "xEdit's global string-encoding default is Windows-1252 for inline plugin fields. Community translations (CN/JP/RU/KR) typically ship FULL/DESC bytes as UTF-8 in non-localized ESMs, and xEdit decodes those bytes as CP-1252 — producing mojibake in BOTH the xEdit GUI and the automation daemon JSON. The automation daemon faithfully transmits whatever xEdit reads, so the bug surfaces identically in the MCP envelope. Until the upstream xEdit fork patches the default, the per-plugin workaround is a `<plugin>.cpoverride` sidecar file containing `utf-8` next to the offending ESM."
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
lastReviewed: "2026-06-11"
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

## Workarounds (per-plugin, until upstream fix lands)

Either:
- Drop a sidecar `<plugin>.cpoverride` next to the offending ESM with the single line `utf-8` (or `65001`). xEdit's `TwbFile` reads the sidecar at load time and sets `flEncodingTrans` to UTF-8 for just that file.
- Or edit the file's SNAM description in xEdit to include `<cp:utf-8>` somewhere in the text. Same effect, but mutates the plugin.

The sidecar approach is preferred because it does not modify the plugin and survives mod-manager re-deployments.

## Where the proper fix belongs

Upstream patch to xEdit fork at `D:\TES5Edit-contrib` on the `automation-4.1.6` branch. Two layers:

- Medium: autodetect UTF-8 at the string-read boundary (`Core/wbInterface.pas:16522-16525`) for `cpTranslate`-flagged elements before falling back to the configured CP encoding.
- Long: expose an automation command `system.set_default_encoding` so the daemon can declare the session default without recompiling.

Both are documented in the encoding-mojibake PRD authored 2026-06-11.

## What NOT to do

- Do not "fix" mojibake in the TS MCP adapter or in downstream consumers. The daemon faithfully transmits what xEdit reads; patching downstream would introduce a second encoding-translation layer that hides the upstream bug and breaks legitimate CP-1252 strings.
- Do not bulk-edit the plugin to re-encode FULL strings to CP-1252. The file is already correct UTF-8; the bug is in the reader.
- Do not rely on Bethesda's STRINGS file encoding table (`wbEncodingForLanguage`) for community ESMs. That table only applies when `IsLocalized = True`, which non-localized community translations are not.

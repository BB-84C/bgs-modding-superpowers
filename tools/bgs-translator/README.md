# bgs-translator

`bgs-translator` is an LLM-driven sister tool for xTranslator and ESP-ESM Translator. It reads Bethesda plugin translatable strings, runs them through an LLM batch pipeline with glossary and protected-span handling, and emits `.sst` files (or ESP-ESM XML for TES3/Morrowind) that the downstream translator GUI can finalize.

## Install

Published package, once available:

```powershell
pipx install bgs-translator
```

Development checkout:

```powershell
cd D:\awesome-bgs-mod-master\tools\bgs-translator
pipx install -e .
```

Confirm the install:

```powershell
xtl version
```

## Quick start

This sequence creates a small project, plans one LLM batch, rehearses the run, and exports SST output:

```powershell
$env:BGS_MODDING_SUPERPOWERS_HOME = "$env:TEMP\bgs-translator-demo"

xtl project init demo-mod --plugin "D:\path\to\MyMod.esp" --game SkyrimSE --target-lang zh-cn

xtl batch plan demo-mod `
  --register names `
  --target-lang zh-cn `
  --profile my-openrouter-profile `
  --sig WEAP `
  --field FULL `
  --game-lore "Skyrim fantasy setting" `
  --mod-name "MyMod" `
  --mod-theme "Adds a small set of weapons." `
  --style "Concise Simplified Chinese item names."

xtl batch run demo-mod --plan <plan_id> --dry-run
xtl project export demo-mod --format sst
```

Open the emitted SST file in xTranslator or ESP-ESM Translator, review, then use that GUI's Finalize workflow to produce the game-ready translation files.

## Commands

Run `xtl --help` or any subcommand's `--help` for the current option surface.

- `xtl version` — JSON envelope with version and capability flags.
- `xtl config ...` — global settings, resolved paths, and KB cache migration.
- `xtl profile ...` — provider profiles by environment-variable key reference.
- `xtl project init|export` — project creation and dictionary export.
- `xtl inspect plugin|signatures|entries|entry|orphans` — parser and memory inspection.
- `xtl batch plan|run|status|cancel|logs` — batch planning, execution, status, cancellation, and logs.
- `xtl edit entry|bulk|status|revert` — manual translation-memory edits.
- `xtl validate project|sst` — project and SST validation.
- `xtl gui` — browser control panel.

## GUI

Launch the browser control panel with:

```powershell
xtl gui
```

The panel is for configuration and monitoring: AI service accounts, prompt preview, batch progress, cancellation, cost tracking, glossary controls, and export checks. It uses the amber/green/mono terminal theme in a local browser page.

The old Tk panel is still available as an opt-in fallback during cut-over:

```powershell
xtl gui --backend tk
```

## Documentation

The product requirements and chunk plans live in:

```text
D:\awesome-bgs-mod-master\docs\plans\translator-tool\
```

Start with `00-overview.md`; `AMENDMENTS.md` overrides earlier PRD notes where implementation spikes found corrections.

## Status

Alpha / release-candidate state. It is ship-ready for personal use and integration testing, with community contribution welcome before a wider v1.0 release.

Known release gates include bgs-kb localization pack publishing, manual xTranslator GUI verification, and continued hardening around Morrowind ESP-ESM XML interoperability.

## License

MIT. Authored by BB-84C as part of `bgs-modding-superpowers`.

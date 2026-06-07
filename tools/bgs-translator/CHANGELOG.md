# Changelog

All notable changes to `bgs-translator` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses pre-1.0 release-candidate versioning while the translator
workflow is hardened against real mod projects.

## [0.9.0-rc1] - 2026-06-07

### Added

- TES4-family plugin parser and extractor for supported Bethesda plugin text.
- TES3 / Morrowind parser path and ESP-ESM XML reader/writer support.
- SST reader and SSU9 writer for xTranslator-style dictionary output.
- AI batch pipeline with prompt construction, protected-span handling, validation,
  retry logic, cost tracking, rate tracking, cancellation markers, and dry-run
  execution.
- Provider clients for OpenAI, Anthropic, Gemini, and OpenAI-compatible endpoints.
- bgs-kb glossary integration through local KB cache readers and glossary
  composition.
- Tk control panel for project/profile/batch/glossary monitoring.
- CLI command groups for config, provider profiles, project init/export,
  inspection, batch plan/run/status/cancel/logs, atomic edits, validation, GUI
  launch, and version reporting.

### Known limitations

- bgs-kb localization prep PR and seed glossary pack publishing are still pending
  before a broader v1.0 release.
- xTranslator / ESP-ESM Translator GUI verification remains a manual acceptance
  step; `bgs-translator` emits dictionaries but does not click Finalize.
- Morrowind EET XML support is based on observed community dictionary schema and
  remains a heuristic interoperability path until more fixtures are tested.

[0.9.0-rc1]: https://github.com/BB-84C/bgs-modding-superpowers/releases/tag/bgs-translator-v0.9.0-rc1

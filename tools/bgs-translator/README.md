# bgs-translator

`bgs-translator` is an LLM-driven sister tool for xTranslator and ESP-ESM Translator. It reads Bethesda plugin translatable strings, runs them through an LLM batch pipeline with glossary and protected-span handling, and emits dictionaries that the downstream translator GUI can finalize.

## Install (dev)

From `tools/bgs-translator/`:

```powershell
pipx install -e .
```

## Run

```powershell
xtl version
```

Expected envelope:

```json
{
  "ok": true,
  "data": {
    "version": "0.1.0-dev",
    "python": "3.12.x",
    "capabilities": {
      "parser": {"tes3": false, "tes4_family": false},
      "output": {"sst": false, "eet_xml": false},
      "providers": {"openai": false, "anthropic": false, "gemini": false, "openai-compat": false},
      "kb": false,
      "gui": false
    }
  },
  "error": null
}
```

Full PRD: `D:\awesome-bgs-mod-master\docs\plans\translator-tool\`.

Shipped chunks: B — repository skeleton, packaging, JSON envelopes, `xtl version` stub, and i18n coverage stub.

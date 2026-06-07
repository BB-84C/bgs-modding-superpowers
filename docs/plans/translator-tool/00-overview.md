# 00 — Overview

## Tool positioning

`bgs-translator` is an **LLM-driven sister tool for xTranslator and ESP-ESM Translator**, not a replacement for either. It performs one job: read a Bethesda plugin's translatable strings, run them through an LLM batch pipeline with proper glossary and protected-span handling, and emit `.sst` files (xTranslator's native dictionary format) that either downstream GUI loads natively.

The user's final finalization step — producing `.STRINGS / .DLSTRINGS / .ILSTRINGS` files and packing into a ship-ready MO2 overlay mod — stays in the user's existing translator GUI. We do not duplicate that mature workflow.

```
┌──────────────┐    ┌──────────────────────┐    ┌────────────────────┐
│ source .esm  │ →  │   bgs-translator     │ →  │ one or more .sst   │
│ source .esp  │    │   (Python, CLI + Tk) │    │ per project        │
└──────────────┘    └──────────────────────┘    └─────────┬──────────┘
                              │                            │
                              │ glossary, prompt,          │ user opens in
                              │ profile, cost              │
                              ▼                            ▼
                    ┌──────────────────────┐    ┌────────────────────────┐
                    │ bgs-kb (existing)    │    │  xTranslator (6 games) │
                    │  - glossary records  │    │       OR               │
                    │  - game-context refs │    │  ESP-ESM Translator    │
                    │                      │    │  (Morrowind/Obliv/FO3) │
                    └──────────────────────┘    └─────────┬──────────────┘
                                                          │
                                                          ▼ user clicks Finalize
                                                ┌─────────────────────────┐
                                                │ MO2 overlay mod → ship  │
                                                └─────────────────────────┘
```

## User story

> I have a 600-string Starfield mod plugin (`adwryos-cc/adwryos.esm`). I want to translate it to Simplified Chinese using my OpenRouter Claude profile. I have xTranslator installed and an LLM API key. I want the agent to do the bulk translation work autonomously while I retain the ability to review system prompts before they dispatch, watch progress in real time, and cancel any single client request without killing the rest.

Acceptance for this user story:
1. Agent runs `xtl project init`, `xtl batch plan`, optionally surfaces system prompt to user via Tk panel, runs `xtl batch run`.
2. User watches Tk Batches tab as 4 concurrent LLM clients translate WEAP, ARMO, MISC, ALCH entries in parallel batches.
3. User reviews one prompt mid-flight, tweaks style directive, lets remaining batches use the tweak.
4. Agent runs `xtl validate project` and `xtl project export --format sst`.
5. User loads the resulting `.sst` files in xTranslator, hits Finalize, builds the MO2 overlay mod, ships.

## Coverage matrix (9 games)

| Game | Plugin format family | Terminal GUI (SST consumer) | This tool supports |
|---|---|---|---|
| Morrowind | TES3 (fundamentally different from TES4) | ESP-ESM Translator | ✓ |
| Oblivion | TES4-family baseline | ESP-ESM Translator | ✓ |
| Fallout 3 | TES4-family (Gamebryo) | ESP-ESM Translator | ✓ |
| Fallout NV | TES4-family (Gamebryo) | xTranslator (`fonvTranslator`) | ✓ |
| Skyrim LE | TES4-family + Creation Engine + localized | xTranslator (`tesvTranslator`) | ✓ |
| Skyrim SE / AE | Skyrim LE + ESL + UTF-8-primary encoding | xTranslator (`sseTranslator`) | ✓ |
| Skyrim VR | Binary-identical to SSE | xTranslator (`sseTranslator`) | ✓ |
| Fallout 4 / VR | TES4-family + Creation Engine 2 | xTranslator (`fo4Translator`) | ✓ |
| Fallout 76 | TES4-family + Creation Engine 2 | xTranslator (`f76Translator`) | ✓ |
| Starfield | TES4-family + CE2 + Starfield extensions + "all 9 langs or break" rule | xTranslator (`sfTranslator`) | ✓ |

The two terminal GUIs together cover the full 9-game matrix. Both consume `.sst` produced by the same `bgs-translator` emitter. SST is the documented common interop format between the two GUIs (per ESP-ESM Translator v3.10 changelog + community references).

A single PRD spike is required to confirm that ESP-ESM Translator's SST reader correctly resolves TES3 record/subrecord signatures (Morrowind). See `11-acceptance-and-spikes.md` §1.

## Non-goals (explicit)

These are deliberately out of scope. Decisions to add any of them must update this section and bump the PRD version.

- **No plugin binary writing.** We never modify `.esp/.esm/.esl` files. We only read them.
- **No MO2 overlay mod emission.** We do not produce ship-ready folders. We hand off to the user's translator GUI for that.
- **No direct `.STRINGS / .DLSTRINGS / .ILSTRINGS` emission.** xTranslator's Finalize step owns that.
- **No MCM translation in this tool.** MCM `.txt` files and `config.json` are simple text. The agent handles them directly with subagents and the bundled BGS knowledge base. A sister skill `translating-mcm` is recommended but **not part of this PRD**.
- **No VMAD (Virtual Machine Adapter Data) translation.** Script-property strings live in VMAD, but the risk/reward of AI-translating them is unacceptable: most VMAD String properties are technical references (ScriptName, animation event names) that break the script if translated. Users with VMAD-heavy mods stay in xTranslator for that surface.
- **No Pex (compiled Papyrus) translation.** Out of scope. Community decompilers exist; users can wire them into xTranslator's existing PEX pipeline if needed.
- **No human-translation editor GUI.** The Tk control panel is **configuration and monitoring only** — provider profiles, batch dispatch initiation, prompt preview, progress display, cancellation, cost accounting. Per-string human translation editing happens in xTranslator's mature GUI, not in our tool.
- **No streaming LLM responses.** Batches return as complete JSON objects. Progress display is per-batch, not per-token.
- **No automatic game-lore injection from KB into the system prompt.** The agent provides game lore because the agent's context typically has fuller information about what THIS specific mod is about. Glossary lookup (term-level) stays automatic; lore framing does not.
- **No persistent CLI daemon.** Each `xtl` CLI invocation spawns the process and exits. The GUI is the only long-lived process variant.

## What the tool emits

- `.sst` files under `~/.bgs-modding-superpowers/translator/projects/<name>/exports/`
- Optionally: XML sidecar (xTranslator's `SSTXMLRessources` schema) for debugging and cross-tool composition with LineWeaver-style pipelines
- For Starfield projects: by default, **9 SST files** (1 real translation + 8 source-as-dummy) to prevent "string not found" runtime breakage on non-target language Starfield installs. (See `03-sst-output.md` §3.)
- Full audit trail: per-batch system prompts, raw LLM responses, validator outputs preserved under `projects/<name>/batches/<run-id>/`.

## Naming conventions

| Slot | Value |
|---|---|
| Tool slug | `bgs-translator` |
| CLI entry point | `xtl` |
| Python package name | `bgs_translator` |
| Config root | `~/.bgs-modding-superpowers/translator/` |
| KB pack ID prefix (translation glossaries) | `bgs-kb-l10n-<game>-<src-lang>-<tgt-lang>` |
| KB record kind (new) | `glossary-entry` |
| Agent skill (single) | `using-bgs-translator` |

## Dependencies on other `bgs-modding-superpowers` components

| Component | Relationship |
|---|---|
| `bgs-kb` SQLite pack stores | Read-only consumer (direct SQLite open, not via MCP tool, for performance) |
| `bgs_kb_status` MCP tool | Called once at startup to enumerate pack paths |
| `maintaining-modding-environments` skill | Reused for player-glossary user-pack registration |
| xEdit MCP | None at runtime. Translator does not call xEdit. |
| MO2 control plane | None at runtime. |
| `using-bgs-modding-superpowers` skill | Will reference `using-bgs-translator` when intent matches mod translation |

## Why a separate tool and not an MCP server

This was an explicit user decision. The translator workflow is:
1. A long-running batch operation (minutes to hours for big mods)
2. With a GUI control panel for monitoring
3. Where the agent's role is to **drive** the batch (init project, plan batches, dispatch, validate) rather than to **be inside** every translation call

MCP servers are best for synchronous "agent asks, server answers" interactions. The translator's long-running, GUI-monitored, multi-process character does not fit that pattern. A standalone CLI + Tk panel suits it better. The agent skill `using-bgs-translator` documents how to drive the CLI.

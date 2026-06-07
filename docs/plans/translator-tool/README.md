# BGS Modpack Translation Tool — Product Requirements

Tool slug (working): `bgs-translator`

This directory is the design-locked specification for the LLM-driven BGS mod translation tool that sits inside the `bgs-modding-superpowers` ecosystem alongside the xEdit MCP, MO2 control plane, and `bgs-kb` knowledge base.

## Status

- Architecture: **locked** (multi-turn design discussion concluded 2026-06-06)
- Implementation: not started
- Document version: **v1** (2026-06-06)

## Reading order

For someone new to this design, read in this order:

| # | File | Topic |
|---|---|---|
| 1 | `00-overview.md` | What it is, who it is for, what is out of scope |
| 2 | `01-architecture.md` | Components, tech stack, process model |
| 3 | `04-ai-pipeline.md` | Core translation pipeline (extract → mask → batch → translate → unmask → validate) |
| 4 | `03-sst-output.md` | SST format spec, Starfield 9-fill, dual-GUI terminal workflow |
| 5 | `02-parser-and-coverage.md` | TES3 + TES4-family parser architecture |
| 6 | `05-glossary-and-kb.md` | 4-layer glossary, `bgs-kb` integration |
| 7 | `06-cli-surface.md` | Agent-facing command surface |
| 8 | `07-tk-control-panel.md` | Tk control panel information architecture |
| 9 | `08-persistence-and-paths.md` | Unified `~/.bgs-modding-superpowers/` root, KB cache migration |
| 10 | `09-providers-and-keys.md` | Provider profiles, API key isolation |
| 11 | `10-cost-rate-cancel.md` | Cost caps, rate limits, cancellation |
| 12 | `11-acceptance-and-spikes.md` | Verification spikes + acceptance criteria |
| 13 | `12-implementation-chunks.md` | 施工切块建议 (no time bindings) |
| 14 | `13-agent-skill-outline.md` | The single agent skill that wraps the tool |
| 15 | `14-open-questions.md` | Items deliberately left for execution-time decisions |

## Inherited hard rules (project-wide)

These rules bind every decision in this PRD. If a decision in this PRD conflicts with one of them, the rule wins and the decision is a bug.

- The MO2 Stock Game `Data` tree is read-only. No emission into it ever.
- Plugin `.esp/.esm/.esl` files are parsed for **read-only** text extraction; the tool does not write back to plugins.
- KB packs follow the `bgs-kb-*` distribution convention; this design adds a new record kind (`glossary-entry`), not a new system.
- API keys live exclusively in `profiles/.env`; the agent does not read this file by default.
- The MO2 launcher / xEdit harness boundaries (control plane, automation daemon) are untouched by this tool.
- All durable evidence (plans, raw LLM responses, validator outputs) lives under `~/.bgs-modding-superpowers/translator/projects/<name>/batches/<run-id>/`.

## Source-of-truth ranking

If documents disagree:

1. This PRD (these 15 files)
2. Code (when implementation begins)
3. Earlier conversation transcripts (clarification only, not authority)

A contradiction inside the PRD itself is a bug — file an issue, mark it load-bearing until reconciled.

## Update protocol

- Significant scope or architecture changes: edit the relevant file, bump the PRD version in this README, leave a dated changelog entry at the bottom.
- Minor wording / clarification: edit in place, no version bump.
- New decisions discovered during施工: capture in `14-open-questions.md` first; promote to the relevant section when locked.

## Cross-references with the rest of `bgs-modding-superpowers`

| Component | Relationship |
|---|---|
| `bgs-kb-core` and per-game KB packs | Read-only consumer for `glossary-entry` records and game-context records |
| `maintaining-modding-environments` skill | Handles KB pack registration; `bgs-translator` user-pack overlays follow that registration pattern |
| `using-bgs-modding-superpowers` skill | Auto-loaded bootstrap that will mention `using-bgs-translator` when the user task involves mod translation |
| xEdit MCP (`tools/xedit-mcp/`) | **No runtime dependency.** `bgs-translator` does not call xEdit. The two tools coexist as siblings. |
| MO2 control plane (`tools/mo2-control-plane/`) | **No runtime dependency.** `bgs-translator` never spawns or talks to MO2. |
| xTranslator (external, MGuffin) | Downstream terminal GUI for `.sst` consumption (6 games: Skyrim LE/SE/AE/VR, FNV, FO4, FO76, Starfield) |
| ESP-ESM Translator (external, Epervier 666) | Downstream terminal GUI for `.sst` consumption (3 outlier games: Morrowind, Oblivion, FO3) |

## Changelog

- **2026-06-06** v1 created from multi-session design discussion.

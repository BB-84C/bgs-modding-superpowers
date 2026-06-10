# 14 — Open Questions

These are decisions deliberately left for execution-time (or for post-v1.0 scope). Each question has a current default that lets施工 proceed; only resolve when concrete data justifies the decision.

Decisions on this page were resolved 2026-06-06 with two-oracle multi-perspective fan-out on the 6 contested OQs (built-in `@oracle` + `@oracle-alpha`, vendor-diverse Anthropic + OpenAI). Bounded OQs resolved by orchestrator solo. Cross-cutting observations from the fan-out are captured at the bottom of this file and have informed multiple decisions.

Format per resolved item: original Q text preserved verbatim. **Decision** and **Reasoning** blocks appended.

---

## OQ-1: CLI command name prefix

**Current default**: `xtl`.

**Alternatives**: `bgs-translator`, `bgs-xlate`, `bxt`, `bgstl`.

**When to decide**: pre-v1.0 release. Bikeshed at the moment of pyproject.toml entry-point declaration.

**Decision criteria**: pronounceability, collision check against existing PATH binaries on user systems.

**Decision (2026-06-06): lock `xtl`, ship as primary entry point. Also expose `bgs-translator` as alias.**

**Reasoning**: `xtl` is the working default already used throughout the PRD; switching now would force inconsistency across 16 documents for no benefit. Three characters, easy to type for repeated agent invocations, no observed collision on Windows PATH binaries. Exposing `bgs-translator` as an alias in `pyproject.toml` entry points costs nothing and helps discoverability for users who don't read docs first.

---

## OQ-2: Default `batch_size` per length tier

**Current default**: short=40, medium=20, long=10.

**Alternatives**: profile-aware defaults (smaller for slower/cheaper models, larger for faster).

**When to decide**: after Spike 3 + first month of real-world usage data. Observe how often batches hit token-budget ceilings.

**Decision criteria**: average input + output token usage per batch in observed runs.

**Decision (2026-06-06): ship v1.0 with current static defaults. Profile-aware tuning revisits after data.**

**Reasoning**: Static defaults are correct for v1.0 because we have zero empirical data on what model × register × language combinations push token budget. Premature profile-aware logic would encode guesses as code, which is harder to update than a TOML default. The Spike 3 run plus first month of usage will surface real distributions; tune then. Users who hit ceilings can override per-batch via `--batch-size` immediately.

---

## OQ-3: Concurrency default per profile

**Current default**: 4 for OpenAI/Anthropic/Gemini, 8 for DeepSeek (cheap, higher rate limits), 3 for OpenRouter.

**Alternatives**: 1 (sequential) until user explicitly raises, or dynamic based on observed throughput.

**When to decide**: after `xtl profile probe` calibration data is available.

**Decision criteria**: probe-suggested ceilings observed across the provider matrix.

**Decision (2026-06-06): ship v1.0 with current conservative defaults. Probe suggests adjustments; user confirms.**

**Reasoning**: Conservative defaults respect the user's "I don't want to wake up to a $500 bill" stance. `xtl profile probe` already surfaces suggested rate limits after a probe request; user confirms via dialog (per `09-providers-and-keys.md` §6). That flow handles per-provider tuning without requiring up-front guesses encoded in code.

---

## OQ-4: cpTranslate slice completeness per game

**Current default**: 30-50 record signatures per game (the most common translatable ones).

**Open**: which records are missing from the slice. As real users translate mods, missing record types will surface in `xtl validate project` reports.

**When to decide**: ongoing, post-v1.0. Each missing record-type → schema YAML manifest update → PR.

**Decision criteria**: user-reported translation gaps + cross-check against xTranslator's coverage.

**Decision (2026-06-06): ongoing process, not a v1.0 binary decision. Ship the initial slice; treat coverage extensions as routine post-release PRs.**

**Reasoning**: Coverage completeness is not knowable without real-world mod corpus exposure. Treat the per-game schema YAML manifests as living documents. Acceptance criterion in `11-acceptance-and-spikes.md` §2.1 already requires per-signature counts to match xTranslator's view on the test fixture; future fixtures expand the verified slice naturally.

---

## OQ-5: Prompt template registry

**Current default**: tool ships one `default.md` template. Users author additional templates manually in `config/prompt-templates/`.

**Open**: should there be a community-curated template registry? E.g., genre-specific (`fantasy-dialogue.md`, `scifi-tech.md`).

**When to decide**: post-v1.0. If users start authoring templates and sharing them, the registry pattern emerges naturally.

**Decision (2026-06-06): defer to v1.x. Community-emergent only.**

**Reasoning**: A registry without contributors is dead infrastructure. Ship `default.md`, document the template format, let community patterns emerge organically. If 3+ users independently author similar templates within the first 6 months, that's the signal to formalize a registry. Until then, manual sharing via gists or Nexus articles is sufficient.

---

## OQ-6: Auto-resume cancelled batches

**Current default**: cancelled batches do NOT auto-resume. User explicitly re-runs.

**Alternatives**: opt-in auto-resume on user setting; auto-resume only for transient errors (network).

**When to decide**: post-v1.0, after observing cancel patterns in usage data.

**Decision criteria**: how often does user re-run cancelled vs. truly abandon. Auto-resume only if re-run is dominant.

**Decision (2026-06-06): defer to v1.x. Cancellation stays manual-resume.**

**Reasoning**: Cancellation in the current design is a user signal of intent, not a transient hiccup. Auto-resume would routinely override that intent. Same-profile transient-error retry (separate from this OQ) is already covered in the pipeline retry layer (`04-ai-pipeline.md` retry section), which is the right place for "network blip" recovery — distinct from "user deliberately stopped."

---

## OQ-7: Translation memory cross-project sharing

**Current default**: each project has its own `memory.sqlite`. No cross-project lookup.

**Alternatives**: opt-in "share memory across projects" feature where a global TM seeds new projects from past translations.

**When to decide**: post-v1.0. Adds complexity; only worth it if users have many similar mods.

**Decision (2026-06-06): defer to v1.x.**

**Reasoning**: Both oracles converged on defer. The 4-layer glossary already absorbs the highest-value reuse (canonical vanilla terms like "Whiterun → 白漫城"). What cross-project TM would add is exact-source-string memoization for mod-author-specific prose (custom item descriptions, quest journal entries, loading screen tips). Real value, but second-order for a single primary user who can promote high-frequency mod-author terms into the glossary manually after the first few projects. The killer technical concern from oracle-alpha: as the user's translation quality improves session over session, old TM entries become low-quality seeds that silently contaminate new projects. Glossary entries are curated; TM entries are bulk-captured. Building staleness-resistant conflict resolution is real schema work that competes with shipping v1.0. Natural evolution path for v1.x once usage volume justifies the staleness machinery.

---

## OQ-8: Provider failover / retry strategy across profiles

**Current default**: a profile that fails (rate-limit halt, cost cap, network) blocks the batch. User must manually switch profile.

**Alternatives**: automatic failover to a secondary profile in a defined chain (e.g., "if OpenRouter fails, try DeepSeek").

**When to decide**: post-v1.0. Likely valuable for production-grade reliability but adds significant orchestration complexity.

**Decision (2026-06-06): defer to v1.x. Same-profile transient retry stays in scope (already in retry layer); cross-profile failover does not.**

**Reasoning**: Both oracles converged on defer. Oracle-alpha cleanly disentangled two often-conflated things: same-profile transient retry (network blip, transient 429, transient 5xx) is table stakes and is already in the pipeline retry layer; cross-profile failover ("Claude is rate-halted → automatically promote to GPT-4o-mini") is a different beast. The killer concern is cost surprise: a failover chain that silently promotes from a $0.27/1M-token profile to a $15/1M-token profile turns a $2 batch into a $200 batch with no confirmation gate. Adding a confirmation prompt eliminates the "automatic" property, leaving you with what the user already does manually today. Secondary concern: translation-style consistency drift across providers within a single .sst dictionary. Manual profile switch on visible halt is the right behavior for a single primary user with cost-aware stance.

---

## OQ-9: Streaming for very long output items

**Current default**: no streaming. Batches return complete JSON.

**Alternatives**: streaming for `length_tier=long` items to give earlier progress feedback.

**When to decide**: post-v1.0. Tradeoff: streaming complicates structured-output validation.

**Decision (2026-06-06): out of scope permanently for the structured-output path.**

**Reasoning**: The pipeline's structured-output schema validation (`BatchTranslationOutput` Pydantic model with `extra=forbid`) is fundamentally incompatible with streaming. Strict JSON schema validation needs the complete object; you can't validate "no extra keys" against a partial stream. Trying to stream and still validate strictly means buffering the whole stream and parsing at end, which gives you zero of streaming's actual benefits (early UX feedback, partial commits). If progress feedback for long items is needed, the right answer is smaller batches in the `long` tier (already configurable per OQ-2). Streaming would be a different product surface (real-time text translation, not bulk dictionary build), not a v1.x bolt-on.

---

## OQ-10: BSA / BA2 archive support

**Current default**: not supported. User must extract plugins from archives manually.

**Open**: should `xtl project init` accept a BSA path and extract the relevant plugin?

**When to decide**: post-v1.0. Common-enough use case but blows scope.

**Decision (2026-06-06): out of scope permanently.**

**Reasoning**: Oracle-alpha argued the harder line here; I'm taking it over the built-in oracle's softer "defer." Three load-bearing reasons. (1) Archive extraction is solved by at least three existing tools in the ecosystem (xTranslator itself, BSA Browser, Cathedral Assets Optimizer); duplicating that capability does not improve translation quality. (2) The user's two-terminal workflow already positions xTranslator as the asset-pipeline frontend; users open xTranslator anyway for Finalize, so they have BSA tools already at hand. (3) Format proliferation cost is real: BSA (Skyrim LE/Morrowind/Oblivion/FO3/FNV), BA2 with two sub-formats (FO4), BA2v3 (Starfield) = at least four parsing surfaces across 9 games, none of which contribute to translation. The .esp/.esm/.esl loose-file path is the integration seam; users extract once with their existing tools, point us at the plugin, we do our job. Mitigation for the rare confused user: README documents extraction with one-command examples for each tool.

---

## OQ-11: MCM translation in this tool (currently scope-out)

**Current default**: MCM is explicitly out of scope. Sister skill `translating-mcm` handles it.

**Open**: should it eventually fold back in to provide unified translation experience?

**When to decide**: after sister skill exists. If users find the two-workflow split awkward, reconsider.

**Decision (2026-06-06): out of scope permanently.**

**Reasoning**: Both oracles converged on permanent OOS. Oracle-alpha's argument is architecturally decisive: plugin translation and MCM translation share an LLM engine but share almost nothing else. Plugin translation reads structured record fields from a binary format via per-game schemas, glossary-maps them, validates against per-field byte budgets, and emits one well-defined .sst output format. MCM spans 4 ecosystems (SkyUI JSON, MCM Helper INI-style, SkyUI SE translation files, FO4 MCM XML), each with its own validation rules, escaping conventions, and output expectations. Folding MCM in does not create "unified UX" — it creates one tool with two completely different I/O surfaces and a shared LLM call in the middle, which is a *library* sharing pattern, not a *tool* unification pattern. If shared logic (provider profiles, glossary lookup, batch orchestration) becomes worth extracting, the right shape is a shared library that both `bgs-translator` and the MCM skill import — not folding MCM into `bgs-translator`. Tool boundary is "LLM-driven text translation of plugin records, emitting .sst dictionaries." MCM does not match that contract.

---

## OQ-12: Voice generation pipeline

**Current default**: voice files are independent assets. We translate text only.

**Open**: integration with community TTS for voiced dialog (xVASynth, ElevenLabs).

**When to decide**: post-v1.0. Major scope expansion; out of scope for v1.x.

**Decision (2026-06-06): out of scope permanently.**

**Reasoning**: Both oracles converged trivially. Voice generation is a different domain (TTS synthesis, not text translation), different output format (audio files, not .sst dictionaries), different cost profile (ElevenLabs is orders of magnitude more expensive per-string than text LLMs), different quality validation workflow (listening vs reading), different ecosystem (xVASynth and voice-type matching have their own toolchains). The PRD's `00-overview.md` already lists this under "non-goals." The .sst output is the correct integration seam for any future voice tool: a TTS pipeline can consume our .sst as input and produce voice assets as a downstream sibling tool. That's the architecture, not a folded-in feature.

---

## OQ-13: Cost estimation refinement

**Current default**: local pricing table + heuristic language expansion factors.

**Open**: dynamic estimation based on actual per-batch observation. Refine factors per-language per-register as data accumulates.

**When to decide**: after first 50 real-world batch runs. Empirical factors will likely improve.

**Decision criteria**: when prediction error rate exceeds tolerable threshold consistently.

**Decision (2026-06-06): ongoing refinement post-v1.0. Baseline ships with hardcoded language expansion factors.**

**Reasoning**: The current `LANGUAGE_EXPANSION_FACTORS` dict in `04-ai-pipeline.md` §encoding is a baseline guess. After real batch runs, recorded `usage` data from `LLMResponse` provides empirical input/output ratios per (target_lang, register). Implementation work for v1.x: a small CLI command `xtl observability calibrate` that reads recent run data from `memory.sqlite` and produces updated factors. Not a v1.0 ship blocker; baseline factors are correct to ±30% which is fine for cost-cap purposes.

---

## OQ-14: Provider-specific structured-output reliability tuning

**Current default**: each `sdk_kind` uses one structured-output mechanism (json_schema strict / tool use strict / response_schema / json_object).

**Open**: some models within a provider may be more or less reliable. Per-model overrides in profile.

**When to decide**: after probe data accumulates.

**Decision (2026-06-06): defer to v1.x. Existing per-profile `json_mode` field in `09-providers-and-keys.md` profile schema already provides one knob; per-model tuning needs evidence.**

**Reasoning**: The `json_mode` field in `profiles.toml` (currently used for DeepSeek's `json_object` constraint) already lets users coerce a specific structured-output mode per profile. Adding per-model tuning requires either a separate config layer or extending profile semantics, both of which need actual reliability data to justify. The probe (`xtl profile probe`) records structured-output behavior per profile; that data is the substrate for any future per-model logic.

---

## OQ-15: Glossary entry confidence-weighted prompt ranking

**Current default**: top 500 glossary entries by score (occurrence × scope priority × confidence) included in prompt.

**Open**: 500 may be too aggressive or too conservative. Tune based on observed prompt rendering.

**When to decide**: after batch runs surface "glossary too crowded" or "important term missing" issues.

**Decision criteria**: prompt rendering observed during real batch runs.

**Decision (2026-06-09): user explicitly raised the default ceiling to 500 for large Starfield batches. Keep ongoing tuning post-v1.0 and expose `glossary_max_entries` knob in `project.toml` for per-project override.**

**Reasoning**: 50 was too low for the active 500/351-entry Starfield stress tests. The right shape remains: ship the cap, expose it as a TOML override so users can experiment per-project, and refine the default after empirical data. Adding the TOML knob is a tiny code change that makes future tuning possible without requiring a release. (This is a small scope addition to the PRD's persistence layout — adding `[translation] glossary_max_entries` to `project.toml`. Approved per orchestrator discretion as minor.)

---

## OQ-16: macOS-specific Tk quirks

**Current default**: target Tk 8.6+ baseline. Cross-platform "looks slightly different per OS" accepted.

**Open**: do we ship custom macOS workarounds for Tk-on-macOS color theming bugs?

**When to decide**: after first macOS user tests the GUI.

**Decision (2026-06-06): out of scope for v1.0. Documented as "Windows-first; macOS untested." No active development for macOS or Linux quirks until user-base demand surfaces.**

**Reasoning**: Per user direction: "Macos/linux的支持可以放一放，毕竟大家都是用windows玩游戏的." BGS modding is a Windows-dominant ecosystem. macOS users exist but are a minority of a minority. Spending v1.0 budget chasing Tk-on-macOS theming bugs is misallocated. The tool's code is portable Python; if a macOS user runs it and reports specific issues, those are bug reports we triage by frequency, not a proactive workstream. Same posture for Linux. v1.0 ships tested on Windows; other platforms documented as "should work, not guaranteed."

---

## OQ-17: Telemetry / opt-in usage metrics

**Current default**: zero telemetry. Tool runs entirely locally.

**Open**: opt-in metrics (provider success rates, average cost per project) would improve cost estimation defaults.

**When to decide**: never for v1.x. Maintain zero-telemetry default. Revisit only if user asks for it.

**Decision (2026-06-06): out of scope permanently. Zero telemetry is a positive feature, not a missing feature.**

**Reasoning**: Telemetry in a tool that handles paid API keys and personal modding workflow is a credibility-damaging move. The user is the single primary user and already has full audit trail access (`batches/<run-id>/`). Aggregated metrics across a community would be useful for cost-estimation factor refinement (OQ-13), but the cost is higher than the benefit: telemetry infrastructure to maintain, privacy policy, opt-in friction, audit obligations. The user's own historical runs can drive factor refinement without phoning home anywhere. Documented as a feature ("zero telemetry, all data stays local") not a TODO.

---

## OQ-18: Pre-release packaging format

**Current default**: PyPI via `pipx install bgs-translator`.

**Alternatives**: standalone Windows installer (PyInstaller), Flatpak/Snap for Linux, Homebrew for macOS.

**When to decide**: post-v1.0 if user demand surfaces. PyPI baseline first.

**Decision (2026-06-06): PyPI baseline only for v1.0. Windows installer (PyInstaller) revisit after data; Linux/macOS native installers permanently out of scope unless community contribution.**

**Reasoning**: `pipx install bgs-translator` is a single command on Windows, no install-wizard ceremony. Users comfortable with MO2, xEdit, BSA tools are comfortable with pipx (or willing to learn one new command). PyInstaller-style Windows installer is the next-most-likely demand (if non-developer users complain about pipx friction), and that's a single-file `pyinstaller bgs_translator/__main__.py` workflow we can revisit. Linux/macOS native installers (Flatpak/Snap/Homebrew) require active maintenance per ecosystem; not justified for a Windows-first audience.

---

## OQ-19: Localization of `bgs-translator` itself

**Current default**: en + zh-cn only.

**Open**: add fr, de, it, es, pl, ru, ja for the UI itself (the user is a Chinese speaker; English + Chinese covers the immediate need).

**When to decide**: post-v1.0 if non-English-non-Chinese users contribute translations.

**Decision (2026-06-06): out of scope for v1.0. Accept community PRs for additional .po files post-release; do not actively author them.**

**Reasoning**: English + Simplified Chinese covers the primary user (Chinese speaker) plus the dominant developer-language fallback. The cost of authoring 5+ additional locales (correctly, including review by native speakers) is real and pulls effort from shipping. The cost of accepting community-contributed .po files is low — CI already runs the i18n coverage check (`gui/i18n/_coverage_check.py`); contributors validate their own files. Net stance: "we are gratefully open to community translations, we will not produce them ourselves."

---

## OQ-20: Integration with Nexus mod page metadata

**Current default**: tool doesn't know what mod page a plugin came from.

**Open**: parse Nexus mod page metadata (description, version, language tags) to seed mod_context automatically.

**When to decide**: post-v1.0 if `mod_context` authoring becomes friction.

**Decision (2026-06-06): revisit after data. Ship v1.0 with manual `mod_context`; explicitly do NOT add a `--nexus-url` flag-stub yet.**

**Reasoning**: Both oracles converged on revisit-after-data. The question hinges on an unknown empirical fact: how painful is manual `mod_context` entry? If a user types "Sim Settlements 2 city-building framework, modern English tone, lore-friendly" in 15 seconds and gets good translations, Nexus integration over-engineers a non-problem. If good translations require 3-4 paragraphs of mod context that turns out to match what Nexus mod pages already contain, the feature earns its complexity. Privacy + scope concerns (Nexus API tokens, rate limits, structured metadata vs HTML) are real but tractable. Implementation note: do NOT ship a `--nexus-url` flag-stub in v1.0; introducing a stub creates user expectation that the feature is "almost there" and increases pressure to ship it before data. Ship clean v1.0, observe authoring friction across the first 10-20 projects, then decide.

---

## Pattern for resolving OQs

When an OQ is ready to resolve:

1. Add a `decided` line with the date and the resolution
2. Move the resolved item to a "Resolved" section at the bottom of this file
3. Update the relevant section in the PRD that the OQ touched (with a note "per OQ-N resolution dated YYYY-MM-DD")
4. Reference the OQ resolution in the implementing PR

Resolved OQs stay in this document as historical record. Do not delete.

---

## Cross-cutting observations (from 2026-06-06 multi-perspective fan-out)

These observations emerged from the two-oracle consultation and inform multiple OQ decisions. Surface here so future scope debates can reference them without re-deriving first principles.

### 1. The glossary layer is doing more work than this PRD makes credit for

OQ-7 (cross-project TM) and OQ-20 (Nexus metadata) both partially dissolve when you recognize that the 4-layer glossary — especially the bgs-kb-backed canonical term layer — already absorbs the highest-frequency, highest-value translation reuse. The marginal value of additional sharing/seeding mechanisms is real but smaller than it appears in isolation. **Future OQ proposals that overlap with glossary territory should explicitly argue against the existing glossary's coverage**, not propose features that duplicate it under different labels.

### 2. "Single primary user" is the strongest filter

Four of the contested OQs (TM sharing, provider failover, BSA extraction, Nexus metadata) become significantly more compelling under "50 community users translating mods they have never seen before." For a single user who knows their mod list, knows their providers, knows their archive tools, and can author a sentence of mod context — the marginal value of each automation feature drops sharply. **This constraint should be re-asserted whenever scope expansion is proposed; if community usage actually scales, several of these decisions can flip without architectural penalty.**

### 3. Tool boundary is "LLM-driven text translation of plugin records, emitting .sst dictionaries"

The three permanent out-of-scope verdicts (OQ-10 BSA, OQ-11 MCM, OQ-12 voice) share this architectural principle. Anything that does not touch that pipeline — archive extraction, MCM text-file manipulation, voice synthesis — belongs in a sibling tool or upstream/downstream workflow step. **The .sst dictionary is the integration seam between this tool and the broader translation ecosystem.** Future scope proposals are evaluated against this boundary; cross-boundary proposals require justification not for the feature's value but for the boundary violation.

### 4. Deferred features (OQ-7, OQ-8) are infrastructure improvements whose value scales with usage volume

A user who has translated 3 mods does not need TM sharing or provider failover. A user who has translated 30 mods and runs overnight batches absolutely does. **These features' v1.x priority should be set by actual v1.0 usage data, not by speculative value estimates.** If after v1.0 the user is translating <5 mods per quarter, neither feature is worth building. If translating >5 per month, both jump up the priority list.

---

## Resolved

(none yet — entries above are *decided* for shipping intent but remain in this file as authoritative record. When implementation of a decided OQ touches code, the implementing PR cross-references the OQ number.)

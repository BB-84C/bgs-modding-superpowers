# Source-mined extraction: localization judgment injection for `using-bgs-translator`

Sources:
- `[E8]` = `F:\my clip\FO4\MOD Tutorial\E8\New Text Document.txt` (BB84 localization 疑难杂症 transcript).
- `[Bili06]` = `.opencode/artifacts/sixiang-sources/bilibili/06-fo4-localization-guide.txt`.

Source quality note: `[E8]` is the usable BB84 localization substrate. `[Bili06]` has a matching localization-guide title/metadata but the body currently contains unrelated phone-review subtitle text; no localization framework claims below are sourced from that body. `[GAP — source mismatch]`: replace or re-scrape `[Bili06]` before using it as corroboration.

## 1. What localization is (curator's view)

Localization is not "run a translator over every string." It is the curator's decision about what the player should see, what must remain technically stable, and how terms stay consistent across the pack.

- There is no one "ultimate localization patch" that fixes every mod. BB84 calls that a basic misconception: any mod plugin loaded after the original game can override already-localized base-game text. `[E8]` lines 37-51, 93-106.
- The first task is attribution: when English appears in game, identify which mod last touched the visible thing, then localize that source or its patch. For clickable objects, BB84 uses Better Console to see original provider and last modifier; for quest/dialogue text, use xEdit filtering by observed English text. `[E8]` lines 181-259.
- Existing translations are inputs, not a license to overwrite the stack blindly. If a mod has update/compatibility patches, the localized output has to be regenerated for the patch layer after the functional patch ordering is settled. `[E8]` lines 325-358.
- Localization quality includes consistency: if the pack picked ANK-style terms, unofficial-Chinese-patch terms, or a custom glossary, later mods should not casually retranslate the same world terms differently. `[E8]` lines 53-90.

## 2. Localization mechanics framing

BB84's key explanation for "missing localization" is a runtime lookup/override chain, not a mysterious failure of the translation tool.

1. Base-game localization is read by the original game plugins. `[E8]` lines 53-61, 93-99.
2. Any mod plugin that edits the same visible object/text is loaded after the original plugin, so its own string values win in game. `[E8]` lines 95-106.
3. A pre-existing game translation therefore cannot cover new or modified mod-side strings. You need a translation for the mod-side plugin/patch that actually wins. `[E8]` lines 107-119.
4. If an update patch or compatibility patch wins after the base mod translation, it can reintroduce English or even invalidate the functional patch if the translation is sorted incorrectly. `[E8]` lines 329-358.
5. Correct repair order: settle base mod + update/compat patch ordering first, then localize the winning patch/plugin layer using comparison translation where appropriate, and load the generated localized patch after the functional layer. `[E8]` lines 347-358.

This should be framed game-agnostically in the skill as "find the winning string provider, then localize that layer," while per-game details about which signatures/fields are visible belong in KB.

## 3. When to localize / what to localize

Priority is player-visible text and pack terminology, not internal identifiers.

Translate or review:
- quest objectives/descriptions, dialogue, loading screens, books/notes, terminal text, UI/menu text, MCM text when exposed to the player;
- item, weapon, armor, location, faction, perk, and effect names only when they are visible player-facing names;
- compatibility/update patches that win visible strings after functional conflict ordering is settled;
- repeated terminology through controlled search/replace or glossary rules, not ad hoc per-entry improvisation. `[E8]` lines 165-177, 299-320, 325-358.

Do not translate by default:
- EditorIDs, script variables, technical keys, file paths, tags, placeholders, FormIDs, and other internal references;
- record/signature/field categories that the current game's KB marks as non-visible or engine-referenced;
- generated naming-rule internals where blind comparison translation can corrupt runtime names.

FO4-specific source example (KB material, not skill body): BB84 says xTranslator ID types `RACE`, `KYWD`, `MGEF`, `ENCH`, and `SPEL` generally do not need localization because they do not display in game, and `INNR` entries should be translated manually rather than via comparison translation because weapon naming can become wrong. `[E8]` lines 371-399. These are game/tool facts and should be moved to KB, not hardcoded into the game-agnostic skill.

## 4. Consistency discipline

- Pick one glossary per pack. BB84 explicitly distinguishes localization variants and notes that terminology differs between ANK and unofficial Chinese patch translations, e.g. Nuka-Cola term choices. `[E8]` lines 53-90.
- Lock core terms early: factions, locations, item families, UI verbs, system names, and lore terms.
- When a later mod retranslates a locked term differently, do not let the latest string win by accident. Decide whether the new term is intentionally better for the pack or should be normalized back to the pack glossary.
- Comparison translation is powerful for restoring already-localized base terms, but sample-check the result. BB84 says after loading comparison translation, only a few entries need to be sampled to verify correspondence in that scenario. `[E8]` lines 283-298.
- `[GAP — policy threshold]`: source does not define how many sampled entries are enough for large batch acceptance; skill should say "sample and inspect" but not invent a numeric threshold.

## 5. What NOT to localize: protected-span discipline

Protected spans are not aesthetic preferences. They are references the engine, scripts, UI formatters, or external tools may need to match exactly.

Protect:
- placeholders and formatter tokens (`{P0}`, `<Alias=...>`, `%s`, `$variable`, bracket tags) unless the current tool explicitly tells you they are safe to edit;
- EditorIDs, script/property names, event names, file paths, plugin names, archive paths, FormIDs, hex IDs;
- JSON keys/config keys and MCM schema keys; translate the displayed value only when the schema/tool supports it;
- per-game non-visible signatures/fields from KB;
- naming-rule internals and other generated-name components that require manual, semantics-aware translation instead of bulk comparison.

## 6. Red flags

| Thought | Reality | Source |
|---|---|---|
| "There must be a final universal localization patch." | BB84 explicitly says there is no one mod/patch that fixes all localization because later mod plugins override strings. | `[E8]` lines 37-51, 93-106 |
| "The base-game Chinese patch is installed, so mod English is a tool bug." | The winning mod-side plugin may be overriding the localized base string. Attribute the winner first. | `[E8]` lines 93-119, 181-259 |
| "Just sort the translation after everything." | If translation overrides an update/compatibility patch, it can make the patch fail or crash; if patch wins after translation, English returns. Regenerate a localized patch layer. | `[E8]` lines 325-358 |
| "Batch/compare-translate every entry." | BB84 names categories that should not be localized or should be manually translated; blind comparison can corrupt generated names. | `[E8]` lines 371-399 |
| "MCM is just plugin text." | MCM may live in `.txt` or `.json` files and needs the correct tool/path. | `[E8]` lines 299-320 |
| "The Bili subtitle file confirms this." | `[Bili06]` body is unrelated to localization despite title metadata. Treat it as a source gap until re-scraped. | `[Bili06]` lines 1-708 |

## 7. Rationalizations

| Excuse | Reality | Source |
|---|---|---|
| "I'm too lazy to trace the source; I'll translate the obvious mod." | BB84's own joke names laziness as the remaining unsolved problem; the workflow is to identify original and last modifier. | `[E8]` lines 21-27, 181-259 |
| "The English is only a few words; manual patching is faster than understanding the chain." | Without knowing the winning provider, you can patch the wrong layer and have the string overwritten again. | `[E8]` lines 93-119, 325-358 |
| "The old translation ESP worked before; put it at the end." | Old translations can be stale relative to updated mods such as ECO/PRP/SS2 examples; use comparison translation against the current patch layer when uncertain. | `[E8]` lines 359-370 |
| "All visible names are safe to bulk-translate." | Generated naming-rule entries can produce wrong weapon names if handled blindly. | `[E8]` lines 385-399 |
| "The tool can load the file, so the output is correct." | BB84 still samples several translations after comparison translation to verify correspondence. | `[E8]` lines 293-298 |

## 8. Game-specific facts to KB

The skill body should teach the framework. The following belong in KB records or variants:

- FO4-specific xTranslator ID/signature guidance: `RACE`, `KYWD`, `MGEF`, `ENCH`, `SPEL` generally non-visible; `INNR` requires manual handling. `[E8]` lines 371-399.
- FO4 attribution tooling: Better Console for clickable objects; FO4Edit filtering for quest/dialogue text. `[E8]` lines 181-259.
- FO4 comparison-translation examples: PRP restoring place names from translated UFO4P-style source; update/compat patch examples ECO, PRP, Sim Settlements 2. `[E8]` lines 277-298, 359-370.
- MCM file-shape details (`.txt` via xTranslator, `.json/config.json` via specific MCM tool). `[E8]` lines 299-320.
- `[GAP — deferred KB]`: per-game protected-string/FormID-dependency lists for Skyrim, Starfield, and Fallout 4 need KB authoring; this fixer intentionally does not add records.

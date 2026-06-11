# bgs-translator Web GUI User Guide

This tool helps translate Bethesda Game Studios mod plugin text from
`.esp/.esm/.esl` files with AI assistance, then exports `.sst` dictionaries for
xTranslator. It does not modify the original mod plugin. xTranslator still owns
the final import and Finalize step.

## Who This Is For

- Players who want AI-assisted localization for Starfield, Skyrim, Fallout, and
  related BGS mods.
- Users who do not know plugin internals, record signatures, or LLM provider
  terminology.
- Users who can select files, review prompts, check translations, and export
  dictionaries.

## Launch

```powershell
xtl gui
```

The GUI opens in a local browser page. The old Tk window has been removed.

## Basic Workflow

1. **Import a project**
   - Open the Project page.
   - Choose the `.esp/.esm/.esl` you want to translate.
   - The tool reads translatable text and tries to detect the game.
   - Confirm that the displayed mod file, game, language, and entry counts look
     correct.

2. **Configure AI**
   - Open AI Settings.
   - Create or select a provider profile.
   - API keys are stored locally in `translator/profiles/.env`.
   - Use the probe/test button to confirm the selected model works.

3. **Inspect entries**
   - Open Entries.
   - Filter by text type, field, and status.
   - Use the source/destination panel to inspect full text and context.
   - Placeholder-only, number-only, and code-like content should not be sent to AI.

4. **Prepare terminology**
   - Open Glossary.
   - Player terms fix preferred translations, such as `Watchtower -> 守望塔`.
   - Do-not-translate terms force names, tags, and variables to remain unchanged.
   - Game terminology is recalled automatically from the current text; player
     entries take priority.

5. **Submit translation work**
   - Select entries, or use Fanatic Mode to submit all currently filtered entries.
   - Batch size controls how many texts go into one AI request.
   - If the prompt may exceed the model context, reduce batch size or terminology
     budgets.

6. **Preview the prompt**
   - Open Prompt.
   - Before AI translation starts, review the system prompt, entries, and terms.
   - Confirm the current group when unsure; approve all remaining groups only when
     the prompt is clearly correct.

7. **Monitor progress**
   - Open Batches.
   - Watch group status, completed counts, failures, and logs.
   - Stop requests only take effect at safe checkpoints; already-sent provider
     requests may still bill.
   - History is for audit unless a real resume action is shown.

8. **Review and fix**
   - Return to Entries and filter by needs-review, untranslated, or locked.
   - Needs-review maps to xTranslator-style partial translation.
   - Locked entries should remain unchanged and should not be sent to AI again.

9. **Export SST**
   - Open Project.
   - Click Export xTranslator File.
   - Open the export directory and find the `.sst`.
   - Import it in xTranslator and Finalize there.

## Pages

- **Project**: import plugin, project metadata, record signature statistics, SST export.
- **Entries**: filter, inspect, edit, quick translate, multi-select, submit queue.
- **Batches**: current/history progress, stop request, audit logs.
- **Prompt**: review the prompt and approve/skip/discard current work.
- **AI Settings**: providers, models, concurrency, rate limits, keys.
- **Glossary**: player terminology, do-not-translate rules, recalled game terms.
- **Logs**: technical logs for troubleshooting.

## Common Questions

**Why are some entries not sent to AI?**

Pure numbers, placeholders, variables, and tags like `<Alias=...>` usually must
stay unchanged. Translating them can break dynamic in-game text.

**Why does xTranslator show partial translation?**

Those entries should appear as needs-review in this GUI. If GUI counts disagree
with xTranslator, fix the status mismatch before publishing.

**Why do I still need xTranslator?**

bgs-translator creates AI-assisted translation memory and SST dictionaries.
xTranslator imports the dictionary and produces the final game string files.

**Can I skip prompt preview?**

Yes, but it is recommended only when you understand the project and model well.
Most players should preview prompts to avoid sending wrong rules to AI.

**Can I trust the cost display?**

Provider and proxy pricing differs. Treat the provider dashboard as the source
of truth for billing.

## Working With an AI Agent

A good agent workflow is:

1. Research the mod page, readme, and sampled entries.
2. Write detailed game context and mod context.
3. Generate the system prompt and show it for review.
4. Translate only after approval.
5. Export SST and report remaining needs-review items.

Do not ask the agent to modify the original plugin file directly.

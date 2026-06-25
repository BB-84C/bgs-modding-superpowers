---
id: install-planning.mod-update-post-state-discipline.v1
title: Intent-aware mutation discipline in mod management
kind: rule
domains: [install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: "A mod-management mutation is complete only when its EFFECT has been verified against the agent's INTENT across every dependent MO2 state dimension. File replacement, meta.ini fields, folder naming, modlist.txt line text, separator ownership, enable flag, and runtime compatibility are separate dimensions; touching one dimension does not prove the full intent was satisfied. After acting, observe the resulting state and reconcile any intent-coverage gaps before declaring the update solved."
  confidence: high
queryKeys: [mod update workflow, separator placement, enable state, modlist.txt, multi-dimensional state, ReAct discipline, post-update verification, observability, latest version compatibility, runtime support verification, changelog check, Game Version 1.16.244, Game Version 1.16.242]
severity: high
sources:
  - kind: project-internal-doc
    url: "https://github.com/BB-84C/bgs-modding-superpowers/blob/main/docs/modpack-dev-logs/bb84-starfield/dev-log.md"
    ref: "BB84 2026-06-24 round-2 audit P2c separator drift report"
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Intent-aware mutation discipline in mod management

Every mod-management action has an **intent** and an **effect**. The intent is the job the agent meant to complete: make a mod usable on the current runtime, update curator-visible state, re-track a Nexus listing, or retire a broken component. The effect is what actually changed in MO2. A command response only proves that an action ran; it does not prove that the effect covers the intent.

The discipline is therefore: after a mutation, verify the effect against the original intent, not against the success envelope. If the action covered only one state dimension while the intent depends on several, the update is only partially complete.

## MO2 mod state is multi-dimensional

A mod's runtime and curator-facing identity in MO2 is not a single field. It is a bundle of dependent dimensions:

- the files in the mod folder, which determine what the game can load;
- `meta.ini`, which carries update metadata, status annotations, source IDs, comments, notes, and version fields;
- the folder name under `<MO2Root>/mods/`, which often encodes version or runtime-support information for humans;
- the `modlist.txt` line text, which must match the folder name exactly;
- the `modlist.txt` line position, which determines separator ownership and therefore how the curator reads the mod's state in MO2's GUI;
- the `modlist.txt` enable flag, which decides whether the mod participates in the active build;
- for runtime-bound plugins, the external game runtime and the author's stated support ceiling.

File replacement is only one dimension. It is often necessary, but it is not a proof that the update intent has been satisfied.

## The intent-coverage failure family

The common root mistake is narrowing the intent from "make this mod correct in the current pack" to "replace the archive contents." That action may leave three broad gap classes:

- **Runtime-support gap** — the latest published file exists, but the author only claims support for an older game runtime. The files are newer than before, yet the mod still fails the original compatibility intent.
- **Classification gap** — the files were replaced, but the mod remains disabled or parked under a curator's `版本已过期`, `等待作者更新`, `观望`, or `[弃用]` separator. The GUI still communicates "not usable" even if the content might now be usable.
- **Metadata gap** — `meta.ini`, folder name, or `modlist.txt` text still point at the old version, old modid, or old support ceiling. The machine and the curator now see inconsistent identities.

These are not separate ad-hoc rules. They are all the same thinking failure: the action covered one dimension, while the intent required multiple dimensions to agree.

## Mental check after acting

After any non-trivial mod update, ask:

> Did the observed post-state satisfy my intent across every dependent dimension, or did I only verify the dimension I directly touched?

Think through the state dimensions as prompts:

- If the intent was runtime compatibility, what does the new file's author actually claim about the current `<game>.exe` `FileVersion`?
- If the intent was curator-visible recovery, does the separator and enable flag now communicate "active and working" rather than "waiting" or "deprecated"?
- If the intent involved a version or source change, do `meta.ini`, folder name, and `modlist.txt` line text now describe the same mod identity?
- If a delegated fixer performed the action, did it only report what it ran, or did someone observe the resulting MO2 state?

The following PowerShell is one practical observation pattern. It is an implementation aid, not the discipline itself:

```powershell
# Check folder
Test-Path "<MO2Root>\mods\<expected new folder name>"

# Check meta.ini fields
$c = [IO.File]::ReadAllText("<modDir>\meta.ini", [Text.UTF8Encoding]::new($false))
# Verify: version, newestVersion, installationFile, lastNexusUpdate match target

# Check modlist.txt line + enable + separator ownership
$lines = Get-Content "<MO2Root>\profiles\<profile>\modlist.txt" -Encoding UTF8
for ($i = 0; $i -lt $lines.Count; $i++) {
  $clean = $lines[$i] -replace '^[+\-\*]', ''
  if ($clean -eq "<expected new folder name>") {
    $enabled = $lines[$i].StartsWith('+')
    # Find owning separator (next separator below in file = above in GUI)
    for ($j = $i + 1; $j -lt $lines.Count; $j++) {
      if ($lines[$j] -match '_separator$') {
        $sep = ($lines[$j] -replace '^[+\-\*]', '' -replace '_separator$', '')
        return @{ enabled = $enabled; separator = $sep; line = $i }
      }
    }
  }
}
```

If observation reveals a mismatch with intent — for example a mod is still in a waiting separator, still disabled, or still claims an old runtime ceiling — report that mismatch and propose the next mutation. Do not call the update complete.

## Runtime-support claims are part of the effect

Runtime-bound plugin mods add another dimension: the author's support claim. Nexus' "latest" file is only the latest published file, not a guarantee that the author has caught up to the user's current game runtime.

The mental model is simple: compare the author's latest explicit support statement with the local `<game>.exe` `FileVersion`. If the changelog or API file description says "Added support for Game Version X.Y.Z" and the local game is newer, then installing that file improved the version dimension but did not satisfy the compatibility intent. The appropriate state is "waiting for author update": keep the closest candidate if useful, tag the support ceiling in curator-visible metadata, disable it if it cannot load, and place it where the curator expects waiting items to live.

The inverse is also possible: a Nexus listing can be hidden or unpublished while its last file still works on the current runtime. Status and compatibility are different dimensions; observe both before deciding.

## Illustrations, not exceptions

- In one Starfield audit, several SFSE plugin mods had their files replaced but remained under `版本已过期` / `等待作者更新` separators or disabled. The action succeeded, but the curator-facing state still said "still broken".
- CharGenMenu #6850 v1.1.0.22 was the latest published file, but its changelog only claimed Game Version 1.16.242 while the local game was 1.16.244. Updating to latest did not satisfy the runtime-compatibility intent; the correct observed state was still "waiting for author update".
- The same pattern applies beyond these cases: any time action scope is narrower than intent scope, observe and reconcile before reporting completion.

## Cross-link

- `engine.xse-update-workflow.v1` — xSE plugin cascade workflow (where this discipline applies directly)
- `mod-evaluation.investigating-pulled-mods.v1` — applies the same observation discipline to pulled-mod investigations
- `.opencode/memory/45-mo2-mcp-internals.md` rule 20 — codifies the orchestrator-level intent-aware mutation discipline

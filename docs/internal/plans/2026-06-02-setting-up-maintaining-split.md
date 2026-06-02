# Setting-up vs maintaining skill split

## Stay in setting-up

- `## Hard guardrails` — These are first-run safety boundaries for any install path and must be visible before MO2/xEdit setup actions.
- `## What the control plane actually is` — This explains the install-time substrate so first-run agents do not try to build or deploy the wrong component.
- `## Workflow` / `### Step 1 - Detect MO2 install` — MO2 discovery is the entry point for first-run setup.
- `### Step 2 - If MO2 absent: branch the user` — The install / no-MO2 branch is strictly first-run setup.
- `### Step 3 - Install the MO2 control plane (Python + broker)` — Control-plane deployment is an install-time action.
- `### Step 4 - Start MO2 visibly` — Visible launch is required to prove setup state after install.
- `### Step 5 - Ask the user whether they want xEdit` — xEdit is an install-time optional component with an explicit consent gate.
- `### Step 6 - If yes: fetch xEdit from BB-84C/TES5Edit` — First acquisition of xEdit belongs in setup; ongoing version-pinning advice should be handled by the maintaining skill.
- `### Step 7 - Deploy the xEdit hook bridge` — Hook bridge deployment is first-run runtime tooling setup.
- `### Step 8 - Initialize dev-log and release-changelog` — Initial project documentation scaffolding is part of first-run project setup; ongoing entries remain with the dev-log / changelog skills.
- `### Step 9 - Verify with a semantic smoke test (NON-BLOCKING)` — This remains as the first-run acceptance smoke; the maintaining skill will have a lighter recurring health-check variant.
- `## Acceptance (semantic, not surface)` — First-run completion criteria belong with the first-run workflow.
- `## Common mistakes` — Current bullets are setup-specific guardrails against unsafe install / launch behavior and should stay.
- `## See also` — Keep, with an added pointer to the new maintaining skill.

## Move to maintaining-modding-environments

- None as full sections in the current `setting-up-bgs-modding-environment` skill. The current body is already mostly first-run install / semantic smoke. KB-3 should add the ongoing-care surface as a new skill rather than deleting large first-run sections.
- `### Step 6 - If yes: fetch xEdit from BB-84C/TES5Edit` — Do not move the section, but migrate the generic version-pinning concept (`-ReleaseTag v<X.Y.Z>`) into maintaining as recurring version-pinning advice. Setup should keep only enough detail to install xEdit the first time.
- `### Step 9 - Verify with a semantic smoke test (NON-BLOCKING)` — Do not move the section, but migrate the reusable health-check idea into maintaining. Setup should keep this as first-run acceptance; maintaining should provide the recurring `bgs_kb_status` / `bgs_kb_query` and xEdit/MO2 sanity-check patterns.

## Net new in maintaining

- KB update checks via `bgs_kb_check_updates` when present, or GitHub Releases fallback before KB-6 lands.
- KB pack installation via `bgs_kb_install_pack` when present, with user-consent download and sha256 verification; before KB-6, describe the manual GitHub Release artifact path.
- Cache hygiene for `%LOCALAPPDATA%/bgs-modding-superpowers/kb/packs/<packId>/<version>/`, keeping current + previous versions as fallback.
- Custom pack authoring and registration: records under `<pack-root>/records/<domain>/<id>.md`, required `bgs-kb-meta.yml`, build / validate / info CLI commands.
- `BGS_KB_USER_PACKS` registration with precise semantics: entries are roots that contain one or more pack directories, not the pack directory itself.
- Reserved official pack IDs: `bgs-kb-core`, `bgs-kb-skyrim`, `bgs-kb-fallout4`, `bgs-kb-fallout3-fnv`, `bgs-kb-starfield`; recommend `user-*` for end-user packs.
- Version-pinning guidance for KB pack versions vs latest, and warnings when a pack's `minPluginVersion` exceeds the installed plugin version.
- Maintenance health checks using `bgs_kb_status`, `bgs_kb_query`, and a clear reminder that KB records are advisory while xEdit readback is authoritative for runtime plugin / load-order state.

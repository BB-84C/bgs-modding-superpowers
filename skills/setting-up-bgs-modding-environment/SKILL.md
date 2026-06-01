---
name: setting-up-bgs-modding-environment
description: "Use on first install of this plugin, when MO2 or xEdit is not yet detected, when starting a new modpack project, or when the user says 'set up', 'install', 'bootstrap', 'configure', or 'initialize' the BGS modding environment. Orchestrates: MO2 detection and control-plane install, optional xEdit download from BB-84C/TES5Edit, dev-log and release-changelog initialization, and end-to-end semantic smoke verification."
---

# Setting Up the BGS Modding Environment

This is the first-run bootstrap. Use it when:

- The user installed `bgs-modding-superpowers` and this is the first conversation
  in their project directory.
- A new modpack project is being set up from scratch.
- MO2 path is not yet known to the agent.
- The user explicitly asks to "set up", "install", "bootstrap", "configure", or
  "initialize" the BGS modding environment.
- A subsequent skill (e.g., `xedit-automation`) finds the environment incomplete
  and routes back here.

## Hard guardrails

- **Do NOT install MO2 yourself by default.** The default path is to detect MO2
  and, if absent, guide the human user to install it themselves. Agent-driven
  install requires explicit user consent ("yes, install MO2 for me").
- **Never write into the user's vanilla game install** (e.g.,
  `<Steam>/steamapps/common/<Game>/Data/`). All overlays go through MO2.
- **Treat the user's existing MO2 profile as canonical.** Do not silently mutate
  `profiles/<Profile>/plugins.txt`, `modlist.txt`, INIs, or load order.
- **Pause and surface state before each install action.** The user should always
  know which MO2 root, which profile, and which file is about to be touched
  before it happens.

## Workflow

### Step 1 - Detect MO2 install

Search for `ModOrganizer.exe` in common locations:

- `$env:LOCALAPPDATA\ModOrganizer*\ModOrganizer.exe`
- `D:\ModOrganizer*\ModOrganizer.exe`, `E:\ModOrganizer*\ModOrganizer.exe`,
  `C:\ModOrganizer*\ModOrganizer.exe`
- The user's Documents folder.
- The user's Desktop / common steam-library siblings.

If exactly one MO2 install is found, propose it to the user for confirmation.
If multiple, list them with paths and ask which is the target. If none, go to
step 2.

Persist the confirmed install root in conversation context as `MO2_Root`. All
subsequent steps reference this variable.

### Step 2 - If MO2 absent: branch the user

Surface a `[BLOCKED]` notice and offer THREE paths, in order of preference:

**(a) Default - human install.** Provide the official MO2 release URL:
https://github.com/ModOrganizer2/modorganizer/releases/latest. Give the user
a brief setup outline (download installer, pick an install root outside Program
Files, launch once to initialize). Wait for the user to install and come back
with the path.

**(b) Agent-handled install (explicit user consent required).** Only if the
user says something like "yes, install MO2 for me, go ahead": download the
official MO2 installer to a temp location, run it (silent install where
supported), register the resulting path as `MO2_Root`. Surface every step
("downloading from ...", "installing to ...", "MO2 ready at ..."). Never
proceed without the explicit verbal consent.

**(c) No-MO2 mode.** If the user says "I do not need MO2 for this project"
(e.g., they are writing modpack docs / planning without a runtime), record
`MO2_Root = none` and skip directly to step 7 (dev-log / changelog init). Mark
that any MO2-bound or xEdit-bound work will be unavailable until they revisit
this skill.

### Step 3 - Install the bgs-modding-superpowers MO2 control plane

Once `MO2_Root` is known (path a or b), deploy the C++ control-plane plugin DLL,
the Python loader, and the broker into the user's MO2:

```powershell
& "<plugin-root>/scripts/install-mo2-control-plane.ps1" -MO2Root "<MO2_Root>"
```

This deploys:

- `tools/mo2-control-plane/plugin/build/Mo2AgentControl.dll` -> `<MO2_Root>/plugins/`
- `tools/mo2-control-plane/live-bridge/mo2_agent_control.py` -> `<MO2_Root>/plugins/`
- The broker binaries -> their canonical install path under MO2.

After the script returns, list `<MO2_Root>/plugins/` and confirm both files are
present. If the script reports an error, stop and surface it; do not continue.

### Step 4 - Ask the user whether they want xEdit

xEdit is optional but high-value. Describe what it does so the user can make
an informed choice:

> "xEdit is the canonical editor for Bethesda plugin files (.esp / .esm / .esl).
> Modpack curators use it to resolve conflicts between mods, generate
> compatibility patches, flag plugins as ESL (light) to free up load-order
> slots, clean stray edits (ITM / UDR), and run Pascal-based bulk edits.
> With this plugin's bundled `xedit` MCP, your agent can drive xEdit
> programmatically - no GUI clicks required."

Then ask: "Would you like me to install xEdit?" - explicit consent gate.

If the user declines, skip to step 7.

### Step 5 - If yes: fetch xEdit from BB-84C/TES5Edit

The forked, agent-friendly xEdit lives at https://github.com/BB-84C/TES5Edit.
Fetch its latest release into the MO2 tools tree:

```powershell
& "<plugin-root>/scripts/fetch-xedit-release.ps1" -MO2Root "<MO2_Root>"
```

This downloads the latest release zip, extracts into
`<MO2_Root>/tools/xEdit/`, and verifies `xEdit.exe` exists post-extract. To
pin a specific tag, pass `-ReleaseTag v<X.Y.Z>`.

### Step 6 - Deploy the xEdit hook bridge

`xEditHookBridge.dll` ships with THIS plugin (it is OWNED by
`bgs-modding-superpowers`, NOT by the xEdit fork). Co-locate it with
`xEdit.exe`:

```powershell
& "<plugin-root>/scripts/install-xedit-hook-bridge.ps1" -MO2Root "<MO2_Root>"
```

This copies `tools/xedit-hook-bridge/dist/xEditHookBridge.dll` into
`<MO2_Root>/tools/xEdit/`. The xEdit daemon will find it there at runtime.

### Step 7 - Initialize dev-log and release-changelog

Ask the user for their **modpack project root**. This is usually one of:

- `<MO2_Root>/profiles/<ProfileName>/` (if the profile is the unit of work).
- A separate Git-tracked source directory the user maintains (more common for
  released modpacks).

Once `<project_root>` is known, route to:

- `writing-modpack-devlog` skill - creates `<project_root>/docs/dev-log.md` with
  the project name and start date as the first entry.
- `writing-modpack-changelog` skill - creates
  `<project_root>/docs/release-changelog.md` skeleton.

From here on, those two skills maintain the files at runtime; do not template
or pre-fill them in this skill.

### Step 8 - Verify with a semantic smoke test

Run the xEdit MCP smoke test (skip if user chose no-MO2 mode in step 2c or
declined xEdit in step 4):

1. `xedit_session({})` - expect `ok: true` with `gameMode`, `loadOrderSize`,
   and a fresh daemon PID.
2. `xedit_list_capabilities({})` - expect ~49 commands and an empty
   `drift.onlyInDigest`.

If both pass: surface `[OK] BGS modding environment ready` with the recorded
`MO2_Root`, xEdit path (if installed), and project root.

If either fails: surface the failure exactly (error code, daemon PID, log path
if any) and STOP. Do not declare success.

## Acceptance (semantic, not surface)

The setup is complete only when ALL of the following hold. Do not declare
success otherwise:

- `<MO2_Root>` is known and `<MO2_Root>/ModOrganizer.exe` exists.
- `<MO2_Root>/plugins/Mo2AgentControl.dll` and
  `<MO2_Root>/plugins/mo2_agent_control.py` both exist (skipped only in no-MO2
  mode).
- If xEdit was chosen: `<MO2_Root>/tools/xEdit/xEdit.exe` AND
  `<MO2_Root>/tools/xEdit/xEditHookBridge.dll` both exist.
- `<project_root>/docs/dev-log.md` and
  `<project_root>/docs/release-changelog.md` both exist (or user explicitly
  declined - record the decline in conversation context).
- `xedit_session` and `xedit_list_capabilities` MCP calls both succeed
  (skipped only if xEdit was declined or no-MO2 mode).

In no-MO2 mode, only the dev-log and changelog steps need to pass.

## Common mistakes

- Skipping the consent gate on step 2(b) or step 4. Both REQUIRE explicit user
  agreement; silent install or silent install-decision is forbidden.
- Silently choosing one MO2 install when multiple are detected. Always ask.
- Treating the absence of `Mo2AgentControl.dll` as fatal during very early
  plugin development (before the build pipeline lands). Surface clearly; do not
  pretend the install succeeded.
- Writing into the user's vanilla game install directly instead of via MO2
  overlay. NEVER do this. See `using-bgs-modding-superpowers` rule 1.
- Declaring success on a green script return without the semantic readback
  (the file existence checks and the MCP smoke calls).

## See also

- `using-bgs-modding-superpowers` - the per-session bootstrap; lists the full
  skill inventory and hard rules.
- `xedit-automation` - hub skill for all xEdit work; load after this skill
  succeeds.
- `writing-modpack-devlog`, `writing-modpack-changelog` - runtime asset skills
  invoked from step 7.
- The installer scripts under `scripts/`: `install-mo2-control-plane.ps1`,
  `fetch-xedit-release.ps1`, `install-xedit-hook-bridge.ps1`. These are
  authored in plan phases P6 and P7; if they are missing, surface that we are
  before-P6 and proceed only as far as the existing scripts allow.

# xedit-cli Model-Layer Selection Design

## Goal

Validate and then exploit xEdit's own internal module-selection model so `xedit-cli` can express real agent-facing `only` and `exclude` semantics without degenerating into slow, fragile per-row UI clicking.

## Problem Statement

The current no-fork hook path has already proven several important things:

- MO2/usvfs semantics are available in the project-local sandbox
- real xEdit launches are possible through the MO2 control plane path
- `load all` can be automated
- the real `Module Selection` dialog and the real `TVirtualStringTree` child window can be detected

The current blocker is narrower:

- the injected DLL cannot reliably recover the host xEdit VCL object graph from window handles
- specifically, `FindControl/GetParentForm/Screen.Forms` in the injected DLL do not recover the real `TfrmModuleSelect` instance

That means continued investment in HWND-to-host-VCL recovery is increasingly poor leverage.

At the same time, upstream xEdit source strongly suggests the real selection semantics are not stored in the tree widget itself.

## Source-Grounded Model Insight

Upstream `xeModuleSelectForm` implements module selection through a model layer:

- `AllModules: TwbModuleInfos`
- `SelectedModules: TwbModuleInfos`
- `FilteredModules: TwbModuleInfos`
- `SelectFlag: TwbModuleFlag`
- `SimulateLoad`

The actual UI checkbox actions merely update module flags and then call `SimulateLoad`.

Important upstream patterns:

- bulk selection actions (`Select All`, `Select None`, `Invert Selection`) mutate `miFlags` and then call `SimulateLoad`
- `PresetLoad` clears all flags, sets requested module flags, then calls `SimulateLoad`
- `DoSingleModuleLoad` does the same for a single requested module

This indicates that the real semantic seam for `only` / `exclude` is the module model, not the `TVirtualStringTree` UI surface.

## Design Decision

Shift the next investigation/implementation slice from “recover and drive the real tree control” to “prove and use xEdit's own model-layer selection semantics.”

The first target is not final production code. It is a focused experiment that answers:

1. If we directly mutate `AllModules` flags and call `SimulateLoad`, do we get the correct `only` semantics?
2. If yes, can the same mechanism express `exclude`, including dependency-driven forced retention?
3. If that works, should the long-term integration use:
   - a small xEdit-side seam / patch
   - or a more surgical hook strategy aimed at the model layer instead of UI widgets?

## Recommended Experiment Shape

### Primary seam

Use xEdit's own model semantics:

- `AllModules.ExcludeAll(SelectFlag)`
- `Include(miFlags, SelectFlag)` for requested roots
- `Exclude(miFlags, SelectFlag)` for requested exclusions
- `SimulateLoad`

### First experiment target

Prove `only` first.

Recommended real scenario:

- requested root: `RaiderOverhaul.esp`
- expected retained dependency: `ArmorKeywords.esm`

### Second experiment target

After `only` is proven, validate `exclude` with:

- safe exclusion: `CraftingTools.esp`
- dependency-blocked exclusion: `ArmorKeywords.esm` while `RaiderOverhaul.esp` remains active

## Why This Is Better Than More Tree Work

### Advantages

- matches xEdit's own internal semantics
- avoids brittle tree/UI automation for agent-facing logic
- reuses the same dependency/reload logic xEdit already trusts
- gives higher-quality evidence about whether `only/exclude` are feasible at all

### What It Does Not Solve Yet

- it does not by itself decide the final no-fork production mechanism
- it does not magically make the current injected DLL able to call host methods
- it does not remove the need to decide later between:
  - a small xEdit-side patch
  - a host-method hook seam
  - continued no-fork experimentation

## Success Criteria For The Experiment

The experiment succeeds when, under the real `.artifacts\mo2` sandbox:

1. `only RaiderOverhaul.esp` produces a final selected set containing:
   - `RaiderOverhaul.esp`
   - `ArmorKeywords.esm`
2. `exclude CraftingTools.esp` removes that plugin from the final selected set when legal
3. `exclude ArmorKeywords.esm` keeps it in the final selected set when dependency rules require it
4. Evidence is retained in artifacts, not inferred from screenshots alone

## Explicit Non-Goals For This Slice

- perfecting synthetic fixture `exclude`
- recovering the full host VCL object graph from HWNDs
- general UI automation over `TVirtualStringTree`
- finalizing the long-term no-fork architecture before the model seam is proven

## Recommendation

Proceed with a focused model-layer experiment first.

If the model seam works, we will know the real blocker is access strategy, not xEdit semantics.

If the model seam does not work, then continued no-fork/UI investment should be reconsidered much earlier.

# xedit-cli Model-Layer Selection Decision

## Conclusion

Real `.artifacts\mo2` evidence now supports an explicit outcome for Task 5:

- xEdit semantics are good; access strategy is bad
- `AllModules`, `SelectFlag`, and `SimulateLoad` correctly express model layer `only` / `exclude` behavior
- `selection_method=model-layer` and `module-selection-confirmed` are present in live evidence
- legal exclusion removes `CraftingTools.esp`
- dependency-driven retention keeps `ArmorKeywords.esm` and reports it through `blocked_exclusions`

## Decision

The practical integration direction for `only` / `exclude` now favors a small xEdit-side patch.

The injected no-fork/tree route remains blocked because the host xEdit VCL object graph cannot yet be recovered reliably from the injected context. Current HWND/tree probing remains diagnostic only.

A no-fork path with a different seam may still be researched later, but it is no longer the primary plan.

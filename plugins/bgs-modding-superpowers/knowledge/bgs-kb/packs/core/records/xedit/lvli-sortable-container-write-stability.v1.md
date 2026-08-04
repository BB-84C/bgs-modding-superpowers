---
id: xedit.lvli-sortable-container-write-stability.v1
title: Capture LVLI entry references before writes can reorder the list
kind: gotcha
domains: [xedit, plugin-format, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: xEdit can sort a leveled-list entry container after a referenced-form write, so an index selected before the first write is not stable for the next one. Capture entry interfaces first, mutate through those references, and inspect the returned locator after elements.set_value rather than treating the requested array index as durable identity.
  confidence: verified-project-doc
queryKeys: [LVLI reorder, leveled list index write, sortable container, elements.set_value locator path, stable element reference]
severity: high
sources:
  - kind: github-issue
    url: "https://github.com/BB-84C/bgs-modding-superpowers/issues/29"
    ref: "Issue #29: xEdit sortable-container write investigation"
    sectionPath: "1. xEdit re-sorts leveled-list entries after every edit"
related:
  - xedit.copy-into-deepcopy-for-structured-overrides.v1
  - plugin-format.lvli-entry-conditions-vendor-stock.v1
lastReviewed: "2026-08-02"
schemaVersion: 1
---

# Capture LVLI entry references before writes can reorder the list

`Leveled List Entries` is a sortable container. In the verified Starfield case, setting a referenced record value re-sorted the array, placing null entries first and then ordering referenced FormIDs. The next `ElementByIndex(entries, i)` therefore addressed a different `LVLO` than the loop author intended.

For a multi-entry edit, first capture every entry interface into a stable local array. Only then resolve `LVLO - Base Data` and set each referenced form through the captured interface. Do not interleave index lookup and mutation.

The daemon-side `elements.set_value` response can return a different `locator.path` from the requested path after such a reorder. Treat that returned locator as readback evidence that the container moved; it is not cosmetic metadata. After the batch, read the full entry set back and compare each intended reference, level, count, and condition against the target design.

---
id: plugin-format.lvli-entry-conditions-vendor-stock.v1
title: LVLI entry-level conditions are first-class suspects in vendor stock diagnosis
kind: rule
domains: [plugin-format, xedit, debugging]
appliesTo:
  games: [Starfield, Fallout4, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine, creation-engine-2]
canonical:
  answer: "Vendor stock can disappear because individual leveled-list entries have CTDA conditions, not because the whole LVLI or vendor container is empty. Diagnose vendor shortages in order: winning CONT override, LVLI chain integrity, entry-level Conditions, entry level vs player level, buy/sell keyword FLST filters, and container reset timing."
  confidence: verified-project-doc
queryKeys:
  - LVLI entry conditions
  - leveled list entry CTDA
  - vendor missing stock
  - vendor container override
  - Use All leveled list
  - buy sell keyword filter
  - GetGlobalValue
severity: high
sources:
  - kind: project-internal-doc
    ref: BB84 Starfield P10 Wave 3.5-4 field notes
    sectionPath: Starvival vendor spaceship items LVLI stock diagnosis
related:
  - load-order.cross-cutting-record-audit.v1
  - pack-curation.leveled-list-overhaul-coherence-discipline.v1
  - install-planning.partial-disable-requires-author-toggle.v1
lastReviewed: "2026-07-05"
schemaVersion: 1
---

# LVLI entry-level conditions are first-class suspects in vendor stock diagnosis

## The trap

`LVLI` records are not just arrays of entries. Individual Leveled List Entry rows can carry their own `Conditions` block. A vendor can therefore have a winning container, a present leveled list, and intact sublists while most categories silently fail their entry conditions.

This often looks like a broken leveled list, a missing injection, or a wiped vendor container. In reality, the author may have made stock conditional on a config global, quest state, DLC flag, player level, or feature toggle.

## Vendor shortage diagnostic order

For a vendor that is missing expected items, check:

1. **Winning `CONT` override**: which plugin wins the vendor container, and did it preserve all item-list links?
2. **LVLI chain integrity**: follow each referenced list and sublist; verify the chain is present in the winner.
3. **Entry-level `Conditions`**: inspect conditions on each Leveled List Entry, not only on the LVLI record header.
4. **Entry level vs player level**: verify the entry's level gate against the test character.
5. **Buy/sell keyword filters**: verify vendor faction/container keyword FLST rules do not filter the category.
6. **Inventory reset timing**: confirm the vendor container had a chance to reset after the patch or config change.

## Starvival spaceship vendor example

Starvival's `_SISA_LeveledList_Vendor_Spaceship_Items [LVLI:31000ADB]` used `Use All` and seven category sublists. Five category entries were individually conditioned on `GetGlobalValue(FuelToggle) == 1`. In the user's stack, Real Fuel owned ship fuel and the Starvival fuel system had never activated, so the fuel toggle global stayed `0`. Result: the vendor sold only the unconditional Misc category, looking as if the leveled list had been emptied.

The same case had a separate container conflict: another mod, `caracal_venera`, overrode the same vendor container (`CONT:0012DF01`) to change the credits list and accidentally displaced Starvival's item lists. That is a merge-patch problem, not necessarily a plugin-order problem: preserve the credit change and restore the intended stock lists in a dedicated compatibility patch.

## Patch shape

When an entry condition encodes the wrong feature authority, prefer replacing it with the semantically correct toggle over deleting the condition. In the Starvival case, changing the condition from the fuel-system toggle to the maintenance-system toggle better preserved the author's intent than unconditional stock injection.

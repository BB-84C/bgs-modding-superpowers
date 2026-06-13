# Plan A acceptance — CLI ↔ MO2 Conflicts tab cross-check

**Status:** PENDING — deferred to combined acceptance with Plan B Task 9.

The Plan A engine + CLI code is complete (commits `9ed82bd` through `c7e1054`
on branch `feat/archive-loose-file-helpers`). All 36 tests pass (34 unit
tests + 2 gated harness tests when the dev harness is present, skipped on
CI / fresh clones).

The semantic acceptance gate — comparing `mo2-assets mod-conflicts <MOD>`
output against MO2's own `信息 → 冲突 → 常规` dialog for a real mod from
`.artifacts/mo2` — is the same kind of human-in-the-loop step as Plan B's
GUI acceptance (Plan B Task 9). Both will be exercised together once the
Plan B IPluginTool plugin lands.

## How to complete this acceptance

1. Open MO2 against the `.artifacts/mo2` harness.
2. Pick a real mod with known loose-file conflicts.
3. Run the CLI:
   ```powershell
   mo2-assets mod-conflicts "<MOD_NAME>" `
     --profile "D:\awesome-bgs-mod-master\.artifacts\mo2\profiles\Default" `
     --mods "D:\awesome-bgs-mod-master\.artifacts\mo2\mods" `
     --game fallout4 `
     --format json `
     > .opencode\artifacts\mo2-assets-engine\acceptance\cli-vs-mo2-conflicts\cli-<MOD>.json
   ```
4. In MO2, right-click the same mod → 信息 → 冲突 → 常规. Take a screenshot
   into this directory as `mo2-builtin-<MOD>.png`.
5. For each loose-file path in MO2's `冲突中被保留的文件` section, verify it
   also appears in the CLI JSON's `kept[].path`. Same for
   `冲突中被覆盖的文件` ↔ `overwritten[].path`.
6. Archive-bucket entries in the CLI output are EXPECTED to have no MO2
   counterpart — that is the gap this engine fills.
7. Fill in the verdict below and remove this "PENDING" header.

## Verdict (fill in at acceptance time)

| Gate | Verdict | Notes |
|---|---|---|
| CLI vs MO2 agreement on loose slice | PASS / FAIL | <count agreeing> |
| Archive-bucket entries surface coherently | PASS / FAIL | <sample 3> |

## Files

- `cli-<MOD>.json` — CLI output (will be created at acceptance).
- `mo2-builtin-<MOD>.png` — MO2 Conflicts-tab screenshot (will be created).

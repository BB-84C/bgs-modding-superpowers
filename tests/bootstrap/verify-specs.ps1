$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path

$requiredPaths = @(
    "tools/xedit-cli/README.md",
    "tools/xedit-cli/CONTRACT.md",
    "tools/xedit-cli/live-integration.md"
)

$missing = $requiredPaths | Where-Object { -not (Test-Path (Join-Path $repoRoot $_)) }
if ($missing.Count -gt 0) {
    throw "Missing spec files: $($missing -join ', ')"
}

$xeditReadme = Get-Content (Join-Path $repoRoot "tools/xedit-cli/README.md") -Raw
foreach ($phrase in @(
    "wrapper",
    "orchestrates upstream xEdit",
    "keep xEdit external",
    'approved step-1 target contract',
    "step-1 hook bridge",
    "Module Selection",
    "--load-mode",
    "all|only|exclude",
    'repeatable `--plugin`',
    '`all` forbids `--plugin`',
    '`only` and `exclude` require at least one repeatable `--plugin` argument',
    "MO2-backed",
    "source of truth for full plugin order",
    'caller chooses a subset, but the MO2-backed active list remains the source of truth',
    'preserve MO2 order',
    "no-fork",
    "hook.dll",
    "launcher path",
    'require authoritative `--game-mode`',
    'primary trust and control signal',
    'maps `Fallout4` to `-FO4`, `Skyrim` to `-TES5`, `SkyrimSE` to `-SSE`, and `Starfield` to `-SF1`',
    '`-FO4`',
    '`-TES5`',
    '`-SSE`',
    '`-SF1`',
    "PID-based",
    "target contract",
    "conflict indexing",
    "inspection",
    "SQLite-backed",
    "drilldown"
)) {
    if ($xeditReadme -notmatch [regex]::Escape($phrase)) {
        throw "tools/xedit-cli/README.md is missing phrase: $phrase"
    }
}

$contract = Get-Content (Join-Path $repoRoot "tools/xedit-cli/CONTRACT.md") -Raw
foreach ($heading in @(
    '## Goals',
    '## Read-Only Commands',
    '## Future Write Commands',
    '## Safety Rules',
    '### `xedit-cli doctor env`',
    '### `xedit-cli conflicts index`',
    '### `xedit-cli conflicts inspect`',
    '### `xedit-cli process launch`',
    '### `xedit-cli process status`',
    '### `xedit-cli process wait`',
    '### `xedit-cli process stop`'
)) {
    if ($contract -notmatch [regex]::Escape($heading)) {
        throw "xedit-cli contract is missing heading: $heading"
    }
}

foreach ($phrase in @(
    'target contract',
    'step-1 hook bridge',
    'Module Selection',
    '--load-mode',
    'all|only|exclude',
    'repeatable `--plugin`',
    '`all` forbids `--plugin`',
    '`only` and `exclude` require at least one repeatable `--plugin` argument',
    'source of truth for full plugin order',
    'Plugin names must match the MO2-backed active set',
    'caller chooses a subset, but MO2 remains the source of truth for full plugin order',
    '`only` preserves MO2 order among requested roots',
    '`exclude` starts from the MO2-backed active set',
    'no-fork',
    'hook.dll',
    'launch xEdit itself',
    'caller-provided launcher path',
    'launcher path',
    'raw PID',
    'MO2 discovery outside the CLI',
    'Current-slice implementation:',
    '--launcher-path',
    '--game-mode',
    '--xedit-pid',
    'require authoritative `--game-mode`',
    'primary trust and control signal',
    'authoritative `--game-mode`',
    'explicit mapped mode argument instead of filename inference',
    '`Fallout4 -> -FO4`, `Skyrim -> -TES5`, `SkyrimSE -> -SSE`, and `Starfield -> -SF1`',
    'maps supported game modes to explicit xEdit mode arguments',
    '`SkyrimSE` to `-SSE`',
    'simple `.bat`/`.cmd` wrappers',
    'complex wrappers fail closed',
    'later Phase 1 work',
    'Target flow:',
    'Target command surface:'
)) {
    if ($contract -notmatch [regex]::Escape($phrase)) {
        throw "xedit-cli contract is missing phrase: $phrase"
    }
}

if ($contract -match [regex]::Escape('launcher arguments')) {
    throw 'xedit-cli contract should use launcher path wording instead of launcher arguments'
}

$liveIntegration = Get-Content (Join-Path $repoRoot "tools/xedit-cli/live-integration.md") -Raw
foreach ($phrase in @(
    'later Phase 1 task',
    'step-1 hook bridge',
    'Module Selection',
    '--load-mode',
    'all|only|exclude',
    'repeatable `--plugin`',
    '`all` forbids `--plugin`',
    '`only` and `exclude` require repeatable `--plugin` args',
    'source of truth for full plugin order',
    'plugin names must match the MO2-backed active set',
    '`exclude` starts from the MO2-backed active set',
    'subset results preserve MO2 order',
    'no-fork',
    'hook.dll',
    'caller-provided launcher path',
    'raw PID',
    'raw PID outputs',
    'require authoritative `--game-mode`',
    'primary trust and control signal',
    'direct `.exe` launchers',
    '`Fallout4 -> -FO4`, `Skyrim -> -TES5`, `SkyrimSE -> -SSE`, and `Starfield -> -SF1`',
    '`SkyrimSE` to `-SSE`',
    'The first live `conflicts index` launch path requires both `--launcher-path` and authoritative `--game-mode`',
    'launched process exits non-zero',
    'normalized to explicit launch commands',
    'complex wrappers fail closed'
)) {
    if ($liveIntegration -notmatch [regex]::Escape($phrase)) {
        throw "tools/xedit-cli/live-integration.md is missing phrase: $phrase"
    }
}

if ($contract -match [regex]::Escape('validates the caller-provided launcher path and game mode before a scan starts')) {
    throw 'xedit-cli contract should not describe launcher-path validation as the current implementation before Task 2 lands'
}

foreach ($check in @(
    @{ Content = $xeditReadme; Pattern = '(?i)step 1 adds|the CLI loads a no-fork `hook\.dll` bridge'; Message = 'tools/xedit-cli/README.md should frame the hook material as target-contract language, not shipped behavior' },
    @{ Content = $contract; Pattern = '(?i)Step 1 extends that launch contract with a step-1 hook bridge\.'; Message = 'xedit-cli contract should frame step 1 as a target contract, not an already-shipped extension' },
    @{ Content = $liveIntegration; Pattern = '(?i)Step 1 adds a step-1 hook bridge'; Message = 'tools/xedit-cli/live-integration.md should frame step 1 as a target contract, not shipped behavior' },
    @{ Content = $xeditReadme; Pattern = '(?i)optional\s+`?--game-mode`?|optional\s+game\s+mode|--game-mode\s+may\s+be\s+omitted|`--game-mode`\s+can\s+be\s+omitted'; Message = 'tools/xedit-cli/README.md should not describe --game-mode as optional' },
    @{ Content = $contract; Pattern = '(?i)optional\s+`?--game-mode`?|optional\s+game\s+mode|--game-mode\s+may\s+be\s+omitted|`--game-mode`\s+can\s+be\s+omitted'; Message = 'xedit-cli contract should not describe --game-mode as optional' },
    @{ Content = $liveIntegration; Pattern = '(?i)optional\s+`?--game-mode`?|optional\s+game\s+mode|--game-mode\s+may\s+be\s+omitted|`--game-mode`\s+can\s+be\s+omitted'; Message = 'tools/xedit-cli/live-integration.md should not describe --game-mode as optional' },
    @{ Content = $xeditReadme; Pattern = '(?i)executable-name\s+inference|filename-based\s+inference|infer.*FO4Edit|infer.*SSEEdit|infer.*SF1Edit|infer.*launcher\s+path|infer.*launcher\s+name|auto-detect.*launcher\s+name|derive.*basename'; Message = 'tools/xedit-cli/README.md should not drift toward filename inference' },
    @{ Content = $contract; Pattern = '(?i)executable-name\s+inference|filename-based\s+inference|infer.*FO4Edit|infer.*SSEEdit|infer.*SF1Edit|infer.*launcher\s+path|infer.*launcher\s+name|auto-detect.*launcher\s+name|derive.*basename'; Message = 'xedit-cli contract should not drift toward filename inference' },
    @{ Content = $liveIntegration; Pattern = '(?i)executable-name\s+inference|filename-based\s+inference|infer.*FO4Edit|infer.*SSEEdit|infer.*SF1Edit|infer.*launcher\s+path|infer.*launcher\s+name|auto-detect.*launcher\s+name|derive.*basename'; Message = 'tools/xedit-cli/live-integration.md should not drift toward filename inference' }
)) {
    if ($check.Content -match $check.Pattern) {
        throw $check.Message
    }
}

Write-Host "Spec bootstrap checks passed."

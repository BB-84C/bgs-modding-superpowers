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

<#
.SYNOPSIS
  Helper for authoring KB records in the bundled source tree.

.DESCRIPTION
  Runs the full author cycle for an in-repo KB pack:
    1. Pre-flight: `cli dev-status --pack <id>` to surface cross-root collisions
    2. Validate every record against the schema
    3. Build kb.sqlite + manifest.json from records/
    4. Optionally materialize the portable plugin tree

  Reminds the caller to restart OpenCode (MCP discovery is one-shot at startup)
  and to follow the two-commit shape from AGENTS.md 2026-06-03.

.PARAMETER PackId
  Pack id to author against. Examples: bgs-kb-core, bgs-kb-fallout4, bgs-kb-skyrim.
  For core, both 'bgs-kb-core' and the bare directory name 'core' work.

.PARAMETER SkipMaterialize
  Skip step 4 (materializing the portable plugin tree). Useful between batched
  KB edits when you want to run materialize once at the end.

.PARAMETER JsonStatus
  Request JSON-formatted dev-status output (machine-readable).

.EXAMPLE
  pwsh scripts/dev-kb-author.ps1 -PackId bgs-kb-core

.EXAMPLE
  pwsh scripts/dev-kb-author.ps1 -PackId bgs-kb-fallout4 -SkipMaterialize
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$PackId,

  [switch]$SkipMaterialize,

  [switch]$JsonStatus
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$cli = Join-Path $repoRoot 'tools\bgs-kb-mcp\dist\cli.js'
$packsRoot = Join-Path $repoRoot 'knowledge\bgs-kb\packs'

if (-not (Test-Path $cli)) {
  throw "cli not built: $cli (run 'npm run build' in tools/bgs-kb-mcp/ first)"
}

# Resolve pack root: 'bgs-kb-core' historically lives in 'core/' subdir, others under their own id.
$packRoot = Join-Path $packsRoot $PackId
if (-not (Test-Path $packRoot)) {
  if ($PackId -eq 'bgs-kb-core') {
    $packRoot = Join-Path $packsRoot 'core'
  }
  if (-not (Test-Path $packRoot)) {
    throw "pack root not found for '$PackId'. Looked at: $packRoot"
  }
}

Write-Host ('=== [1/{0}] dev-status preview (cross-root collision check) ===' -f $(if ($SkipMaterialize) { '3' } else { '4' })) -ForegroundColor Cyan
$statusArgs = @('dev-status', '--pack', $PackId)
if ($JsonStatus) { $statusArgs += '--json' }
& node $cli @statusArgs
if ($LASTEXITCODE -ne 0) { throw 'dev-status failed' }

Write-Host ''
Write-Host ('=== [2/{0}] validate ===' -f $(if ($SkipMaterialize) { '3' } else { '4' })) -ForegroundColor Cyan
& node $cli validate $packRoot
if ($LASTEXITCODE -ne 0) { throw 'validate failed' }

Write-Host ''
Write-Host ('=== [3/{0}] build ===' -f $(if ($SkipMaterialize) { '3' } else { '4' })) -ForegroundColor Cyan
$buildOutput = & node $cli build $packRoot 2>&1
$buildExit = $LASTEXITCODE
$buildOutput | ForEach-Object { Write-Host $_ }
if ($buildExit -ne 0) {
  # EBUSY on kb.sqlite means a live process (typically the OpenCode MCP server
  # in another shell) holds a read handle. The in-place rebuild script avoids
  # the unlink step entirely.
  $sawEbusy = ($buildOutput | Out-String) -match 'EBUSY|resource busy|locked'
  $rebuilder = Join-Path $repoRoot 'scripts\rebuild-locked-pack.mjs'
  if ($sawEbusy -and (Test-Path $rebuilder)) {
    Write-Host ''
    Write-Host 'EBUSY on kb.sqlite — falling back to in-place rebuild' -ForegroundColor Yellow
    Write-Host '  (typical cause: live MCP server holds a read handle; in-place DROP+CREATE bypasses unlink)' -ForegroundColor DarkGray
    & node $rebuilder $packRoot
    if ($LASTEXITCODE -ne 0) { throw 'in-place rebuild also failed' }
  } else {
    throw 'build failed'
  }
}

if (-not $SkipMaterialize) {
  Write-Host ''
  Write-Host '=== [4/4] materialize portable plugin tree ===' -ForegroundColor Cyan
  $materialize = Join-Path $repoRoot 'scripts\build-portable-plugin.ps1'
  if (-not (Test-Path $materialize)) {
    throw "materialize script not found: $materialize"
  }
  & pwsh -NoProfile -File $materialize -OutputDir plugins -PluginName bgs-modding-superpowers -McpPathStrategy relative -Force
  if ($LASTEXITCODE -ne 0) { throw 'materialize failed' }
}

Write-Host ''
Write-Host '=== DONE ===' -ForegroundColor Green
Write-Host 'Next steps:' -ForegroundColor Yellow
Write-Host '  1. Restart OpenCode session (MCP discovery is one-shot at startup)' -ForegroundColor Yellow
Write-Host '  2. After restart, verify via:' -ForegroundColor Yellow
Write-Host '       bgs_kb_status()      ← expect 0 pack_id_collision warnings' -ForegroundColor Yellow
Write-Host ('       bgs_kb_query({{ query: "...", packIds: ["{0}"] }})  ← expect hit on new record' -f $PackId) -ForegroundColor Yellow
Write-Host '  3. Commit (two-commit shape per AGENTS.md 2026-06-03):' -ForegroundColor Yellow
Write-Host ("       git add knowledge/bgs-kb/packs/{0}/" -f (Split-Path -Leaf $packRoot)) -ForegroundColor Yellow
Write-Host ("       git commit -m 'kb({0}): <what changed>'" -f $PackId) -ForegroundColor Yellow
if (-not $SkipMaterialize) {
  Write-Host '       git add plugins/bgs-modding-superpowers/' -ForegroundColor Yellow
  Write-Host ("       git commit -m 'chore(plugin-dist): rematerialize after {0} KB update'" -f $PackId) -ForegroundColor Yellow
}
Write-Host '  4. Push to main, then vendor pull:' -ForegroundColor Yellow
Write-Host "       git push origin main" -ForegroundColor Yellow
Write-Host "       git -C 'D:\Starfield MO2\.opencode\vendor\bgs-modding-superpowers' pull --ff-only origin main" -ForegroundColor Yellow

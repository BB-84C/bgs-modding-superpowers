#requires -Version 5.1
<#
.SYNOPSIS
  Materialize a portable plugins/<name>/ tree for downstream packaging.

.DESCRIPTION
  Builds a self-contained, hand-distributable copy of the plugin into
  <OutputDir>/<PluginName>/. The output contains only real files (no
  directory junctions, no machine-specific absolute paths), so it can be
  zipped, committed to a release branch, or dropped into a Codex
  marketplace cache without further surgery.

  Closes roadmap Target 1 (Portable publishability): the current
  per-machine workaround under repo-root plugins/ relies on directory
  junctions and absolute paths, and Codex's marketplace cache strips
  junctions on copy. This script produces the same shape with copies.

  Source-of-truth files (read from repo root):
    .claude-plugin/         (Claude Code manifest + marketplace.json)
    .codex-plugin/          (Codex manifest)
    .mcp.json               (MCP server registrations)
    .opencode/plugins/      (OpenCode plugin entrypoint)
    hooks/                  (session-start bootstrap)
    scripts/                (operator scripts: start-mo2, fetch-xedit, installers)
    skills/                 (every shipped SKILL.md tree)
    tools/xedit-mcp/        (dist/ + src/ + package.json + README.md)
    tools/bgs-kb-mcp/       (dist/ + src/ + package.json + README.md + bundled core KB pack)
    tools/xedit-hook-bridge/dist/   (xEditHookBridge.dll only)
    tools/mo2-vfs-launcher/         (PowerShell launcher surface)
    tools/mo2-control-plane/        (broker + live-bridge Python plugin)
    tools/bgs-archive/              (Rust BA2/BSA CLI source + docs)
    tools/bgs-papyrus/              (Python Papyrus CLI source + docs)
    package.json, README.md, LICENSE, RELEASE-NOTES.md

  .mcp.json strategies (-McpPathStrategy):
    claude-plugin-root  Keep ${CLAUDE_PLUGIN_ROOT}/tools/.../dist/index.js
                        (canonical for Claude Code; some harnesses don't
                        expand this variable).
    relative            Rewrite to ./tools/<mcp>/dist/index.js.
                        Portable; best default for Codex marketplaces and
                        anything that resolves relative to the plugin dir.
    absolute            Rewrite to the absolute resolved path of the
                        materialized dist/index.js. Use only for one-shot
                        local installs; not portable.

  The script does NOT:
    - run `npm install` or `npm run build` (run those first)
    - bundle dev dependencies into the output (runtime dependency closures are
      copied from each source MCP package's node_modules; package.json files
      still have build/test scripts and devDependencies stripped)
    - mutate the live repo-root plugins/ workaround tree

.PARAMETER OutputDir
  Where the portable tree is written. Default: "dist/portable-plugin".
  Relative paths resolve from the repo root.

.PARAMETER PluginName
  Subdirectory name inside OutputDir. Default: "bgs-modding-superpowers".

.PARAMETER McpPathStrategy
  How to write paths inside the materialized .mcp.json. See description.
  Default: "relative".

.PARAMETER EmitMarketplace
  Also write OutputDir/marketplace.json shaped for Codex's
  `.agents/plugins/marketplace.json` convention, pointing at ./PluginName.
  Default: $true.

.PARAMETER Force
  If OutputDir/PluginName exists, remove it before writing.

.EXAMPLE
  pwsh scripts/build-portable-plugin.ps1

  Produces dist/portable-plugin/bgs-modding-superpowers/ + dist/portable-plugin/marketplace.json.

.EXAMPLE
  pwsh scripts/build-portable-plugin.ps1 -McpPathStrategy claude-plugin-root -OutputDir dist/claude-shape

  Produces a Claude-Code-shaped tree that keeps the ${CLAUDE_PLUGIN_ROOT} sentinel.

.NOTES
  Inputs that MUST exist before running:
    tools/xedit-mcp/dist/index.js  (run `npm run build` inside tools/xedit-mcp/ first)
    tools/bgs-kb-mcp/dist/index.js (run `npm run build` inside tools/bgs-kb-mcp/ first)
    tools/xedit-hook-bridge/dist/xEditHookBridge.dll
#>

[CmdletBinding()]
param(
  [string]$OutputDir = "dist/portable-plugin",
  [string]$PluginName = "bgs-modding-superpowers",

  [ValidateSet("claude-plugin-root", "relative", "absolute")]
  [string]$McpPathStrategy = "relative",

  [bool]$EmitMarketplace = $true,

  [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# ---- Resolve repo root from this script's location -------------------------
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# ---- Resolve OutputDir relative to repo root if not rooted -----------------
if (-not [IO.Path]::IsPathRooted($OutputDir)) {
  $OutputDir = Join-Path $RepoRoot $OutputDir
}
$PluginRoot = Join-Path $OutputDir $PluginName

Write-Host "[build-portable-plugin] repo root:  $RepoRoot"
Write-Host "[build-portable-plugin] output dir: $OutputDir"
Write-Host "[build-portable-plugin] plugin:     $PluginName"
Write-Host "[build-portable-plugin] mcp path strategy: $McpPathStrategy"

# ---- Preflight: required prebuilt artifacts --------------------------------
$RequiredArtifacts = @(
  "tools/xedit-mcp/dist/index.js",
  "tools/bgs-kb-mcp/dist/index.js",
  "tools/xedit-hook-bridge/dist/xEditHookBridge.dll"
)
foreach ($rel in $RequiredArtifacts) {
  $full = Join-Path $RepoRoot $rel
  if (-not (Test-Path -LiteralPath $full)) {
    throw "Required artifact missing: $rel. " +
          "If this is an MCP dist, run `npm run build` inside that tools/<mcp>/ package first."
  }
}

# ---- Prepare output ---------------------------------------------------------
if (Test-Path -LiteralPath $PluginRoot) {
  if ($Force) {
    Write-Host "[build-portable-plugin] removing existing $PluginRoot"
    Remove-Item -LiteralPath $PluginRoot -Recurse -Force
  } else {
    throw "$PluginRoot already exists. Pass -Force to overwrite."
  }
}
New-Item -ItemType Directory -Path $PluginRoot -Force | Out-Null

# ---- Helpers ----------------------------------------------------------------
function Copy-Tree {
  param(
    [Parameter(Mandatory)][string]$From,
    [Parameter(Mandatory)][string]$To,
    [string[]]$ExcludeNames = @()
  )
  $srcFull = Join-Path $RepoRoot $From
  if (-not (Test-Path -LiteralPath $srcFull)) {
    throw "Source not found: $From"
  }
  # Resolve any directory junctions / symlinks at the source itself.
  $resolvedSrc = (Get-Item -LiteralPath $srcFull).Target
  if ($resolvedSrc) {
    $srcFull = $resolvedSrc
  }
  $dstFull = Join-Path $PluginRoot $To
  $dstParent = Split-Path $dstFull -Parent
  if (-not (Test-Path -LiteralPath $dstParent)) {
    New-Item -ItemType Directory -Path $dstParent -Force | Out-Null
  }
  if ($ExcludeNames.Count -gt 0) {
    Copy-Item -LiteralPath $srcFull -Destination $dstFull -Recurse -Force `
      -Exclude $ExcludeNames
  } else {
    Copy-Item -LiteralPath $srcFull -Destination $dstFull -Recurse -Force
  }
}

function Copy-FileOnly {
  param(
    [Parameter(Mandatory)][string]$From,
    [Parameter(Mandatory)][string]$To
  )
  $srcFull = Join-Path $RepoRoot $From
  if (-not (Test-Path -LiteralPath $srcFull)) {
    throw "Source file not found: $From"
  }
  $dstFull = Join-Path $PluginRoot $To
  $dstParent = Split-Path $dstFull -Parent
  if (-not (Test-Path -LiteralPath $dstParent)) {
    New-Item -ItemType Directory -Path $dstParent -Force | Out-Null
  }
  Copy-Item -LiteralPath $srcFull -Destination $dstFull -Force
}

function Strip-PortableMcpPackageJson {
  param(
    [Parameter(Mandatory)][string]$PackageJsonPath
  )

  $pkg = Get-Content -LiteralPath $PackageJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($pkg.scripts) {
    foreach ($scriptKey in @("prepare", "build", "test", "test:watch", "test:integration", "typecheck")) {
      if ($pkg.scripts.PSObject.Properties.Name -contains $scriptKey) {
        $pkg.scripts.PSObject.Properties.Remove($scriptKey)
      }
    }
  }
  if ($pkg.PSObject.Properties.Name -contains "devDependencies") {
    $pkg.PSObject.Properties.Remove("devDependencies")
  }
  $pkgOut = ($pkg | ConvertTo-Json -Depth 10).Replace("`r`n", "`n")
  [IO.File]::WriteAllText($PackageJsonPath, $pkgOut + "`n", [Text.UTF8Encoding]::new($false))
}

function Copy-McpPackage {
  param(
    [Parameter(Mandatory)][string]$PackageName
  )

  $dst = Join-Path $PluginRoot "tools/$PackageName"
  New-Item -ItemType Directory -Path $dst -Force | Out-Null
  Copy-FileOnly -From "tools/$PackageName/package.json" -To "tools/$PackageName/package.json"
  if (Test-Path -LiteralPath (Join-Path $RepoRoot "tools/$PackageName/README.md")) {
    Copy-FileOnly -From "tools/$PackageName/README.md" -To "tools/$PackageName/README.md"
  }
  if (Test-Path -LiteralPath (Join-Path $RepoRoot "tools/$PackageName/tsconfig.json")) {
    Copy-FileOnly -From "tools/$PackageName/tsconfig.json" -To "tools/$PackageName/tsconfig.json"
  }
  Copy-Tree -From "tools/$PackageName/dist" -To "tools/$PackageName/dist"
  Copy-Tree -From "tools/$PackageName/src" -To "tools/$PackageName/src"
  Strip-PortableMcpPackageJson -PackageJsonPath (Join-Path $PluginRoot "tools/$PackageName/package.json")
  Copy-McpRuntimeDependencies -PackageName $PackageName
}

function Copy-McpRuntimeDependencies {
  param(
    [Parameter(Mandatory)][string]$PackageName
  )

  $srcPkgRoot = Join-Path $RepoRoot "tools/$PackageName"
  $srcNodeModules = Join-Path $srcPkgRoot "node_modules"
  if (-not (Test-Path -LiteralPath $srcNodeModules)) {
    throw "Source runtime dependencies missing for tools/$PackageName. Run npm install inside tools/$PackageName before building the portable tree."
  }

  Push-Location $srcPkgRoot
  try {
    $depRoots = @(& npm ls --omit=dev --parseable --all --silent)
    if ($LASTEXITCODE -ne 0) {
      throw "npm ls --omit=dev failed for tools/$PackageName with exit code $LASTEXITCODE"
    }
  } finally {
    Pop-Location
  }

  foreach ($depRoot in $depRoots) {
    if ($depRoot -eq $srcPkgRoot) { continue }
    if (-not $depRoot.StartsWith($srcNodeModules, [StringComparison]::OrdinalIgnoreCase)) { continue }
    $relativeDepPath = $depRoot.Substring($srcPkgRoot.Length).TrimStart([char]'\', [char]'/')
    $dstDepPath = Join-Path (Join-Path $PluginRoot "tools/$PackageName") $relativeDepPath
    $dstParent = Split-Path $dstDepPath -Parent
    if (-not (Test-Path -LiteralPath $dstParent)) {
      New-Item -ItemType Directory -Path $dstParent -Force | Out-Null
    }
    Copy-Item -LiteralPath $depRoot -Destination $dstDepPath -Recurse -Force
  }
}

# ---- 1. Manifest + MCP + OpenCode plugin entrypoint ------------------------
Copy-Tree -From ".claude-plugin"     -To ".claude-plugin"
Copy-Tree -From ".codex-plugin"      -To ".codex-plugin"
Copy-FileOnly -From ".mcp.json"      -To ".mcp.json"
Copy-Tree -From ".opencode/plugins"  -To ".opencode/plugins"

# ---- 2. Hooks + Scripts -----------------------------------------------------
# `dev-*.ps1` scripts (e.g. dev-kb-author.ps1) are repo-internal — they require
# the source tree under `knowledge/bgs-kb/packs/` which end-users do not have.
# Exclude them from the published plugin tree so the user-facing seam stays clean.
Copy-Tree -From "hooks"   -To "hooks"
Copy-Tree -From "scripts" -To "scripts" -ExcludeNames "dev-*"

# ---- 3. Skills (entire shipped surface) ------------------------------------
Copy-Tree -From "skills" -To "skills"

# ---- 4. MCP packages (dist + src + package.json + README + tsconfig) --------
#       Exclude tests/ and .gitignore. Copy production node_modules closure so
#       the materialized MCP stdio entries can smoke-run without a network step.
#       Dev package.json files have `prepare: npm run build`; portable trees
#       already ship dist/ pre-built, so strip build/test scripts + dev deps.
Copy-McpPackage -PackageName "xedit-mcp"
Copy-McpPackage -PackageName "bgs-kb-mcp"
Copy-McpPackage -PackageName "mo2-mcp"

# ---- 5. tools/xedit-hook-bridge (dist DLL only) ----------------------------
Copy-Tree -From "tools/xedit-hook-bridge/dist" -To "tools/xedit-hook-bridge/dist"

# ---- 6. tools/mo2-vfs-launcher + tools/mo2-control-plane -------------------
Copy-Tree -From "tools/mo2-vfs-launcher"  -To "tools/mo2-vfs-launcher"
Copy-Tree -From "tools/mo2-control-plane" -To "tools/mo2-control-plane"

# ---- 6b. tools/bgs-translator (xtl reference tree) -------------------------
# bgs-translator is PyPI-distributed (`pipx install bgs-translator`); the
# canonical runtime is the installed `xtl` console script. This tree is bundled
# so that agent-facing references resolve from the materialized plugin:
#   tools/bgs-translator/USER-GUIDE.{en,zh-cn}.md   (human manuals)
#   tools/bgs-translator/scripts/restart-web-gui.ps1 (helper for stuck GUI)
#   tools/bgs-translator/README.md                  (entry-point overview)
# It also lets a user pip-install from the vendored source as a fallback when
# PyPI is unreachable. `pyproject.toml` declares console scripts `xtl` and
# `bgs-translator`.
#
# Use robocopy with /XD because Python dev caches (__pycache__, .mypy_cache,
# .pytest_cache, .ruff_cache, *.egg-info, build/, dist/) can appear at any depth
# in the source tree after pytest/mypy/ruff runs; Copy-Item -Exclude only
# matches top-level filenames. Failing to exclude them ships hundreds of MB of
# dev-only artifacts to vendor clones.
$bgsTranslatorSrc = Join-Path $RepoRoot "tools/bgs-translator"
$bgsTranslatorDst = Join-Path $PluginRoot "tools/bgs-translator"
if (-not (Test-Path -LiteralPath $bgsTranslatorSrc)) {
  throw "Source not found: tools/bgs-translator"
}
New-Item -ItemType Directory -Path $bgsTranslatorDst -Force | Out-Null
$robocopyArgs = @(
  $bgsTranslatorSrc,
  $bgsTranslatorDst,
  "/E",
  "/XD", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
  "/XD", "bgs_translator.egg-info", "build", "dist",
  "/XD", ".venv", "venv", "env",
  "/NFL", "/NDL", "/NJH", "/NJS", "/NP"
)
& robocopy @robocopyArgs | Out-Null
# robocopy exit codes 0-7 are success variants; 8+ are real errors.
if ($LASTEXITCODE -gt 7) {
  throw "robocopy failed copying tools/bgs-translator (exit $LASTEXITCODE)"
}
# Reset $LASTEXITCODE so downstream cmdlets see a clean state.
$global:LASTEXITCODE = 0

# ---- 6c. tools/bgs-archive (Rust BA2/BSA CLI reference tree) ----------------
# bgs-archive is distributed as a GitHub Release binary; the plugin tree bundles
# source, tests, scripts, Cargo.lock, and README so agent-facing references and
# fallback source builds work from a fresh vendor clone. Exclude only Rust build
# output; target/ can be large and is fully reproducible.
$bgsArchiveSrc = Join-Path $RepoRoot "tools/bgs-archive"
$bgsArchiveDst = Join-Path $PluginRoot "tools/bgs-archive"
if (-not (Test-Path -LiteralPath $bgsArchiveSrc)) {
  throw "Source not found: tools/bgs-archive"
}
New-Item -ItemType Directory -Path $bgsArchiveDst -Force | Out-Null
$robocopyArgs = @(
  $bgsArchiveSrc,
  $bgsArchiveDst,
  "/E",
  "/XD", "target",
  "/NFL", "/NDL", "/NJH", "/NJS", "/NP"
)
& robocopy @robocopyArgs | Out-Null
# robocopy exit codes 0-7 are success variants; 8+ are real errors.
if ($LASTEXITCODE -gt 7) {
  throw "robocopy failed copying tools/bgs-archive (exit $LASTEXITCODE)"
}
# Reset $LASTEXITCODE so downstream cmdlets see a clean state.
$global:LASTEXITCODE = 0

# ---- 6d. tools/bgs-papyrus (Papyrus compile/decompile CLI reference tree) ----
# bgs-papyrus is distributed as a Python CLI. The plugin tree bundles source,
# tests, README, bilingual user guides, and changelog so agent-facing references
# and fallback source installs work from a fresh vendor clone. Use robocopy with
# /XD because Python dev caches can appear at any depth after local test runs.
$bgsPapyrusSrc = Join-Path $RepoRoot "tools/bgs-papyrus"
$bgsPapyrusDst = Join-Path $PluginRoot "tools/bgs-papyrus"
if (-not (Test-Path -LiteralPath $bgsPapyrusSrc)) {
  throw "Source not found: tools/bgs-papyrus"
}
New-Item -ItemType Directory -Path $bgsPapyrusDst -Force | Out-Null
$robocopyArgs = @(
  $bgsPapyrusSrc,
  $bgsPapyrusDst,
  "/E",
  "/XD", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
  "/XD", "*.egg-info", "build", "dist",
  "/XD", ".venv", "venv", "env",
  "/NFL", "/NDL", "/NJH", "/NJS", "/NP"
)
& robocopy @robocopyArgs | Out-Null
# robocopy exit codes 0-7 are success variants; 8+ are real errors.
if ($LASTEXITCODE -gt 7) {
  throw "robocopy failed copying tools/bgs-papyrus (exit $LASTEXITCODE)"
}
# Reset $LASTEXITCODE so downstream cmdlets see a clean state.
$global:LASTEXITCODE = 0

# ---- 6e. tools/mo2-assets-engine (offline archive/loose-file engine) --------
# Bundled so Plan A's Python engine + `mo2-assets` CLI are available from the
# materialized plugin tree. Use robocopy with /XD for the same reason as
# bgs-translator: Python dev caches can appear at any depth after local test
# runs and must not ship to vendor clones.
$mo2AssetsEngineSrc = Join-Path $RepoRoot "tools/mo2-assets-engine"
$mo2AssetsEngineDst = Join-Path $PluginRoot "tools/mo2-assets-engine"
if (-not (Test-Path -LiteralPath $mo2AssetsEngineSrc)) {
  throw "Source not found: tools/mo2-assets-engine"
}
New-Item -ItemType Directory -Path $mo2AssetsEngineDst -Force | Out-Null
$robocopyArgs = @(
  $mo2AssetsEngineSrc,
  $mo2AssetsEngineDst,
  "/E",
  "/XD", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
  "/XD", "*.egg-info", "build", "dist",
  "/XD", ".venv",
  "/NFL", "/NDL", "/NJH", "/NJS", "/NP"
)
& robocopy @robocopyArgs | Out-Null
# robocopy exit codes 0-7 are success variants; 8+ are real errors.
if ($LASTEXITCODE -gt 7) {
  throw "robocopy failed copying tools/mo2-assets-engine (exit $LASTEXITCODE)"
}
# Reset $LASTEXITCODE so downstream cmdlets see a clean state.
$global:LASTEXITCODE = 0

# ---- 6f. tools/mo2-mcp-sidecar (Python JSON-RPC sidecar) --------------------
# Bundled so the mo2-mcp TypeScript server can launch the sidecar from the
# materialized plugin tree. Use robocopy with /XD for Python dev caches.
$mo2SidecarSrc = Join-Path $RepoRoot "tools/mo2-mcp-sidecar"
$mo2SidecarDst = Join-Path $PluginRoot "tools/mo2-mcp-sidecar"
if (-not (Test-Path -LiteralPath $mo2SidecarSrc)) {
  throw "Source not found: tools/mo2-mcp-sidecar"
}
New-Item -ItemType Directory -Path $mo2SidecarDst -Force | Out-Null
$robocopyArgs = @(
  $mo2SidecarSrc,
  $mo2SidecarDst,
  "/E",
  "/XD", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
  "/XD", "*.egg-info", "build", "dist",
  "/XD", ".venv",
  "/NFL", "/NDL", "/NJH", "/NJS", "/NP"
)
& robocopy @robocopyArgs | Out-Null
# robocopy exit codes 0-7 are success variants; 8+ are real errors.
if ($LASTEXITCODE -gt 7) {
  throw "robocopy failed copying tools/mo2-mcp-sidecar (exit $LASTEXITCODE)"
}
# Reset $LASTEXITCODE so downstream cmdlets see a clean state.
$global:LASTEXITCODE = 0

# ---- 7. Bundled knowledge-base core pack -----------------------------------
# Large per-game and localization packs ship as KB Release artifacts. Keep the
# portable plugin small and deterministic; first-run/maintenance can install
# bgs-kb-starfield, bgs-l10n-starfield-zhhans, and other packs from releases.
Copy-FileOnly -From "knowledge/bgs-kb/packs/core/manifest.json" -To "knowledge/bgs-kb/packs/core/manifest.json"
Copy-Tree -From "knowledge/bgs-kb/packs/core/records" -To "knowledge/bgs-kb/packs/core/records"
if (Test-Path -LiteralPath (Join-Path $RepoRoot "knowledge/bgs-kb/packs/core/kb.sqlite")) {
  Copy-FileOnly -From "knowledge/bgs-kb/packs/core/kb.sqlite" -To "knowledge/bgs-kb/packs/core/kb.sqlite"
} else {
  Write-Warning "Bundled core KB sqlite is missing: knowledge/bgs-kb/packs/core/kb.sqlite. Portable bgs-kb-mcp will start but bgs-kb-core discovery will skip until kb.sqlite is built."
}

# ---- 8. Top-level public surface -------------------------------------------
Copy-FileOnly -From "package.json"      -To "package.json"
Copy-FileOnly -From "README.md"         -To "README.md"
Copy-FileOnly -From "LICENSE"           -To "LICENSE"
if (Test-Path -LiteralPath (Join-Path $RepoRoot "RELEASE-NOTES.md")) {
  Copy-FileOnly -From "RELEASE-NOTES.md" -To "RELEASE-NOTES.md"
}

# ---- 9. Rewrite .mcp.json based on strategy --------------------------------
$mcpJsonPath = Join-Path $PluginRoot ".mcp.json"
$mcpRaw = Get-Content -LiteralPath $mcpJsonPath -Raw -Encoding UTF8
$mcp = $mcpRaw | ConvertFrom-Json

function Resolve-McpEntryPath {
  param(
    [Parameter(Mandatory)][string]$EntryRel
  )

  switch ($McpPathStrategy) {
    "claude-plugin-root" {
      return "`${CLAUDE_PLUGIN_ROOT}/$EntryRel"
    }
    "relative" {
      return "./$EntryRel"
    }
    "absolute" {
      return (Join-Path $PluginRoot $EntryRel) -replace "\\", "/"
    }
  }
}

if (-not $mcp.mcpServers -or -not $mcp.mcpServers.xedit -or -not $mcp.mcpServers.bgs_kb -or -not $mcp.mcpServers.mo2) {
  throw "Materialized .mcp.json is missing mcpServers.xedit, mcpServers.bgs_kb, or mcpServers.mo2. The source .mcp.json shape changed; update this script."
}
$xeditMcpPath = Resolve-McpEntryPath -EntryRel "tools/xedit-mcp/dist/index.js"
$bgsKbMcpPath = Resolve-McpEntryPath -EntryRel "tools/bgs-kb-mcp/dist/index.js"
$mo2McpPath = Resolve-McpEntryPath -EntryRel "tools/mo2-mcp/dist/index.js"
$mcp.mcpServers.xedit.args = @($xeditMcpPath)
$mcp.mcpServers.bgs_kb.args = @($bgsKbMcpPath)
$mcp.mcpServers.mo2.args = @($mo2McpPath)

# Pretty-print without BOM, LF line endings.
$mcpOut = ($mcp | ConvertTo-Json -Depth 10).Replace("`r`n", "`n")
[IO.File]::WriteAllText($mcpJsonPath, $mcpOut + "`n", [Text.UTF8Encoding]::new($false))

# ---- 10. Optional sibling marketplace.json (Codex shape) -------------------
if ($EmitMarketplace) {
  $marketplace = [ordered]@{
    name = "$PluginName-portable"
    interface = [ordered]@{
      displayName = "BGS Modding Superpowers (portable)"
    }
    plugins = @(
      [ordered]@{
        name = $PluginName
        source = [ordered]@{
          source = "local"
          path = "./$PluginName"
        }
        policy = [ordered]@{
          installation = "AVAILABLE"
          authentication = "ON_INSTALL"
        }
        category = "Engineering"
      }
    )
  }
  $mpJson = ($marketplace | ConvertTo-Json -Depth 10).Replace("`r`n", "`n")
  $mpPath = Join-Path $OutputDir "marketplace.json"
  [IO.File]::WriteAllText($mpPath, $mpJson + "`n", [Text.UTF8Encoding]::new($false))
  Write-Host "[build-portable-plugin] wrote marketplace: $mpPath"
}

# ---- 11. Summary ------------------------------------------------------------
$fileCount = (Get-ChildItem -LiteralPath $PluginRoot -Recurse -File).Count
$totalBytes = (Get-ChildItem -LiteralPath $PluginRoot -Recurse -File | Measure-Object -Property Length -Sum).Sum
$totalMB = [math]::Round($totalBytes / 1MB, 2)
Write-Host ""
Write-Host "[build-portable-plugin] DONE"
Write-Host "[build-portable-plugin]   plugin root: $PluginRoot"
Write-Host "[build-portable-plugin]   files:       $fileCount"
Write-Host "[build-portable-plugin]   total size:  $totalMB MB (runtime node_modules included)"
Write-Host "[build-portable-plugin]   .mcp.json xedit args:  $xeditMcpPath"
Write-Host "[build-portable-plugin]   .mcp.json bgs_kb args: $bgsKbMcpPath"
Write-Host ""
Write-Host "Next step for consumers:"
Write-Host "  Install/copy the materialized plugin tree; MCP runtime dependencies are already included."

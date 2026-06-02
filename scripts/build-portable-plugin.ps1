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
    tools/xedit-hook-bridge/dist/   (xEditHookBridge.dll only)
    tools/mo2-vfs-launcher/         (PowerShell launcher surface)
    tools/mo2-control-plane/        (broker + live-bridge Python plugin)
    package.json, README.md, LICENSE, RELEASE-NOTES.md

  .mcp.json strategies (-McpPathStrategy):
    claude-plugin-root  Keep ${CLAUDE_PLUGIN_ROOT}/tools/.../dist/index.js
                        (canonical for Claude Code; some harnesses don't
                        expand this variable).
    relative            Rewrite to ./tools/xedit-mcp/dist/index.js.
                        Portable; best default for Codex marketplaces and
                        anything that resolves relative to the plugin dir.
    absolute            Rewrite to the absolute resolved path of the
                        materialized dist/index.js. Use only for one-shot
                        local installs; not portable.

  The script does NOT:
    - run `npm install` or `npm run build` (run those first)
    - bundle node_modules into the output (consumers run `npm install
      --omit=dev` inside tools/xedit-mcp/ post-extract; only @modelcontextprotocol/sdk
      and zod are needed at runtime)
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
  "tools/xedit-hook-bridge/dist/xEditHookBridge.dll"
)
foreach ($rel in $RequiredArtifacts) {
  $full = Join-Path $RepoRoot $rel
  if (-not (Test-Path -LiteralPath $full)) {
    throw "Required artifact missing: $rel. " +
          "If this is the xedit-mcp dist, run `npm run build` inside tools/xedit-mcp/ first."
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

# ---- 1. Manifest + MCP + OpenCode plugin entrypoint ------------------------
Copy-Tree -From ".claude-plugin"     -To ".claude-plugin"
Copy-Tree -From ".codex-plugin"      -To ".codex-plugin"
Copy-FileOnly -From ".mcp.json"      -To ".mcp.json"
Copy-Tree -From ".opencode/plugins"  -To ".opencode/plugins"

# ---- 2. Hooks + Scripts -----------------------------------------------------
Copy-Tree -From "hooks"   -To "hooks"
Copy-Tree -From "scripts" -To "scripts"

# ---- 3. Skills (entire shipped surface) ------------------------------------
Copy-Tree -From "skills" -To "skills"

# ---- 4. tools/xedit-mcp (dist + src + package.json + README + tsconfig) ----
#       Exclude tests/, node_modules/, .gitignore — consumers `npm install --omit=dev`.
$xeditMcpDst = Join-Path $PluginRoot "tools/xedit-mcp"
New-Item -ItemType Directory -Path $xeditMcpDst -Force | Out-Null
Copy-FileOnly -From "tools/xedit-mcp/package.json"        -To "tools/xedit-mcp/package.json"
Copy-FileOnly -From "tools/xedit-mcp/README.md"           -To "tools/xedit-mcp/README.md"
if (Test-Path -LiteralPath (Join-Path $RepoRoot "tools/xedit-mcp/tsconfig.json")) {
  Copy-FileOnly -From "tools/xedit-mcp/tsconfig.json"     -To "tools/xedit-mcp/tsconfig.json"
}
Copy-Tree    -From "tools/xedit-mcp/dist"                 -To "tools/xedit-mcp/dist"
Copy-Tree    -From "tools/xedit-mcp/src"                  -To "tools/xedit-mcp/src"

# The dev package.json has `prepare: npm run build` so that contributors get
# a fresh dist/ after `npm install` in the source tree. The portable tree
# already ships dist/ pre-built, and a `npm install --omit=dev` consumer
# does not have typescript or @types/node installed, so the prepare hook
# would fail. Strip it (and other build-time scripts) from the materialized
# package.json. dist/ is the source of truth for the portable build.
$xeditPkgJsonPath = Join-Path $PluginRoot "tools/xedit-mcp/package.json"
$xeditPkg = Get-Content -LiteralPath $xeditPkgJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($xeditPkg.scripts) {
  foreach ($scriptKey in @("prepare", "build", "test", "test:watch", "test:integration", "typecheck")) {
    if ($xeditPkg.scripts.PSObject.Properties.Name -contains $scriptKey) {
      $xeditPkg.scripts.PSObject.Properties.Remove($scriptKey)
    }
  }
}
# devDependencies aren't needed at runtime; drop them so `npm install` doesn't
# even try to resolve them.
if ($xeditPkg.PSObject.Properties.Name -contains "devDependencies") {
  $xeditPkg.PSObject.Properties.Remove("devDependencies")
}
$xeditPkgOut = ($xeditPkg | ConvertTo-Json -Depth 10).Replace("`r`n", "`n")
[IO.File]::WriteAllText($xeditPkgJsonPath, $xeditPkgOut + "`n", [Text.UTF8Encoding]::new($false))

# ---- 5. tools/xedit-hook-bridge (dist DLL only) ----------------------------
Copy-Tree -From "tools/xedit-hook-bridge/dist" -To "tools/xedit-hook-bridge/dist"

# ---- 6. tools/mo2-vfs-launcher + tools/mo2-control-plane -------------------
Copy-Tree -From "tools/mo2-vfs-launcher"  -To "tools/mo2-vfs-launcher"
Copy-Tree -From "tools/mo2-control-plane" -To "tools/mo2-control-plane"

# ---- 7. Top-level public surface -------------------------------------------
Copy-FileOnly -From "package.json"      -To "package.json"
Copy-FileOnly -From "README.md"         -To "README.md"
Copy-FileOnly -From "LICENSE"           -To "LICENSE"
if (Test-Path -LiteralPath (Join-Path $RepoRoot "RELEASE-NOTES.md")) {
  Copy-FileOnly -From "RELEASE-NOTES.md" -To "RELEASE-NOTES.md"
}

# ---- 8. Rewrite .mcp.json based on strategy --------------------------------
$mcpJsonPath = Join-Path $PluginRoot ".mcp.json"
$mcpRaw = Get-Content -LiteralPath $mcpJsonPath -Raw -Encoding UTF8
$mcp = $mcpRaw | ConvertFrom-Json

$entryRel = "tools/xedit-mcp/dist/index.js"
switch ($McpPathStrategy) {
  "claude-plugin-root" {
    $newPath = "`${CLAUDE_PLUGIN_ROOT}/$entryRel"
  }
  "relative" {
    $newPath = "./$entryRel"
  }
  "absolute" {
    $newPath = (Join-Path $PluginRoot $entryRel) -replace "\\", "/"
  }
}

if (-not $mcp.mcpServers -or -not $mcp.mcpServers.xedit) {
  throw "Materialized .mcp.json is missing mcpServers.xedit. The source .mcp.json shape changed; update this script."
}
$mcp.mcpServers.xedit.args = @($newPath)

# Pretty-print without BOM, LF line endings.
$mcpOut = ($mcp | ConvertTo-Json -Depth 10).Replace("`r`n", "`n")
[IO.File]::WriteAllText($mcpJsonPath, $mcpOut + "`n", [Text.UTF8Encoding]::new($false))

# ---- 9. Optional sibling marketplace.json (Codex shape) --------------------
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

# ---- 10. Summary ------------------------------------------------------------
$fileCount = (Get-ChildItem -LiteralPath $PluginRoot -Recurse -File).Count
$totalBytes = (Get-ChildItem -LiteralPath $PluginRoot -Recurse -File | Measure-Object -Property Length -Sum).Sum
$totalMB = [math]::Round($totalBytes / 1MB, 2)
Write-Host ""
Write-Host "[build-portable-plugin] DONE"
Write-Host "[build-portable-plugin]   plugin root: $PluginRoot"
Write-Host "[build-portable-plugin]   files:       $fileCount"
Write-Host "[build-portable-plugin]   total size:  $totalMB MB (node_modules NOT included)"
Write-Host "[build-portable-plugin]   .mcp.json xedit args: $newPath"
Write-Host ""
Write-Host "Next step for consumers:"
Write-Host "  cd $PluginRoot/tools/xedit-mcp"
Write-Host "  npm install --omit=dev"

#requires -Version 5.1
<#
.SYNOPSIS
  Stage KB release artifacts: rebuild all 5 packs, zip each, write manifest-index.json.

.DESCRIPTION
  Resolves the KB-* loop's two documented carry-forwards from
  `docs/internal/roadmap.md` in one shot:

    CF-1 (rebuild core kb.sqlite): runs `bgs-kb-mcp build` on every pack so
         each `kb.sqlite` + `manifest.json` reflects the current `records/`
         tree. Useful after a KB-4-style parallel-authoring session where
         a Windows handle lock prevented an in-session core rebuild.

    CF-2 (publish Release artifacts): zips each built pack into
         `dist/kb-release/<packId>-<version>.zip`, computes sha256 +
         sizeBytes per artifact, and writes a `manifest-index.json` matching
         the shape `bgs_kb_check_updates` expects from the live GitHub
         Release.

  This script DOES NOT call `gh release create`. It prints the exact `gh`
  command at the end for the maintainer to run, preserving the explicit
  permission boundary on a network-side publish.

.PARAMETER OutputDir
  Where to stage zipped artifacts + manifest-index.json. Default:
  "dist/kb-release". Path may be relative; resolved from repo root.

.PARAMETER ReleaseTag
  The Git tag to associate with the staged release. Default: derived from
  the core pack's `manifest.json` version, e.g. `kb-2026.06.02`.

.PARAMETER ReleaseRepo
  `owner/repo` for the GitHub Release. Default: `BB-84C/bgs-modding-superpowers`.
  Used only to print the final `gh release create` command + the
  `releaseUrl` field in `manifest-index.json`.

.PARAMETER Force
  If `OutputDir` already exists, remove it before staging.

.PARAMETER SkipBuild
  Skip the per-pack rebuild step. Useful if you already ran the build
  manually and just want to stage zips + index.

.EXAMPLE
  pwsh scripts/build-kb-release.ps1

  Stages dist/kb-release/{core,skyrim,fallout4,fallout3-fnv,starfield}-2026.06.02.zip
  plus dist/kb-release/manifest-index.json. Prints the `gh release create`
  command at the end.

.EXAMPLE
  pwsh scripts/build-kb-release.ps1 -SkipBuild -OutputDir dist/kb-release-test

  Stages a test build without rebuilding kb.sqlite for each pack.

.NOTES
  Requirements:
    - Node 22+ (the bgs-kb-mcp CLI ships built; no install needed)
    - PowerShell 5.1+ on Windows; Compress-Archive available
    - For the final publish step: `gh` (GitHub CLI), authenticated.
#>

[CmdletBinding()]
param(
  [string]$OutputDir = "dist/kb-release",

  [string]$ReleaseTag,

  [string]$ReleaseRepo = "BB-84C/bgs-modding-superpowers",

  [switch]$Force,

  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Resolve repo root from this script's location ------------------------------
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PacksRoot = Join-Path $RepoRoot "knowledge/bgs-kb/packs"
$CliPath = Join-Path $RepoRoot "tools/bgs-kb-mcp/dist/cli.js"

if (-not [IO.Path]::IsPathRooted($OutputDir)) {
  $OutputDir = Join-Path $RepoRoot $OutputDir
}

# Verify prereqs --------------------------------------------------------------
foreach ($p in @($PacksRoot, $CliPath)) {
  if (-not (Test-Path -LiteralPath $p)) {
    throw "Required path missing: $p"
  }
}

# Reserved pack IDs (per spec §6.1) -----------------------------------------
$PACK_IDS = @(
  "core",
  "bgs-kb-skyrim",
  "bgs-kb-fallout4",
  "bgs-kb-fallout3-fnv",
  "bgs-kb-starfield"
)

# Verify every pack directory exists
foreach ($pid in $PACK_IDS) {
  $packDir = Join-Path $PacksRoot $pid
  if (-not (Test-Path -LiteralPath $packDir)) {
    throw "Pack directory missing: $packDir"
  }
}

# Stage 1: rebuild each pack -------------------------------------------------
if (-not $SkipBuild) {
  Write-Host "[build-kb-release] === STAGE 1: rebuild each pack ==="
  foreach ($pid in $PACK_IDS) {
    $packDir = Join-Path $PacksRoot $pid
    Write-Host "[build-kb-release] building $pid ..."
    & node $CliPath build $packDir
    if ($LASTEXITCODE -ne 0) {
      throw "Pack build failed for $pid (exit $LASTEXITCODE). If EBUSY on kb.sqlite, run this script in a fresh shell."
    }
  }
} else {
  Write-Host "[build-kb-release] === STAGE 1 SKIPPED (-SkipBuild) ==="
}

# Stage 2: prepare output dir ------------------------------------------------
Write-Host "[build-kb-release] === STAGE 2: prepare $OutputDir ==="
if (Test-Path -LiteralPath $OutputDir) {
  if ($Force) {
    Write-Host "[build-kb-release] removing existing $OutputDir"
    Remove-Item -LiteralPath $OutputDir -Recurse -Force
  } else {
    throw "$OutputDir already exists. Pass -Force to overwrite, or pick a different -OutputDir."
  }
}
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

# Stage 3: zip each pack, compute sha256 + size -----------------------------
Write-Host "[build-kb-release] === STAGE 3: zip each pack ==="

# Resolve the release tag from the core pack's manifest if not provided
$coreManifestPath = Join-Path $PacksRoot "core/manifest.json"
$coreManifest = Get-Content -LiteralPath $coreManifestPath -Raw | ConvertFrom-Json
if (-not $ReleaseTag) {
  $ReleaseTag = "kb-$($coreManifest.version)"
}
Write-Host "[build-kb-release] release tag: $ReleaseTag"

$indexEntries = New-Object System.Collections.Generic.List[object]

foreach ($pid in $PACK_IDS) {
  $packDir = Join-Path $PacksRoot $pid
  $manifestPath = Join-Path $packDir "manifest.json"
  $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json

  $assetName = "$pid-$($manifest.version).zip"
  $assetPath = Join-Path $OutputDir $assetName

  Write-Host "[build-kb-release] zipping $pid -> $assetName"

  # Compress-Archive zips the contents into a path-rooted at $packDir.
  # We want the zip's root to contain `<packDir-basename>/...` so consumers
  # can extract directly and end up with a single top-level pack directory.
  $tmpStage = Join-Path $env:TEMP "kb-release-stage-$([guid]::NewGuid().ToString('n'))"
  New-Item -ItemType Directory -Path $tmpStage -Force | Out-Null
  $tmpPackParent = Join-Path $tmpStage $pid
  Copy-Item -LiteralPath $packDir -Destination $tmpPackParent -Recurse -Force
  Compress-Archive -Path "$tmpPackParent" -DestinationPath $assetPath -Force
  Remove-Item -LiteralPath $tmpStage -Recurse -Force

  $sha = (Get-FileHash -LiteralPath $assetPath -Algorithm SHA256).Hash.ToLower()
  $size = (Get-Item -LiteralPath $assetPath).Length

  $releaseUrl = "https://github.com/$ReleaseRepo/releases/download/$ReleaseTag/$assetName"

  $indexEntries.Add([ordered]@{
    packId           = $manifest.packId
    version          = $manifest.version
    schemaVersion    = $manifest.schemaVersion
    minPluginVersion = $manifest.minPluginVersion
    releaseUrl       = $releaseUrl
    sha256           = $sha
    sizeBytes        = $size
  }) | Out-Null
}

# Stage 4: write manifest-index.json ----------------------------------------
Write-Host "[build-kb-release] === STAGE 4: write manifest-index.json ==="

$index = [ordered]@{
  releaseTag  = $ReleaseTag
  publishedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  packs       = $indexEntries.ToArray()
}

$indexJson = ($index | ConvertTo-Json -Depth 10).Replace("`r`n", "`n")
$indexPath = Join-Path $OutputDir "manifest-index.json"
[IO.File]::WriteAllText($indexPath, $indexJson + "`n", [Text.UTF8Encoding]::new($false))

# Stage 5: summary + suggested gh command -----------------------------------
Write-Host ""
Write-Host "[build-kb-release] DONE"
Write-Host "[build-kb-release]   output dir : $OutputDir"
Write-Host "[build-kb-release]   release tag: $ReleaseTag"
Write-Host "[build-kb-release]   assets     :"
foreach ($entry in $indexEntries) {
  $entryHash = $entry["sha256"]
  $entrySha = if ($entryHash) { $entryHash.Substring(0, 12) } else { "n/a" }
  $sizeKb = [math]::Round($entry["sizeBytes"] / 1KB, 1)
  Write-Host ("[build-kb-release]     {0,-22} v{1}  {2} KB  sha256 {3}" -f $entry["packId"], $entry["version"], $sizeKb, $entrySha)
}
Write-Host "[build-kb-release]   index      : $indexPath"

# Build the gh command --------------------------------------------------------
$assetArgs = @($indexPath)
foreach ($pid in $PACK_IDS) {
  $entry = $indexEntries | Where-Object { $_["packId"] -in @($pid, "bgs-kb-$pid") } | Select-Object -First 1
  if ($entry) {
    $assetName = "$($entry["packId"])-$($entry["version"]).zip"
    if ($entry["packId"] -eq "bgs-kb-core") {
      $assetName = "core-$($entry["version"]).zip"
    }
    $assetArgs += (Join-Path $OutputDir $assetName)
  }
}

Write-Host ""
Write-Host "Next step — publish the Release (requires authenticated 'gh'):"
Write-Host ""
$ghLine = "  gh release create $ReleaseTag ``"
$ghLine += "`n    --repo $ReleaseRepo ``"
$ghLine += "`n    --title 'BGS KB packs $ReleaseTag' ``"
$ghLine += "`n    --notes 'See docs/internal/roadmap.md for the KB-* loop closeout (2026-06-02).' ``"
foreach ($a in $assetArgs) {
  $ghLine += "`n    `"$a`""
}
Write-Host $ghLine
Write-Host ""
Write-Host "After the Release is live, sanity-check with:"
Write-Host "  bgs_kb_check_updates({})   # via the MCP, should surface upgradeAvailable=false because we're already at $($coreManifest.version)"
Write-Host "  curl -sSL https://github.com/$ReleaseRepo/releases/download/$ReleaseTag/manifest-index.json"

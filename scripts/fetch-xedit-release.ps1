<#
.SYNOPSIS
Downloads an xEdit release from BB-84C/TES5Edit and extracts it into the user's
MO2 tools directory.

.DESCRIPTION
The agent-friendly xEdit fork at https://github.com/BB-84C/TES5Edit ships
release zips containing the xEdit.exe + associated runtime files. This script
fetches the latest release (or a specific tag) via the GitHub REST API,
downloads the .zip asset, and extracts it into <MO2Root>/tools/xEdit/.

The bgs-modding-superpowers xEdit MCP expects xEdit.exe at
<MO2Root>/tools/xEdit/xEdit.exe by default. After this script runs, register
the binary as an MO2 tool if not already (Tools menu -> Executables -> Add).

.PARAMETER MO2Root
Absolute path to the user's MO2 install root.

.PARAMETER ReleaseTag
Optional release tag (e.g. "v0.10.0"). Defaults to the latest release.

.EXAMPLE
.\scripts\fetch-xedit-release.ps1 -MO2Root "D:\ModOrganizer2"

.EXAMPLE
.\scripts\fetch-xedit-release.ps1 -MO2Root "D:\ModOrganizer2" -ReleaseTag v0.10.0
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$MO2Root,
    [string]$ReleaseTag = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # Speeds up Invoke-WebRequest

# --- Validate ---------------------------------------------------------------

$resolvedRoot = (Resolve-Path -Path $MO2Root -ErrorAction Stop).Path
$mo2Exe = Join-Path $resolvedRoot "ModOrganizer.exe"
if (-not (Test-Path $mo2Exe -PathType Leaf)) {
    throw "MO2 root does not contain ModOrganizer.exe: $resolvedRoot"
}

$xeditTarget = Join-Path $resolvedRoot "tools\xEdit"
New-Item -ItemType Directory -Force -Path $xeditTarget | Out-Null

# --- Query GitHub for the release -----------------------------------------

$repo = "BB-84C/TES5Edit"
if ([string]::IsNullOrEmpty($ReleaseTag)) {
    $apiUrl = "https://api.github.com/repos/$repo/releases/latest"
    $description = "latest release"
} else {
    $apiUrl = "https://api.github.com/repos/$repo/releases/tags/$ReleaseTag"
    $description = "release $ReleaseTag"
}

Write-Host ""
Write-Host "Querying GitHub for $description of $repo ..."
$release = $null
try {
    $release = Invoke-RestMethod -Uri $apiUrl -Headers @{ "User-Agent" = "bgs-modding-superpowers-installer" }
} catch {
    throw "Failed to query GitHub release API at $apiUrl. $($_.Exception.Message)"
}

$tag = $release.tag_name
$published = $release.published_at
Write-Host "Found release: $tag (published $published)"

# --- Pick the zip asset ---------------------------------------------------

$asset = $release.assets | Where-Object { $_.name -like "*.zip" } | Select-Object -First 1
if (-not $asset) {
    throw "No .zip asset found in release $tag. Available assets: $(($release.assets | ForEach-Object { $_.name }) -join ', '). Manual download required from $($release.html_url)."
}

$downloadUrl = $asset.browser_download_url
$tempZip = Join-Path $env:TEMP "xedit-release-$tag.zip"
$sizeMb = [Math]::Round($asset.size / 1MB, 1)

Write-Host "Downloading $($asset.name) (~$sizeMb MB) -> $tempZip ..."
Invoke-WebRequest -Uri $downloadUrl -OutFile $tempZip -UseBasicParsing

# --- Extract ---------------------------------------------------------------

Write-Host "Extracting into $xeditTarget ..."
try {
    Expand-Archive -Path $tempZip -DestinationPath $xeditTarget -Force
} finally {
    if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
}

# --- Verify xEdit.exe -----------------------------------------------------

$xeditExe = Join-Path $xeditTarget "xEdit.exe"
if (-not (Test-Path $xeditExe -PathType Leaf)) {
    # Some release zips wrap their contents in a subfolder. Find it.
    $found = Get-ChildItem -Path $xeditTarget -Filter "xEdit.exe" -Recurse | Select-Object -First 1
    if ($found) {
        Write-Warning "xEdit.exe found at $($found.FullName), not at expected top-level $xeditExe."
        Write-Warning "  If your MO2 tool registration expects the top-level location, move the extracted contents up one level."
        $xeditExe = $found.FullName
    } else {
        throw "xEdit.exe not found anywhere under $xeditTarget after extraction. Manual intervention required."
    }
}

# --- Summary --------------------------------------------------------------

Write-Host ""
Write-Host "==========================================================="
Write-Host "xEdit deployed"
Write-Host "==========================================================="
Write-Host "  Release tag:  $tag"
Write-Host "  MO2 root:     $resolvedRoot"
Write-Host "  xEdit.exe:    $xeditExe"
Write-Host ""
Write-Host "Next:"
Write-Host "  1. Register xEdit.exe as an MO2 tool if not already" -ForegroundColor Cyan
Write-Host "     (Tools menu -> Executables -> Add, point at the path above)."
Write-Host "  2. Deploy the xEdit hook bridge (ships with this plugin):" -ForegroundColor Cyan
Write-Host "     .\scripts\install-xedit-hook-bridge.ps1 -MO2Root `"$resolvedRoot`""
Write-Host ""
Write-Host "[OK] xEdit $tag ready." -ForegroundColor Green

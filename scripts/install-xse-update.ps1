<#
.SYNOPSIS
Downloads and installs the latest xSE runtime into a game root.

.DESCRIPTION
Productionizes the script-extender update workflow for SFSE, SKSE64, F4SE,
xNVSE/NVSE, and FOSE. This script writes to the real game root after prompting,
because xSE loaders must live beside the game executable.

.PARAMETER GameRoot
Game installation root containing the game executable.

.PARAMETER XseMod
Script extender family: sfse, skse, f4se, nvse, or fose.

.PARAMETER MO2Root
Optional MO2 root. Used for downloads and default backup location.

.PARAMETER BackupDir
Optional explicit backup directory.

.PARAMETER DownloadDir
Optional explicit download directory. Defaults to <MO2Root>/downloads or <GameRoot>/.xse-staging.

.PARAMETER Force
Skip the interactive confirmation prompt before writing to GameRoot.

.PARAMETER DryRun
Query Nexus and print intended actions without writing, downloading, extracting, or backing up.

.EXAMPLE
pwsh scripts/install-xse-update.ps1 -GameRoot "D:\SteamLibrary\steamapps\common\Starfield" -XseMod sfse -MO2Root "D:\Starfield MO2" -DryRun

.EXAMPLE
pwsh scripts/install-xse-update.ps1 -GameRoot "C:\Games\Skyrim Special Edition" -XseMod skse -MO2Root "D:\MO2-Skyrim" -Force

.EXAMPLE
pwsh scripts/install-xse-update.ps1 -GameRoot "C:\Games\Fallout 4" -XseMod f4se -MO2Root "D:\MO2-FO4"

.EXAMPLE
pwsh scripts/install-xse-update.ps1 -GameRoot "C:\Games\Fallout New Vegas" -XseMod nvse -Force

.EXAMPLE
pwsh scripts/install-xse-update.ps1 -GameRoot "C:\Games\Fallout 3" -XseMod fose -Force
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot,

    [Parameter(Mandatory = $true)]
    [ValidateSet("sfse", "skse", "f4se", "nvse", "fose")]
    [string]$XseMod,

    [string]$MO2Root,
    [string]$BackupDir,
    [string]$DownloadDir,
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ProgressPreference = "SilentlyContinue"

# Nexus IDs verified in project workflow for SFSE/SKSE/F4SE. NVSE/FOSE IDs are
# the common Nexus-hosted xNVSE/FOSE entries; if Nexus changes ownership, resolve
# with /v1/games/{game}/mods/search.json?name=<sfse|skse|f4se|nvse|fose>.
$XseModIds = @{ sfse = 106; skse = 100216; f4se = 42147; nvse = 67883; fose = 8606 }
$GameDomains = @{ sfse = "starfield"; skse = "skyrimspecialedition"; f4se = "fallout4"; nvse = "newvegas"; fose = "fallout3" }
$FilePrefixes = @{ sfse = "sfse"; skse = "skse64"; f4se = "f4se"; nvse = "nvse"; fose = "fose" }
$GameExecutables = @{ sfse = "Starfield.exe"; skse = "SkyrimSE.exe"; f4se = "Fallout4.exe"; nvse = "FalloutNV.exe"; fose = "Fallout3.exe" }

function Add-CredManType {
    if ("BgsModdingSuperpowers.CredMan" -as [type]) { return }
    $signature = @'
using System;
using System.Runtime.InteropServices;
using System.Text;
namespace BgsModdingSuperpowers {
  public class CredMan {
    [DllImport("advapi32.dll", SetLastError=true, EntryPoint="CredReadW", CharSet=CharSet.Unicode)]
    static extern bool CredRead(string target, uint type, uint flag, out IntPtr cred);
    [DllImport("advapi32.dll")] static extern void CredFree(IntPtr p);
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
    public struct CREDENTIAL { public uint Flags,Type; public IntPtr TargetName,Comment; public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten; public uint CredentialBlobSize; public IntPtr CredentialBlob; public uint Persist,AttributeCount; public IntPtr Attributes,TargetAlias,UserName; }
    public static string Read(string t) { IntPtr p; if (!CredRead(t,1,0,out p)) return null; try { var c=(CREDENTIAL)Marshal.PtrToStructure(p,typeof(CREDENTIAL)); byte[] b=new byte[c.CredentialBlobSize]; Marshal.Copy(c.CredentialBlob,b,0,(int)c.CredentialBlobSize); int nz=0; for(int i=1;i<b.Length;i+=2)if(b[i]==0)nz++; return nz>(b.Length/4)?Encoding.Unicode.GetString(b):Encoding.UTF8.GetString(b); } finally { CredFree(p); } }
  }
}
'@
    Add-Type -TypeDefinition $signature -Language CSharp
}

function Get-NexusApiKey {
    Add-CredManType
    $apiKey = [BgsModdingSuperpowers.CredMan]::Read("ModOrganizer2_APIKEY")
    if ([string]::IsNullOrWhiteSpace($apiKey)) {
        throw "Nexus API key not found in Windows Credential Manager target 'ModOrganizer2_APIKEY'. Connect MO2 to Nexus first."
    }
    return $apiKey.Trim()
}

function Normalize-VersionString {
    param([string]$Version)
    if ([string]::IsNullOrWhiteSpace($Version)) { return "" }
    $parts = ($Version -replace '[^0-9\._-].*$', '') -replace '_', '.' -split '\.' | Where-Object { $_ -ne '' }
    while ($parts.Count -gt 1 -and $parts[-1] -eq '0') { $parts = $parts[0..($parts.Count - 2)] }
    return ($parts -join '.')
}

function Compare-VersionLoose {
    param([string]$Left, [string]$Right)
    $l = Normalize-VersionString $Left
    $r = Normalize-VersionString $Right
    try { return ([version]$l).CompareTo([version]$r) } catch { return [string]::Compare($l, $r, $true) }
}

function Get-Sha256 {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Copy-IfChanged {
    param([string]$Source, [string]$Destination)
    if ((Test-Path -LiteralPath $Destination -PathType Leaf) -and ((Get-Sha256 $Source) -eq (Get-Sha256 $Destination))) {
        Write-Host "[OK] Unchanged, skipping: $Destination"
        return $false
    }
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
    Write-Host "[OK] Copied: $Source -> $Destination"
    return $true
}

function Find-FirstFile {
    param([string]$Root, [string[]]$Patterns)
    foreach ($pattern in $Patterns) {
        $hit = Get-ChildItem -LiteralPath $Root -Recurse -File -Filter $pattern | Select-Object -First 1
        if ($hit) { return $hit }
    }
    return $null
}

function Invoke-NexusRequest {
    param([string]$Uri, [string]$Method, [hashtable]$Headers)
    $response = Invoke-WebRequest -Uri $Uri -Method $Method -Headers $Headers -SkipHttpErrorCheck
    if ([int]$response.StatusCode -ge 400) {
        throw "Nexus API $Method $Uri returned HTTP $($response.StatusCode): $($response.Content)"
    }
    if ([string]::IsNullOrWhiteSpace($response.Content)) { return $null }
    return $response.Content | ConvertFrom-Json
}

$resolvedGameRoot = (Resolve-Path -LiteralPath $GameRoot -ErrorAction Stop).Path
$prefix = $FilePrefixes[$XseMod]
$gameDomain = $GameDomains[$XseMod]
$modId = $XseModIds[$XseMod]
$gameExeName = $GameExecutables[$XseMod]
$gameExe = Join-Path $resolvedGameRoot $gameExeName
if (-not (Test-Path -LiteralPath $gameExe -PathType Leaf)) {
    throw "Game executable not found for $XseMod at $gameExe"
}

$currentDll = Get-ChildItem -LiteralPath $resolvedGameRoot -File -Filter "$prefix`_*.dll" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$currentRuntime = if ($currentDll) { Normalize-VersionString (($currentDll.BaseName -replace "^$([regex]::Escape($prefix))_", '') -replace '_', '.') } else { "" }
$currentXseVersion = if ($currentDll) { Normalize-VersionString $currentDll.VersionInfo.FileVersion } else { "" }
$steamRuntime = Normalize-VersionString (Get-Item -LiteralPath $gameExe).VersionInfo.FileVersion

Write-Host "xSE update probe"
Write-Host "  Game root:       $resolvedGameRoot"
Write-Host "  xSE:             $XseMod ($prefix)"
Write-Host "  Current DLL:     $($currentDll.FullName)"
Write-Host "  DLL runtime:     $currentRuntime"
Write-Host "  Steam runtime:   $steamRuntime"
Write-Host "  Current xSE ver: $currentXseVersion"

$apiKey = Get-NexusApiKey
$headers = @{ APIKEY = $apiKey; "User-Agent" = "bgs-modding-superpowers-install-xse-update" }
$filesUri = "https://api.nexusmods.com/v1/games/$gameDomain/mods/$modId/files.json"
$filesResponse = Invoke-NexusRequest -Uri $filesUri -Method Get -Headers $headers
$mainFile = $filesResponse.files | Where-Object { $_.category_name -eq "MAIN" -or $_.category_id -eq 1 } | Sort-Object uploaded_timestamp -Descending | Select-Object -First 1
if (-not $mainFile) { throw "No MAIN file found for Nexus $gameDomain mod $modId." }

$newFileId = [int]$mainFile.file_id
$newXseVersion = [string]$mainFile.version
Write-Host "  Nexus MAIN file: file_id=$newFileId version=$newXseVersion name=$($mainFile.name)"

if ($currentRuntime -eq $steamRuntime -and $currentXseVersion -and ((Compare-VersionLoose $currentXseVersion $newXseVersion) -ge 0)) {
    Write-Host "Already up to date: runtime and xSE version are current."
    exit 0
}

$stagingBase = if ($MO2Root) { (Resolve-Path -LiteralPath $MO2Root -ErrorAction Stop).Path } else { Join-Path $resolvedGameRoot ".xse-staging" }
$resolvedDownloadDir = if ($DownloadDir) { $DownloadDir } elseif ($MO2Root) { Join-Path $stagingBase "downloads" } else { Join-Path $stagingBase "downloads" }
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$defaultBackupRoot = if ($MO2Root) { Join-Path $stagingBase ".backups" } else { Join-Path $stagingBase ".backups" }
$backupPath = if ($BackupDir) { $BackupDir } else { Join-Path $defaultBackupRoot "$XseMod-$currentRuntime`_pre-$newXseVersion-update_$timestamp" }
$archivePath = Join-Path $resolvedDownloadDir "$XseMod-$newXseVersion-file$newFileId.7z"
$extractRoot = Join-Path $resolvedDownloadDir "$XseMod-$newXseVersion-file$newFileId-extracted"

Write-Host "[!] WILL WRITE TO GAME ROOT: $resolvedGameRoot"
Write-Host "  Download dir: $resolvedDownloadDir"
Write-Host "  Backup dir:   $backupPath"

if ($DryRun) {
    Write-Host "[DRY-RUN] Would request download link for file_id=$newFileId, download/extract archive, backup current files, copy new xSE files, delete old runtime DLL if replaced, and verify SHA256."
    exit 0
}

if (-not $Force) {
    $answer = Read-Host "Type Y to continue writing to game root"
    if ($answer -ne "Y") { throw "User declined game-root write." }
}

$sevenZip = "C:\Program Files\7-Zip\7z.exe"
if (-not (Test-Path -LiteralPath $sevenZip -PathType Leaf)) {
    throw "7-Zip not found at '$sevenZip'. Install 7-Zip or update the script path before running."
}

New-Item -ItemType Directory -Force -Path $resolvedDownloadDir | Out-Null
New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null

$downloadUri = "https://api.nexusmods.com/v1/games/$gameDomain/mods/$modId/files/$newFileId/download_link.json"
$links = Invoke-NexusRequest -Uri $downloadUri -Method Post -Headers $headers
$firstLink = $links | Select-Object -First 1
$mirrorUrl = if ($firstLink.URI) { $firstLink.URI } elseif ($firstLink.uri) { $firstLink.uri } else { [string]$firstLink }
if ([string]::IsNullOrWhiteSpace($mirrorUrl)) { throw "Nexus returned no usable download mirror for file_id=$newFileId." }

Write-Host "Downloading: $archivePath"
Invoke-WebRequest -Uri $mirrorUrl -OutFile $archivePath -Headers @{ "User-Agent" = "bgs-modding-superpowers-install-xse-update" }

Write-Host "Extracting archive with 7-Zip..."
& $sevenZip x "-o$extractRoot" -y $archivePath | Out-Host
if ($LASTEXITCODE -ne 0) { throw "7-Zip extraction failed with exit code $LASTEXITCODE." }

$newDll = Get-ChildItem -LiteralPath $extractRoot -Recurse -File -Filter "$prefix`_*.dll" | Select-Object -First 1
if (-not $newDll) { throw "Extracted archive did not contain $prefix`_*.dll under $extractRoot." }
$newLoader = Find-FirstFile -Root $extractRoot -Patterns @("$prefix`_loader.exe", "${prefix}loader.exe")
$newReadme = Find-FirstFile -Root $extractRoot -Patterns @("*readme*.txt", "*README*.txt")
$newWhatsNew = Find-FirstFile -Root $extractRoot -Patterns @("*whatsnew*.txt", "*what*new*.txt", "*changes*.txt")
$installFiles = @($newDll, $newLoader, $newReadme, $newWhatsNew) | Where-Object { $_ }
if ($installFiles.Count -lt 2) { throw "Archive did not expose enough xSE payload files; found $($installFiles.Count)." }

$backupMade = $false
try {
    New-Item -ItemType Directory -Force -Path $backupPath | Out-Null
    $currentFiles = @()
    if ($currentDll) { $currentFiles += $currentDll }
    foreach ($name in @("$prefix`_loader.exe", "${prefix}loader.exe", "readme.txt", "$prefix`_readme.txt", "whatsnew.txt", "$prefix`_whatsnew.txt")) {
        $p = Join-Path $resolvedGameRoot $name
        if (Test-Path -LiteralPath $p -PathType Leaf) { $currentFiles += Get-Item -LiteralPath $p }
    }
    $currentFiles = $currentFiles | Sort-Object FullName -Unique
    foreach ($file in $currentFiles) {
        Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $backupPath $file.Name) -Force
    }
    $backupMade = $true
    Write-Host "[OK] Backed up $($currentFiles.Count) existing files to $backupPath"

    $installed = @()
    foreach ($file in $installFiles) {
        $dest = Join-Path $resolvedGameRoot $file.Name
        Copy-IfChanged -Source $file.FullName -Destination $dest | Out-Null
        $installed += [pscustomobject]@{ Source = $file.FullName; Destination = $dest }
    }

    if ($currentDll -and $currentDll.Name -ne $newDll.Name -and (Test-Path -LiteralPath $currentDll.FullName -PathType Leaf)) {
        Remove-Item -LiteralPath $currentDll.FullName -Force
        Write-Host "[OK] Removed old runtime DLL: $($currentDll.FullName)"
    }

    foreach ($item in $installed) {
        $srcHash = Get-Sha256 $item.Source
        $dstHash = Get-Sha256 $item.Destination
        if ($srcHash -ne $dstHash) { throw "SHA256 verification failed for $($item.Destination)." }
    }

    Write-Host ""
    Write-Host "xSE update complete"
    Write-Host "==================="
    Write-Host "  Game root:  $resolvedGameRoot"
    Write-Host "  Backup:     $backupPath"
    Write-Host "  Archive:    $archivePath"
    Write-Host "  Extracted:  $extractRoot"
    Write-Host "  New DLL:    $($newDll.Name)"
} catch {
    Write-Error "xSE update failed: $($_.Exception.Message)"
    if ($backupMade) {
        Write-Warning "Attempting automatic restore from backup: $backupPath"
        try {
            Get-ChildItem -LiteralPath $backupPath -File | ForEach-Object {
                Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $resolvedGameRoot $_.Name) -Force
            }
            Write-Warning "Restore attempt completed. Backup remains at: $backupPath"
        } catch {
            Write-Warning "Automatic restore failed. Manually restore files from: $backupPath"
        }
    } else {
        Write-Warning "No backup was made before failure. Game root should still be unchanged."
    }
    exit 1
}

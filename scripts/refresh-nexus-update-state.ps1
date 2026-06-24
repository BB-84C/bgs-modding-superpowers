<#
.SYNOPSIS
Refreshes MO2 meta.ini Nexus update fields from the Nexus Mods API.

.DESCRIPTION
Iterates <MO2Root>/mods/*/meta.ini, finds entries with repository=Nexus and a
positive modid, queries the Nexus Mods API, and writes newestVersion,
nexusFileStatus, lastNexusQuery, and lastNexusUpdate back to meta.ini.

.PARAMETER MO2Root
MO2 instance root containing a mods directory.

.PARAMETER Game
Nexus game domain: starfield, fallout4, or skyrimspecialedition.

.PARAMETER DryRun
Show intended writes without modifying meta.ini files.

.PARAMETER ModFilter
Optional wildcard filter applied to MO2 mod folder names, e.g. "Star*".

.EXAMPLE
pwsh scripts/refresh-nexus-update-state.ps1 -MO2Root "D:\Starfield MO2" -Game starfield -DryRun

.EXAMPLE
pwsh scripts/refresh-nexus-update-state.ps1 -MO2Root "D:\MO2-FO4" -Game fallout4 -ModFilter "Sim Settlements*"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$MO2Root,

    [Parameter(Mandatory = $true)]
    [ValidateSet("starfield", "fallout4", "skyrimspecialedition")]
    [string]$Game,

    [switch]$DryRun,

    [string]$ModFilter
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ProgressPreference = "SilentlyContinue"

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

function Read-MetaIniValue {
    param([string[]]$Lines, [string]$Key)
    foreach ($line in $Lines) {
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=\s*(.*)\s*$") {
            return $Matches[1].Trim()
        }
    }
    return $null
}

function Set-MetaIniValue {
    param([string[]]$Lines, [string]$Key, [string]$Value)
    $pattern = "^\s*$([regex]::Escape($Key))\s*="
    $out = New-Object System.Collections.Generic.List[string]
    $replaced = $false
    $inserted = $false

    for ($i = 0; $i -lt $Lines.Count; $i++) {
        $line = $Lines[$i]
        if ($line -match $pattern) {
            $out.Add("$Key=$Value")
            $replaced = $true
            continue
        }
        if (-not $replaced -and -not $inserted -and $line -match '^\s*\[[^\]]+\]\s*$' -and $line -notmatch '^\s*\[General\]\s*$' -and $out.Count -gt 0) {
            $out.Add("$Key=$Value")
            $inserted = $true
        }
        $out.Add($line)
    }

    if (-not $replaced -and -not $inserted) {
        if ($Lines -notcontains "[General]") { $out.Insert(0, "[General]") }
        $generalIndex = [Math]::Max(0, $out.IndexOf("[General]"))
        $out.Insert($generalIndex + 1, "$Key=$Value")
    }
    return $out.ToArray()
}

function Invoke-NexusGet {
    param([string]$Uri, [hashtable]$Headers)

    $attempt = 0
    while ($true) {
        $attempt++
        $response = Invoke-WebRequest -Uri $Uri -Headers $Headers -Method Get -SkipHttpErrorCheck
        if ([int]$response.StatusCode -eq 429 -and $attempt -eq 1) {
            Write-Warning "Nexus returned 429 rate limit. Sleeping 60 seconds, then retrying once."
            Start-Sleep -Seconds 60
            continue
        }
        return $response
    }
}

function Convert-NexusStatusToMetaCode {
    param([string]$Status)
    switch ($Status) {
        "published" { return 1 }
        "hidden" { return 9 }
        "removed" { return 6 }
        "wastebinned" { return 6 }
        "under_moderation" { return 9 }
        default { return 1 }
    }
}

$resolvedRoot = (Resolve-Path -LiteralPath $MO2Root -ErrorAction Stop).Path
$modsDir = Join-Path $resolvedRoot "mods"
if (-not (Test-Path -LiteralPath $modsDir -PathType Container)) {
    throw "MO2 root does not contain a mods directory: $modsDir"
}

$apiKey = Get-NexusApiKey
$headers = @{ APIKEY = $apiKey; "User-Agent" = "bgs-modding-superpowers-refresh-nexus-update-state" }
$metaFiles = Get-ChildItem -LiteralPath $modsDir -Directory | Where-Object {
    [string]::IsNullOrEmpty($ModFilter) -or $_.Name -like $ModFilter
} | ForEach-Object { Join-Path $_.FullName "meta.ini" } | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }

$candidates = @()
foreach ($metaPath in $metaFiles) {
    $lines = [System.IO.File]::ReadAllLines($metaPath, [Text.Encoding]::UTF8)
    $repository = Read-MetaIniValue -Lines $lines -Key "repository"
    $modIdRaw = Read-MetaIniValue -Lines $lines -Key "modid"
    $modId = 0
    if ($repository -eq "Nexus" -and [int]::TryParse($modIdRaw, [ref]$modId) -and $modId -gt 0) {
        $candidates += [pscustomobject]@{ Name = (Split-Path -Leaf (Split-Path -Parent $metaPath)); Path = $metaPath; Lines = $lines; ModId = $modId }
    }
}

if ($candidates.Count -eq 0) {
    throw "No Nexus mods found under $modsDir with repository=Nexus and positive modid."
}

$processed = 0
$updatesDiscovered = 0
$removedHidden = 0
$errors = New-Object System.Collections.Generic.List[object]
$rateRemaining = "unknown"

foreach ($candidate in $candidates) {
    $processed++
    $uri = "https://api.nexusmods.com/v1/games/$Game/mods/$($candidate.ModId).json"
    Write-Verbose "Querying $($candidate.Name) ($($candidate.ModId)): $uri"

    try {
        $response = Invoke-NexusGet -Uri $uri -Headers $headers
        if ($response.Headers["X-RL-Hourly-Remaining"]) { $rateRemaining = $response.Headers["X-RL-Hourly-Remaining"] }

        if ([int]$response.StatusCode -eq 404) {
            $status = "removed"
            $version = Read-MetaIniValue -Lines $candidate.Lines -Key "version"
            if (-not $version) { $version = Read-MetaIniValue -Lines $candidate.Lines -Key "newestVersion" }
            Write-Warning "Nexus mod removed or unavailable: $($candidate.Name) (modid=$($candidate.ModId))"
        } elseif ([int]$response.StatusCode -ge 400) {
            $errors.Add([pscustomobject]@{ mod = $candidate.Name; modid = $candidate.ModId; error = "HTTP $($response.StatusCode)" })
            continue
        } else {
            $mod = $response.Content | ConvertFrom-Json
            $status = [string]$mod.status
            $version = [string]$mod.version
        }

        $fileStatus = Convert-NexusStatusToMetaCode -Status $status
        if ($fileStatus -in @(6, 9)) { $removedHidden++ }

        $oldNewest = Read-MetaIniValue -Lines $candidate.Lines -Key "newestVersion"
        if ($version -and $oldNewest -and $version -ne $oldNewest) { $updatesDiscovered++ }

        $now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        $newLines = $candidate.Lines
        $newLines = Set-MetaIniValue -Lines $newLines -Key "newestVersion" -Value $version
        $newLines = Set-MetaIniValue -Lines $newLines -Key "nexusFileStatus" -Value ([string]$fileStatus)
        $newLines = Set-MetaIniValue -Lines $newLines -Key "lastNexusQuery" -Value $now
        $newLines = Set-MetaIniValue -Lines $newLines -Key "lastNexusUpdate" -Value $now

        if ($DryRun) {
            Write-Output "[DRY-RUN] $($candidate.Name): newestVersion=$version nexusFileStatus=$fileStatus lastNexusQuery=$now lastNexusUpdate=$now"
        } else {
            [System.IO.File]::WriteAllLines($candidate.Path, $newLines, [Text.UTF8Encoding]::new($false))
            Write-Verbose "Updated $($candidate.Path)"
        }
    } catch {
        $errors.Add([pscustomobject]@{ mod = $candidate.Name; modid = $candidate.ModId; error = $_.Exception.Message })
        continue
    } finally {
        Start-Sleep -Milliseconds 100
    }
}

Write-Output ""
Write-Output "Nexus update-state refresh summary"
Write-Output "=================================="
[pscustomobject]@{
    total_processed = $processed
    updates_discovered = $updatesDiscovered
    removed_or_hidden = $removedHidden
    errors = $errors.Count
    api_rate_budget_remaining = $rateRemaining
} | Format-Table -AutoSize

if ($errors.Count -gt 0) {
    Write-Output "Anomalies:"
    $errors | Format-Table -AutoSize
}

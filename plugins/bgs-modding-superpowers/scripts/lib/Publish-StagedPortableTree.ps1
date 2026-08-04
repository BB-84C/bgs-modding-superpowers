#requires -Version 7.0
Set-StrictMode -Version Latest

function Remove-OwnedPortableBuildTree {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)][string]$Path,
    [Parameter(Mandatory)][string]$RepoRoot,
    [Parameter(Mandatory)][string]$ContainmentRoot,
    [Parameter(Mandatory)][string[]]$AcceptedMarkerNames
  )

  if (-not (Test-Path -LiteralPath $Path)) { return }
  $markerFound = @($AcceptedMarkerNames | Where-Object {
    Test-BgsGeneratedMarker -Target $Path -MarkerName $_
  }).Count -gt 0
  if (-not $markerFound) {
    throw "Refusing to remove '$Path': it does not carry an invocation-owned portable-build marker."
  }
  $null = Assert-SafeDeleteTarget -Target $Path -RepoRoot $RepoRoot -ContainmentRoot $ContainmentRoot
  Remove-Item -LiteralPath $Path -Recurse -Force
}

function Publish-StagedPortableTree {
  <#
  .SYNOPSIS
    Atomically promotes a completed portable-plugin staging tree where possible.

  .DESCRIPTION
    The current final tree is never recursively deleted. It is first renamed to
    an invocation-private backup. If that rename is blocked (for example by an
    open SQLite handle), the final tree is untouched and only the staged tree is
    cleaned up. If promotion fails after the first rename, the backup is renamed
    back to its original path before the failure is reported.
  #>
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)][string]$StagingRoot,
    [Parameter(Mandatory)][string]$FinalRoot,
    [Parameter(Mandatory)][string]$RepoRoot,
    [Parameter(Mandatory)][string]$ContainmentRoot,
    [Parameter(Mandatory)][string]$GeneratedMarker,
    [Parameter(Mandatory)][string]$StagingMarker,
    # Internal test seams. Production callers use the safe defaults below.
    [scriptblock]$MoveDirectory,
    [scriptblock]$RemoveOwnedTree
  )

  if ($null -eq $MoveDirectory) {
    $MoveDirectory = {
      param([string]$Source, [string]$Destination)
      [IO.Directory]::Move($Source, $Destination)
    }
  }
  if ($null -eq $RemoveOwnedTree) {
    $RemoveOwnedTree = {
      param([string]$Path, [string]$SafeRepoRoot, [string]$SafeContainmentRoot, [string[]]$MarkerNames)
      Remove-OwnedPortableBuildTree -Path $Path -RepoRoot $SafeRepoRoot -ContainmentRoot $SafeContainmentRoot -AcceptedMarkerNames $MarkerNames
    }
  }

  $stagingFull = [IO.Path]::GetFullPath($StagingRoot)
  $finalFull = [IO.Path]::GetFullPath($FinalRoot)
  $repoFull = [IO.Path]::GetFullPath($RepoRoot)
  $containmentFull = [IO.Path]::GetFullPath($ContainmentRoot)
  $parent = Split-Path -Parent $finalFull
  $comparison = [System.StringComparison]::OrdinalIgnoreCase

  if (-not [string]::Equals((Split-Path -Parent $stagingFull), $parent, $comparison)) {
    throw "Refusing staged publish: staging root '$stagingFull' is not a sibling of final root '$finalFull'."
  }
  if (-not (Test-BgsGeneratedMarker -Target $stagingFull -MarkerName $GeneratedMarker)) {
    throw "Refusing staged publish: completed staging root '$stagingFull' is missing $GeneratedMarker."
  }
  $null = Assert-SafeDeleteTarget -Target $stagingFull -RepoRoot $repoFull -ContainmentRoot $containmentFull

  $backupRoot = Join-Path $parent (".bgs-portable-build-backup-{0}" -f [Guid]::NewGuid().ToString('N'))
  $null = Assert-SafeDeleteTarget -Target $backupRoot -RepoRoot $repoFull -ContainmentRoot $containmentFull
  $finalExisted = Test-Path -LiteralPath $finalFull
  $backupCreated = $false
  $published = $false

  if ($finalExisted) {
    if (-not (Test-BgsGeneratedMarker -Target $finalFull -MarkerName $GeneratedMarker)) {
      throw "Refusing to replace '$finalFull': existing output is missing $GeneratedMarker. The materializer only replaces trees it previously generated."
    }
    $null = Assert-SafeDeleteTarget -Target $finalFull -RepoRoot $repoFull -ContainmentRoot $containmentFull
  }

  try {
    if ($finalExisted) {
      # Same-parent renames stay on the same volume. A locked descendant causes
      # this operation to fail before the final path is modified.
      # Do not use Move-Item here: its FileSystem-provider fallback can move
      # descendants one by one, leaving a locked source tree partially changed.
      # Directory.Move maps to a same-volume directory rename instead.
      & $MoveDirectory $finalFull $backupRoot
      $backupCreated = $true
    }

    & $MoveDirectory $stagingFull $finalFull
    $published = $true

    if ($backupCreated -and (Test-Path -LiteralPath $backupRoot)) {
      try {
        & $RemoveOwnedTree $backupRoot $repoFull $containmentFull @($GeneratedMarker)
      } catch {
        Write-Warning "Portable plugin published, but the previous generated tree was quarantined at '$backupRoot': $($_.Exception.Message)"
        return [pscustomobject]@{ Published = $true; FinalRoot = $finalFull; QuarantinedBackup = $backupRoot }
      }
    }

    return [pscustomobject]@{ Published = $true; FinalRoot = $finalFull; QuarantinedBackup = $null }
  } catch {
    $publishError = $_
    $rollbackError = $null

    if ($backupCreated -and (Test-Path -LiteralPath $backupRoot) -and -not (Test-Path -LiteralPath $finalFull)) {
      try {
        & $MoveDirectory $backupRoot $finalFull
      } catch {
        $rollbackError = $_
      }
    }

    if (-not $published -and (Test-Path -LiteralPath $stagingFull)) {
      try {
        & $RemoveOwnedTree $stagingFull $repoFull $containmentFull @($GeneratedMarker, $StagingMarker)
      } catch {
        Write-Warning "Failed staged publish left invocation-owned staging tree quarantined at '$stagingFull': $($_.Exception.Message)"
      }
    }

    if ($null -ne $rollbackError) {
      throw "Portable publish failed: $($publishError.Exception.Message). Rollback also failed; original generated tree is quarantined at '$backupRoot': $($rollbackError.Exception.Message)"
    }
    throw "Portable publish failed without modifying the existing final tree: $($publishError.Exception.Message)"
  }
}

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $repoRoot 'scripts\lib\Assert-SafeDeleteTarget.ps1')
. (Join-Path $repoRoot 'scripts\lib\Publish-StagedPortableTree.ps1')

$marker = '.bgs-portable-build'
$stagingMarker = '.bgs-portable-build-staging'
$testRoot = Join-Path $repoRoot ('.opencode\artifacts\materializer-hardening-test-' + [Guid]::NewGuid().ToString('N'))
$finalRoot = Join-Path $testRoot 'bgs-modding-superpowers'

function New-TestPortableTree {
  param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Payload)
  New-Item -ItemType Directory -Path $Path -Force | Out-Null
  [IO.File]::WriteAllText((Join-Path $Path 'payload.txt'), $Payload, [Text.UTF8Encoding]::new($false))
  Write-BgsGeneratedMarker -Target $Path -MarkerName $marker -Content "test=$Payload"
}

function Get-TestTreeFingerprint {
  param([Parameter(Mandatory)][string]$Path)
  $entries = foreach ($file in (Get-ChildItem -LiteralPath $Path -Recurse -Force -File | Sort-Object FullName)) {
    $relative = $file.FullName.Substring($Path.Length).TrimStart([char]'\', [char]'/') -replace '\\', '/'
    "$relative $((Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash)"
  }
  return ($entries -join "`n")
}

try {
  New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
  New-TestPortableTree -Path $finalRoot -Payload 'old-final-bytes'
  if (-not (Test-BgsGeneratedMarker -Target $finalRoot -MarkerName $marker)) { throw 'Test setup did not create the final-tree sentinel.' }
  $beforeFingerprint = Get-TestTreeFingerprint -Path $finalRoot

  $failedStage = Join-Path $testRoot '.bgs-portable-build-staging-locked'
  New-TestPortableTree -Path $failedStage -Payload 'new-staged-bytes'
  Write-BgsGeneratedMarker -Target $failedStage -MarkerName $stagingMarker -Content 'owned-by-test'

  # FileShare.Read deliberately denies delete/rename access without spawning a
  # helper process, so the test has no process to orphan.
  $lock = [IO.File]::Open((Join-Path $finalRoot 'payload.txt'), [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
  try {
    $publishFailed = $false
    $publishFailure = $null
    try {
      Publish-StagedPortableTree -StagingRoot $failedStage -FinalRoot $finalRoot -RepoRoot $repoRoot -ContainmentRoot $testRoot -GeneratedMarker $marker -StagingMarker $stagingMarker | Out-Null
    } catch {
      $publishFailed = $true
      $publishFailure = $_.Exception.Message
    }
    if (-not $publishFailed) { throw 'Locked final tree unexpectedly published.' }
    $afterFingerprint = Get-TestTreeFingerprint -Path $finalRoot
    if ($afterFingerprint -ne $beforeFingerprint) { throw 'Locked replacement changed the existing final tree.' }
    if (-not (Test-BgsGeneratedMarker -Target $finalRoot -MarkerName $marker)) {
      $finalNames = (Get-ChildItem -LiteralPath $finalRoot -Force | ForEach-Object Name) -join ', '
      throw "Locked replacement removed the final-tree sentinel. Publish failure: $publishFailure. Final entries: $finalNames"
    }
    if (Test-Path -LiteralPath $failedStage) { throw 'Failed replacement left its invocation-owned staging tree behind.' }
  } finally {
    $lock.Dispose()
  }

  # Deterministically fail the second rename only. The third invocation must be
  # the rollback rename from backup back to the original final path.
  $rollbackStage = Join-Path $testRoot '.bgs-portable-build-staging-rollback'
  New-TestPortableTree -Path $rollbackStage -Payload 'rollback-staged-bytes'
  Write-BgsGeneratedMarker -Target $rollbackStage -MarkerName $stagingMarker -Content 'owned-by-test'
  $moveState = [pscustomobject]@{ Count = 0 }
  $failSecondMove = {
    param([string]$Source, [string]$Destination)
    $moveState.Count++
    if ($moveState.Count -eq 2) { throw [IO.IOException]::new('injected second rename failure') }
    [IO.Directory]::Move($Source, $Destination)
  }
  $rollbackFailed = $false
  try {
    Publish-StagedPortableTree -StagingRoot $rollbackStage -FinalRoot $finalRoot -RepoRoot $repoRoot -ContainmentRoot $testRoot -GeneratedMarker $marker -StagingMarker $stagingMarker -MoveDirectory $failSecondMove | Out-Null
  } catch {
    $rollbackFailed = $true
  }
  if (-not $rollbackFailed) { throw 'Injected second rename failure unexpectedly published.' }
  if ($moveState.Count -ne 3) { throw "Expected final-to-backup, failed staging-to-final, and rollback moves; saw $($moveState.Count)." }
  if ((Get-TestTreeFingerprint -Path $finalRoot) -ne $beforeFingerprint) { throw 'Second-rename failure did not restore the final tree byte-identically.' }
  if (Test-Path -LiteralPath $rollbackStage) { throw 'Second-rename failure left staging behind.' }
  if (@(Get-ChildItem -LiteralPath $testRoot -Directory -Filter '.bgs-portable-build-backup-*').Count -ne 0) { throw 'Second-rename failure left a backup tree behind.' }

  # The new tree is already published when old-tree cleanup starts. An injected
  # cleanup failure must return the old tree as a quarantined backup instead of
  # corrupting the new final tree.
  $quarantineStage = Join-Path $testRoot '.bgs-portable-build-staging-quarantine'
  New-TestPortableTree -Path $quarantineStage -Payload 'quarantined-new-final-bytes'
  Write-BgsGeneratedMarker -Target $quarantineStage -MarkerName $stagingMarker -Content 'owned-by-test'
  $oldFingerprint = Get-TestTreeFingerprint -Path $finalRoot
  $cleanupState = [pscustomobject]@{ Calls = 0 }
  $failBackupCleanup = {
    param([string]$Path, [string]$SafeRepoRoot, [string]$SafeContainmentRoot, [string[]]$MarkerNames)
    $cleanupState.Calls++
    throw [IO.IOException]::new('injected backup cleanup failure')
  }
  $quarantineResult = Publish-StagedPortableTree -StagingRoot $quarantineStage -FinalRoot $finalRoot -RepoRoot $repoRoot -ContainmentRoot $testRoot -GeneratedMarker $marker -StagingMarker $stagingMarker -RemoveOwnedTree $failBackupCleanup
  if (-not $quarantineResult.Published -or [string]::IsNullOrWhiteSpace($quarantineResult.QuarantinedBackup)) { throw 'Backup cleanup failure did not return a quarantined successful publish.' }
  if ($cleanupState.Calls -ne 1) { throw "Expected one backup cleanup attempt; saw $($cleanupState.Calls)." }
  if ((Get-Content -LiteralPath (Join-Path $finalRoot 'payload.txt') -Raw) -ne 'quarantined-new-final-bytes') { throw 'Backup cleanup failure corrupted the new final tree.' }
  if (-not (Test-Path -LiteralPath $quarantineResult.QuarantinedBackup)) { throw 'Returned quarantined backup path does not exist.' }
  if ((Get-TestTreeFingerprint -Path $quarantineResult.QuarantinedBackup) -ne $oldFingerprint) { throw 'Quarantined backup does not preserve the previous final tree.' }
  Remove-OwnedPortableBuildTree -Path $quarantineResult.QuarantinedBackup -RepoRoot $repoRoot -ContainmentRoot $testRoot -AcceptedMarkerNames @($marker)

  $successfulStage = Join-Path $testRoot '.bgs-portable-build-staging-success'
  New-TestPortableTree -Path $successfulStage -Payload 'new-final-bytes'
  Write-BgsGeneratedMarker -Target $successfulStage -MarkerName $stagingMarker -Content 'owned-by-test'
  $result = Publish-StagedPortableTree -StagingRoot $successfulStage -FinalRoot $finalRoot -RepoRoot $repoRoot -ContainmentRoot $testRoot -GeneratedMarker $marker -StagingMarker $stagingMarker
  if (-not $result.Published) { throw 'Unlocked replacement did not report publication.' }
  if ((Get-Content -LiteralPath (Join-Path $finalRoot 'payload.txt') -Raw) -ne 'new-final-bytes') { throw 'Unlocked replacement did not publish staged bytes.' }
  if (Test-Path -LiteralPath $successfulStage) { throw 'Successful replacement left staging behind.' }
  if (@(Get-ChildItem -LiteralPath $testRoot -Directory -Filter '.bgs-portable-build-backup-*').Count -ne 0) { throw 'Successful replacement left a backup tree behind.' }

  Write-Host 'build-portable-plugin staged publish regression tests passed.'
} finally {
  if (Test-Path -LiteralPath $testRoot) {
    Remove-Item -LiteralPath $testRoot -Recurse -Force
  }
}

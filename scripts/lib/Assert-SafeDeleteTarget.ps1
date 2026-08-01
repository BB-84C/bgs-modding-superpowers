#requires -Version 7.0
Set-StrictMode -Version Latest

function Test-BgsPathStrictlyInside {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)][string]$Candidate,
    [Parameter(Mandatory)][string]$Root
  )

  $comparison = [System.StringComparison]::OrdinalIgnoreCase
  $candidateFull = [System.IO.Path]::GetFullPath($Candidate).TrimEnd([char]'\', [char]'/')
  $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd([char]'\', [char]'/')
  return $candidateFull.StartsWith($rootFull + [System.IO.Path]::DirectorySeparatorChar, $comparison)
}

function Get-BgsReparseDestination {
  [CmdletBinding()]
  param([Parameter(Mandatory)]$Item)

  # PowerShell 7/.NET exposes ResolveLinkTarget. Windows PowerShell 5.1 does
  # not, so its FileSystem provider's Target property is used as the fallback.
  if ($Item.PSObject.Methods.Match('ResolveLinkTarget').Count -gt 0) {
    try {
      $resolved = $Item.ResolveLinkTarget($true)
      if ($null -ne $resolved -and $resolved.FullName) {
        return [System.IO.Path]::GetFullPath($resolved.FullName)
      }
    } catch {
      # Fall through to the PS 5.1-compatible provider property.
    }
  }

  $targets = @($Item.Target | Where-Object { $_ })
  if ($targets.Count -eq 0) {
    throw "Refusing unsafe delete target '$($Item.FullName)': unable to resolve reparse point."
  }
  $target = [string]$targets[0]
  if (-not [System.IO.Path]::IsPathRooted($target)) {
    $target = Join-Path (Split-Path -Parent $Item.FullName) $target
  }
  return [System.IO.Path]::GetFullPath($target)
}

function Resolve-BgsPathThroughLinks {
  [CmdletBinding()]
  param([Parameter(Mandatory)][string]$Path)

  $fullPath = [System.IO.Path]::GetFullPath($Path)
  for ($pass = 0; $pass -lt 64; $pass++) {
    $driveRoot = [System.IO.Path]::GetPathRoot($fullPath)
    [char[]]$separators = @([char]'\', [char]'/')
    $relative = $fullPath.Substring($driveRoot.Length)
    $parts = @($relative.Split($separators, [System.StringSplitOptions]::RemoveEmptyEntries))
    $cursor = $driveRoot
    $restarted = $false

    for ($index = 0; $index -lt $parts.Count; $index++) {
      $candidate = Join-Path $cursor $parts[$index]
      try {
        $item = Get-Item -LiteralPath $candidate -Force -ErrorAction Stop
      } catch [System.Management.Automation.ItemNotFoundException] {
        $item = $null
      } catch {
        throw "Refusing unsafe delete target '$fullPath': cannot inspect path component '$candidate': $($_.Exception.Message)"
      }
      if ($null -eq $item) {
        if ($index -eq $parts.Count - 1) { return [System.IO.Path]::GetFullPath($candidate) }
        $remaining = $parts[$index..($parts.Count - 1)] -join [System.IO.Path]::DirectorySeparatorChar
        return [System.IO.Path]::GetFullPath((Join-Path $cursor $remaining))
      }

      if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        $destination = Get-BgsReparseDestination -Item $item
        if ($index -lt $parts.Count - 1) {
          $destination = Join-Path $destination ($parts[($index + 1)..($parts.Count - 1)] -join [System.IO.Path]::DirectorySeparatorChar)
        }
        $fullPath = [System.IO.Path]::GetFullPath($destination)
        $restarted = $true
        break
      }
      $cursor = $item.FullName
    }

    if (-not $restarted) { return [System.IO.Path]::GetFullPath($fullPath) }
  }
  throw "Refusing unsafe delete target '$Path': reparse-point resolution exceeded 64 hops."
}

function Assert-BgsSafeTreeContents {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)][string]$Target,
    [Parameter(Mandatory)][string]$ResolvedContainmentRoot,
    [Parameter(Mandatory)][string]$ResolvedRepoRoot,
    [Parameter(Mandatory)][bool]$RequireRepoContainment
  )

  if (-not (Test-Path -LiteralPath $Target)) { return }
  $comparison = [System.StringComparison]::OrdinalIgnoreCase
  $pending = New-Object System.Collections.Stack
  $visited = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
  $pending.Push((Resolve-BgsPathThroughLinks -Path $Target))

  while ($pending.Count -gt 0) {
    $current = [string]$pending.Pop()
    if (-not $visited.Add($current)) { continue }
    if (Test-Path -LiteralPath (Join-Path $current '.git')) {
      throw "Refusing unsafe delete target '$Target': descendant directory '$current' contains a .git entry."
    }

    foreach ($child in @(Get-ChildItem -LiteralPath $current -Force)) {
      if ($child.Name -ieq '.git') {
        throw "Refusing unsafe delete target '$Target': descendant contains a .git entry at '$($child.FullName)'."
      }
      if (($child.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        $resolvedChild = Resolve-BgsPathThroughLinks -Path $child.FullName
        if (-not (Test-BgsPathStrictlyInside -Candidate $resolvedChild -Root $ResolvedContainmentRoot)) {
          throw "Refusing unsafe delete target '$Target': descendant reparse point '$($child.FullName)' resolves outside containment root '$ResolvedContainmentRoot' to '$resolvedChild'."
        }
        if ($RequireRepoContainment -and -not (Test-BgsPathStrictlyInside -Candidate $resolvedChild -Root $ResolvedRepoRoot)) {
          throw "Refusing unsafe delete target '$Target': descendant reparse point '$($child.FullName)' escapes repository root '$ResolvedRepoRoot' to '$resolvedChild'."
        }
        if ($child.PSIsContainer) { $pending.Push($resolvedChild) }
      } elseif ($child.PSIsContainer) {
        $pending.Push($child.FullName)
      }
    }
  }
}

function Assert-BgsSafeAncestorEntries {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)][string]$Target,
    [Parameter(Mandatory)][string]$StopAt
  )

  $comparison = [System.StringComparison]::OrdinalIgnoreCase
  $current = [System.IO.Path]::GetFullPath($Target).TrimEnd([char]'\', [char]'/')
  $normalizedStopAt = [System.IO.Path]::GetFullPath($StopAt).TrimEnd([char]'\', [char]'/')
  while ($true) {
    $parent = Split-Path -Parent $current
    if (-not $parent -or [string]::Equals($parent.TrimEnd([char]'\', [char]'/'), $normalizedStopAt, $comparison)) { return }
    if (Test-Path -LiteralPath (Join-Path $parent '.git')) {
      throw "Refusing unsafe delete target '$Target': ancestor '$parent' contains a .git entry."
    }
    $current = $parent
  }
}

function Assert-SafeDeleteTarget {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)][string]$Target,
    [Parameter(Mandatory)][string]$RepoRoot,
    [Parameter(Mandatory)][string]$ContainmentRoot
  )

  if ([string]::IsNullOrWhiteSpace($Target)) {
    throw "Refusing unsafe delete target '<empty>': target is empty or whitespace."
  }

  $comparison = [System.StringComparison]::OrdinalIgnoreCase
  $fullTarget = [System.IO.Path]::GetFullPath($Target)
  $targetDriveRoot = [System.IO.Path]::GetPathRoot($fullTarget)
  $normalizedTarget = $fullTarget.TrimEnd([char]'\', [char]'/')
  $normalizedDriveRoot = $targetDriveRoot.TrimEnd([char]'\', [char]'/')
  if ([string]::Equals($normalizedTarget, $normalizedDriveRoot, $comparison)) {
    throw "Refusing unsafe delete target '$fullTarget': target is a drive root."
  }

  [char[]]$pathSeparators = @([char]'\', [char]'/')
  $segments = @($normalizedTarget.Split($pathSeparators, [System.StringSplitOptions]::RemoveEmptyEntries))
  if ($segments.Count -lt 3) {
    throw "Refusing unsafe delete target '$normalizedTarget': path has fewer than three segments."
  }

  $normalizedRepoRoot = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd([char]'\', [char]'/')
  $normalizedContainmentRoot = [System.IO.Path]::GetFullPath($ContainmentRoot).TrimEnd([char]'\', [char]'/')
  if (-not (Test-BgsPathStrictlyInside -Candidate $normalizedTarget -Root $normalizedContainmentRoot)) {
    throw "Refusing unsafe delete target '$normalizedTarget': target is outside containment root '$normalizedContainmentRoot'."
  }
  if ([string]::Equals($normalizedTarget, $normalizedRepoRoot, $comparison)) {
    throw "Refusing unsafe delete target '$normalizedTarget': target is the repository root."
  }
  if ($normalizedRepoRoot.StartsWith($normalizedTarget + [System.IO.Path]::DirectorySeparatorChar, $comparison)) {
    throw "Refusing unsafe delete target '$normalizedTarget': target is an ancestor of repository root '$normalizedRepoRoot'."
  }

  $resolvedContainmentRoot = (Resolve-BgsPathThroughLinks -Path $normalizedContainmentRoot).TrimEnd([char]'\', [char]'/')
  $resolvedTarget = (Resolve-BgsPathThroughLinks -Path $normalizedTarget).TrimEnd([char]'\', [char]'/')
  if (-not (Test-BgsPathStrictlyInside -Candidate $resolvedTarget -Root $resolvedContainmentRoot)) {
    throw "Refusing unsafe delete target '$normalizedTarget': resolved target '$resolvedTarget' escapes resolved containment root '$resolvedContainmentRoot'."
  }
  $resolvedRepoRoot = (Resolve-BgsPathThroughLinks -Path $normalizedRepoRoot).TrimEnd([char]'\', [char]'/')
  $lexicallyInsideRepo = Test-BgsPathStrictlyInside -Candidate $normalizedTarget -Root $normalizedRepoRoot
  if ($lexicallyInsideRepo -and -not (Test-BgsPathStrictlyInside -Candidate $resolvedTarget -Root $resolvedRepoRoot)) {
    throw "Refusing unsafe delete target '$normalizedTarget': lexically in-repository target resolves outside repository root '$resolvedRepoRoot' to '$resolvedTarget'."
  }
  if ([string]::Equals($resolvedTarget, $resolvedRepoRoot, $comparison) -or $resolvedRepoRoot.StartsWith($resolvedTarget + [System.IO.Path]::DirectorySeparatorChar, $comparison)) {
    throw "Refusing unsafe delete target '$normalizedTarget': resolved target '$resolvedTarget' is the repository root or its ancestor '$resolvedRepoRoot'."
  }

  $ancestorStop = if ($lexicallyInsideRepo) { $resolvedRepoRoot } else { $resolvedContainmentRoot }
  Assert-BgsSafeAncestorEntries -Target $resolvedTarget -StopAt $ancestorStop
  Assert-BgsSafeTreeContents -Target $normalizedTarget -ResolvedContainmentRoot $resolvedContainmentRoot -ResolvedRepoRoot $resolvedRepoRoot -RequireRepoContainment $lexicallyInsideRepo
  return [pscustomobject]@{
    Path = $normalizedTarget
    ResolvedPath = $resolvedTarget
    ResolvedContainmentRoot = $resolvedContainmentRoot
    ResolvedRepoRoot = $resolvedRepoRoot
  }
}

function Write-SafeDeletePreview {
  [CmdletBinding()]
  param([Parameter(Mandatory)][string]$Target)

  $resolvedTarget = Resolve-BgsPathThroughLinks -Path $Target
  $files = @(Get-ChildItem -LiteralPath $resolvedTarget -Recurse -Force -File)
  $totalBytes = [int64]0
  foreach ($file in $files) { $totalBytes += $file.Length }
  Write-Host ("[safe-delete] target: {0}" -f $resolvedTarget)
  Write-Host ("[safe-delete] files: {0:N0}; total size: {1:N0} bytes" -f $files.Count, $totalBytes)
}

function Test-BgsGeneratedMarker {
  [CmdletBinding()]
  param([Parameter(Mandatory)][string]$Target, [Parameter(Mandatory)][string]$MarkerName)
  return Test-Path -LiteralPath (Join-Path $Target $MarkerName)
}

function Write-BgsGeneratedMarker {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)][string]$Target,
    [Parameter(Mandatory)][string]$MarkerName,
    [Parameter(Mandatory)][string]$Content
  )
  [System.IO.File]::WriteAllText((Join-Path $Target $MarkerName), $Content + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
}

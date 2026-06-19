param(
  [string]$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$toolRoot = Join-Path $RepoRoot 'tools\bgs-archive'
$acceptanceDir = Join-Path $RepoRoot '.opencode\artifacts\archive-papyrus-tools\acceptance'
$workDir = Join-Path $acceptanceDir 'A11-work'
$evidencePath = Join-Path $acceptanceDir 'A11-real-archive-acceptance.md'

$fixtures = @(
  [pscustomobject]@{
    Name = 'FO4 BA2'
    Path = Join-Path $RepoRoot '.opencode\artifacts\archive-papyrus-tools\fixtures\fo4-ba2\ccbgsfo4008-pipgrn - main.ba2'
    ExpectedFamily = 'fo4'
    ExpectedVersion = 1
    Game = 'fallout4'
    RepackedName = 'fo4-repacked.ba2'
  },
  [pscustomobject]@{
    Name = 'Skyrim SE BSA'
    Path = Join-Path $RepoRoot '.opencode\artifacts\archive-papyrus-tools\fixtures\skyrim-bsa\SofiaHideTrackingMarker.bsa'
    ExpectedFamily = 'tes4'
    ExpectedVersion = 105
    Game = 'skyrimse'
    RepackedName = 'skyrim-repacked.bsa'
  }
)

function Reset-Directory([string]$Path) {
  if ([System.IO.Directory]::Exists($Path)) {
    [System.IO.Directory]::Delete($Path, $true)
  }
  [void][System.IO.Directory]::CreateDirectory($Path)
}

function Invoke-BgsArchive([string[]]$Arguments) {
  Push-Location -LiteralPath $toolRoot
  try {
    $output = & cargo run --quiet -- @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "bgs-archive failed with exit code $LASTEXITCODE for args: $($Arguments -join ' ')"
    }
    return ($output -join "`n")
  }
  finally {
    Pop-Location
  }
}

function Convert-ToRelativeArchivePath([string]$Root, [string]$Path) {
  $relative = [System.IO.Path]::GetRelativePath($Root, $Path)
  return $relative.Replace('\', '/').ToLowerInvariant()
}

function Get-FirstBytes([string]$Path, [int]$Count = 32) {
  return @(Get-Content -LiteralPath $Path -AsByteStream -TotalCount $Count)
}

function Format-Magic([byte[]]$Bytes) {
  $head = @($Bytes | Select-Object -First 16)
  $hex = ($head | ForEach-Object { $_.ToString('X2') }) -join ' '
  $chars = foreach ($byte in $head) {
    if (($byte -ge 32) -and ($byte -le 126)) { [char]$byte } else { '.' }
  }
  return "$hex / $(-join $chars)"
}

function Test-ExpectedMagic([string]$Extension, [byte[]]$Bytes) {
  $ascii = [System.Text.Encoding]::ASCII.GetString($Bytes)
  $hex4 = (@($Bytes | Select-Object -First 4) | ForEach-Object { $_.ToString('X2') }) -join ' '
  switch ($Extension.ToLowerInvariant()) {
    '.dds' { return [pscustomobject]@{ Expected = 'DDS '; Ok = $ascii.StartsWith('DDS ') } }
    '.nif' { return [pscustomobject]@{ Expected = 'Gamebryo File Format or NetImmerse'; Ok = ($ascii.StartsWith('Gamebryo File Format') -or $ascii.StartsWith('NetImmerse')) } }
    '.pex' { return [pscustomobject]@{ Expected = 'FA 57 C0 DE'; Ok = ($hex4 -eq 'FA 57 C0 DE') } }
    '.bgsm' { return [pscustomobject]@{ Expected = 'BGSM'; Ok = $ascii.StartsWith('BGSM') } }
    '.bgem' { return [pscustomobject]@{ Expected = 'BGEM'; Ok = $ascii.StartsWith('BGEM') } }
    '.wav' { return [pscustomobject]@{ Expected = 'RIFF'; Ok = $ascii.StartsWith('RIFF') } }
    '.xwm' { return [pscustomobject]@{ Expected = 'RIFF'; Ok = $ascii.StartsWith('RIFF') } }
    '.fuz' { return [pscustomobject]@{ Expected = 'RIFF or FUZE'; Ok = ($ascii.StartsWith('RIFF') -or $ascii.StartsWith('FUZE')) } }
    '.swf' { return [pscustomobject]@{ Expected = 'FWS or CWS'; Ok = ($ascii.StartsWith('FWS') -or $ascii.StartsWith('CWS')) } }
    default { return [pscustomobject]@{ Expected = 'unknown extension; non-empty'; Ok = ($Bytes.Length -gt 0) } }
  }
}

function Test-StructuralValidation([object[]]$Entries, [string]$ExtractDir) {
  $rows = @()
  foreach ($entry in $Entries) {
    $relativeForDisk = $entry.path.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
    $filePath = Join-Path $ExtractDir $relativeForDisk
    if (-not [System.IO.File]::Exists($filePath)) {
      $rows += [pscustomobject]@{
        File = $entry.path; Ext = [System.IO.Path]::GetExtension($entry.path); ExpectedMagic = 'file exists'; ActualMagic = 'MISSING'
        ReportedSize = [int64]$entry.size; ExtractedSize = 0; SizeMatch = $false; Verdict = $false
      }
      continue
    }
    $info = [System.IO.FileInfo]::new($filePath)
    $bytes = Get-FirstBytes -Path $filePath
    $extension = [System.IO.Path]::GetExtension($filePath)
    $magic = Test-ExpectedMagic -Extension $extension -Bytes $bytes
    $sizeMatch = ($info.Length -eq [int64]$entry.size)
    $rows += [pscustomobject]@{
      File = $entry.path
      Ext = $extension.ToLowerInvariant()
      ExpectedMagic = $magic.Expected
      ActualMagic = Format-Magic -Bytes $bytes
      ReportedSize = [int64]$entry.size
      ExtractedSize = [int64]$info.Length
      SizeMatch = $sizeMatch
      Verdict = ($sizeMatch -and $magic.Ok -and ($info.Length -gt 0))
    }
  }
  return $rows
}

function Find-FirstDiffOffset([string]$Left, [string]$Right) {
  $leftBytes = @(Get-Content -LiteralPath $Left -AsByteStream)
  $rightBytes = @(Get-Content -LiteralPath $Right -AsByteStream)
  $limit = [Math]::Min($leftBytes.Count, $rightBytes.Count)
  for ($i = 0; $i -lt $limit; $i++) {
    if ($leftBytes[$i] -ne $rightBytes[$i]) { return $i }
  }
  return $limit
}

function Compare-ArchiveTrees([string]$LeftRoot, [string]$RightRoot) {
  $leftFiles = @{}
  $rightFiles = @{}
  foreach ($file in Get-ChildItem -LiteralPath $LeftRoot -Recurse -File) {
    $leftFiles[(Convert-ToRelativeArchivePath -Root $LeftRoot -Path $file.FullName)] = $file.FullName
  }
  foreach ($file in Get-ChildItem -LiteralPath $RightRoot -Recurse -File) {
    $rightFiles[(Convert-ToRelativeArchivePath -Root $RightRoot -Path $file.FullName)] = $file.FullName
  }

  $leftOnly = @($leftFiles.Keys | Where-Object { -not $rightFiles.ContainsKey($_) } | Sort-Object)
  $rightOnly = @($rightFiles.Keys | Where-Object { -not $leftFiles.ContainsKey($_) } | Sort-Object)
  [void](Compare-Object -ReferenceObject @($leftFiles.Keys) -DifferenceObject @($rightFiles.Keys))

  $rows = @()
  foreach ($key in @($leftFiles.Keys | Where-Object { $rightFiles.ContainsKey($_) } | Sort-Object)) {
    $leftHash = (Get-FileHash -LiteralPath $leftFiles[$key] -Algorithm SHA256).Hash.ToLowerInvariant()
    $rightHash = (Get-FileHash -LiteralPath $rightFiles[$key] -Algorithm SHA256).Hash.ToLowerInvariant()
    $matches = ($leftHash -eq $rightHash)
    $rows += [pscustomobject]@{
      File = $key
      OriginalSha256 = $leftHash
      RoundTripSha256 = $rightHash
      Match = $matches
      FirstDiffOffset = if ($matches) { 'n/a' } else { Find-FirstDiffOffset -Left $leftFiles[$key] -Right $rightFiles[$key] }
    }
  }

  return [pscustomobject]@{ Rows = @($rows); LeftOnly = $leftOnly; RightOnly = $rightOnly }
}

function Add-CodeBlock([System.Text.StringBuilder]$Builder, [string]$Language, [string]$Body) {
  [void]$Builder.AppendLine("``````$Language")
  [void]$Builder.AppendLine($Body.Trim())
  [void]$Builder.AppendLine("``````")
  [void]$Builder.AppendLine()
}

[void][System.IO.Directory]::CreateDirectory($acceptanceDir)
Reset-Directory -Path $workDir

$md = [System.Text.StringBuilder]::new()
[void]$md.AppendLine('# Task A11 real archive semantic acceptance')
[void]$md.AppendLine()
[void]$md.AppendLine('- Mode: CLI-only (`cargo run --quiet -- <args>`).')
[void]$md.AppendLine('- External archive tools: none.')
[void]$md.AppendLine('- GUI programs launched: none.')
[void]$md.AppendLine('- Validation: structural magic/size checks plus bgs-archive pack/extract self-consistency SHA256.')
[void]$md.AppendLine()

$overallPass = $true
$summary = New-Object System.Collections.Generic.List[object]

foreach ($fixture in $fixtures) {
  if (-not [System.IO.File]::Exists($fixture.Path)) { throw "Missing fixture: $($fixture.Path)" }

  $safeName = ($fixture.Name.ToLowerInvariant() -replace '[^a-z0-9]+', '-')
  $extractDir = Join-Path $workDir "$safeName-extract"
  $repacked = Join-Path $workDir $fixture.RepackedName
  $reoutDir = Join-Path $workDir "$safeName-reout"

  $infoJson = Invoke-BgsArchive -Arguments @('info', $fixture.Path, '--json')
  $listJson = Invoke-BgsArchive -Arguments @('list', $fixture.Path, '--json')
  $infoObj = $infoJson | ConvertFrom-Json
  $listObj = $listJson | ConvertFrom-Json
  $autoDetectOk = ($infoObj.ok -eq $true -and $infoObj.data.family -eq $fixture.ExpectedFamily -and [int]$infoObj.data.version -eq [int]$fixture.ExpectedVersion)

  Reset-Directory -Path $extractDir
  [void](Invoke-BgsArchive -Arguments @('extract', $fixture.Path, '--out', $extractDir))
  $structuralRows = @(Test-StructuralValidation -Entries @($listObj.data) -ExtractDir $extractDir)
  $structuralFailures = @($structuralRows | Where-Object { -not $_.Verdict })
  $structuralOk = ($structuralFailures.Count -eq 0)

  [void](Invoke-BgsArchive -Arguments @('pack', $extractDir, $repacked, '--game', $fixture.Game))
  Reset-Directory -Path $reoutDir
  [void](Invoke-BgsArchive -Arguments @('extract', $repacked, '--out', $reoutDir))
  $comparison = Compare-ArchiveTrees -LeftRoot $extractDir -RightRoot $reoutDir
  $roundTripFailures = @($comparison.Rows | Where-Object { -not $_.Match })
  $roundTripOk = ($roundTripFailures.Count -eq 0 -and $comparison.LeftOnly.Count -eq 0 -and $comparison.RightOnly.Count -eq 0)
  $fixturePass = ($autoDetectOk -and $structuralOk -and $roundTripOk)
  $overallPass = ($overallPass -and $fixturePass)

  $summary.Add([pscustomobject]@{
    Fixture = $fixture.Name
    Family = $infoObj.data.family
    Version = $infoObj.data.version
    Format = $infoObj.data.format
    Compression = $infoObj.data.compression
    EntryCount = $infoObj.data.entry_count
    StructuralFiles = $structuralRows.Count
    StructuralOk = $structuralOk
    RoundTripFiles = $comparison.Rows.Count
    RoundTripOk = $roundTripOk
    Verdict = if ($fixturePass) { 'PASS' } else { 'FAIL' }
  })

  [void]$md.AppendLine("## $($fixture.Name)")
  [void]$md.AppendLine()
  [void]$md.AppendLine("- Fixture: ``$($fixture.Path)``")
  [void]$md.AppendLine("- Expected auto-detect: family ``$($fixture.ExpectedFamily)``, version ``$($fixture.ExpectedVersion)``")
  [void]$md.AppendLine("- Auto-detect verdict: $(if ($autoDetectOk) { 'PASS' } else { 'FAIL' })")
  [void]$md.AppendLine()
  [void]$md.AppendLine('### `info --json`')
  [void]$md.AppendLine()
  Add-CodeBlock -Builder $md -Language 'json' -Body $infoJson
  [void]$md.AppendLine('### `list --json`')
  [void]$md.AppendLine()
  Add-CodeBlock -Builder $md -Language 'json' -Body $listJson

  [void]$md.AppendLine('### Structural validation')
  [void]$md.AppendLine()
  [void]$md.AppendLine('| file | ext | expected magic | actual magic | reported size | extracted size | size match | verdict |')
  [void]$md.AppendLine('|---|---|---|---|---:|---:|---|---|')
  foreach ($row in $structuralRows) {
    [void]$md.AppendLine("| ``$($row.File)`` | ``$($row.Ext)`` | ``$($row.ExpectedMagic)`` | ``$($row.ActualMagic)`` | $($row.ReportedSize) | $($row.ExtractedSize) | $(if ($row.SizeMatch) { 'yes' } else { 'no' }) | $(if ($row.Verdict) { 'PASS' } else { 'FAIL' }) |")
  }
  [void]$md.AppendLine()

  [void]$md.AppendLine('### Self-consistency round-trip SHA256')
  [void]$md.AppendLine()
  [void]$md.AppendLine("- Missing after round-trip: ``$($comparison.LeftOnly -join ', ')``")
  [void]$md.AppendLine("- Extra after round-trip: ``$($comparison.RightOnly -join ', ')``")
  [void]$md.AppendLine()
  [void]$md.AppendLine('| file | original sha256 | round-trip sha256 | match | first diff offset |')
  [void]$md.AppendLine('|---|---|---|---|---|')
  foreach ($row in $comparison.Rows) {
    [void]$md.AppendLine("| ``$($row.File)`` | ``$($row.OriginalSha256)`` | ``$($row.RoundTripSha256)`` | $(if ($row.Match) { 'yes' } else { 'no' }) | $($row.FirstDiffOffset) |")
  }
  [void]$md.AppendLine()
  [void]$md.AppendLine("### Fixture verdict: $(if ($fixturePass) { 'PASS' } else { 'FAIL' })")
  [void]$md.AppendLine()
}

[void]$md.AppendLine('## Summary')
[void]$md.AppendLine()
[void]$md.AppendLine('| fixture | family | version | format | compression | entries | structural files | structural ok | round-trip files | round-trip ok | verdict |')
[void]$md.AppendLine('|---|---|---:|---|---|---:|---:|---|---:|---|---|')
foreach ($row in $summary) {
  [void]$md.AppendLine("| $($row.Fixture) | $($row.Family) | $($row.Version) | $($row.Format) | $($row.Compression) | $($row.EntryCount) | $($row.StructuralFiles) | $($row.StructuralOk) | $($row.RoundTripFiles) | $($row.RoundTripOk) | $($row.Verdict) |")
}
[void]$md.AppendLine()
[void]$md.AppendLine("## Overall verdict: $(if ($overallPass) { 'PASS' } else { 'FAIL' })")

[System.IO.File]::WriteAllText($evidencePath, $md.ToString(), [System.Text.UTF8Encoding]::new($false))
Write-Output "A11 evidence written: $evidencePath"
Write-Output "Overall verdict: $(if ($overallPass) { 'PASS' } else { 'FAIL' })"
$summary | Format-Table -AutoSize | Out-String | Write-Output

if (-not $overallPass) {
  exit 1
}

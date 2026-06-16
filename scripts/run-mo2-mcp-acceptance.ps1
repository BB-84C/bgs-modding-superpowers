[CmdletBinding()]
param(
  [string]$Mo2Root = "B:\WastelandBlues 2.0",
  [string]$Profile = "BB84自用",
  [ValidateSet("all", "live", "closed")] [string]$Mode = "all"
)

function Ensure-HarnessMo2Alive {
  $harnessRoot = "D:\awesome-bgs-mod-master\.artifacts\mo2"
  $existing = Get-Process -Name "ModOrganizer*" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like "$harnessRoot\*" }
  if (-not $existing) {
    Write-Host "[acceptance] Starting harness MO2..."
    Start-Process -FilePath "$harnessRoot\ModOrganizer.exe" -WorkingDirectory $harnessRoot
    Start-Sleep -Seconds 25
  } else {
    Write-Host "[acceptance] Harness MO2 already alive (PID $($existing.Id -join ','))"
  }
}

function Stop-AllMo2 {
  $procs = Get-Process -Name "ModOrganizer*" -ErrorAction SilentlyContinue
  if ($procs) {
    Write-Host "[acceptance] Stopping MO2 processes (PID $($procs.Id -join ','))..."
    $procs | Stop-Process -Force
    Start-Sleep -Seconds 5
  } else {
    Write-Host "[acceptance] No MO2 processes to stop"
  }
}

$env:MO2_MCP_ACCEPTANCE = "1"
$env:BGS_MO2_ROOT = $Mo2Root
$env:BGS_MO2_PROFILE = $Profile

Push-Location "$PSScriptRoot\..\tools\mo2-mcp"
try {
  npm run build
  if ($LASTEXITCODE -ne 0) { throw "build failed" }

  $liveExit = 0
  $closedExit = 0

  if ($Mode -in @("all", "live")) {
    Write-Host ""
    Write-Host "=== Phase: LIVE suite ==="
    Ensure-HarnessMo2Alive
    npx vitest run tests/acceptance-live.test.ts
    $liveExit = $LASTEXITCODE
  }

  if ($Mode -in @("all", "closed")) {
    Write-Host ""
    Write-Host "=== Phase: CLOSED suite ==="
    Stop-AllMo2
    npx vitest run tests/acceptance-closed.test.ts
    $closedExit = $LASTEXITCODE
  }

  Write-Host ""
  Write-Host "=== Summary ==="
  if ($Mode -in @("all", "live")) { Write-Host "  Live   suite exit: $liveExit" }
  if ($Mode -in @("all", "closed")) { Write-Host "  Closed suite exit: $closedExit" }

  if ($liveExit -ne 0 -or $closedExit -ne 0) { exit 1 }
}
finally {
  Pop-Location
  Remove-Item env:MO2_MCP_ACCEPTANCE -ErrorAction SilentlyContinue
  Remove-Item env:BGS_MO2_ROOT -ErrorAction SilentlyContinue
  Remove-Item env:BGS_MO2_PROFILE -ErrorAction SilentlyContinue
}

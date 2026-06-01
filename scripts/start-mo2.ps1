<#
.SYNOPSIS
Starts MO2 with a visible GUI window so the user can see and interact with it.

.DESCRIPTION
The bgs-modding-superpowers agent harness assumes MO2 is running with the
Mo2AgentControl Python plugin loaded. This script launches MO2 the way a
human would: a normal window, taskbar entry, optional profile activation.

It does NOT start MO2 in any hidden / background mode. If a stale MO2 process
exists with no main window (the symptom of a botched background launch), the
script surfaces it and offers to terminate before launching a fresh one.

.PARAMETER MO2Root
Absolute path to the MO2 install root (contains ModOrganizer.exe). Required.

.PARAMETER Profile
MO2 profile to activate. Defaults to "Default".

.PARAMETER KillStale
Without prompting, terminate any existing MO2 process that has no visible
main window (zombie / background-launched MO2).

.PARAMETER WaitForWindowSeconds
How long to wait for the MO2 main window to appear before reporting back.
Defaults to 30. Set to 0 to skip the wait.

.EXAMPLE
.\scripts\start-mo2.ps1 -MO2Root "D:\ModOrganizer2"

.EXAMPLE
.\scripts\start-mo2.ps1 -MO2Root "D:\awesome-bgs-mod-master\.artifacts\mo2" -Profile "Default" -KillStale
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$MO2Root,
    [string]$Profile = "Default",
    [switch]$KillStale,
    [int]$WaitForWindowSeconds = 30
)

$ErrorActionPreference = "Stop"

# --- Validate -------------------------------------------------------------

$resolvedRoot = (Resolve-Path -Path $MO2Root -ErrorAction Stop).Path
$mo2Exe = Join-Path $resolvedRoot "ModOrganizer.exe"
if (-not (Test-Path $mo2Exe -PathType Leaf)) {
    throw "MO2 root does not contain ModOrganizer.exe: $resolvedRoot"
}

$profilesDir = Join-Path $resolvedRoot ("profiles\" + $Profile)
if (-not (Test-Path $profilesDir -PathType Container)) {
    throw "MO2 profile '$Profile' not found at $profilesDir. Use -Profile <name> to specify another, or initialize the profile in MO2 first."
}

# --- Detect existing MO2 processes ----------------------------------------

$existingProcs = @(Get-Process -Name "ModOrganizer" -ErrorAction SilentlyContinue)
$visibleProcs = @($existingProcs | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero })
$zombieProcs = @($existingProcs | Where-Object { $_.MainWindowHandle -eq [IntPtr]::Zero })

Write-Host ""
Write-Host "bgs-modding-superpowers: start MO2"
Write-Host "  MO2 root:  $resolvedRoot"
Write-Host "  Profile:   $Profile"
Write-Host ""

if ($visibleProcs.Count -gt 0) {
    Write-Host "[INFO] A visible MO2 is already running:" -ForegroundColor Yellow
    foreach ($p in $visibleProcs) {
        Write-Host ("       PID {0}  Window: '{1}'  Started: {2}" -f $p.Id, $p.MainWindowTitle, $p.StartTime)
    }
    Write-Host "Not launching a new one. Bring it to the foreground or exit it first if you need a fresh start."
    return
}

if ($zombieProcs.Count -gt 0) {
    Write-Host "[WARN] Found $($zombieProcs.Count) zombie MO2 process(es) (running but no GUI window):" -ForegroundColor Yellow
    foreach ($p in $zombieProcs) {
        Write-Host ("       PID {0}  Started: {1}" -f $p.Id, $p.StartTime)
    }
    Write-Host "These are usually from a previous botched background launch and must be terminated before"
    Write-Host "a new MO2 can start cleanly (only one MO2 per instance)."
    Write-Host ""
    if ($KillStale) {
        foreach ($p in $zombieProcs) {
            Write-Host ("  Killing zombie PID {0}..." -f $p.Id)
            Stop-Process -Id $p.Id -Force
        }
        Start-Sleep -Seconds 1
    } else {
        $reply = Read-Host "Kill the zombie process(es) and continue? [y/N]"
        if ($reply -notmatch '^[yY]') {
            Write-Host "Aborted. Re-run with -KillStale to skip the prompt." -ForegroundColor Red
            return
        }
        foreach ($p in $zombieProcs) {
            Write-Host ("  Killing zombie PID {0}..." -f $p.Id)
            Stop-Process -Id $p.Id -Force
        }
        Start-Sleep -Seconds 1
    }
}

# --- Launch MO2 visibly ---------------------------------------------------

# MO2 accepts -p <profile> to activate a profile on launch. Use Start-Process
# with -WindowStyle Normal so the GUI is visible AND the launcher process is
# fully detached (we do not block waiting for MO2 to exit).
$arguments = @("-p", $Profile)

Write-Host ""
Write-Host "Launching MO2 (visible GUI)..."
Write-Host "  Command: `"$mo2Exe`" $($arguments -join ' ')"
$proc = Start-Process -FilePath $mo2Exe -ArgumentList $arguments -WindowStyle Normal -PassThru
Write-Host ("  Started PID: {0}" -f $proc.Id)

# --- Wait for main window to appear ---------------------------------------

if ($WaitForWindowSeconds -gt 0) {
    Write-Host "Waiting up to ${WaitForWindowSeconds}s for the MO2 main window..."
    $deadline = (Get-Date).AddSeconds($WaitForWindowSeconds)
    $windowSeen = $false
    while ((Get-Date) -lt $deadline) {
        $live = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
        if (-not $live) {
            Write-Host "[ERROR] MO2 process exited unexpectedly before showing a window." -ForegroundColor Red
            return
        }
        $live.Refresh()
        if ($live.MainWindowHandle -ne [IntPtr]::Zero) {
            $windowSeen = $true
            Write-Host ("  Window appeared after {0:F1}s: '{1}'" -f (((Get-Date) - $live.StartTime).TotalSeconds), $live.MainWindowTitle)
            break
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $windowSeen) {
        Write-Host "[WARN] MO2 process is running (PID $($proc.Id)) but no window appeared within ${WaitForWindowSeconds}s." -ForegroundColor Yellow
        Write-Host "       Check the taskbar / system tray, or use Task Manager to confirm state."
    }
}

Write-Host ""
Write-Host "[OK] MO2 launched. Bootstrap runtime files will appear at:" -ForegroundColor Green
Write-Host ("     {0}\plugins\Mo2AgentControl\bootstrap\runtime\" -f $resolvedRoot)
Write-Host "Once status.json reports state='ok' there, the agent's xEdit MCP can drive xEdit."

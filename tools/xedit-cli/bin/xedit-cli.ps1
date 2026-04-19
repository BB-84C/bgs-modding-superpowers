$ErrorActionPreference = "Stop"

$toolRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\")).Path

. (Join-Path $toolRoot "lib/common.ps1")
. (Join-Path $toolRoot "lib/doctor-env.ps1")
. (Join-Path $toolRoot "lib/hook-session.ps1")
. (Join-Path $toolRoot "lib/mo2-launch.ps1")
. (Join-Path $toolRoot "lib/process.ps1")
. (Join-Path $toolRoot "lib/session-plugins.ps1")
. (Join-Path $toolRoot "lib/sqlite-store.ps1")
. (Join-Path $toolRoot "lib/conflicts-index.ps1")
. (Join-Path $toolRoot "lib/conflicts-inspect.ps1")

try {
    if ($args.Count -lt 2) {
        Write-Host "Usage: xedit-cli.ps1 <group> <command> [options]"
        exit 1
    }

    $group = $args[0]
    $command = $args[1]
    $remaining = @()
    if ($args.Count -gt 2) {
        $remaining = $args[2..($args.Count - 1)]
    }

    switch ("$group $command") {
        "doctor env" {
            exit (Invoke-XeditCliDoctorEnv -Arguments $remaining)
        }
        "process launch" {
            exit (Invoke-XeditCliProcessLaunch -Arguments $remaining)
        }
        "process status" {
            exit (Invoke-XeditCliProcessStatus -Arguments $remaining)
        }
        "process wait" {
            exit (Invoke-XeditCliProcessWait -Arguments $remaining)
        }
        "process stop" {
            exit (Invoke-XeditCliProcessStop -Arguments $remaining)
        }
        "conflicts index" {
            exit (Invoke-XeditCliConflictsIndex -Arguments $remaining)
        }
        "conflicts inspect" {
            exit (Invoke-XeditCliConflictsInspect -Arguments $remaining)
        }
        default {
            Write-Host "Unknown command: $group $command"
            exit 1
        }
    }
}
catch {
    Write-Host $_.Exception.Message
    exit 1
}

$ErrorActionPreference = "Stop"

$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

. (Join-Path $toolRoot 'lib/xedit-client.common.ps1')
. (Join-Path $toolRoot 'lib/xedit-client.session.ps1')
. (Join-Path $toolRoot 'lib/xedit-client.launch.ps1')
. (Join-Path $toolRoot 'lib/xedit-client.call.ps1')

if ($args.Count -lt 2) {
    Write-Host 'Usage: xedit-client.ps1 <group> <command> [options]'
    exit 1
}

$group = $args[0]
$command = $args[1]
$remaining = @()
if ($args.Count -gt 2) {
    $remaining = @($args[2..($args.Count - 1)])
}

switch ("$group $command") {
    'process launch' { exit (Invoke-XeditClientProcessLaunch -Arguments $remaining) }
    'process status' { exit (Invoke-XeditClientProcessStatus -Arguments $remaining) }
    'process wait' { exit (Invoke-XeditClientProcessWait -Arguments $remaining) }
    'process stop' { exit (Invoke-XeditClientProcessStop -Arguments $remaining) }
    'automation call' { exit (Invoke-XeditClientAutomationCallCommand -Arguments $remaining) }
    default {
        Write-Host "Unknown command: $group $command"
        exit 1
    }
}

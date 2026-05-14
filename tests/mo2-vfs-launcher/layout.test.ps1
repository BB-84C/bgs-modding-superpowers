$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

foreach ($path in @(
    'tools/mo2-vfs-launcher/xedit-client.ps1',
    'tools/mo2-vfs-launcher/xedit-client.md',
    'tools/mo2-vfs-launcher/lib/xedit-client.common.ps1',
    'tools/mo2-vfs-launcher/lib/xedit-client.session.ps1',
    'tools/mo2-vfs-launcher/lib/xedit-client.launch.ps1',
    'tools/mo2-vfs-launcher/lib/xedit-client.call.ps1'
)) {
    if (-not (Test-Path (Join-Path $repoRoot $path))) { throw "Missing expected xedit outer-client path: $path" }
}

foreach ($path in @('tools/xedit-cli', 'tools/xedit-hook-bridge', 'tests/xedit-cli')) {
    if (Test-Path (Join-Path $repoRoot $path)) { throw "Legacy path should be removed: $path" }
}

Write-Host 'mo2-vfs-launcher layout checks passed.'

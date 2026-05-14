$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path

$requiredPaths = @(
    "tools/README.md",
    "tools/mo2-vfs-launcher/mo2-vfs-launcher.ps1",
    "tools/mo2-vfs-launcher/mo2-vfs-launcher.cmd",
    "tools/mo2-vfs-launcher/README.md",
    "tools/mo2-vfs-launcher/xedit-client.ps1",
    "tools/mo2-vfs-launcher/xedit-client.md",
    "tools/mo2-control-plane/README.md",
    "tools/mo2-control-plane/live-integration.md",
    "tools/mo2-control-plane/live-bridge/README.md",
    "tools/mo2-control-plane/broker/README.md",
    "tools/mo2-control-plane/plugin/README.md",
    "tests/mo2-control-plane/live-sandbox.ps1",
    "docs/plans/2026-04-16-mo2-agent-control-plane-design.md"
)

$missing = $requiredPaths | Where-Object { -not (Test-Path (Join-Path $repoRoot $_)) }
if ($missing.Count -gt 0) {
    throw "Missing spec files: $($missing -join ', ')"
}

function Assert-ContainsAll {
    param(
        [string]$Content,
        [string]$Label,
        [string[]]$Phrases
    )

    foreach ($phrase in $Phrases) {
        if ($Content -notmatch [regex]::Escape($phrase)) {
            throw "$Label is missing phrase: $phrase"
        }
    }
}

function Assert-ContainsNone {
    param(
        [string]$Content,
        [string]$Label,
        [string[]]$Phrases
    )

    foreach ($phrase in $Phrases) {
        if ($Content -match [regex]::Escape($phrase)) {
            throw "$Label should not contain phrase: $phrase"
        }
    }
}

$xeditClientDoc = Get-Content (Join-Path $repoRoot "tools/mo2-vfs-launcher/xedit-client.md") -Raw
Assert-ContainsAll -Content $xeditClientDoc -Label 'tools/mo2-vfs-launcher/xedit-client.md' -Phrases @(
    'xedit-client.ps1',
    'MO2-facing outer client for native xEdit automation',
    'It does not own records, conflicts, jobs, scripts, or patch semantics.',
    'native xEdit in `D:\TES5Edit-contrib`',
    'session-scoped `plugins.txt` generation',
    'game-mode and launcher normalization',
    'MO2/control-plane launch',
    'native serve readiness detection',
    'native automation-call request/response artifact handling',
    'PID lifecycle'
)

$mo2LauncherReadme = Get-Content (Join-Path $repoRoot "tools/mo2-vfs-launcher/README.md") -Raw
Assert-ContainsAll -Content $mo2LauncherReadme -Label 'tools/mo2-vfs-launcher/README.md' -Phrases @(
    'target path',
    '--target-path',
    'environment injection',
    '--env',
    'state file',
    '--state-file',
    'wait mode',
    '--wait-mode',
    'failure behavior',
    'writes a failed state',
    'MO2 `run -e OpenCodeVfsLauncher`',
    '## xEdit outer client',
    'xedit-client.ps1',
    'MO2-facing client for native xEdit automation',
    'generic launcher remains tool-agnostic',
    'neighboring outer-client layer'
)

$toolsReadme = Get-Content (Join-Path $repoRoot "tools/README.md") -Raw
Assert-ContainsAll -Content $toolsReadme -Label 'tools/README.md' -Phrases @(
    'MO2 control plane',
    'broker CLI',
    'plugin kernel',
    'generic VFS launcher',
    'xEdit outer client layer'
)

$controlPlaneReadme = Get-Content (Join-Path $repoRoot "tools/mo2-control-plane/README.md") -Raw
Assert-ContainsAll -Content $controlPlaneReadme -Label 'tools/mo2-control-plane/README.md' -Phrases @(
    'control plane',
    'broker CLI',
    'plugin kernel'
)

$brokerReadme = Get-Content (Join-Path $repoRoot "tools/mo2-control-plane/broker/README.md") -Raw
Assert-ContainsAll -Content $brokerReadme -Label 'tools/mo2-control-plane/broker/README.md' -Phrases @(
    'broker CLI',
    'capability discovery',
    'session/artifact'
)

$pluginReadme = Get-Content (Join-Path $repoRoot "tools/mo2-control-plane/plugin/README.md") -Raw
Assert-ContainsAll -Content $pluginReadme -Label 'tools/mo2-control-plane/plugin/README.md' -Phrases @(
    'plugin kernel',
    'capability discovery',
    'safe-read'
)

$controlPlaneLiveIntegration = Get-Content (Join-Path $repoRoot "tools/mo2-control-plane/live-integration.md") -Raw
Assert-ContainsAll -Content $controlPlaneLiveIntegration -Label 'tools/mo2-control-plane/live-integration.md' -Phrases @(
    '.artifacts/mo2/',
    '.external-resource/Mod.Organizer-2.5.3dev7.exe',
    'endpoint',
    'usvfs',
    'instance-specific',
    'mutex',
    'pwsh -NoProfile -File tools/mo2-vfs-launcher/xedit-client.ps1 process launch --launcher-path <xedit.exe> --game-mode Fallout4 --mo-profile Default'
)
Assert-ContainsNone -Content $controlPlaneLiveIntegration -Label 'tools/mo2-control-plane/live-integration.md' -Phrases @(
    'tools/xedit-cli/bin/xedit-cli.ps1 process launch'
)

$liveBridgeReadme = Get-Content (Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/README.md") -Raw
Assert-ContainsAll -Content $liveBridgeReadme -Label 'tools/mo2-control-plane/live-bridge/README.md' -Phrases @(
    'live bridge',
    '.artifacts/mo2/plugins/',
    '.artifacts/mo2/plugins/mo2_agent_control.py',
    'Mo2AgentControl/bootstrap/runtime',
    'scaffold-only',
    'instance-specific',
    'named-pipe server'
)

$controlPlaneDesign = Get-Content (Join-Path $repoRoot "docs/plans/2026-04-16-mo2-agent-control-plane-design.md") -Raw
Assert-ContainsAll -Content $controlPlaneDesign -Label 'MO2 control-plane design' -Phrases @(
    'control plane',
    'plugin kernel',
    'broker CLI',
    'capability discovery',
    'session/artifact'
)

Write-Host "Spec bootstrap checks passed."

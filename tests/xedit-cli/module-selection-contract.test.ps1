$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$hookMainPath = Join-Path $repoRoot "tools/xedit-hook-bridge/src/HookMain.pas"
$hookStatusPath = Join-Path $repoRoot "tools/xedit-hook-bridge/src/HookStatus.pas"
$hookSessionPath = Join-Path $repoRoot "tools/xedit-hook-bridge/src/HookSession.pas"

function Assert-Equal {
    param(
        $Actual,
        $Expected,
        [string]$Message
    )

    if ($Actual -ne $Expected) {
        throw "$Message`nExpected: $Expected`nActual: $Actual"
    }
}

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-NotMatch {
    param(
        [string]$Value,
        [string]$Pattern,
        [string]$Message
    )

    if ($Value -match $Pattern) {
        throw "$Message`nUnexpected pattern: $Pattern"
    }
}

function New-TempSessionPath {
    $sessionRoot = Join-Path $env:TEMP ("xedit-hook-contract-" + [guid]::NewGuid().ToString("N"))
    $null = New-Item -ItemType Directory -Path $sessionRoot -Force
    return $sessionRoot
}

function Read-StatusMap {
    param(
        [string]$SessionPath
    )

    $statusPath = Join-Path $SessionPath 'hook-status.txt'
    $map = @{}
    foreach ($line in Get-Content -Path $statusPath) {
        if ($line -match '^(?<key>[^=]+)=(?<value>.*)$') {
            $map[$matches.key] = $matches.value
        }
    }

    return $map
}

$hookMainSource = Get-Content -Path $hookMainPath -Raw
$hookStatusSource = Get-Content -Path $hookStatusPath -Raw
$hookSessionSource = Get-Content -Path $hookSessionPath -Raw

Assert-NotMatch -Value $hookMainSource -Pattern 'TryAdoptModelLayerResult' -Message 'HookMain should not keep model-layer result adoption after the load-only rollback'
Assert-NotMatch -Value $hookMainSource -Pattern 'selection_method\s*=\s*''model-layer''' -Message 'HookMain should not restore selection_method=model-layer after the load-only rollback'
Assert-NotMatch -Value $hookMainSource -Pattern 'GForcedDependencies' -Message 'HookMain should not track forced dependency status after the load-only rollback'
Assert-NotMatch -Value $hookMainSource -Pattern 'GBlockedExclusions' -Message 'HookMain should not track blocked exclusion status after the load-only rollback'
Assert-NotMatch -Value $hookMainSource -Pattern 'UsesSubsetLoadMode|ApplySubsetPolicyAndCapture|ParseRequestedPlugins|BuildForcedDependencies|BuildBlockedExclusions|ApplyOnlyPolicy|ApplyExcludePolicy' -Message 'HookMain should keep only load-only Module Selection automation helpers'
Assert-True -Condition ($hookMainSource -match 'function\s+TryReadSessionSelectedModules') -Message 'HookMain should expose a session plugins.txt fallback reader for selected_modules evidence'
Assert-True -Condition ($hookMainSource -match 'plugins\.txt') -Message 'HookMain should read selected_modules fallback evidence from the session plugins.txt path'
Assert-True -Condition ($hookMainSource -match 'TryCaptureSelectedModulesOrFallback') -Message 'HookMain should wrap tree capture with a fallback evidence path instead of relying on the real VCL tree only'
Assert-NotMatch -Value $hookMainSource -Pattern 'CompleteModuleSelection\(''failed'',\s*CaptureDetail,\s*True,\s*False\)' -Message 'HookMain should not fail immediately on module-tree capture detail before attempting confirmation'

Assert-NotMatch -Value $hookStatusSource -Pattern 'ShouldPreserveModelLayerStatus' -Message 'HookStatus should not preserve stale model-layer status after the load-only rollback'
Assert-NotMatch -Value $hookStatusSource -Pattern 'load_mode=' -Message 'HookStatus should not emit load_mode after the load-only rollback'
Assert-NotMatch -Value $hookStatusSource -Pattern 'plugins=' -Message 'HookStatus should not emit plugins after the load-only rollback'
Assert-NotMatch -Value $hookStatusSource -Pattern 'selection_method=' -Message 'HookStatus should not emit selection_method after the load-only rollback'
Assert-NotMatch -Value $hookStatusSource -Pattern 'forced_dependencies=' -Message 'HookStatus should not emit forced_dependencies after the load-only rollback'
Assert-NotMatch -Value $hookStatusSource -Pattern 'blocked_exclusions=' -Message 'HookStatus should not emit blocked_exclusions after the load-only rollback'
Assert-NotMatch -Value $hookSessionSource -Pattern 'XEDIT_CLI_HOOK_LOAD_MODE|XEDIT_CLI_HOOK_PLUGINS' -Message 'HookSession should not read retired subset-era environment variables after the load-only rollback'
Assert-NotMatch -Value $hookSessionSource -Pattern 'IsAllLoadMode|IsOnlyLoadMode|IsExcludeLoadMode|UsesSubsetLoadMode' -Message 'HookSession should not retain retired subset-era mode helpers after the load-only rollback'

$sessionPath = New-TempSessionPath

try {
    Set-Content -Path (Join-Path $sessionPath 'hook-status.txt') -Value @'
status=module-selection-confirmed
selection_detected=true
selection_confirmed=true
selected_modules=Fallout4.esm|DLCRobot.esm|ExamplePatch.esp
detail=Detected Module Selection and confirmed the current selection.
heartbeat=worker-loop-3
checkpoint=final-selected-modules
'@

    $hookStatus = Read-StatusMap -SessionPath $sessionPath
    Assert-Equal -Actual $hookStatus['selection_detected'] -Expected 'true' -Message 'hook-session parsing should preserve dialog detection'
    Assert-Equal -Actual $hookStatus['selection_confirmed'] -Expected 'true' -Message 'hook-session parsing should preserve confirmation'
    Assert-Equal -Actual $hookStatus['selected_modules'] -Expected 'Fallout4.esm|DLCRobot.esm|ExamplePatch.esp' -Message 'hook-session parsing should preserve final selected module evidence'
    Assert-Equal -Actual $hookStatus['detail'] -Expected 'Detected Module Selection and confirmed the current selection.' -Message 'hook-session parsing should preserve checkpoint detail'
    Assert-Equal -Actual $hookStatus['heartbeat'] -Expected 'worker-loop-3' -Message 'hook-session parsing should preserve heartbeat detail lines'
    Assert-Equal -Actual $hookStatus['checkpoint'] -Expected 'final-selected-modules' -Message 'hook-session parsing should preserve checkpoint detail lines'
    Assert-True -Condition ([string]::IsNullOrWhiteSpace($hookStatus['load_mode'])) -Message 'hook-session parsing should observe that load_mode is absent'
    Assert-True -Condition ([string]::IsNullOrWhiteSpace($hookStatus['plugins'])) -Message 'hook-session parsing should observe that plugins is absent'
    Assert-True -Condition ([string]::IsNullOrWhiteSpace($hookStatus['selection_method'])) -Message 'hook-session parsing should observe that selection_method is absent'
    Assert-True -Condition ([string]::IsNullOrWhiteSpace($hookStatus['forced_dependencies'])) -Message 'hook-session parsing should observe that forced_dependencies is absent'
    Assert-True -Condition ([string]::IsNullOrWhiteSpace($hookStatus['blocked_exclusions'])) -Message 'hook-session parsing should observe that blocked_exclusions is absent'
}
finally {
    if (Test-Path $sessionPath) {
        Remove-Item -Path $sessionPath -Recurse -Force
    }
}

exit 0

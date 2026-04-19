$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\.." )).Path
$hookMainPath = Join-Path $repoRoot "tools/xedit-hook-bridge/src/HookMain.pas"

if (-not (Test-Path $hookMainPath -PathType Leaf)) {
    throw "Missing HookMain.pas at $hookMainPath"
}

$source = [System.IO.File]::ReadAllText($hookMainPath)

foreach ($requiredSnippet in @(
    "'SysTreeView32'",
    "FindComponent('vstModules')",
    "TfrmModuleSelect",
    "form not found",
    "vstModules not found",
    "unsupported access path",
    "root_hwnd=",
    "root_class=",
    "child_count=",
    "child[",
    "find_control=",
    "virtual_tree_child_find_control_success=",
    "virtual_tree_top_level_sample_count=",
    "virtual_tree_top_level_sample[",
    "get_parent_form=",
    "screen_form_count="
)) {
    if (-not $source.Contains($requiredSnippet)) {
        throw "HookMain.pas should preserve the native TreeView fallback and add the VCL vstModules discovery path: missing '$requiredSnippet'"
    }
}

Write-Host "hook-vcl-discovery-contract.test.ps1 passed"

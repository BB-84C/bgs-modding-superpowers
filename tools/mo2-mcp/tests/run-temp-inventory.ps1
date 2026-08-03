$ErrorActionPreference = "Stop"

$packageRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$repoRoot = (Resolve-Path (Join-Path $packageRoot "..\..")).Path
. (Join-Path $repoRoot "tests\helpers\tracked-temp.ps1")

$tempRoot = New-TrackedTestTempDirectory -Prefix "mo2-mcp-suite-inventory-"
$previousTemp = $env:TEMP
$previousTmp = $env:TMP
$previousNodeCompileCache = $env:NODE_COMPILE_CACHE

try {
    $beforeCount = @(Get-ChildItem -LiteralPath $tempRoot -Force).Count
    $env:TEMP = $tempRoot
    $env:TMP = $tempRoot
    $nodeCompileCache = Join-Path $tempRoot "node-compile-cache"
    $env:NODE_COMPILE_CACHE = $nodeCompileCache

    $output = & npm.cmd test 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "mo2-mcp test suite failed while measuring tracked temp residue:`n$($output -join "`n")"
    }

    if (Test-Path $nodeCompileCache -PathType Container) {
        Remove-Item -LiteralPath $nodeCompileCache -Recurse -Force -ErrorAction Stop
    }

    $afterEntries = @(Get-ChildItem -LiteralPath $tempRoot -Force)
    $afterCount = $afterEntries.Count
    if ($afterCount -ne 0) {
        throw "mo2-mcp test suite left $afterCount entry(s) in its isolated temp root: $($afterEntries.FullName -join ', ')"
    }

    [pscustomobject]@{
        suite = "tools/mo2-mcp npm test"
        temp_root = $tempRoot
        before_count = $beforeCount
        after_count = $afterCount
        mapped_prefix_residue = 0
    } | ConvertTo-Json -Compress
}
finally {
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp
    $env:NODE_COMPILE_CACHE = $previousNodeCompileCache
    Remove-TrackedTestTempDirectories
}

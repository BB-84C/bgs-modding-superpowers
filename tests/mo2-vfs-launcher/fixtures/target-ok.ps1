param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$TargetArguments
)

if ($env:MO2_VFS_TEST_EMIT_STREAMS -eq "1") {
    Write-Output "target-ok stdout"
    Write-Error "target-ok stderr"
}

$resultPath = $env:MO2_VFS_TEST_RESULT_PATH
if (-not [string]::IsNullOrWhiteSpace($resultPath)) {
    $payload = [ordered]@{
        args = @($TargetArguments)
        env  = [ordered]@{
            ALPHA = $env:ALPHA
            BRAVO = $env:BRAVO
        }
    }

    $payload | ConvertTo-Json -Depth 4 -Compress | Set-Content -Path $resultPath
}

exit 0

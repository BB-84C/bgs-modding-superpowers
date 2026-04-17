if ($env:MO2_VFS_TEST_EMIT_STREAMS -eq "1") {
    Write-Output "target-sleep stdout"
    Write-Error "target-sleep stderr"
}
Start-Sleep -Seconds 10
exit 0

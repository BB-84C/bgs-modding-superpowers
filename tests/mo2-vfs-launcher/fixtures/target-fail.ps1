if ($env:MO2_VFS_TEST_EMIT_STREAMS -eq "1") {
    Write-Output "target-fail stdout"
    Write-Error "target-fail stderr"
}
exit 7

$pipes = [System.IO.Directory]::GetFiles('\\.\pipe\')
$found = $pipes | Where-Object { $_ -match 'xEdit|automation|SSEEdit|14556' }
if ($found) {
    Write-Host "FOUND: $found"
} else {
    Write-Host "Not found in $($pipes.Count) pipes. Checking by PID..."
    # Maybe the pipe name uses a different format
    $pipes | ForEach-Object { Write-Host $_ }
}

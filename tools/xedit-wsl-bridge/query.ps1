param($command, $argsJson)

$xePid = (Get-Process -Name 'xEdit64').Id
$pipeName = "xedit-$xePid"
Write-Host "Pipe: $pipeName"

$pipe = New-Object System.IO.Pipes.NamedPipeClientStream(".", $pipeName, "InOut")
$pipe.Connect(5000)

$payload = @{ command = $command; args = ($argsJson | ConvertFrom-Json) } | ConvertTo-Json -Compress -Depth 5
Write-Host "SEND: $payload"

$bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
$pipe.Write($bytes, 0, $bytes.Length)
$pipe.Flush()
$pipe.WaitForPipeDrain()

$reader = New-Object System.IO.StreamReader($pipe, [System.Text.Encoding]::UTF8)
$resp = $reader.ReadToEnd()
$reader.Close()
$pipe.Close()

Write-Host "RESP: $resp"

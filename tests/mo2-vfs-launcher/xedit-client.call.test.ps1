$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$commonLibPath = Join-Path $repoRoot "tools/mo2-vfs-launcher/lib/xedit-client.common.ps1"
$callLibPath = Join-Path $repoRoot "tools/mo2-vfs-launcher/lib/xedit-client.call.ps1"

. $commonLibPath
. $callLibPath

function Assert-Equal {
    param($Actual, $Expected, [string]$Message)
    if ($Actual -ne $Expected) {
        throw "$Message`nExpected: $Expected`nActual: $Actual"
    }
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

$tempRoot = Join-Path $env:TEMP ('xedit-client-call-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $tempRoot -Force

try {
    $requestPath = Join-Path $tempRoot 'system-describe.request.json'
    $responsePath = Join-Path $tempRoot 'system-describe.response.json'
    Set-Content -Path $requestPath -Value '{"command":"system.describe","args":{}}'

    $script:CapturedStartInfo = $null
    function Start-Process {
        param(
            [string]$FilePath,
            [string[]]$ArgumentList,
            [switch]$PassThru,
            [System.Diagnostics.ProcessWindowStyle]$WindowStyle
        )

        $script:CapturedStartInfo = $PSBoundParameters
        Set-Content -Path $responsePath -Value '{"ok":true,"result":{"name":"xEdit"}}'
        $process = [pscustomobject]@{ Id = 1234 }
        $process | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value { param([int]$Milliseconds) return $true }
        return $process
    }

    $response = Invoke-XeditClientAutomationCall -XeditExecutablePath 'D:\xedit\xEdit.exe' -XeditPid 54321 -RequestPath $requestPath -ResponsePath $responsePath -TimeoutSeconds 10

    Assert-Equal -Actual $script:CapturedStartInfo.FilePath -Expected 'D:\xedit\xEdit.exe' -Message 'call mode should launch the xEdit executable directly'
    Assert-Equal -Actual $script:CapturedStartInfo.ArgumentList[0] -Expected '-automation-call-pid:54321' -Message 'call mode should target the live daemon PID'
    Assert-Equal -Actual $script:CapturedStartInfo.ArgumentList[1] -Expected ('-automation-call-request:' + $requestPath) -Message 'call mode should forward the request file path'
    Assert-Equal -Actual $script:CapturedStartInfo.ArgumentList[2] -Expected ('-automation-call-response:' + $responsePath) -Message 'call mode should forward the response file path'
    Assert-True -Condition ($response.ok -eq $true) -Message 'call mode should parse the JSON response file'
    Assert-True -Condition ($response.ContainsKey('result')) -Message 'call mode should preserve the response result payload'
}
finally {
    if (Test-Path $tempRoot) { Remove-Item -Path $tempRoot -Recurse -Force -ErrorAction SilentlyContinue }
}

Write-Host 'xedit-client automation call checks passed.'
exit 0

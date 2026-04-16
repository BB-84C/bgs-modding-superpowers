function Get-XeditCliHookEnvironmentVariables {
    param(
        [pscustomobject]$SelectionPolicy,
        [string]$SessionId,
        [string]$SessionPath
    )

    $environmentVariables = @{
        XEDIT_CLI_HOOK_SESSION_ID = $SessionId
        XEDIT_CLI_HOOK_SESSION_PATH = $SessionPath
        XEDIT_CLI_HOOK_LOAD_MODE = $SelectionPolicy.LoadMode
    }

    if ($SelectionPolicy.LoadMode -ne 'all' -and $SelectionPolicy.Plugins.Count -gt 0) {
        $environmentVariables.XEDIT_CLI_HOOK_PLUGINS = ($SelectionPolicy.Plugins -join '|')
    }

    return $environmentVariables
}

function New-XeditCliHookSession {
    param(
        [pscustomobject]$SelectionPolicy
    )

    $sessionId = [guid]::NewGuid().ToString("N")
    $sessionPath = Join-Path (Join-Path $env:TEMP "xedit-cli-hook-sessions") $sessionId
    $null = New-Item -ItemType Directory -Path $sessionPath -Force

    return [pscustomobject]@{
        SessionId = $sessionId
        SessionPath = $sessionPath
        EnvironmentVariables = (Get-XeditCliHookEnvironmentVariables -SelectionPolicy $SelectionPolicy -SessionId $sessionId -SessionPath $sessionPath)
    }
}

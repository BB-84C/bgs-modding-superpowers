function Get-XeditCliHookEnvironmentVariables {
    param(
        [string]$SessionId,
        [string]$SessionPath
    )

    return @{
        XEDIT_CLI_HOOK_SESSION_ID = $SessionId
        XEDIT_CLI_HOOK_SESSION_PATH = $SessionPath
    }
}

function New-XeditCliHookSession {
    param(
        [string[]]$PluginLines
    )

    $sessionId = [guid]::NewGuid().ToString("N")
    $sessionPath = Join-Path (Join-Path $env:TEMP "xedit-cli-hook-sessions") $sessionId
    $sessionPlugins = New-XeditCliSessionPluginsFile -SessionPath $sessionPath -PluginLines $PluginLines

    return [pscustomobject]@{
        SessionId = $sessionId
        SessionPath = $sessionPlugins.SessionPath
        SessionPluginsFilePath = $sessionPlugins.PluginsFilePath
        PluginLines = $sessionPlugins.PluginLines
        EnvironmentVariables = (Get-XeditCliHookEnvironmentVariables -SessionId $sessionId -SessionPath $sessionPlugins.SessionPath)
    }
}

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$sessionPluginsLibPath = Join-Path $repoRoot "tools/xedit-cli/lib/session-plugins.ps1"

. $sessionPluginsLibPath

function Assert-Equal {
    param(
        $Actual,
        $Expected,
        [string]$Message
    )

    if ($Actual -is [System.Array] -or $Expected -is [System.Array]) {
        $actualText = [string]::Join("`n", @($Actual))
        $expectedText = [string]::Join("`n", @($Expected))
        if ($actualText -ne $expectedText) {
            throw "$Message`nExpected: $expectedText`nActual: $actualText"
        }

        return
    }

    if ($Actual -ne $Expected) {
        throw "$Message`nExpected: $Expected`nActual: $Actual"
    }
}

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-Throws {
    param(
        [scriptblock]$Action,
        [string]$ExpectedMessage,
        [string]$Message
    )

    try {
        & $Action
    }
    catch {
        if ($_.Exception.Message -ne $ExpectedMessage) {
            throw "$Message`nExpected error: $ExpectedMessage`nActual error: $($_.Exception.Message)"
        }

        return
    }

    throw "$Message`nExpected error: $ExpectedMessage`nActual error: <no error>"
}

function New-TestPluginsFile {
    param(
        [string[]]$Lines
    )

    $tempRoot = Join-Path $env:TEMP ("xedit-cli-session-plugins-test-" + [guid]::NewGuid().ToString("N"))
    $null = New-Item -ItemType Directory -Path $tempRoot -Force
    $pluginsFilePath = Join-Path $tempRoot "plugins.txt"
    Set-Content -Path $pluginsFilePath -Value $Lines
    return $pluginsFilePath
}

$pathsToRemove = @()

try {
    $pluginsFilePath = New-TestPluginsFile -Lines @(
        "  *ArmorKeywords.esm  ",
        "",
        "# comment",
        "*RaiderOverhaul.esp",
        "*RaiderOverhaul.esp"
    )
    $pathsToRemove += Split-Path -Path $pluginsFilePath -Parent

    $normalizedPlugins = Resolve-XeditCliPluginLines -PluginFilePath $pluginsFilePath

    Assert-Equal -Actual $normalizedPlugins -Expected @(
        "*ArmorKeywords.esm",
        "*RaiderOverhaul.esp"
    ) -Message "caller-provided plugins files should normalize whitespace, ignore blank lines, and deduplicate repeated plugins"

    $profilePluginsFilePath = New-TestPluginsFile -Lines @(
        "*Fallout4.esm",
        "*DLCRobot.esm",
        "*DLCRobot.esm"
    )
    $pathsToRemove += Split-Path -Path $profilePluginsFilePath -Parent

    $resolvedPluginSource = Resolve-XeditCliPluginSource -ProfilePluginFilePath $profilePluginsFilePath

    Assert-Equal -Actual $resolvedPluginSource.SourcePluginFilePath -Expected $profilePluginsFilePath -Message "session plugin resolution should fall back to the profile plugins file when no caller file is provided"
    Assert-Equal -Actual $resolvedPluginSource.PluginLines -Expected @(
        "*Fallout4.esm",
        "*DLCRobot.esm"
    ) -Message "session plugin resolution should normalize the profile-derived plugin list"

    Assert-Throws -Action {
        Resolve-XeditCliPluginLinesFromValues -PluginLines @("", "   ")
    } -ExpectedMessage "Plugin list must contain at least one non-empty entry." -Message "empty plugin lists should be rejected"

    $sessionRoot = Join-Path $env:TEMP ("xedit-cli-session-write-test-" + [guid]::NewGuid().ToString("N"))
    $pathsToRemove += $sessionRoot
    $null = New-Item -ItemType Directory -Path $sessionRoot -Force
    $canonicalSessionRoot = (Get-Item -Path $sessionRoot).FullName

    $writeResult = New-XeditCliSessionPluginsFile -SessionPath $sessionRoot -PluginLines @(
        "*ArmorKeywords.esm",
        "*RaiderOverhaul.esp",
        "*RaiderOverhaul.esp"
    )

    Assert-Equal -Actual $writeResult.SessionPath -Expected $canonicalSessionRoot -Message "session plugin writes should return the canonical session path"
    Assert-Equal -Actual $writeResult.PluginsFilePath -Expected (Join-Path $canonicalSessionRoot "plugins.txt") -Message "session plugin writes should target plugins.txt inside the session directory"
    Assert-True -Condition (Test-Path $writeResult.PluginsFilePath -PathType Leaf) -Message "session plugin writes should materialize plugins.txt"
    Assert-True -Condition (-not (Test-Path (Join-Path $sessionRoot "plugins.txt.tmp"))) -Message "session plugin writes should not leave the temporary file behind"
    Assert-Equal -Actual (Get-Content -Path $writeResult.PluginsFilePath) -Expected @(
        "*ArmorKeywords.esm",
        "*RaiderOverhaul.esp"
    ) -Message "session plugin writes should be atomic and persist the normalized plugin list"
}
finally {
    foreach ($path in $pathsToRemove) {
        if ($path -and (Test-Path $path)) {
            Remove-Item -Path $path -Recurse -Force
        }
    }
}

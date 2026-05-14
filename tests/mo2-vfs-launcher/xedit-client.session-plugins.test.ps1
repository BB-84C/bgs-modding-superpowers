$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
. (Join-Path $repoRoot "tools/mo2-vfs-launcher/lib/xedit-client.session.ps1")
$xeditClientPath = Join-Path $repoRoot "tools/mo2-vfs-launcher/xedit-client.ps1"

function Assert-Equal {
    param($Actual, $Expected, [string]$Message)
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

function Assert-Throws {
    param([scriptblock]$Action, [string]$ExpectedMessage, [string]$Message)
    try { & $Action } catch {
        if ($_.Exception.Message -ne $ExpectedMessage) {
            throw "$Message`nExpected error: $ExpectedMessage`nActual error: $($_.Exception.Message)"
        }
        return
    }
    throw "$Message`nExpected error: $ExpectedMessage`nActual error: <no error>"
}

$plugins = Resolve-XeditClientPluginLinesFromValues -PluginLines @(
    "  *ArmorKeywords.esm  ",
    "",
    "# comment",
    "*RaiderOverhaul.esp",
    "*RaiderOverhaul.esp"
)

Assert-Equal -Actual $plugins -Expected @("*ArmorKeywords.esm", "*RaiderOverhaul.esp") -Message "plugin lines should normalize and dedupe"

Assert-Throws -Action {
    Resolve-XeditClientPluginLinesFromValues -PluginLines @("", "   ")
} -ExpectedMessage "Plugin list must contain at least one non-empty entry." -Message "empty plugin lists should fail"

$session = New-XeditClientSessionContext -PluginLines @("*Fallout4.esm", "*ExamplePatch.esp")
Assert-Equal -Actual (Split-Path $session.SessionPluginsFilePath -Leaf) -Expected "plugins.txt" -Message "session should materialize plugins.txt"
Assert-Equal -Actual (Get-Content $session.SessionPluginsFilePath) -Expected @("*Fallout4.esm", "*ExamplePatch.esp") -Message "session plugins file should persist normalized lines"
$tmpPluginsPath = Join-Path $session.SessionPath "plugins.txt.tmp"
Assert-Equal -Actual (Test-Path -LiteralPath $tmpPluginsPath) -Expected $false -Message "temporary plugin staging file should not persist"

$clientOutput = & pwsh -NoProfile -File $xeditClientPath group command
$clientExitCode = $LASTEXITCODE
if ($clientExitCode -eq 0) {
    throw "xedit-client entrypoint should reject unknown commands"
}

$clientOutputText = ($clientOutput | ForEach-Object { $_.ToString() }) -join "`n"
if ($clientOutputText.Trim() -ne "Unknown command: group command") {
    throw "xedit-client entrypoint should print an unknown command diagnostic`nActual: $clientOutputText"
}

Write-Host "xedit-client session/plugins checks passed."

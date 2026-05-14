$ErrorActionPreference = "Stop"

function ConvertTo-XeditClientOptionMap {
    param(
        [string[]]$Arguments,
        [string[]]$RepeatableNames = @(),
        [string[]]$AllowedNames = @()
    )

    $options = @{}
    $repeatableLookup = @{}
    $allowedLookup = @{}
    foreach ($name in $RepeatableNames) { $repeatableLookup[$name] = $true }
    foreach ($name in $AllowedNames) { $allowedLookup[$name] = $true }

    for ($index = 0; $index -lt $Arguments.Count; $index++) {
        $token = $Arguments[$index]
        if (-not $token.StartsWith('--')) { throw "Unexpected argument: $token" }
        if ($AllowedNames.Count -gt 0 -and -not $allowedLookup.ContainsKey($token)) { throw "Unexpected option: $token" }
        if ($index + 1 -ge $Arguments.Count) { throw "Missing value for option: $token" }

        $value = $Arguments[$index + 1]
        if ($value.StartsWith('--')) { throw "Missing value for option: $token" }

        if ($repeatableLookup.ContainsKey($token)) {
            if (-not $options.ContainsKey($token)) { $options[$token] = @() }
            $options[$token] += $value
        }
        else {
            $options[$token] = $value
        }

        $index++
    }

    return $options
}

function Get-XeditClientSessionBasePath {
    param(
        [string]$TempPath
    )

    $baseTempPath = if ([string]::IsNullOrWhiteSpace($TempPath)) { $env:TEMP } else { $TempPath }
    if ([string]::IsNullOrWhiteSpace($baseTempPath)) {
        $baseTempPath = [System.IO.Path]::GetTempPath()
    }

    return Join-Path $baseTempPath 'xedit-client-sessions'
}

function Get-XeditClientDefaultPluginsFilePath {
    param([string]$GameMode)

    $directoryName = switch ($GameMode) {
        'Fallout4' { 'Fallout4' }
        'Skyrim' { 'Skyrim' }
        'SkyrimSE' { 'Skyrim Special Edition' }
        'Starfield' { 'Starfield' }
        default { $null }
    }

    if ([string]::IsNullOrWhiteSpace($directoryName)) { return $null }
    return Join-Path (Join-Path $env:LOCALAPPDATA $directoryName) 'plugins.txt'
}

function Get-XeditClientMo2ProfilePluginsFilePath {
    param([string]$Profile, [string]$SandboxRoot)

    if ([string]::IsNullOrWhiteSpace($Profile)) { return $null }
    $resolvedSandboxRoot = if ([string]::IsNullOrWhiteSpace($SandboxRoot)) { Get-XeditClientDefaultMo2SandboxRoot } else { $SandboxRoot }
    return Join-Path (Join-Path (Join-Path $resolvedSandboxRoot 'profiles') $Profile) 'plugins.txt'
}

function Get-XeditClientUnsupportedLegacyLaunchOptions {
    param([hashtable]$Options)

    $unsupportedOptions = @()
    foreach ($optionName in @('--load-mode', '--plugin')) {
        if ($Options.ContainsKey($optionName)) { $unsupportedOptions += $optionName }
    }
    return $unsupportedOptions
}

function Get-XeditClientResolvedPluginSource {
    param(
        [hashtable]$Options,
        [string]$GameMode,
        [string]$MoProfile,
        [string]$SandboxRoot
    )

    $pluginsFilePath = $null
    if ($Options.ContainsKey('--plugins-file')) {
        $pluginsFilePath = [string]$Options['--plugins-file']
        if ([string]::IsNullOrWhiteSpace($pluginsFilePath)) {
            Write-Host 'Plugins file path must be non-empty'
            return $null
        }
    }

    $profilePluginFilePath = Get-XeditClientMo2ProfilePluginsFilePath -Profile $MoProfile -SandboxRoot $SandboxRoot
    if ([string]::IsNullOrWhiteSpace($profilePluginFilePath)) {
        $profilePluginFilePath = Get-XeditClientDefaultPluginsFilePath -GameMode $GameMode
    }

    try {
        return Resolve-XeditClientPluginSource -PluginFilePath $pluginsFilePath -ProfilePluginFilePath $profilePluginFilePath
    }
    catch {
        Write-Host $_.Exception.Message
        return $null
    }
}

function Test-XeditClientLauncherPath {
    param([string]$Path)
    if (-not (Test-Path $Path -PathType Leaf)) { return $false }
    return @('.bat', '.cmd', '.exe') -contains ([System.IO.Path]::GetExtension($Path).ToLowerInvariant())
}

function Test-XeditClientExecutablePathLooksLikeXedit {
    param([string]$Path)
    if (-not (Test-Path $Path -PathType Leaf)) { return $false }
    return Test-XeditClientExecutableHasXeditIdentity -Path (Get-Item -Path $Path).FullName
}

function Test-XeditClientExecutableHasXeditIdentity {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path $Path -PathType Leaf)) { return $false }
    try { $versionInfo = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($Path) } catch { return $false }

    $xeditIdentityPattern = '(?i)\b(xedit(?:64)?|fo4edit(?:64)?|sseedit(?:64)?|sf1edit(?:64)?|tes5edit(?:64)?|tes4edit(?:64)?|fo3edit(?:64)?|fnvedit(?:64)?|enderaledit(?:64)?)\b'
    $identityMarkers = @($versionInfo.OriginalFilename, $versionInfo.FileDescription, $versionInfo.ProductName) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    if ($identityMarkers.Count -eq 0) { return $false }
    return ($identityMarkers -join "`n") -match $xeditIdentityPattern
}

function Get-XeditClientGameModeMap {
    return [ordered]@{
        Fallout4  = '-FO4'
        Skyrim    = '-TES5'
        SkyrimSE  = '-SSE'
        Starfield = '-SF1'
    }
}

function Get-XeditClientSupportedGameModes { return (Get-XeditClientGameModeMap).Keys }
function Get-XeditClientSupportedGameModeArguments { return @((Get-XeditClientGameModeMap).Values) }

function Resolve-XeditClientGameModeArgument {
    param([string]$GameMode)
    $gameModeMap = Get-XeditClientGameModeMap
    if (-not $gameModeMap.Contains($GameMode)) { return $null }
    return $gameModeMap[$GameMode]
}

function Get-XeditClientValidatedGameModeArgument {
    param([string]$GameMode)
    $gameModeArgument = Resolve-XeditClientGameModeArgument -GameMode $GameMode
    if ($null -eq $gameModeArgument) {
        Write-Host "Unsupported game mode: $GameMode. Supported game modes: $((Get-XeditClientSupportedGameModes) -join ', ')"
        return $null
    }
    return $gameModeArgument
}

function Test-XeditClientGameModeArgument {
    param([string]$Argument)
    if ([string]::IsNullOrWhiteSpace($Argument)) { return $false }
    return (Get-XeditClientSupportedGameModeArguments) -icontains $Argument
}

function ConvertTo-XeditClientProcessId {
    param([string]$ProcessId)
    $parsedId = 0
    if (-not [int]::TryParse($ProcessId, [ref]$parsedId) -or $parsedId -le 0) { return $null }
    return $parsedId
}

function ConvertTo-XeditClientPositiveIntValue {
    param([string]$Value)
    $parsedValue = 0
    if (-not [int]::TryParse($Value, [ref]$parsedValue) -or $parsedValue -le 0) { return $null }
    return $parsedValue
}

function Get-XeditClientProcessById {
    param([string]$ProcessId)
    $parsedId = ConvertTo-XeditClientProcessId -ProcessId $ProcessId
    if ($null -eq $parsedId) { return $null }
    try { return Get-CimInstance Win32_Process -Filter "ProcessId = $parsedId" -ErrorAction Stop } catch { return $null }
}

function Test-XeditClientProcessLooksLikeXedit {
    param($Process)
    if ($null -eq $Process) { return $false }
    if ([string]::IsNullOrWhiteSpace($Process.ExecutablePath) -or -not (Test-Path $Process.ExecutablePath)) { return $false }
    return Test-XeditClientExecutableHasXeditIdentity -Path $Process.ExecutablePath
}

function ConvertTo-XeditCliOptionMap {
    param(
        [string[]]$Arguments,
        [string[]]$RepeatableNames = @()
    )

    $options = @{}
    $repeatableLookup = @{}
    foreach ($name in $RepeatableNames) {
        $repeatableLookup[$name] = $true
    }

    for ($index = 0; $index -lt $Arguments.Count; $index++) {
        $token = $Arguments[$index]
        if (-not $token.StartsWith("--")) {
            throw "Unexpected argument: $token"
        }

        if ($index + 1 -ge $Arguments.Count) {
            throw "Missing value for option: $token"
        }

        $value = $Arguments[$index + 1]
        if ($value.StartsWith("--")) {
            throw "Missing value for option: $token"
        }

        if ($repeatableLookup.ContainsKey($token)) {
            if (-not $options.ContainsKey($token)) {
                $options[$token] = @()
            }

            $options[$token] += $value
        }
        else {
            $options[$token] = $value
        }

        $index++
    }

    return $options
}

function Get-XeditCliDefaultPluginsFilePath {
    param(
        [string]$GameMode
    )

    $directoryName = switch ($GameMode) {
        'Fallout4' { 'Fallout4' }
        'Skyrim' { 'Skyrim' }
        'SkyrimSE' { 'Skyrim Special Edition' }
        'Starfield' { 'Starfield' }
        default { $null }
    }

    if ([string]::IsNullOrWhiteSpace($directoryName)) {
        return $null
    }

    return Join-Path (Join-Path $env:LOCALAPPDATA $directoryName) 'plugins.txt'
}

function Get-XeditCliMo2ProfilePluginsFilePath {
    param(
        [string]$Profile,
        [string]$SandboxRoot
    )

    if ([string]::IsNullOrWhiteSpace($Profile)) {
        return $null
    }

    $resolvedSandboxRoot = if ([string]::IsNullOrWhiteSpace($SandboxRoot)) {
        Get-XeditCliDefaultMo2SandboxRoot
    }
    else {
        $SandboxRoot
    }

    return Join-Path (Join-Path (Join-Path $resolvedSandboxRoot 'profiles') $Profile) 'plugins.txt'
}

function Get-XeditCliUnsupportedLegacyLaunchOptions {
    param(
        [hashtable]$Options
    )

    $unsupportedOptions = @()
    foreach ($optionName in @('--load-mode', '--plugin')) {
        if ($Options.ContainsKey($optionName)) {
            $unsupportedOptions += $optionName
        }
    }

    return $unsupportedOptions
}

function Get-XeditCliResolvedPluginSource {
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

    $profilePluginFilePath = Get-XeditCliMo2ProfilePluginsFilePath -Profile $MoProfile -SandboxRoot $SandboxRoot
    if ([string]::IsNullOrWhiteSpace($profilePluginFilePath)) {
        $profilePluginFilePath = Get-XeditCliDefaultPluginsFilePath -GameMode $GameMode
    }

    try {
        return Resolve-XeditCliPluginSource -PluginFilePath $pluginsFilePath -ProfilePluginFilePath $profilePluginFilePath
    }
    catch {
        Write-Host $_.Exception.Message
        return $null
    }
}

function Ensure-XeditCliParentDirectory {
    param(
        [string]$Path
    )

    $parent = Split-Path -Path $Path -Parent
    if ($parent -and -not (Test-Path $parent)) {
        $null = New-Item -ItemType Directory -Path $parent -Force
    }
}

function Test-XeditCliLauncherPath {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path -PathType Leaf)) {
        return $false
    }

    return @('.bat', '.cmd', '.exe') -contains ([System.IO.Path]::GetExtension($Path).ToLowerInvariant())
}

function Test-XeditCliExecutablePathLooksLikeXedit {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path -PathType Leaf)) {
        return $false
    }

    return Test-XeditCliExecutableHasXeditIdentity -Path (Get-Item -Path $Path).FullName
}

function Test-XeditCliExecutableHasXeditIdentity {
    param(
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path $Path -PathType Leaf)) {
        return $false
    }

    try {
        $versionInfo = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($Path)
    }
    catch {
        return $false
    }

    $xeditIdentityPattern = '(?i)\b(xedit(?:64)?|fo4edit(?:64)?|sseedit(?:64)?|sf1edit(?:64)?|tes5edit(?:64)?|tes4edit(?:64)?|fo3edit(?:64)?|fnvedit(?:64)?|enderaledit(?:64)?)\b'
    $identityMarkers = @(
        $versionInfo.OriginalFilename,
        $versionInfo.FileDescription,
        $versionInfo.ProductName
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

    if ($identityMarkers.Count -eq 0) {
        return $false
    }

    return ($identityMarkers -join "`n") -match $xeditIdentityPattern
}

function Get-XeditCliGameModeMap {
    return [ordered]@{
        Fallout4 = '-FO4'
        Skyrim   = '-TES5'
        SkyrimSE = '-SSE'
        Starfield = '-SF1'
    }
}

function Get-XeditCliSupportedGameModes {
    return (Get-XeditCliGameModeMap).Keys
}

function Get-XeditCliSupportedGameModeArguments {
    return @((Get-XeditCliGameModeMap).Values)
}

function Resolve-XeditCliGameModeArgument {
    param(
        [string]$GameMode
    )

    $gameModeMap = Get-XeditCliGameModeMap
    if (-not $gameModeMap.Contains($GameMode)) {
        return $null
    }

    return $gameModeMap[$GameMode]
}

function Get-XeditCliValidatedGameModeArgument {
    param(
        [string]$GameMode
    )

    $gameModeArgument = Resolve-XeditCliGameModeArgument -GameMode $GameMode
    if ($null -eq $gameModeArgument) {
        Write-Host "Unsupported game mode: $GameMode. Supported game modes: $((Get-XeditCliSupportedGameModes) -join ', ')"
        return $null
    }

    return $gameModeArgument
}

function Test-XeditCliGameModeArgument {
    param(
        [string]$Argument
    )

    if ([string]::IsNullOrWhiteSpace($Argument)) {
        return $false
    }

    return (Get-XeditCliSupportedGameModeArguments) -icontains $Argument
}

function ConvertTo-XeditCliProcessId {
    param(
        [string]$ProcessId
    )

    $parsedId = 0
    if (-not [int]::TryParse($ProcessId, [ref]$parsedId) -or $parsedId -le 0) {
        return $null
    }

    return $parsedId
}

function ConvertTo-XeditCliPositiveIntValue {
    param(
        [string]$Value
    )

    $parsedValue = 0
    if (-not [int]::TryParse($Value, [ref]$parsedValue) -or $parsedValue -le 0) {
        return $null
    }

    return $parsedValue
}

function Get-XeditCliProcessById {
    param(
        [string]$ProcessId
    )

    $parsedId = ConvertTo-XeditCliProcessId -ProcessId $ProcessId
    if ($null -eq $parsedId) {
        return $null
    }

    try {
        return Get-CimInstance Win32_Process -Filter "ProcessId = $parsedId" -ErrorAction Stop
    }
    catch {
        return $null
    }
}

function Test-XeditCliProcessLooksLikeXedit {
    param(
        $Process
    )

    if ($null -eq $Process) {
        return $false
    }

    if ([string]::IsNullOrWhiteSpace($Process.ExecutablePath) -or -not (Test-Path $Process.ExecutablePath)) {
        return $false
    }

    return Test-XeditCliExecutableHasXeditIdentity -Path $Process.ExecutablePath
}

function Test-XeditCliProcessImageLooksLikeXedit {
    param(
        $Process
    )

    if ($null -eq $Process) {
        return $false
    }

    $processName = $Process.Name
    if ([string]::IsNullOrWhiteSpace($processName) -and -not [string]::IsNullOrWhiteSpace($Process.ExecutablePath)) {
        $processName = [System.IO.Path]::GetFileName($Process.ExecutablePath)
    }

    if ([string]::IsNullOrWhiteSpace($processName)) {
        return $false
    }

    return ($processName -match '(?i)^(xedit(?:64)?|fo4edit(?:64)?|sseedit(?:64)?|sf1edit(?:64)?|tes5edit(?:64)?|tes4edit(?:64)?|fo3edit(?:64)?|fnvedit(?:64)?|enderaledit(?:64)?)\.exe$')
}

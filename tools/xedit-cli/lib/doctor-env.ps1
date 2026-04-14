function Invoke-XeditCliDoctorEnv {
    param(
        [string[]]$Arguments
    )

    $options = ConvertTo-XeditCliOptionMap -Arguments $Arguments

    $missing = @()
    foreach ($name in @("--launcher-path", "--game-mode")) {
        if (-not $options.ContainsKey($name)) {
            $missing += $name
        }
    }

    if ($missing.Count -gt 0) {
        Write-Host "Missing required options: $($missing -join ', ')"
        return 1
    }

    $launcherPath = $options["--launcher-path"]
    $gameMode = $options["--game-mode"]
    $gameModeArgument = Resolve-XeditCliGameModeArgument -GameMode $gameMode

    if ($null -eq $gameModeArgument) {
        Write-Host "Unsupported game mode: $gameMode. Supported game modes: $((Get-XeditCliSupportedGameModes) -join ', ')"
        return 1
    }

    if (-not (Test-Path $launcherPath -PathType Leaf)) {
        Write-Host "Launcher path does not exist: $launcherPath"
        return 1
    }

    if (-not (Test-XeditCliLauncherPath -Path $launcherPath)) {
        Write-Host "Launcher path must end with .bat, .cmd, or .exe: $launcherPath"
        return 1
    }

    $null = Get-XeditCliNormalizedLauncherCommand -LauncherPath $launcherPath -GameModeArgument $gameModeArgument

    $xeditPid = $null
    if ($options.ContainsKey("--xedit-pid")) {
        $xeditPid = $options["--xedit-pid"]
        $parsedPid = ConvertTo-XeditCliProcessId -ProcessId $xeditPid
        if ($null -eq $parsedPid) {
            Write-Host "Invalid xEdit PID: $xeditPid"
            return 1
        }

        $process = Get-XeditCliProcessById -ProcessId $xeditPid
        if (-not $process) {
            Write-Host "xEdit PID is not running: $xeditPid"
            return 1
        }

        if (-not (Test-XeditCliProcessLooksLikeXedit -Process $process)) {
            Write-Host "Process is not an xEdit instance: $xeditPid"
            return 1
        }
    }

    Write-Host "doctor env"
    Write-Host "status: ok"
    Write-Host "game-mode: $gameMode ($gameModeArgument)"
    Write-Host "launcher-path: $launcherPath"
    if ($null -ne $xeditPid) {
        Write-Host "xedit-pid: $xeditPid"
    }

    return 0
}

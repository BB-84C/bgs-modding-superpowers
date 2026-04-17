function Get-Mo2ControlPlanePrimitiveCommands {
    return @(
        "profile.list",
        "profile.get-current",
        "profile.set-current",
        "executables.list",
        "executables.get",
        "mods.list",
        "plugins.list",
        "organizer.refresh",
        "launch.start",
        "launch.status",
        "launch.wait",
        "launch.stop"
    )
}

function Get-Mo2ControlPlaneAdvertisedCommands {
    return @(
        (Get-Mo2ControlPlaneLiveBootstrapSupportedCommands)
        "session.open",
        "session.artifacts"
    ) + (Get-Mo2ControlPlanePrimitiveCommands)
}

function New-Mo2ControlPlanePrimitiveStubResult {
    param(
        [string]$Command
    )

    return [ordered]@{
        command = $Command
        stub = $true
    }
}

function Resolve-Mo2ControlPlaneCapabilitiesResult {
    param(
        [object]$Result
    )

    $advertisedCommands = @()
    foreach ($commandName in (Get-Mo2ControlPlaneAdvertisedCommands)) {
        if ($advertisedCommands -notcontains $commandName) {
            $advertisedCommands += $commandName
        }
    }

    if ($null -ne $Result -and $null -ne $Result.commands) {
        foreach ($commandName in $Result.commands) {
            if ($advertisedCommands -notcontains $commandName) {
                $advertisedCommands += $commandName
            }
        }
    }

    return [ordered]@{
        commands = $advertisedCommands
    }
}

function Invoke-Mo2ControlPlaneLaunchRequest {
    param(
        [hashtable]$Request
    )

    if (-not (Test-Mo2ControlPlaneFakeKernelAvailable) -and -not (Test-Mo2ControlPlaneTransportPayload -Request $Request)) {
        $error = New-Mo2ControlPlaneError -Code "transport_error" -Message "Launch command requires fake kernel or explicit transport payload: $($Request.command)"
        return New-Mo2ControlPlaneResponse -Request $Request -Ok $false -Error $error
    }

    try {
        $result = if (Test-Mo2ControlPlaneFakeKernelAvailable) {
            Invoke-Mo2ControlPlaneFakeKernelLaunchCommand -Request $Request
        }
        else {
            Invoke-Mo2ControlPlaneLocalLaunchCommand -Request $Request
        }

        return New-Mo2ControlPlaneResponse -Request $Request -Ok $true -Result $result
    }
    catch {
        $error = New-Mo2ControlPlaneError -Code "transport_error" -Message $_.Exception.Message
        return New-Mo2ControlPlaneResponse -Request $Request -Ok $false -Error $error
    }
}

function Invoke-Mo2ControlPlaneClientRequest {
    param(
        [hashtable]$Request,
        [string]$LiveRoot = $null
    )

    if (-not [string]::IsNullOrWhiteSpace($LiveRoot) -and (Test-Mo2ControlPlaneLiveBootstrapCommand -Command $Request.command)) {
        $response = Invoke-Mo2ControlPlaneLiveBootstrapRequest -Request $Request -LiveRoot $LiveRoot
        if ($Request.command -eq "system.capabilities" -and $response.ok) {
            $response.result = Resolve-Mo2ControlPlaneCapabilitiesResult -Result $response.result
        }

        return $response
    }

    if ($Request.command -like "launch.*") {
        return Invoke-Mo2ControlPlaneLaunchRequest -Request $Request
    }

    $fixturePath = $env:MO2_CONTROL_PLANE_FAKE_RESPONSE_PATH
    if ([string]::IsNullOrWhiteSpace($fixturePath) -or -not (Test-Path $fixturePath -PathType Leaf)) {
        $error = New-Mo2ControlPlaneError -Code "transport_error" -Message "Missing fake kernel response fixture" -Details @{ path = $fixturePath }
        return New-Mo2ControlPlaneResponse -Request $Request -Ok $false -Error $error
    }

    $fixture = Get-Content -Path $fixturePath -Raw | ConvertFrom-Json -ErrorAction Stop
    $property = $fixture.PSObject.Properties[$Request.command]
    if ($null -eq $property) {
        if ((Get-Mo2ControlPlanePrimitiveCommands) -contains $Request.command) {
            return New-Mo2ControlPlaneResponse -Request $Request -Ok $true -Result (New-Mo2ControlPlanePrimitiveStubResult -Command $Request.command)
        }

        $error = New-Mo2ControlPlaneError -Code "unsupported_command" -Message "No fake kernel response for $($Request.command)"
        return New-Mo2ControlPlaneResponse -Request $Request -Ok $false -Error $error
    }

    $result = $property.Value.result
    if ($Request.command -eq "system.capabilities" -and $property.Value.ok) {
        $result = Resolve-Mo2ControlPlaneCapabilitiesResult -Result $result
    }

    return New-Mo2ControlPlaneResponse -Request $Request -Ok ([bool]$property.Value.ok) -Result $result -Error $property.Value.error
}

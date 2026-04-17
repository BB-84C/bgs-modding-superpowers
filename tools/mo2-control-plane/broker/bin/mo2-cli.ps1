$ErrorActionPreference = "Stop"

$toolRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\")).Path

. (Join-Path $toolRoot "lib/common.ps1")
. (Join-Path $toolRoot "lib/protocol.ps1")
. (Join-Path $toolRoot "lib/session.ps1")
. (Join-Path $toolRoot "lib/launch.ps1")
. (Join-Path $toolRoot "lib/ipc-client.ps1")
. (Join-Path $toolRoot "lib/live-bootstrap.ps1")
. (Join-Path $toolRoot "lib/client.ps1")

function Write-Mo2ControlPlaneJson {
    param(
        [object]$Value
    )

    $json = $Value | ConvertTo-Json -Depth 10 -Compress
    [Console]::Out.WriteLine($json)
}

function New-Mo2ControlPlaneCliRequest {
    param(
        [string]$Group,
        [string]$Command,
        [string]$SessionId = $null,
        [object]$Payload = $null
    )

    $commandName = if ([string]::IsNullOrWhiteSpace($Group)) {
        ""
    }
    elseif ([string]::IsNullOrWhiteSpace($Command)) {
        $Group
    }
    else {
        "$Group.$Command"
    }

    return New-Mo2ControlPlaneRequest -SessionId $SessionId -Command $commandName -Payload $Payload
}

function Resolve-Mo2ControlPlaneCliErrorCode {
    param(
        [string]$Message
    )

    if ($Message -like "Unknown command:*") {
        return "unsupported_command"
    }

    if (
        $Message -like "Usage:*" -or
        $Message -like "Unexpected arguments for *" -or
        $Message -like "Unexpected option:*" -or
        $Message -like "Missing required options:*" -or
        $Message -like "Missing value for option:*" -or
        $Message -like "Unexpected argument:*" -or
        $Message -like "Duplicate option:*" -or
        $Message -like "Invalid session id:*"
    ) {
        return "validation_error"
    }

    if ($Message -like "Session not found:*") {
        return "mo2_state_error"
    }

    return "internal_error"
}

function Write-Mo2ControlPlaneCliError {
    param(
        [string]$Group,
        [string]$Command,
        [string]$SessionId = $null,
        [string]$Message,
        [object]$Details = $null
    )

    $request = New-Mo2ControlPlaneCliRequest -Group $Group -Command $Command -SessionId $SessionId -Payload @{}
    $error = New-Mo2ControlPlaneError -Code (Resolve-Mo2ControlPlaneCliErrorCode -Message $Message) -Message $Message -Details $Details
    $response = New-Mo2ControlPlaneResponse -Request $request -Ok $false -Error $error
    Write-Mo2ControlPlaneJson -Value $response
}

function Assert-Mo2ControlPlaneCliNoArguments {
    param(
        [string]$CommandName,
        [string[]]$Arguments
    )

    if ($Arguments.Count -gt 0) {
        throw "Unexpected arguments for ${CommandName}: $($Arguments -join ' ')"
    }
}

function Assert-Mo2ControlPlaneCliAllowedOptions {
    param(
        [hashtable]$Options,
        [string[]]$AllowedOptions
    )

    foreach ($optionName in $Options.Keys) {
        if ($AllowedOptions -notcontains $optionName) {
            throw "Unexpected option: $optionName"
        }
    }
}

function Invoke-Mo2ControlPlaneCliSessionBackedCommand {
    param(
        [string]$Group,
        [string]$Command,
        [string[]]$Arguments
    )

    $options = ConvertTo-Mo2ControlPlaneOptionMap -Arguments $Arguments
    Assert-Mo2ControlPlaneCliAllowedOptions -Options $options -AllowedOptions @("--session-id")
    if (-not $options.ContainsKey("--session-id")) {
        throw "Missing required options: --session-id"
    }

    $session = Get-Mo2ControlPlaneSession -SessionId $options["--session-id"]
    $request = New-Mo2ControlPlaneRequest -SessionId $session.SessionId -Command "$Group.$Command" -Payload @{}
    $response = Invoke-Mo2ControlPlaneClientRequest -Request $request
    Write-Mo2ControlPlaneJson -Value $response
    exit $(if ($response.ok) { 0 } else { 1 })
}

function Invoke-Mo2ControlPlaneCliLaunchCommand {
    param(
        [string]$Command,
        [string[]]$Arguments
    )

    $allowedOptions = @("--session-id")
    if ($Command -ne "start") {
        $allowedOptions += "--launch-id"
    }

    $options = ConvertTo-Mo2ControlPlaneOptionMap -Arguments $Arguments
    Assert-Mo2ControlPlaneCliAllowedOptions -Options $options -AllowedOptions $allowedOptions
    if (-not $options.ContainsKey("--session-id")) {
        throw "Missing required options: --session-id"
    }

    if ($Command -ne "start" -and -not $options.ContainsKey("--launch-id")) {
        throw "Missing required options: --launch-id"
    }

    $session = Get-Mo2ControlPlaneSession -SessionId $options["--session-id"]
    $payload = [ordered]@{}
    if ($options.ContainsKey("--launch-id")) {
        $payload.launch_id = $options["--launch-id"]
    }

    $request = New-Mo2ControlPlaneRequest -SessionId $session.SessionId -Command ("launch.{0}" -f $Command) -Payload $payload
    $response = Invoke-Mo2ControlPlaneClientRequest -Request $request
    Write-Mo2ControlPlaneJson -Value $response
    exit $(if ($response.ok) { 0 } else { 1 })
}

function Invoke-Mo2ControlPlaneCliSystemCommand {
    param(
        [string]$Command,
        [string[]]$Arguments
    )

    $options = ConvertTo-Mo2ControlPlaneOptionMap -Arguments $Arguments
    Assert-Mo2ControlPlaneCliAllowedOptions -Options $options -AllowedOptions @("--live-root")

    $request = New-Mo2ControlPlaneRequest -SessionId $null -Command ("system.{0}" -f $Command) -Payload @{}
    $liveRoot = $null
    if ($options.ContainsKey("--live-root")) {
        $liveRoot = $options["--live-root"]
    }

    $response = Invoke-Mo2ControlPlaneClientRequest -Request $request -LiveRoot $liveRoot
    Write-Mo2ControlPlaneJson -Value $response
    exit $(if ($response.ok) { 0 } else { 1 })
}

 $group = $null
 $command = $null
 $sessionId = $null

try {
    if ($args.Count -lt 2) {
        throw "Usage: mo2-cli.ps1 <group> <command> [options]"
    }

    $group = $args[0]
    $command = $args[1]
    $remaining = @()
    if ($args.Count -gt 2) {
        $remaining = $args[2..($args.Count - 1)]
    }

    switch ("$group $command") {
        "system ping" {
            Invoke-Mo2ControlPlaneCliSystemCommand -Command $command -Arguments $remaining
        }
        "system capabilities" {
            Invoke-Mo2ControlPlaneCliSystemCommand -Command $command -Arguments $remaining
        }
        "session open" {
            Assert-Mo2ControlPlaneCliNoArguments -CommandName "session open" -Arguments $remaining
            $session = Open-Mo2ControlPlaneSession -SessionId (New-Mo2ControlPlaneSessionId)
            $request = New-Mo2ControlPlaneRequest -SessionId $session.SessionId -Command "session.open" -Payload @{}
            $response = New-Mo2ControlPlaneResponse -Request $request -Ok $true -Result ([ordered]@{
                session_id = $session.SessionId
                session_root = $session.Root
                launches_root = $session.LaunchesRoot
                artifacts_root = $session.ArtifactsRoot
            })
            Write-Mo2ControlPlaneJson -Value $response
            exit 0
        }
        "session artifacts" {
            $options = ConvertTo-Mo2ControlPlaneOptionMap -Arguments $remaining
            Assert-Mo2ControlPlaneCliAllowedOptions -Options $options -AllowedOptions @("--session-id")
            if (-not $options.ContainsKey("--session-id")) {
                throw "Missing required options: --session-id"
            }

            $sessionId = $options["--session-id"]
            $session = Get-Mo2ControlPlaneSession -SessionId $sessionId
            $request = New-Mo2ControlPlaneRequest -SessionId $session.SessionId -Command "session.artifacts" -Payload @{}
            $response = New-Mo2ControlPlaneResponse -Request $request -Ok $true -Result ([ordered]@{
                session_id = $session.SessionId
                session_root = $session.Root
                launches_root = $session.LaunchesRoot
                artifacts_root = $session.ArtifactsRoot
            })
            Write-Mo2ControlPlaneJson -Value $response
            exit 0
        }
        "profile list" {
            Invoke-Mo2ControlPlaneCliSessionBackedCommand -Group $group -Command $command -Arguments $remaining
        }
        "profile get-current" {
            Invoke-Mo2ControlPlaneCliSessionBackedCommand -Group $group -Command $command -Arguments $remaining
        }
        "profile set-current" {
            Invoke-Mo2ControlPlaneCliSessionBackedCommand -Group $group -Command $command -Arguments $remaining
        }
        "executables list" {
            Invoke-Mo2ControlPlaneCliSessionBackedCommand -Group $group -Command $command -Arguments $remaining
        }
        "executables get" {
            Invoke-Mo2ControlPlaneCliSessionBackedCommand -Group $group -Command $command -Arguments $remaining
        }
        "mods list" {
            Invoke-Mo2ControlPlaneCliSessionBackedCommand -Group $group -Command $command -Arguments $remaining
        }
        "plugins list" {
            Invoke-Mo2ControlPlaneCliSessionBackedCommand -Group $group -Command $command -Arguments $remaining
        }
        "organizer refresh" {
            Invoke-Mo2ControlPlaneCliSessionBackedCommand -Group $group -Command $command -Arguments $remaining
        }
        "launch start" {
            Invoke-Mo2ControlPlaneCliLaunchCommand -Command $command -Arguments $remaining
        }
        "launch status" {
            Invoke-Mo2ControlPlaneCliLaunchCommand -Command $command -Arguments $remaining
        }
        "launch wait" {
            Invoke-Mo2ControlPlaneCliLaunchCommand -Command $command -Arguments $remaining
        }
        "launch stop" {
            Invoke-Mo2ControlPlaneCliLaunchCommand -Command $command -Arguments $remaining
        }
        default {
            throw "Unknown command: $group $command"
        }
    }
}
catch {
    Write-Mo2ControlPlaneCliError -Group $group -Command $command -SessionId $sessionId -Message $_.Exception.Message
    exit 1
}

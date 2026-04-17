function Assert-Mo2ControlPlaneSessionId {
    param(
        [string]$SessionId
    )

    if ([string]::IsNullOrWhiteSpace($SessionId) -or $SessionId -notmatch '^sess-[0-9a-f]{32}$') {
        throw "Invalid session id: $SessionId"
    }

    return $SessionId
}

function New-Mo2ControlPlaneSessionInfo {
    param(
        [string]$SessionId
    )

    return [pscustomobject]@{
        SessionId = $SessionId
        Root = Join-Path (Get-Mo2ControlPlaneRoot) $SessionId
        LaunchesRoot = Join-Path (Join-Path (Get-Mo2ControlPlaneRoot) $SessionId) "launches"
        ArtifactsRoot = Join-Path (Join-Path (Get-Mo2ControlPlaneRoot) $SessionId) "artifacts"
    }
}

function Get-Mo2ControlPlaneSessionRoot {
    param(
        [string]$SessionId
    )

    $validatedSessionId = Assert-Mo2ControlPlaneSessionId -SessionId $SessionId
    return (New-Mo2ControlPlaneSessionInfo -SessionId $validatedSessionId).Root
}

function Get-Mo2ControlPlaneLaunchesRoot {
    param(
        [string]$SessionId
    )

    return Join-Path (Get-Mo2ControlPlaneSessionRoot -SessionId $SessionId) "launches"
}

function Get-Mo2ControlPlaneArtifactsRoot {
    param(
        [string]$SessionId
    )

    return Join-Path (Get-Mo2ControlPlaneSessionRoot -SessionId $SessionId) "artifacts"
}

function Get-Mo2ControlPlaneSession {
    param(
        [string]$SessionId
    )

    $validatedSessionId = Assert-Mo2ControlPlaneSessionId -SessionId $SessionId
    $session = New-Mo2ControlPlaneSessionInfo -SessionId $validatedSessionId

    foreach ($path in @($session.Root, $session.LaunchesRoot, $session.ArtifactsRoot)) {
        if (-not (Test-Path $path -PathType Container)) {
            throw "Session not found: $validatedSessionId"
        }
    }

    return $session
}

function Open-Mo2ControlPlaneSession {
    param(
        [string]$SessionId
    )

    $validatedSessionId = Assert-Mo2ControlPlaneSessionId -SessionId $SessionId
    $session = New-Mo2ControlPlaneSessionInfo -SessionId $validatedSessionId

    $session.Root = Ensure-Mo2ControlPlaneDirectory -Path $session.Root
    $session.LaunchesRoot = Ensure-Mo2ControlPlaneDirectory -Path $session.LaunchesRoot
    $session.ArtifactsRoot = Ensure-Mo2ControlPlaneDirectory -Path $session.ArtifactsRoot

    return $session
}

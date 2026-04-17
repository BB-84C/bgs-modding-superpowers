function Get-Mo2ControlPlaneProtocolVersion {
    return "1"
}

function New-Mo2ControlPlaneRequestId {
    return "req-" + [guid]::NewGuid().ToString("N")
}

function New-Mo2ControlPlaneSessionId {
    return "sess-" + [guid]::NewGuid().ToString("N")
}

function Get-Mo2ControlPlaneRoot {
    return Join-Path $env:TEMP "mo2-control-plane"
}

function Ensure-Mo2ControlPlaneDirectory {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path -PathType Container)) {
        $null = New-Item -ItemType Directory -Path $Path -Force
    }

    return $Path
}

function ConvertTo-Mo2ControlPlaneOptionMap {
    param(
        [string[]]$Arguments
    )

    $options = @{}
    for ($index = 0; $index -lt $Arguments.Count; $index++) {
        $token = $Arguments[$index]
        if (-not $token.StartsWith("--")) {
            throw "Unexpected argument: $token"
        }

        if ($options.ContainsKey($token)) {
            throw "Duplicate option: $token"
        }

        if ($index + 1 -ge $Arguments.Count) {
            throw "Missing value for option: $token"
        }

        $value = $Arguments[$index + 1]
        if ([string]::IsNullOrWhiteSpace($value) -or $value.StartsWith("--")) {
            throw "Missing value for option: $token"
        }

        $options[$token] = $value
        $index++
    }

    return $options
}

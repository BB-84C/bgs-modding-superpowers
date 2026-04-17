function Get-Mo2ControlPlaneLiveBootstrapSupportedCommands {
    return @(
        "system.ping",
        "system.capabilities",
        "launch.start",
        "launch.status",
        "launch.wait",
        "launch.stop"
    )
}

function Test-Mo2ControlPlaneLiveBootstrapCommand {
    param(
        [string]$Command
    )

    return (Get-Mo2ControlPlaneLiveBootstrapSupportedCommands) -contains $Command
}

function Get-Mo2ControlPlaneLiveBootstrapSupportedSchemaVersion {
    return 1
}

function Resolve-Mo2ControlPlaneLiveBootstrapRoot {
    param(
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw "Missing live bootstrap root"
    }

    try {
        return (Resolve-Path -Path $Path -ErrorAction Stop).Path
    }
    catch {
        throw "Live bootstrap root not found: $Path"
    }
}

function Read-Mo2ControlPlaneLiveBootstrapJsonFile {
    param(
        [string]$RuntimeRoot,
        [string]$FileName,
        [string[]]$RequiredFields
    )

    $path = Join-Path $RuntimeRoot $FileName
    if (-not (Test-Path $path -PathType Leaf)) {
        throw "Missing live bootstrap file: $FileName"
    }

    try {
        $document = Get-Content -Path $path -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    }
    catch {
        throw "Malformed live bootstrap file: $FileName"
    }

    foreach ($field in $RequiredFields) {
        if (-not $document.ContainsKey($field) -or $null -eq $document[$field]) {
            throw "Malformed live bootstrap file: $FileName"
        }
    }

    if ([string]$document.schemaVersion -ne [string](Get-Mo2ControlPlaneLiveBootstrapSupportedSchemaVersion)) {
        throw "Unsupported live bootstrap schemaVersion in ${FileName}: $($document.schemaVersion)"
    }

    return $document
}

function Test-Mo2ControlPlaneLiveBootstrapProcess {
    param(
        [object]$ProcessId
    )

    $parsedProcessId = 0
    if (-not [int]::TryParse([string]$ProcessId, [ref]$parsedProcessId)) {
        return $false
    }

    if ($parsedProcessId -le 0) {
        return $false
    }

    return $null -ne (Get-Process -Id $parsedProcessId -ErrorAction SilentlyContinue)
}

function Get-Mo2ControlPlaneLiveBootstrapRuntime {
    param(
        [string]$LiveRoot
    )

    $runtimeRoot = Resolve-Mo2ControlPlaneLiveBootstrapRoot -Path $LiveRoot
    $status = Read-Mo2ControlPlaneLiveBootstrapJsonFile -RuntimeRoot $runtimeRoot -FileName "status.json" -RequiredFields @("schemaVersion", "state", "mo2Pid")
    $endpoint = Read-Mo2ControlPlaneLiveBootstrapJsonFile -RuntimeRoot $runtimeRoot -FileName "endpoint.json" -RequiredFields @("schemaVersion", "transport")
    $capabilities = $null

    if ([string]::IsNullOrWhiteSpace([string]$status.state)) {
        throw "Malformed live bootstrap file: status.json"
    }

    if (-not (Test-Mo2ControlPlaneLiveBootstrapProcess -ProcessId $status.mo2Pid)) {
        throw "Stale live bootstrap file: status.json"
    }

    if ([string]::IsNullOrWhiteSpace([string]$endpoint.transport)) {
        throw "Malformed live bootstrap file: endpoint.json"
    }

    if ([string]$endpoint.transport -eq "named-pipe") {
        $null = Get-Mo2ControlPlaneIpcDiscoveryValue -Endpoint $endpoint
    }
    elseif ([string]$endpoint.transport -eq "stdio") {
        $capabilities = Read-Mo2ControlPlaneLiveBootstrapJsonFile -RuntimeRoot $runtimeRoot -FileName "capabilities.json" -RequiredFields @("schemaVersion", "methods")

        if ($capabilities.methods -isnot [System.Collections.IEnumerable] -or $capabilities.methods -is [string]) {
            throw "Malformed live bootstrap file: capabilities.json"
        }

        foreach ($methodName in $capabilities.methods) {
            if ([string]::IsNullOrWhiteSpace([string]$methodName)) {
                throw "Malformed live bootstrap file: capabilities.json"
            }
        }
    }
    else {
        throw "Unsupported live bootstrap transport: $($endpoint.transport)"
    }

    return [ordered]@{
        root = $runtimeRoot
        status = $status
        capabilities = $capabilities
        endpoint = $endpoint
    }
}

function Invoke-Mo2ControlPlaneLiveBootstrapRequest {
    param(
        [hashtable]$Request,
        [string]$LiveRoot
    )

    try {
        $runtime = Get-Mo2ControlPlaneLiveBootstrapRuntime -LiveRoot $LiveRoot

        if ([string]$runtime.endpoint.transport -eq "named-pipe") {
            return Invoke-Mo2ControlPlaneNamedPipeRequest -Request $Request -Endpoint $runtime.endpoint
        }

        if ($runtime.capabilities.methods -notcontains $Request.command) {
            throw "Live bootstrap does not advertise command: $($Request.command)"
        }

        switch ($Request.command) {
            "system.ping" {
                $result = [ordered]@{
                    status = [string]$runtime.status.state
                }
            }
            "system.capabilities" {
                $result = [ordered]@{
                    commands = @(
                        foreach ($commandName in (Get-Mo2ControlPlaneLiveBootstrapSupportedCommands)) {
                            if ($runtime.capabilities.methods -contains $commandName) {
                                $commandName
                            }
                        }
                    )
                }
            }
            default {
                $error = New-Mo2ControlPlaneError -Code "unsupported_command" -Message "Live bootstrap does not support command: $($Request.command)"
                return New-Mo2ControlPlaneResponse -Request $Request -Ok $false -Error $error
            }
        }

        return New-Mo2ControlPlaneResponse -Request $Request -Ok $true -Result $result
    }
    catch {
        $error = New-Mo2ControlPlaneError -Code "transport_error" -Message $_.Exception.Message
        return New-Mo2ControlPlaneResponse -Request $Request -Ok $false -Error $error
    }
}

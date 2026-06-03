function New-Mo2ControlPlaneRequest {
    param(
        [string]$SessionId,
        [string]$Command,
        [object]$Payload
    )

    return [ordered]@{
        protocol_version = Get-Mo2ControlPlaneProtocolVersion
        request_id = New-Mo2ControlPlaneRequestId
        session_id = $SessionId
        command = $Command
        payload = $Payload
    }
}

function New-Mo2ControlPlaneError {
    param(
        [string]$Code,
        [string]$Message,
        [object]$Details = $null
    )

    return [ordered]@{
        code = $Code
        message = $Message
        details = $Details
    }
}

function New-Mo2ControlPlaneResponse {
    param(
        [hashtable]$Request,
        [bool]$Ok,
        [object]$Result = $null,
        [object]$Error = $null
    )

    return [ordered]@{
        protocol_version = Get-Mo2ControlPlaneProtocolVersion
        request_id = $Request.request_id
        session_id = $Request.session_id
        ok = $Ok
        result = $Result
        error = $Error
    }
}

function Get-Mo2ControlPlaneCommandClassMetadata {
    return @{
        "safe-read" = [ordered]@{
            name = "safe-read"
            description = "Read-only command with no persistent side effects."
        }
        "controlled-write" = [ordered]@{
            name = "controlled-write"
            description = "Mutation command that should stay gated behind broker policy."
        }
        "dangerous-write" = [ordered]@{
            name = "dangerous-write"
            description = "High-risk mutation command requiring explicit policy review."
        }
    }
}

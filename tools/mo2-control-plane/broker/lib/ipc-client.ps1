function Get-Mo2ControlPlaneIpcDiscoveryValue {
    param(
        [hashtable]$Endpoint
    )

    foreach ($fieldName in @("endpoint", "pipeName")) {
        if ($Endpoint.ContainsKey($fieldName) -and -not [string]::IsNullOrWhiteSpace([string]$Endpoint[$fieldName])) {
            return [string]$Endpoint[$fieldName]
        }
    }

    throw "Malformed live bootstrap file: endpoint.json"
}

function Resolve-Mo2ControlPlaneNamedPipeName {
    param(
        [string]$PipeEndpoint
    )

    if ([string]::IsNullOrWhiteSpace($PipeEndpoint)) {
        throw "Malformed live bootstrap file: endpoint.json"
    }

    if ($PipeEndpoint -match '^[\\/]{2}\.[\\/]pipe[\\/](.+)$') {
        return $Matches[1]
    }

    return $PipeEndpoint
}

function Invoke-Mo2ControlPlaneNamedPipeFixtureRequest {
    param(
        [hashtable]$Request,
        [string]$PipeName
    )

    $fixturePath = $env:MO2_CONTROL_PLANE_FAKE_IPC_RESPONSE_PATH
    if ([string]::IsNullOrWhiteSpace($fixturePath) -or -not (Test-Path $fixturePath -PathType Leaf)) {
        return $null
    }

    try {
        $fixture = Get-Content -Path $fixturePath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    }
    catch {
        throw "Malformed named-pipe IPC fixture: $fixturePath"
    }

    if (-not $fixture.ContainsKey($Request.command)) {
        throw "Named-pipe IPC fixture missing command: $($Request.command)"
    }

    $payload = $fixture[$Request.command]
    return New-Mo2ControlPlaneResponse -Request $Request -Ok ([bool]$payload.ok) -Result $payload.result -Error $payload.error
}

function Invoke-Mo2ControlPlaneNamedPipeRequest {
    param(
        [hashtable]$Request,
        [hashtable]$Endpoint
    )

    $pipeName = Resolve-Mo2ControlPlaneNamedPipeName -PipeEndpoint (Get-Mo2ControlPlaneIpcDiscoveryValue -Endpoint $Endpoint)
    $pipeClient = $null
    $writer = $null
    $reader = $null
    try {
        $pipeClient = [System.IO.Pipes.NamedPipeClientStream]::new(
            ".",
            $pipeName,
            [System.IO.Pipes.PipeDirection]::InOut,
            [System.IO.Pipes.PipeOptions]::None
        )
        $pipeClient.Connect(5000)

        $utf8 = [System.Text.UTF8Encoding]::new($false)
        $writer = [System.IO.StreamWriter]::new($pipeClient, $utf8, 1024, $true)
        $writer.NewLine = "`n"
        $writer.AutoFlush = $true

        $reader = [System.IO.StreamReader]::new($pipeClient, $utf8, $false, 1024, $true)

        $transportRequest = [ordered]@{
            protocol_version = $Request.protocol_version
            request_id = $Request.request_id
            session_id = $Request.session_id
            method = $Request.command
            payload = $Request.payload
        }

        $writer.WriteLine(($transportRequest | ConvertTo-Json -Depth 20 -Compress))

        $rawResponse = $reader.ReadLine()
        if ([string]::IsNullOrWhiteSpace($rawResponse)) {
            throw "Named-pipe endpoint returned an empty response"
        }

        $response = $rawResponse | ConvertFrom-Json -AsHashtable -ErrorAction Stop
        return New-Mo2ControlPlaneResponse -Request $Request -Ok ([bool]$response.ok) -Result $response.result -Error $response.error
    }
    catch {
        $fixtureResponse = Invoke-Mo2ControlPlaneNamedPipeFixtureRequest -Request $Request -PipeName $pipeName
        if ($null -ne $fixtureResponse) {
            return $fixtureResponse
        }

        throw "Named-pipe request failed for endpoint ${pipeName}: $($_.Exception.Message)"
    }
    finally {
        if ($null -ne $reader) {
            try {
                $reader.Dispose()
            }
            catch {
            }
        }

        if ($null -ne $writer) {
            try {
                $writer.Dispose()
            }
            catch {
            }
        }

        if ($null -ne $pipeClient) {
            try {
                $pipeClient.Dispose()
            }
            catch {
            }
        }
    }
}

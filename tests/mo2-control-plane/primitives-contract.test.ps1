$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$cliPath = Join-Path $repoRoot "tools/mo2-control-plane/broker/bin/mo2-cli.ps1"
$fixturePath = Join-Path $PSScriptRoot "fixtures/fake-kernel-response.json"

$primitiveExpectations = @(
    @{ Command = "profile.list"; SafetyLevel = "CommandSafetyLevel::SafeRead" }
    @{ Command = "profile.get-current"; SafetyLevel = "CommandSafetyLevel::SafeRead" }
    @{ Command = "profile.set-current"; SafetyLevel = "CommandSafetyLevel::ControlledWrite" }
    @{ Command = "executables.list"; SafetyLevel = "CommandSafetyLevel::SafeRead" }
    @{ Command = "executables.get"; SafetyLevel = "CommandSafetyLevel::SafeRead" }
    @{ Command = "mods.list"; SafetyLevel = "CommandSafetyLevel::SafeRead" }
    @{ Command = "plugins.list"; SafetyLevel = "CommandSafetyLevel::SafeRead" }
    @{ Command = "organizer.refresh"; SafetyLevel = "CommandSafetyLevel::ControlledWrite" }
    @{ Command = "launch.start"; SafetyLevel = "CommandSafetyLevel::ControlledWrite" }
    @{ Command = "launch.status"; SafetyLevel = "CommandSafetyLevel::SafeRead" }
    @{ Command = "launch.wait"; SafetyLevel = "CommandSafetyLevel::SafeRead" }
    @{ Command = "launch.stop"; SafetyLevel = "CommandSafetyLevel::ControlledWrite" }
)

function Invoke-Cli {
    param(
        [string[]]$Arguments
    )

    $output = & pwsh -NoProfile -File $cliPath @Arguments 2>&1

    return [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = ($output | ForEach-Object { $_.ToString() }) -join "`n"
    }
}

$registryImplementation = Get-Content -Path (Join-Path $repoRoot "tools/mo2-control-plane/plugin/src/CommandRegistry.cpp") -Raw
foreach ($primitive in $primitiveExpectations) {
    if ($registryImplementation -notmatch [regex]::Escape($primitive.Command)) {
        throw "Command registry is missing primitive command: $($primitive.Command)"
    }

    $expectedEntry = ('{{"{0}", {1}}}' -f $primitive.Command, $primitive.SafetyLevel)
    if ($registryImplementation -notmatch [regex]::Escape($expectedEntry)) {
        throw "Command registry is missing primitive safety classification: $($primitive.Command) -> $($primitive.SafetyLevel)"
    }
}

$env:MO2_CONTROL_PLANE_FAKE_RESPONSE_PATH = $fixturePath

$capabilities = Invoke-Cli -Arguments @("system", "capabilities")
if ($capabilities.ExitCode -ne 0) {
    throw "system capabilities should succeed while advertising MO2 primitive commands"
}

$capabilitiesJson = $capabilities.Output | ConvertFrom-Json -ErrorAction Stop
foreach ($primitive in $primitiveExpectations) {
    if ($capabilitiesJson.result.commands -notcontains $primitive.Command) {
        throw "system capabilities should advertise primitive command: $($primitive.Command)"
    }
}

$sessionOpen = Invoke-Cli -Arguments @("session", "open")
if ($sessionOpen.ExitCode -ne 0) {
    throw "session open should succeed before routing primitive commands"
}

$sessionOpenJson = $sessionOpen.Output | ConvertFrom-Json -ErrorAction Stop
$sessionId = $sessionOpenJson.result.session_id

foreach ($primitive in $primitiveExpectations) {
    $parts = $primitive.Command.Split('.', 2)
    $arguments = @($parts[0], $parts[1], "--session-id", $sessionId)
    if ($primitive.Command -in @("launch.status", "launch.wait", "launch.stop")) {
        $arguments += @("--launch-id", "launch-test")
    }

    $result = Invoke-Cli -Arguments $arguments

    $resultJson = $result.Output | ConvertFrom-Json -ErrorAction Stop
    if ($primitive.Command -like "launch.*") {
        if ($result.ExitCode -eq 0) {
            throw "Primitive launch route should fail closed for $($primitive.Command) without a real transport"
        }

        if ($resultJson.ok) {
            throw "Primitive launch route should return ok=false for $($primitive.Command) without a real transport"
        }

        if ($resultJson.error.code -ne "transport_error") {
            throw "Primitive launch route should surface transport_error for $($primitive.Command) without a real transport"
        }

        if ($resultJson.error.message -notmatch [regex]::Escape("Launch command requires fake kernel or explicit transport payload: $($primitive.Command)")) {
            throw "Primitive launch route should explain the missing real transport for $($primitive.Command)"
        }

        continue
    }

    if ($result.ExitCode -ne 0) {
        throw "Primitive route should succeed for $($primitive.Command): $($result.Output)"
    }

    if (-not $resultJson.ok) {
        throw "Primitive route should return ok=true for $($primitive.Command)"
    }

    if ($resultJson.result.command -ne $primitive.Command) {
        throw "Primitive route should preserve command name for $($primitive.Command)"
    }

    if ($resultJson.result.stub -ne $true) {
        throw "Primitive route should return a stub marker for $($primitive.Command)"
    }
}

Write-Host "MO2 primitive contract checks passed."

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

$requiredPaths = @(
    "tools/mo2-control-plane/plugin/CMakeLists.txt",
    "tools/mo2-control-plane/plugin/src/Mo2AgentControlPlugin.h",
    "tools/mo2-control-plane/plugin/src/Mo2AgentControlPlugin.cpp",
    "tools/mo2-control-plane/plugin/src/CommandRegistry.h",
    "tools/mo2-control-plane/plugin/src/CommandRegistry.cpp",
    "tools/mo2-control-plane/plugin/src/ProtocolTypes.h"
)

foreach ($path in $requiredPaths) {
    if (-not (Test-Path (Join-Path $repoRoot $path))) {
        throw "Missing plugin scaffold path: $path"
    }
}

$pluginHeader = Get-Content -Path (Join-Path $repoRoot "tools/mo2-control-plane/plugin/src/Mo2AgentControlPlugin.h") -Raw
foreach ($phrase in @(
    "class Mo2AgentControlPlugin",
    "CommandRegistry"
)) {
    if ($pluginHeader -notmatch [regex]::Escape($phrase)) {
        throw "Mo2AgentControlPlugin.h is missing phrase: $phrase"
    }
}

$registryHeader = Get-Content -Path (Join-Path $repoRoot "tools/mo2-control-plane/plugin/src/CommandRegistry.h") -Raw
foreach ($phrase in @(
    "enum class CommandSafetyLevel",
    "struct RegisteredCommand",
    "CommandRegistry"
)) {
    if ($registryHeader -notmatch [regex]::Escape($phrase)) {
        throw "CommandRegistry.h is missing phrase: $phrase"
    }
}

$registryImplementation = Get-Content -Path (Join-Path $repoRoot "tools/mo2-control-plane/plugin/src/CommandRegistry.cpp") -Raw
foreach ($commandName in @(
    "system.ping",
    "system.capabilities",
    "system.status"
)) {
    if ($registryImplementation -notmatch [regex]::Escape($commandName)) {
        throw "Command registry is missing foundation command: $commandName"
    }
}

if ($registryImplementation -notmatch [regex]::Escape("CommandSafetyLevel::SafeRead")) {
    throw "Command registry is missing safety classification"
}

if ($registryImplementation -match [regex]::Escape("const_cast")) {
    throw "Command registry should not use const_cast-based lazy initialization"
}

if ($registryHeader -notmatch [regex]::Escape("CommandRegistry();")) {
    throw "CommandRegistry.h is missing an eager initialization constructor"
}

$protocolHeader = Get-Content -Path (Join-Path $repoRoot "tools/mo2-control-plane/plugin/src/ProtocolTypes.h") -Raw
foreach ($phrase in @(
    "protocolVersion",
    "requestId",
    "sessionId",
    "command"
)) {
    if ($protocolHeader -notmatch [regex]::Escape($phrase)) {
        throw "ProtocolTypes.h is missing phrase: $phrase"
    }
}

Write-Host "MO2 plugin scaffold contract checks passed."

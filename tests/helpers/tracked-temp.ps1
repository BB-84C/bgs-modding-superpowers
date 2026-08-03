$ErrorActionPreference = "Stop"

$script:TrackedTestTempDirectories = [System.Collections.Generic.List[string]]::new()

function Register-TrackedTestTempDirectory {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) { throw "Tracked temp path is required." }
    if (-not $script:TrackedTestTempDirectories.Contains($Path)) {
        $script:TrackedTestTempDirectories.Add($Path)
    }
    return $Path
}

function New-TrackedTestTempDirectory {
    param([Parameter(Mandatory = $true)][string]$Prefix)

    $path = Join-Path ([System.IO.Path]::GetTempPath()) ($Prefix + [guid]::NewGuid().ToString("N"))
    $null = New-Item -ItemType Directory -Path $path -Force
    return Register-TrackedTestTempDirectory -Path $path
}

function Remove-TrackedTestTempDirectories {
    $paths = @($script:TrackedTestTempDirectories)
    $script:TrackedTestTempDirectories.Clear()
    foreach ($path in $paths) {
        if (Test-Path $path -PathType Container) {
            Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

#requires -Version 5.1
<#
.SYNOPSIS
  One-shot Codex installer for bgs-modding-superpowers.

.DESCRIPTION
  Codex's `codex plugin add` only installs the plugin's skills + hooks. It does
  NOT auto-import .mcp.json. This script wraps the full install: marketplace
  add, plugin add, and MCP-server wiring for `xedit` and `bgs_kb`. Idempotent
  on every step (safe to re-run; safe to re-run after a plugin upgrade to
  re-point MCP paths at the new cache location).

  Steps:
    1. Verify `codex` is on PATH.
    2. Add the marketplace (skipped if already present; refreshed via
       `codex plugin marketplace upgrade` instead).
    3. Install the plugin (skipped if already installed).
    4. Resolve the on-disk plugin path from `codex plugin list` output.
    5. Register `xedit` and `bgs_kb` MCP servers via `codex mcp add`
       (removed+re-added if they already exist, so paths stay fresh).

.PARAMETER Source
  Marketplace source spec accepted by `codex plugin marketplace add`. Accepts
  `owner/repo[@ref]`, an HTTPS URL, an SSH URL, or a local path.
  Default: "BB-84C/bgs-modding-superpowers"

.PARAMETER Marketplace
  Marketplace name Codex will use for this entry. Must match the `name` field
  inside the marketplace's `.agents/plugins/marketplace.json`. Defaults to
  "bgs-modding-superpowers" (the value committed to this repo).

.PARAMETER Plugin
  Plugin name to install from the marketplace. Default: "bgs-modding-superpowers".

.PARAMETER McpOnly
  Skip the marketplace+plugin install steps; only resolve the installed plugin
  path and re-wire MCP servers. Use this after a manual `codex plugin add` or
  after a plugin upgrade.

.PARAMETER SkipMcp
  Run the marketplace+plugin install but do not touch `codex mcp`. Useful for
  documentation-only installs that don't need the MCP runtime.

.PARAMETER Ref
  Optional git ref forwarded to `codex plugin marketplace add --ref`.

.EXAMPLE
  pwsh scripts/install-codex.ps1

  Full install from GitHub main.

.EXAMPLE
  iwr -useb https://raw.githubusercontent.com/BB-84C/bgs-modding-superpowers/main/scripts/install-codex.ps1 | iex

  One-liner from any PowerShell prompt. (Inspect the script first if you don't
  trust remote execution; the manual path in README.md is equivalent.)

.EXAMPLE
  pwsh scripts/install-codex.ps1 -McpOnly

  Re-wire the two MCP servers against the currently-installed plugin path.
  Useful after `codex plugin marketplace upgrade`.
#>

[CmdletBinding()]
param(
  [string]$Source       = "BB-84C/bgs-modding-superpowers",
  [string]$Marketplace  = "bgs-modding-superpowers",
  [string]$Plugin       = "bgs-modding-superpowers",
  [string]$Ref          = "",
  [switch]$McpOnly,
  [switch]$SkipMcp
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step  ($msg) { Write-Host "[install-codex] $msg" -ForegroundColor Cyan }
function Write-Ok    ($msg) { Write-Host "[install-codex] $msg" -ForegroundColor Green }
function Write-Warn2 ($msg) { Write-Host "[install-codex] $msg" -ForegroundColor Yellow }

# ---- 1. preflight: codex CLI on PATH ---------------------------------------
$codex = Get-Command codex -ErrorAction SilentlyContinue
if (-not $codex) {
  throw "codex CLI not found on PATH. Install it from https://github.com/openai/codex first."
}
Write-Step "codex found: $($codex.Source)"

# ---- helpers ----------------------------------------------------------------
function Invoke-Codex {
  param([string[]]$Args)
  # Capture stdout+stderr; return $LASTEXITCODE so callers can decide.
  $out = & codex @Args 2>&1
  return @{ ExitCode = $LASTEXITCODE; Output = ($out -join "`n") }
}

function Test-MarketplaceExists {
  param([string]$Name)
  $r = Invoke-Codex -Args @("plugin", "marketplace", "list")
  if ($r.ExitCode -ne 0) { return $false }
  return ($r.Output -split "`n") | Where-Object { $_ -match "^\s*$([regex]::Escape($Name))\s+" } | Select-Object -First 1
}

function Test-PluginInstalled {
  param([string]$Plugin, [string]$Marketplace)
  $r = Invoke-Codex -Args @("plugin", "list", "--marketplace", $Marketplace)
  if ($r.ExitCode -ne 0) { return $false }
  $needle = "$Plugin@$Marketplace"
  return ($r.Output -split "`n") | Where-Object { $_ -match "^\s*$([regex]::Escape($needle))\s+installed" } | Select-Object -First 1
}

function Get-InstalledPluginPath {
  param([string]$Plugin, [string]$Marketplace)
  $r = Invoke-Codex -Args @("plugin", "list", "--marketplace", $Marketplace)
  if ($r.ExitCode -ne 0) {
    throw "codex plugin list failed: $($r.Output)"
  }
  $needle = "$Plugin@$Marketplace"
  $line = ($r.Output -split "`n") | Where-Object { $_ -match "^\s*$([regex]::Escape($needle))\s+" } | Select-Object -First 1
  if (-not $line) {
    throw "Plugin '$needle' is not visible in `codex plugin list --marketplace $Marketplace`."
  }
  # Output format (whitespace-aligned columns):
  #   PLUGIN                   STATUS              VERSION  PATH
  #   bgs-...@bgs-...          installed, enabled  0.2.0    C:\...\plugins\bgs-modding-superpowers
  # PATH is the last column; rsplit on 2+ spaces gives reliable separation.
  $cols = [regex]::Split($line, "\s{2,}")
  $path = $cols[-1].Trim()
  if (-not $path -or -not (Test-Path -LiteralPath $path)) {
    throw "Resolved plugin path does not exist on disk: '$path'. Try `codex plugin marketplace upgrade $Marketplace` and re-run with -McpOnly."
  }
  return $path
}

function Test-McpServerExists {
  param([string]$Name)
  $r = Invoke-Codex -Args @("mcp", "list")
  if ($r.ExitCode -ne 0) { return $false }
  return ($r.Output -split "`n") | Where-Object { $_ -match "^\s*$([regex]::Escape($Name))\s+" } | Select-Object -First 1
}

function Add-McpServer {
  param([string]$Name, [string]$Command, [string[]]$ArgsList)
  if (Test-McpServerExists -Name $Name) {
    Write-Warn2 "MCP server '$Name' already configured; removing+re-adding to refresh path."
    $rm = Invoke-Codex -Args @("mcp", "remove", $Name)
    if ($rm.ExitCode -ne 0) {
      Write-Warn2 "  codex mcp remove $Name returned non-zero (continuing): $($rm.Output)"
    }
  }
  $addArgs = @("mcp", "add", $Name, "--", $Command) + $ArgsList
  $add = Invoke-Codex -Args $addArgs
  if ($add.ExitCode -ne 0) {
    throw "codex mcp add $Name failed: $($add.Output)"
  }
  Write-Ok "  registered MCP server '$Name' -> $Command $($ArgsList -join ' ')"
}

# ---- 2. add marketplace -----------------------------------------------------
if (-not $McpOnly) {
  Write-Step "Step 1/3: marketplace '$Marketplace' from source '$Source'"
  $existing = Test-MarketplaceExists -Name $Marketplace
  if ($existing) {
    Write-Warn2 "  marketplace '$Marketplace' already registered; refreshing via `codex plugin marketplace upgrade`."
    $up = Invoke-Codex -Args @("plugin", "marketplace", "upgrade", $Marketplace)
    if ($up.ExitCode -ne 0) {
      Write-Warn2 "  upgrade returned non-zero (continuing): $($up.Output)"
    }
  } else {
    $addArgs = @("plugin", "marketplace", "add", $Source)
    if ($Ref) { $addArgs += @("--ref", $Ref) }
    $add = Invoke-Codex -Args $addArgs
    if ($add.ExitCode -ne 0) {
      throw "codex plugin marketplace add $Source failed: $($add.Output)"
    }
    Write-Ok "  added marketplace '$Marketplace'."
  }

  # ---- 3. install plugin ----------------------------------------------------
  Write-Step "Step 2/3: install plugin '$Plugin@$Marketplace'"
  if (Test-PluginInstalled -Plugin $Plugin -Marketplace $Marketplace) {
    Write-Warn2 "  plugin '$Plugin@$Marketplace' already installed; skipping."
  } else {
    $sel = "$Plugin@$Marketplace"
    $add = Invoke-Codex -Args @("plugin", "add", $sel)
    if ($add.ExitCode -ne 0) {
      throw "codex plugin add $sel failed: $($add.Output)"
    }
    Write-Ok "  installed plugin '$sel'."
  }
} else {
  Write-Step "[-McpOnly] skipping marketplace + plugin install steps."
}

# ---- 4. wire MCP servers ----------------------------------------------------
if ($SkipMcp) {
  Write-Warn2 "[-SkipMcp] skipping MCP server registration."
  Write-Ok "Done. Plugin installed without MCP wiring."
  return
}

Write-Step "Step 3/3: wire MCP servers (xedit, bgs_kb)"
$pluginPath = Get-InstalledPluginPath -Plugin $Plugin -Marketplace $Marketplace
Write-Step "  resolved plugin path: $pluginPath"

$xeditEntry = Join-Path $pluginPath "tools\xedit-mcp\dist\index.js"
$kbEntry    = Join-Path $pluginPath "tools\bgs-kb-mcp\dist\index.js"

foreach ($entry in @($xeditEntry, $kbEntry)) {
  if (-not (Test-Path -LiteralPath $entry)) {
    throw "Required MCP entrypoint missing: $entry. The plugin install may be incomplete; try `codex plugin marketplace upgrade $Marketplace`."
  }
}

Add-McpServer -Name "xedit"  -Command "node" -ArgsList @($xeditEntry)
Add-McpServer -Name "bgs_kb" -Command "node" -ArgsList @($kbEntry)

Write-Ok ""
Write-Ok "============================================================"
Write-Ok " bgs-modding-superpowers installed for Codex."
Write-Ok "   plugin path: $pluginPath"
Write-Ok "   MCP servers: xedit, bgs_kb"
Write-Ok ""
Write-Ok " Restart any open Codex sessions for changes to take effect."
Write-Ok " Verify with:  codex mcp list"
Write-Ok "============================================================"

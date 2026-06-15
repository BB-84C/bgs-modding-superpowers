[CmdletBinding()]
param(
  [string]$Mo2Root = "B:\WastelandBlues 2.0",
  [string]$Profile = "BB84自用"
)

$env:MO2_MCP_ACCEPTANCE = "1"
$env:BGS_MO2_ROOT = $Mo2Root
$env:BGS_MO2_PROFILE = $Profile

Push-Location "$PSScriptRoot\..\tools\mo2-mcp"
try {
  npm run build
  if ($LASTEXITCODE -ne 0) { throw "build failed" }
  npx vitest run tests/acceptance-v1.test.ts
}
finally {
  Pop-Location
  Remove-Item env:MO2_MCP_ACCEPTANCE -ErrorAction SilentlyContinue
  Remove-Item env:BGS_MO2_ROOT -ErrorAction SilentlyContinue
  Remove-Item env:BGS_MO2_PROFILE -ErrorAction SilentlyContinue
}

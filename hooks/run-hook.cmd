@echo off
REM Windows shim for bgs-modding-superpowers hook dispatch.
REM Routes `<shim> session-start` to printing the bootstrap SKILL body.

setlocal
set "PLUGIN_ROOT=%~dp0.."
set "HOOK_NAME=%~1"

if /I "%HOOK_NAME%"=="session-start" (
  set "BOOTSTRAP=%PLUGIN_ROOT%\skills\using-bgs-modding-superpowers\SKILL.md"
  if exist "%BOOTSTRAP%" type "%BOOTSTRAP%"
)
endlocal

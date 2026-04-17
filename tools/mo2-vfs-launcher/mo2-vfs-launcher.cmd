@echo off
setlocal
set "SCRIPT_PATH=%~dp0mo2-vfs-launcher.ps1"
pwsh -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_PATH%" %*
exit /b %ERRORLEVEL%

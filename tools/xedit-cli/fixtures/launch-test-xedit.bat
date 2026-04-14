@echo off
if "%XEDIT_CLI_TEST_EXE%"=="" exit /b 1
start "" "%XEDIT_CLI_TEST_EXE%" /c ping -n 30 127.0.0.1 ^> nul

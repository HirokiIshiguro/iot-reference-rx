@echo off
setlocal

set "E2L_SERIAL=%~1"
if "%E2L_SERIAL%"=="" (
    echo ERROR: E2 Lite serial number required.
    echo Usage: flash.bat ^<E2L_SERIAL^> [REPO_ROOT] [USERPROG_MOT]
    echo.
    echo To find available E2 Lite devices:
    echo   rfp-cli -d RX65x -t e2l -if fine -list-tools
    exit /b 1
)

set "REPO_ROOT=%~2"
if "%REPO_ROOT%"=="" set "REPO_ROOT=%~dp0.."

set "USERPROG_MOT=%~3"
if "%USERPROG_MOT%"=="" set "USERPROG_MOT=%REPO_ROOT%\userprog.mot"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0flash.ps1" -E2LSerial "%E2L_SERIAL%" -RepoRoot "%REPO_ROOT%" -UserprogMot "%USERPROG_MOT%"
exit /b %ERRORLEVEL%

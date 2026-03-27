@echo off
REM ============================================================
REM iot-reference-rx RX72N headless build wrapper
REM
REM Usage: build_headless.bat [REPO_ROOT] [E2STUDIO_CLI] [WORKSPACE]
REM
REM Prerequisites:
REM   - Git submodules must be initialized (git submodule update --init --recursive)
REM   - CC-RX v3.07 installed
REM   - e2studio with e2studio-cli installed
REM
REM This wrapper keeps the historical batch entry point working by
REM delegating to the maintained RX72N PowerShell build script.
REM ============================================================

setlocal

REM --- Parameters ---
set "REPO_ROOT=%~1"
if "%REPO_ROOT%"=="" set "REPO_ROOT=%~dp0.."

set "E2STUDIO_CLI=%~2"
if "%E2STUDIO_CLI%"=="" set "E2STUDIO_CLI=C:\Renesas\e2_studio_2025_12\eclipse\e2studioc.exe"

set "WORKSPACE=%~3"
if "%WORKSPACE%"=="" set "WORKSPACE=C:\iotref-rx72n-ws"
set "BUILD_SCRIPT=%~dp0build_headless_rx72n.ps1"
set "LOG_FILE=%REPO_ROOT%\rx72n_e2studio_build.log"

echo ============================================================
echo iot-reference-rx RX72N headless build
echo ============================================================
echo REPO_ROOT:     %REPO_ROOT%
echo E2STUDIO_CLI:  %E2STUDIO_CLI%
echo WORKSPACE:     %WORKSPACE%
echo BUILD_SCRIPT:  %BUILD_SCRIPT%
echo ============================================================

if not exist "%BUILD_SCRIPT%" (
    echo ERROR: build script not found: %BUILD_SCRIPT%
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%BUILD_SCRIPT%" ^
    -ProjectRoot "%REPO_ROOT%" ^
    -E2Studio "%E2STUDIO_CLI%" ^
    -Workspace "%WORKSPACE%" ^
    -LogFile "%LOG_FILE%"
exit /b %ERRORLEVEL%

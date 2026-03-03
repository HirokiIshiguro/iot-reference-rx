@echo off
REM ============================================================
REM iot-reference-rx headless build script for CI/CD
REM
REM Usage: build_headless.bat [REPO_ROOT] [E2STUDIO_CLI] [WORKSPACE]
REM
REM Prerequisites:
REM   - Git submodules must be initialized (git submodule update --init --recursive)
REM   - CC-RX v3.07 installed
REM   - e2studio with e2studio-cli installed
REM
REM This script:
REM   1. Imports both projects into a fresh e2studio workspace
REM   2. Builds boot_loader (HardwareDebug)
REM   3. Builds aws_ether app (HardwareDebug)
REM   4. Verifies .mot output files
REM ============================================================

setlocal enabledelayedexpansion

REM --- Parameters ---
set "REPO_ROOT=%~1"
if "%REPO_ROOT%"=="" set "REPO_ROOT=%~dp0.."

set "E2STUDIO_CLI=%~2"
if "%E2STUDIO_CLI%"=="" set "E2STUDIO_CLI=C:\Renesas\e2_studio_2025_12\eclipse\e2studio-cli.exe"

set "WORKSPACE=%~3"
if "%WORKSPACE%"=="" set "WORKSPACE=%TEMP%\e2ws_iot_ref"

REM --- Directories ---
set "APP_PROJECT_DIR=%REPO_ROOT%\Projects\aws_ether_ck_rx65n_v2\e2studio_ccrx"
set "BL_PROJECT_DIR=%REPO_ROOT%\Projects\boot_loader_ck_rx65n_v2\e2studio_ccrx"

echo ============================================================
echo iot-reference-rx headless build
echo ============================================================
echo REPO_ROOT:     %REPO_ROOT%
echo E2STUDIO_CLI:  %E2STUDIO_CLI%
echo WORKSPACE:     %WORKSPACE%
echo APP_PROJECT:   %APP_PROJECT_DIR%
echo BL_PROJECT:    %BL_PROJECT_DIR%
echo ============================================================

REM --- Verify prerequisites ---
if not exist "%E2STUDIO_CLI%" (
    echo ERROR: e2studio-cli not found: %E2STUDIO_CLI%
    exit /b 1
)

REM Verify submodules are initialized (FreeRTOS-Kernel/include must exist)
if not exist "%REPO_ROOT%\Middleware\FreeRTOS\FreeRTOS-Kernel\include\FreeRTOS.h" (
    echo ERROR: Git submodules not initialized.
    echo Run: git submodule update --init --recursive
    exit /b 1
)

REM --- Clean workspace ---
if exist "%WORKSPACE%" (
    echo Cleaning old workspace: %WORKSPACE%
    rmdir /s /q "%WORKSPACE%"
)

REM ============================================================
REM Step 1: Import projects and build boot_loader
REM ============================================================
echo.
echo === Building boot_loader_ck_rx65n_v2 and aws_ether_ck_rx65n_v2 ===

"%E2STUDIO_CLI%" -nosplash ^
    -application org.eclipse.cdt.managedbuilder.core.headlessbuild ^
    -data "%WORKSPACE%" ^
    -import "%APP_PROJECT_DIR%" ^
    -import "%BL_PROJECT_DIR%" ^
    -cleanBuild "boot_loader_ck_rx65n_v2/HardwareDebug" ^
    -cleanBuild "aws_ether_ck_rx65n_v2/HardwareDebug" ^
    -no-indexer

set BUILD_RESULT=%ERRORLEVEL%
echo Build exit code: %BUILD_RESULT%

REM ============================================================
REM Step 2: Check results
REM ============================================================
echo.
echo ============================================================
echo Build Results:

set FAIL=0

if exist "%BL_PROJECT_DIR%\HardwareDebug\boot_loader_ck_rx65n_v2.mot" (
    echo   boot_loader .mot: FOUND
) else (
    echo   boot_loader .mot: NOT FOUND
    set FAIL=1
)

if exist "%APP_PROJECT_DIR%\HardwareDebug\aws_ether_ck_rx65n_v2.mot" (
    echo   aws_ether .mot: FOUND
) else (
    echo   aws_ether .mot: NOT FOUND
    set FAIL=1
)

echo ============================================================

if %FAIL% equ 1 (
    echo ERROR: One or more .mot files missing
    exit /b 1
)

if %BUILD_RESULT% neq 0 exit /b %BUILD_RESULT%

echo BUILD SUCCESS
exit /b 0

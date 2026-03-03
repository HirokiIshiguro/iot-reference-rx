@echo off
REM ============================================================
REM iot-reference-rx flash script for CK-RX65N (V1)
REM
REM Usage: flash.bat [E2L_SERIAL] [REPO_ROOT]
REM
REM Prerequisites:
REM   - Renesas Flash Programmer V3.22 installed
REM   - E2 emulator Lite connected to CK-RX65N
REM   - Boot loader and app .mot files built (run build_headless.bat first)
REM
REM This script:
REM   1. Erases chip (resets BANKSEL, clears all flash)
REM   2. Writes boot_loader
REM   3. Writes app (preserving boot_loader region)
REM ============================================================

setlocal enabledelayedexpansion

REM --- Parameters ---
set "E2L_SERIAL=%~1"
if "%E2L_SERIAL%"=="" (
    echo ERROR: E2 Lite serial number required.
    echo Usage: flash.bat ^<E2L_SERIAL^> [REPO_ROOT]
    echo.
    echo To find available E2 Lite devices:
    echo   rfp-cli -d RX65x -t e2l -if fine -list-tools
    exit /b 1
)

set "REPO_ROOT=%~2"
if "%REPO_ROOT%"=="" set "REPO_ROOT=%~dp0.."

REM --- Tool paths ---
set "RFP_CLI=C:\Program Files (x86)\Renesas Electronics\Programming Tools\Renesas Flash Programmer V3.22\rfp-cli.exe"

REM --- File paths ---
set "BL_MOT=%REPO_ROOT%\Projects\boot_loader_ck_rx65n_v2\e2studio_ccrx\HardwareDebug\boot_loader_ck_rx65n_v2.mot"
set "APP_MOT=%REPO_ROOT%\Projects\aws_ether_ck_rx65n_v2\e2studio_ccrx\HardwareDebug\aws_ether_ck_rx65n_v2.mot"

REM --- rfp-cli common options ---
set "RFP_COMMON=-d RX65x -t "e2l:%E2L_SERIAL%" -if fine -s 500K -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"

echo ============================================================
echo iot-reference-rx flash (CK-RX65N V1)
echo ============================================================
echo E2L_SERIAL: %E2L_SERIAL%
echo REPO_ROOT:  %REPO_ROOT%
echo BL_MOT:     %BL_MOT%
echo APP_MOT:    %APP_MOT%
echo ============================================================

REM --- Verify prerequisites ---
if not exist "%RFP_CLI%" (
    echo ERROR: rfp-cli not found: %RFP_CLI%
    exit /b 1
)
if not exist "%BL_MOT%" (
    echo ERROR: boot_loader .mot not found: %BL_MOT%
    echo Run build_headless.bat first.
    exit /b 1
)
if not exist "%APP_MOT%" (
    echo ERROR: app .mot not found: %APP_MOT%
    echo Run build_headless.bat first.
    exit /b 1
)

REM ============================================================
REM Step 1: Erase chip
REM ============================================================
echo.
echo === Step 1: Erase chip ===
"%RFP_CLI%" -d RX65x -t "e2l:%E2L_SERIAL%" -if fine -s 500K -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF -erase-chip -noquery
if %ERRORLEVEL% neq 0 (
    echo ERROR: Chip erase failed (exit code: %ERRORLEVEL%)
    exit /b %ERRORLEVEL%
)
echo Chip erase: OK

REM ============================================================
REM Step 2: Write boot_loader
REM ============================================================
echo.
echo === Step 2: Write boot_loader ===
"%RFP_CLI%" -d RX65x -t "e2l:%E2L_SERIAL%" -if fine -s 500K -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF -p "%BL_MOT%" -run -noquery
if %ERRORLEVEL% neq 0 (
    echo ERROR: boot_loader write failed (exit code: %ERRORLEVEL%)
    exit /b %ERRORLEVEL%
)
echo boot_loader write: OK

REM ============================================================
REM Step 3: Write app (noerase - preserve boot_loader)
REM ============================================================
echo.
echo === Step 3: Write app ===
"%RFP_CLI%" -d RX65x -t "e2l:%E2L_SERIAL%" -if fine -s 500K -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF -file "%APP_MOT%" -auto -noerase -run -noquery
if %ERRORLEVEL% neq 0 (
    echo ERROR: app write failed (exit code: %ERRORLEVEL%)
    exit /b %ERRORLEVEL%
)
echo app write: OK

echo.
echo ============================================================
echo FLASH SUCCESS
echo ============================================================
exit /b 0

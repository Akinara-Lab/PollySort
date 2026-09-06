@echo off
REM ---------------------------------------------------------------------------
REM PollySort - Deinstallation (Windows, Doppelklick-freundlich)
REM
REM Duenner Starter fuer uninstall.ps1. Die eigentliche Arbeit macht PowerShell:
REM nur dort laesst sich der Benutzer-PATH sauber zuruecknehmen.
REM
REM   Doppelklick auf uninstall.bat   ODER   im Terminal:  uninstall.bat
REM   uninstall.bat --alles           auch die globale Ablage ~/.pollysort
REM   uninstall.bat --dry-run         zeigt nur, was passieren wuerde
REM
REM Deine Projektordner und die einsortierten Dateien bleiben IMMER unberuehrt.
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "PS="
where pwsh >nul 2>&1 && set "PS=pwsh"
if not defined PS ( where powershell >nul 2>&1 && set "PS=powershell" )

if not defined PS (
  echo [X] Weder pwsh noch powershell gefunden.
  echo     Alternativ in Git-Bash:  bash uninstall.sh
  echo.
  pause
  exit /b 1
)

set "ARGS="
:parse
if "%~1"=="" goto run
if /i "%~1"=="--alles"   set "ARGS=%ARGS% -Alles"
if /i "%~1"=="--all"     set "ARGS=%ARGS% -Alles"
if /i "%~1"=="--dry-run" set "ARGS=%ARGS% -DryRun"
if /i "%~1"=="-Alles"    set "ARGS=%ARGS% -Alles"
if /i "%~1"=="-DryRun"   set "ARGS=%ARGS% -DryRun"
shift
goto parse

:run
%PS% -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"%ARGS%
set "RC=%ERRORLEVEL%"

echo.
pause
endlocal & exit /b %RC%

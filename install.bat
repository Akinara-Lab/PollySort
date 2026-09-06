@echo off
REM ---------------------------------------------------------------------------
REM PollySort - Installer (Windows, Doppelklick-freundlich)
REM
REM Duenner Starter fuer install.ps1. Die eigentliche Arbeit macht PowerShell:
REM nur dort laesst sich der Benutzer-PATH sauber und dauerhaft setzen, damit
REM man danach ueberall einfach `pollysort` tippen kann.
REM
REM   Doppelklick auf install.bat   ODER   im Terminal:  install.bat
REM   install.bat --dry-run         zeigt nur, was passieren wuerde
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "PS="
where pwsh >nul 2>&1 && set "PS=pwsh"
if not defined PS ( where powershell >nul 2>&1 && set "PS=powershell" )

if not defined PS (
  echo [X] Weder pwsh noch powershell gefunden.
  echo     PowerShell gehoert zu Windows - bitte pruefen, ob es im PATH liegt.
  echo     Alternativ in Git-Bash:  bash install.sh
  echo.
  pause
  exit /b 1
)

REM Argumente durchreichen: --dry-run / --no-path -^> -DryRun / -NoPath
set "ARGS="
:parse
if "%~1"=="" goto run
if /i "%~1"=="--dry-run" set "ARGS=%ARGS% -DryRun"
if /i "%~1"=="--no-path" set "ARGS=%ARGS% -NoPath"
if /i "%~1"=="-DryRun"   set "ARGS=%ARGS% -DryRun"
if /i "%~1"=="-NoPath"   set "ARGS=%ARGS% -NoPath"
shift
goto parse

:run
%PS% -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"%ARGS%
set "RC=%ERRORLEVEL%"

echo.
pause
endlocal & exit /b %RC%

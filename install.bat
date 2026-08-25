@echo off
REM ---------------------------------------------------------------------------
REM PollySort - Installer (Windows)
REM Prueft die Voraussetzungen und installiert das Tool isoliert (uv -^> pipx -^> pip).
REM Nutzung: Doppelklick auf install.bat  ODER  im Terminal:  install.bat
REM ---------------------------------------------------------------------------
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ===  PollySort-Installer  ===
echo.

REM 1) Richtiger Ordner?
if not exist "pyproject.toml" (
  echo [X] pyproject.toml nicht gefunden - bitte install.bat im PollySort-Ordner ausfuehren.
  goto :fail
)
echo [ok] Projektdateien gefunden

REM 2) Python vorhanden? (py-Launcher bevorzugt, sonst python)
set "PY="
where py >nul 2>&1 && set "PY=py"
if not defined PY ( where python >nul 2>&1 && set "PY=python" )
if not defined PY (
  echo [X] Python nicht gefunden. Bitte Python 3.12+ installieren:
  echo     https://www.python.org/downloads/
  goto :fail
)

REM 3) Python-Version 3.12+?
%PY% -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 12) else 1)"
if errorlevel 1 (
  echo [X] Python 3.12+ benoetigt. Bitte aktualisieren: https://www.python.org/downloads/
  goto :fail
)
for /f "delims=" %%v in ('%PY% -c "import platform; print(platform.python_version())"') do set "PYV=%%v"
echo [ok] Python !PYV! gefunden

REM 4) Bestes Installationswerkzeug waehlen: uv -^> pipx -^> pip
echo.
echo Installiere PollySort (mit Text-Extraktion [extract]) ...
where uv >nul 2>&1
if not errorlevel 1 (
  echo [ok] uv erkannt
  uv tool install --force ".[extract]"
  goto :verify
)
where pipx >nul 2>&1
if not errorlevel 1 (
  echo [ok] pipx erkannt
  pipx install --force ".[extract]"
  goto :verify
)
echo [ok] Weder uv noch pipx gefunden - verwende pip (Benutzer-Installation)
%PY% -m pip install --user ".[extract]"

:verify
echo.
echo Pruefe Installation ...
where bumble >nul 2>&1
if errorlevel 1 (
  echo [!] 'bumble' ist noch nicht im PATH.
  echo     Tipp: Terminal neu oeffnen, oder 'pipx ensurepath' ausfuehren, dann erneut versuchen.
  echo     Alternativ direkt starten:  %PY% Beehive.py
  goto :end
)
echo [ok] Befehl 'bumble' verfuegbar
bumble-cli --version
echo.
echo Fertig! Starte das Tool mit:  bumble
goto :end

:fail
echo.
echo Installation abgebrochen.
echo.
pause
exit /b 1

:end
echo.
pause
endlocal

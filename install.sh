#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# PollySort — Installer (Linux / macOS / Git-Bash)
# Prüft die Voraussetzungen und installiert das Tool isoliert (uv → pipx → pip).
# Nutzung:  bash install.sh        (ggf. vorher: chmod +x install.sh)
# ---------------------------------------------------------------------------
set -euo pipefail

say() { printf '\n\033[1;33m🐝  %s\033[0m\n' "$1"; }
ok()  { printf '   \033[32m✓\033[0m %s\n' "$1"; }
err() { printf '   \033[31m✗ %s\033[0m\n' "$1" >&2; }

# Immer aus dem Ordner dieses Skripts arbeiten (= Projekt-Root).
cd "$(dirname "$0")"

say "PollySort-Installer"

# 1) Richtiger Ordner?
if [ ! -f pyproject.toml ]; then
  err "pyproject.toml nicht gefunden — bitte install.sh im PollySort-Ordner ausführen."
  exit 1
fi
ok "Projektdateien gefunden"

# 2) Python vorhanden?
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  err "Python nicht gefunden. Bitte Python 3.12+ installieren: https://www.python.org/downloads/"
  exit 1
fi

# 3) Python-Version >= 3.12?
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 12) else 1)'; then
  V=$("$PY" -c 'import platform; print(platform.python_version())')
  err "Python 3.12+ benötigt (gefunden $V). Bitte aktualisieren."
  exit 1
fi
ok "Python $("$PY" -c 'import platform; print(platform.python_version())') gefunden"

# 4) Bestes Installationswerkzeug wählen: uv → pipx → pip.
say "Installiere PollySort (mit Text-Extraktion [extract]) …"
if command -v uv >/dev/null 2>&1; then
  ok "uv erkannt"
  uv tool install --force ".[extract]"
elif command -v pipx >/dev/null 2>&1; then
  ok "pipx erkannt"
  pipx install --force ".[extract]"
else
  ok "Weder uv noch pipx gefunden — verwende pip (Benutzer-Installation)"
  "$PY" -m pip install --user ".[extract]"
fi

# 5) Ergebnis prüfen.
say "Prüfe Installation …"
if command -v pollysort >/dev/null 2>&1; then
  ok "Befehl 'pollysort' verfügbar — $(pollysort-cli --version 2>/dev/null || echo 'bereit')"
  say "Fertig! Starte das Tool mit:  pollysort"
else
  err "'pollysort' ist noch nicht im PATH."
  echo "   Tipp: Terminal neu öffnen, oder 'pipx ensurepath' (bzw. 'uv tool update-shell')"
  echo "   ausführen und erneut versuchen. Alternativ direkt: $PY polly.py"
  exit 1
fi

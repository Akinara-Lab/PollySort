#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# PollySort — Installer für Linux, macOS und Git-Bash (Windows)
#
# Installiert das Tool isoliert (uv → pipx → pip --user) und sorgt dafür, dass der
# Befehl `pollysort` danach wirklich im PATH liegt — in dieser Shell und dauerhaft.
#
#   bash install.sh              installieren
#   bash install.sh --no-path    installieren, PATH NICHT anfassen
#   bash install.sh --dry-run    nur zeigen, was passieren würde
# ---------------------------------------------------------------------------
set -euo pipefail

say()  { printf '\n\033[1;33m🐝  %s\033[0m\n' "$1"; }
ok()   { printf '   \033[32m✓\033[0m %s\n' "$1"; }
info() { printf '   %s\n' "$1"; }
warn() { printf '   \033[33m!\033[0m %s\n' "$1"; }
err()  { printf '   \033[31m✗ %s\033[0m\n' "$1" >&2; }

TOUCH_PATH=1
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --no-path) TOUCH_PATH=0 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) err "Unbekannte Option: $arg"; exit 2 ;;
  esac
done

run() { if [ "$DRY_RUN" = 1 ]; then info "[dry-run] $*"; else "$@"; fi; }

cd "$(dirname "$0")"
say "PollySort-Installer"
[ "$DRY_RUN" = 1 ] && warn "Trockenlauf — es wird nichts verändert."

# --------------------------------------------------------------------------- #
# 1) Voraussetzungen
# --------------------------------------------------------------------------- #
if [ ! -f pyproject.toml ]; then
  err "pyproject.toml nicht gefunden — bitte install.sh im PollySort-Ordner ausführen."
  exit 1
fi
ok "Projektdateien gefunden"

# Den ersten Kandidaten nehmen, der WIRKLICH ein passendes Python ist.
# Wichtig auf Windows: `python3`/`python` sind dort oft nur Microsoft-Store-Platzhalter,
# die beim Aufruf lediglich eine Werbemeldung ausgeben — die dürfen wir nicht wählen.
PY=""
PY_ANY=""
PY_ANY_VER=""
for c in python3 python py; do
  command -v "$c" >/dev/null 2>&1 || continue
  ver="$("$c" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)"
  case "$ver" in [0-9]*.[0-9]*) : ;; *) continue ;; esac      # Platzhalter überspringen
  PY_ANY="$c"; PY_ANY_VER="$ver"
  if "$c" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 12) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ] && [ -n "$PY_ANY" ]; then
  err "Python 3.12+ benötigt — gefunden wurde nur $PY_ANY ($PY_ANY_VER)."
  info "Aktuelle Version: https://www.python.org/downloads/"
  exit 1
fi
if [ -z "$PY" ]; then
  err "Kein funktionierendes Python gefunden."
  info "Bitte Python 3.12+ installieren: https://www.python.org/downloads/"
  info "Windows-Hinweis: 'python3' ist dort oft nur ein Store-Platzhalter ohne Funktion."
  exit 1
fi
ok "Python $("$PY" -c 'import platform; print(platform.python_version())') gefunden ($PY)"

# --------------------------------------------------------------------------- #
# 2) Installieren — bestes verfügbares Werkzeug
# --------------------------------------------------------------------------- #
say "Installiere PollySort (mit Text-Extraktion [extract]) …"
BIN_DIR=""
if command -v uv >/dev/null 2>&1; then
  ok "uv erkannt"
  run uv tool install --force ".[extract]"
  BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
elif command -v pipx >/dev/null 2>&1; then
  ok "pipx erkannt"
  run pipx install --force ".[extract]"
  BIN_DIR="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "$HOME/.local/bin")"
else
  ok "Weder uv noch pipx — verwende pip (Benutzer-Installation)"
  run "$PY" -m pip install --user ".[extract]"
  BIN_DIR="$("$PY" -c 'import site,os; print(os.path.join(site.getuserbase(), "bin"))')"
fi
info "Programme landen in: $BIN_DIR"

# --------------------------------------------------------------------------- #
# 3) PATH — damit `pollysort` überall funktioniert
# --------------------------------------------------------------------------- #
# Erst in DIESER Shell verfügbar machen, damit die Prüfung unten ehrlich ist.
case ":$PATH:" in *":$BIN_DIR:"*) : ;; *) PATH="$BIN_DIR:$PATH"; export PATH ;; esac
hash -r 2>/dev/null || true

rc_file() {
  # Welche Startdatei liest die Login-Shell des Nutzers wirklich?
  local shell_name; shell_name="$(basename "${SHELL:-bash}")"
  case "$shell_name" in
    zsh)  echo "${ZDOTDIR:-$HOME}/.zshrc" ;;
    fish) echo "$HOME/.config/fish/config.fish" ;;
    bash)
      # macOS startet Terminals als Login-Shell → .bash_profile, Linux → .bashrc.
      if [ "$(uname -s)" = "Darwin" ]; then echo "$HOME/.bash_profile"; else echo "$HOME/.bashrc"; fi ;;
    *) echo "$HOME/.profile" ;;
  esac
}

MARKER="# >>> pollysort >>>"
persist_path() {
  local rc; rc="$(rc_file)"
  if [ -f "$rc" ] && grep -qF "$MARKER" "$rc" 2>/dev/null; then
    ok "PATH-Eintrag steht schon in $rc"
    return 0
  fi
  if [ "$DRY_RUN" = 1 ]; then
    info "[dry-run] würde PATH-Eintrag an $rc anhängen"
    return 0
  fi
  mkdir -p "$(dirname "$rc")"
  if [ "$(basename "${SHELL:-bash}")" = "fish" ]; then
    {
      printf '\n%s\n' "$MARKER"
      printf 'set -gx PATH "%s" $PATH\n' "$BIN_DIR"
      printf '%s\n' "# <<< pollysort <<<"
    } >> "$rc"
  else
    {
      printf '\n%s\n' "$MARKER"
      printf 'export PATH="%s:$PATH"\n' "$BIN_DIR"
      printf '%s\n' "# <<< pollysort <<<"
    } >> "$rc"
  fi
  ok "PATH dauerhaft ergänzt in $rc"
  info "Wirksam in neuen Terminals — oder sofort mit:  source $rc"
}

if [ "$TOUCH_PATH" = 0 ]; then
  warn "--no-path gesetzt — PATH bleibt unangetastet."
elif command -v pollysort >/dev/null 2>&1 && [ "$DRY_RUN" = 0 ]; then
  # Schon erreichbar? Dann nur sicherstellen, dass das auch nach einem Neustart gilt.
  case ":${PATH}:" in
    *":$BIN_DIR:"*) persist_path ;;
    *) ok "'pollysort' ist bereits im PATH" ;;
  esac
else
  # Die Werkzeuge bringen eigene, sauberere Mechanismen mit — die zuerst.
  if command -v uv >/dev/null 2>&1; then run uv tool update-shell || true; fi
  if command -v pipx >/dev/null 2>&1; then run pipx ensurepath >/dev/null 2>&1 || true; fi
  persist_path
fi

# --------------------------------------------------------------------------- #
# 4) Ergebnis
# --------------------------------------------------------------------------- #
say "Prüfe Installation …"
if [ "$DRY_RUN" = 1 ]; then
  info "Trockenlauf beendet — nichts wurde verändert."
  exit 0
fi
if command -v pollysort >/dev/null 2>&1; then
  ok "Befehl 'pollysort' verfügbar ($(pollysort-cli --version 2>/dev/null || echo 'bereit'))"
  say "Fertig! Tippe einfach:  pollysort"
else
  err "'pollysort' ist in dieser Shell noch nicht auffindbar."
  info "Öffne ein neues Terminal — der PATH-Eintrag greift dort."
  info "Notfalls direkt aus dem Repo starten:  $PY polly.py"
  exit 1
fi

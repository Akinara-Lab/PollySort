#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# PollySort — Deinstallation für Linux, macOS und Git-Bash (Windows)
#
#   bash uninstall.sh              nur die Anwendung (Befehle + PATH-Eintrag)
#   bash uninstall.sh --alles      zusätzlich die globale Ablage ~/.pollysort
#   bash uninstall.sh --dry-run    nur zeigen, was passieren würde
#
# WAS NIE ANGERÜHRT WIRD — unter keiner Option:
#   * deine Projektordner und die einsortierten Dateien darin
#   * die versteckten `.honig`-Ordner in den Projekten. Darin liegt unter anderem
#     `papierkorb/` — die Quarantäne, die noch echte Dateien enthalten kann, die du
#     zwar aussortiert, aber nie endgültig gelöscht hast.
#
# Das Skript listet sie am Ende auf, damit du selbst entscheiden kannst. Ein
# Deinstaller, der ungefragt Nutzerdaten mitnimmt, ist ein Datenverlust mit gutem
# Gewissen — und das Grundprinzip von PollySort ist: nie löschen.
# ---------------------------------------------------------------------------
set -euo pipefail

say()  { printf '\n\033[1;33m🐝  %s\033[0m\n' "$1"; }
ok()   { printf '   \033[32m✓\033[0m %s\n' "$1"; }
info() { printf '   %s\n' "$1"; }
warn() { printf '   \033[33m!\033[0m %s\n' "$1"; }

ALLES=0
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --alles|--all) ALLES=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) printf '   \033[31m✗ Unbekannte Option: %s\033[0m\n' "$arg" >&2; exit 2 ;;
  esac
done

say "PollySort deinstallieren"
[ "$DRY_RUN" = 1 ] && warn "Trockenlauf — es wird nichts verändert."

# --------------------------------------------------------------------------- #
# 0) Projekte merken, BEVOR die Registry verschwindet
# --------------------------------------------------------------------------- #
HOME_DIR="${POLLYSORT_HOME:-${BEEHIVE_HOME:-$HOME/.pollysort}}"
LEGACY_DIR="$HOME/.beehive"
PROJEKTE=""
if [ -f "$HOME_DIR/projects.txt" ]; then
  PROJEKTE="$(grep -v '^[[:space:]]*$' "$HOME_DIR/projects.txt" 2>/dev/null || true)"
fi

# --------------------------------------------------------------------------- #
# 1) Anwendung entfernen
# --------------------------------------------------------------------------- #
say "Entferne die Anwendung …"
ENTFERNT=0
run() { if [ "$DRY_RUN" = 1 ]; then info "[dry-run] $*"; else "$@" >/dev/null 2>&1 || true; fi; }

if command -v uv >/dev/null 2>&1 && uv tool list 2>/dev/null | grep -qi pollysort; then
  run uv tool uninstall pollysort
  ok "per uv entfernt"; ENTFERNT=1
fi
if command -v pipx >/dev/null 2>&1 && pipx list --short 2>/dev/null | grep -qi pollysort; then
  run pipx uninstall pollysort
  ok "per pipx entfernt"; ENTFERNT=1
fi
for c in python3 python py; do
  command -v "$c" >/dev/null 2>&1 || continue
  if "$c" -m pip show pollysort >/dev/null 2>&1; then
    run "$c" -m pip uninstall -y pollysort
    ok "per pip entfernt ($c)"; ENTFERNT=1
  fi
  break
done
[ "$ENTFERNT" = 0 ] && info "Keine installierte Version gefunden (vielleicht schon entfernt)."

# --------------------------------------------------------------------------- #
# 2) PATH-Eintrag zurücknehmen
# --------------------------------------------------------------------------- #
say "Räume den PATH auf …"
MARKER="# >>> pollysort >>>"
ENDE="# <<< pollysort <<<"
GEFUNDEN=0
for rc in "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile" \
          "${ZDOTDIR:-$HOME}/.zshrc" "$HOME/.config/fish/config.fish"; do
  [ -f "$rc" ] || continue
  grep -qF "$MARKER" "$rc" 2>/dev/null || continue
  GEFUNDEN=1
  if [ "$DRY_RUN" = 1 ]; then
    info "[dry-run] würde den PollySort-Block aus $rc entfernen"
    continue
  fi
  # Nur unseren markierten Block herausnehmen — der Rest der Datei bleibt Zeile
  # für Zeile, wie der Nutzer sie hat. Vorher eine Sicherung daneben legen.
  cp "$rc" "$rc.pollysort-bak"
  awk -v a="$MARKER" -v b="$ENDE" '
    index($0, a) { drin = 1; next }
    index($0, b) { drin = 0; next }
    !drin { print }
  ' "$rc.pollysort-bak" > "$rc"
  ok "PATH-Block entfernt aus $rc  (Sicherung: $rc.pollysort-bak)"
done
[ "$GEFUNDEN" = 0 ] && info "Kein von uns gesetzter PATH-Eintrag gefunden."

# --------------------------------------------------------------------------- #
# 3) Globale Ablage (nur mit --alles)
# --------------------------------------------------------------------------- #
if [ "$ALLES" = 1 ]; then
  say "Entferne die globale Ablage …"
  info "Darin liegen: Einstellungen, dein OpenRouter-Schlüssel, die Projektliste,"
  info "die Flugrouten (Discord/SMTP) und die Eingabe-Historie."
  for d in "$HOME_DIR" "$LEGACY_DIR"; do
    [ -d "$d" ] || continue
    if [ "$DRY_RUN" = 1 ]; then info "[dry-run] würde löschen: $d"; continue; fi
    printf '   Wirklich löschen? %s  [ja/NEIN]: ' "$d"
    read -r antwort || antwort=""
    if [ "$antwort" = "ja" ]; then
      rm -rf "$d" && ok "gelöscht: $d"
    else
      info "behalten: $d"
    fi
  done
else
  say "Globale Ablage bleibt erhalten"
  info "$HOME_DIR"
  info "Mit --alles wird sie mitentfernt (Einstellungen, Schlüssel, Projektliste)."
fi

# --------------------------------------------------------------------------- #
# 4) Was bleibt — bewusst
# --------------------------------------------------------------------------- #
say "Deine Dokumente bleiben unangetastet"
if [ -n "$PROJEKTE" ]; then
  info "PollySort kannte diese Projektordner:"
  printf '%s\n' "$PROJEKTE" | while IFS= read -r p; do [ -n "$p" ] && info "  $p"; done
  info ""
  info "Dort liegen deine einsortierten Dateien und je ein verstecktes '.honig'."
  info "Darin steckt auch 'papierkorb' — die Quarantäne, die noch echte Dateien"
  info "enthalten kann. Deshalb rührt dieser Deinstaller sie nicht an. Wenn du"
  info "sicher bist, dass nichts mehr drin ist, kannst du die '.honig'-Ordner"
  info "selbst löschen; die Kategorie-Ordner bleiben dann normale Ordner."
else
  info "Keine Projektordner bekannt."
fi

say "Fertig."
[ "$DRY_RUN" = 0 ] && info "Neues Terminal öffnen, damit der PATH neu gelesen wird."
exit 0

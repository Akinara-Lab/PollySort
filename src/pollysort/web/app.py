"""PollySort als eigene Anwendung — das Flugbrett im eigenen Fenster.

``pollysort-app`` (oder ``app`` in der Konsole) startet denselben lokalen Server wie
``pollysort-web`` — nur ``127.0.0.1``, Sitzungs-Token, ein freier Port —, zeigt die
Oberfläche aber nicht in einem Browser-Tab, sondern in einem eigenen Programmfenster.
**Schließt man das Fenster, beendet sich PollySort**: Server und Wache fahren herunter.

Drei Wege, in dieser Reihenfolge — der erste, der klappt, gewinnt:

1. **natives Fenster** über pywebview (Extra ``[app]``): Edge WebView2 unter Windows,
   WebKit unter macOS, GTK/Qt unter Linux;
2. **App-Fenster** eines installierten Chromium-Browsers (Edge, Chrome, Chromium, Brave)
   im ``--app``-Modus mit eigenem Profil unter ``~/.pollysort/fenster`` — randlos, ohne
   Adressleiste;
3. **Browser-Tab** als letzter Ausweg.

Unter Windows wird ``pollysort-app`` als *GUI-Programm* installiert (kein Konsolenfenster).
Deshalb landen Ausgaben in ``~/.pollysort/app.log``, und ein Startfehler erscheint als
Meldungsfenster statt im Nirgendwo.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from .. import config, i18n
from ..console import resolve_theme
from .server import starten, startziel

ICON = Path(__file__).parent / "static" / "pollysort.ico"
ICON_PNG = Path(__file__).parent / "static" / "pollysort.png"
FENSTER = ("auto", "nativ", "app", "browser")
#: Hintergrund des Fensters vor dem ersten Bild — gleich der Seite, kein weißer Blitz.
HINTERGRUND = {"dark": "#17110A", "light": "#FBF4E2"}


# --------------------------------------------------------------------------- #
#  Chromium-Browser finden (für das App-Fenster)
# --------------------------------------------------------------------------- #
def chromium_kandidaten() -> list[Path]:
    """Wo Edge, Chrome, Chromium und Brave üblicherweise liegen — je Betriebssystem."""
    if sys.platform.startswith("win"):
        wurzeln = [os.environ.get(k) for k in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA")]
        teile = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
                 r"BraveSoftware\Brave-Browser\Application\brave.exe", r"Chromium\Application\chrome.exe"]
        return [Path(w) / t for t in teile for w in wurzeln if w]
    if sys.platform == "darwin":
        apps = ["Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "Google Chrome.app/Contents/MacOS/Google Chrome",
                "Chromium.app/Contents/MacOS/Chromium",
                "Brave Browser.app/Contents/MacOS/Brave Browser"]
        return [Path(w) / a for a in apps for w in ("/Applications", str(Path.home() / "Applications"))]
    namen = ["microsoft-edge", "microsoft-edge-stable", "google-chrome", "google-chrome-stable",
             "chromium", "chromium-browser", "brave-browser"]
    return [Path(p) for p in (shutil.which(n) for n in namen) if p]


def chromium_finden() -> Path | None:
    for p in chromium_kandidaten():
        if p.is_file():
            return p
    return None


def chromium_befehl(exe: Path, url: str, profil: Path, *, breite: int = 1240, hoehe: int = 860) -> list[str]:
    """Aufruf für ein randloses App-Fenster. Das eigene Profil sorgt dafür, dass der Prozess
    so lange lebt wie das Fenster (statt die Seite an einen offenen Browser abzugeben)."""
    return [str(exe), f"--app={url}", f"--user-data-dir={profil}", f"--window-size={breite},{hoehe}",
            "--no-first-run", "--no-default-browser-check", "--disable-sync",
            "--disable-features=Translate,msEdgeSidebarV2"]


# --------------------------------------------------------------------------- #
#  Warten, bis das Fenster zu ist
# --------------------------------------------------------------------------- #
def warten(bus, prozess: subprocess.Popen | None = None, *, frist: float = 12.0,
           takt: float = 0.5, anlauf: float = 60.0, stopp: threading.Event | None = None) -> str:
    """Blockieren, bis niemand mehr zuschaut. Gibt den Grund zurück.

    - ``prozess``: Das App-Fenster ist zu, wenn sein Prozess endet. Endet er sofort (der
      Browser hat die Seite an einen schon laufenden Prozess abgegeben), zählt stattdessen,
      ob die Seite noch verbunden ist.
    - ``leer``: Die Seite war verbunden und ist seit ``frist`` Sekunden weg (Tab/Fenster zu;
      ein Neuladen dauert nur einen Augenblick und fällt nicht darunter).
    - ``nie``: In ``anlauf`` Sekunden hat sich keine Seite verbunden.
    """
    beginn = time.monotonic()
    verbunden = False
    abgegeben = False
    leer_seit: float | None = None
    while not (stopp and stopp.is_set()):
        jetzt = time.monotonic()
        if bus.abonnenten():
            verbunden, leer_seit = True, None
        elif leer_seit is None:
            leer_seit = jetzt
        if prozess is not None and not abgegeben and prozess.poll() is not None:
            if jetzt - beginn > 5:
                return "prozess"
            abgegeben = True       # sofort beendet: die Seite lebt in einem anderen Prozess weiter
        if verbunden and leer_seit is not None and jetzt - leer_seit > frist:
            return "leer"
        if not verbunden and jetzt - beginn > anlauf:
            return "nie"
        time.sleep(takt)
    return "stopp"


# --------------------------------------------------------------------------- #
#  Die drei Fenster-Arten
# --------------------------------------------------------------------------- #
def _hintergrund() -> str:
    return HINTERGRUND.get(resolve_theme(config.load_config().theme), HINTERGRUND["dark"])


def fenster_nativ(url: str) -> bool:
    """Natives Fenster über pywebview. ``False``, wenn es das hier nicht gibt."""
    try:
        import webview
    except Exception:
        return False
    try:
        webview.create_window("PollySort", url, width=1240, height=860, min_size=(420, 560),
                              background_color=_hintergrund(), text_select=True, zoomable=True)
        webview.start(icon=str(ICON) if ICON.is_file() else None, private_mode=True)
        return True
    except Exception:
        return False          # z. B. fehlende WebView2-Laufzeit — dann das App-Fenster


def fenster_app(url: str, bus) -> bool:
    """Randloses App-Fenster eines Chromium-Browsers; blockiert, bis es zu ist."""
    exe = chromium_finden()
    if exe is None:
        return False
    profil = config.POLLYSORT_HOME / "fenster"
    profil.mkdir(parents=True, exist_ok=True)
    try:
        prozess = subprocess.Popen(chromium_befehl(exe, url, profil),
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    if warten(bus, prozess) == "nie":
        if prozess.poll() is None:
            prozess.terminate()
        return False          # Fenster kam nie an — lieber noch den Browser versuchen
    return True


def fenster_browser(url: str, bus) -> bool:
    webbrowser.open(url)
    warten(bus)
    return True


# --------------------------------------------------------------------------- #
#  Start
# --------------------------------------------------------------------------- #
def _windows_identitaet() -> None:
    """Unter Windows eine eigene App-Kennung setzen — sonst gruppiert die Taskleiste
    PollySort unter „Python" und zeigt dessen Symbol."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Akinara.PollySort")
        except Exception:
            pass


def _ausgabe_umleiten() -> None:
    """Ohne Konsole (GUI-Programm) sind stdout/stderr ``None`` — dann in eine Logdatei."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        config.POLLYSORT_HOME.mkdir(parents=True, exist_ok=True)
        log = open(config.POLLYSORT_HOME / "app.log", "w", encoding="utf-8", buffering=1)
    except OSError:
        log = open(os.devnull, "w", encoding="utf-8")
    sys.stdout = sys.stdout or log
    sys.stderr = sys.stderr or log


def _melden(text: str) -> None:
    """Eine Startmeldung zeigen — als Meldungsfenster, wenn es keine Konsole gibt."""
    print(f"🐝  {text}", file=sys.stderr, flush=True)
    if sys.platform.startswith("win") and not (sys.stderr and sys.stderr.isatty()):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, "PollySort", 0x10)
        except Exception:
            pass


def oeffnen(hive: Path | None, *, fenster: str = "auto", port: int | None = 0) -> str:
    """Server starten, Fenster zeigen, nach dem Schließen aufräumen. Gibt die Fenster-Art zurück.

    Muss im Haupt-Thread laufen (native Fenster verlangen das).
    """
    httpd, url, dienst = starten(hive, port=port, browser=False)
    faden = threading.Thread(target=httpd.serve_forever, name="flugbrett", daemon=True)
    faden.start()
    bus = dienst.bus
    try:
        wege = {"nativ": [("nativ", lambda: fenster_nativ(url))],
                "app": [("app", lambda: fenster_app(url, bus))],
                "browser": [("browser", lambda: fenster_browser(url, bus))]}
        reihe = wege.get(fenster) or (wege["nativ"] + wege["app"] + wege["browser"])
        # Diagnose fürs app.log — bewusst ohne Token und ohne Pfade.
        print(f"flugbrett port={httpd.port}", flush=True)
        for art, versuch in reihe:
            print(f"fenster versuch={art}", flush=True)
            if versuch():
                print(f"fenster geschlossen={art}", flush=True)
                return art
        return "keins"
    finally:
        dienst.wache.stoppen()
        httpd.shutdown()
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    """Einstiegspunkt von ``pollysort-app``."""
    _ausgabe_umleiten()
    _windows_identitaet()
    i18n.set_language(getattr(config.load_config(), "language", "de"))
    parser = argparse.ArgumentParser(prog="pollysort-app", description=i18n.t("web.app.desc"))
    parser.add_argument("pfad", nargs="?", help=i18n.t("web.cli.arg_path"))
    parser.add_argument("--fenster", "--window", dest="fenster", choices=FENSTER, default="auto",
                        help=i18n.t("web.app.arg_window"))
    args = parser.parse_args(argv)
    hive = Path(args.pfad).expanduser().resolve() if args.pfad else startziel()
    try:
        art = oeffnen(hive, fenster=args.fenster)
    except Exception as exc:          # ohne Konsole sähe man sonst gar nichts
        _melden(i18n.t("web.app.failed", err=exc))
        return 1
    if art == "keins":
        _melden(i18n.t("web.app.nowindow"))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

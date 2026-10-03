"""PollySort als eigene Anwendung (web/app.py) — Fenster-Wahl, Aufräumen, App-Symbol.

Kein Test öffnet ein echtes Fenster: Die drei Fenster-Arten werden ersetzt, die Uhr der
Warte-Logik läuft simuliert. Geprüft wird, was beim Doppelklick zählt — die Reihenfolge
nativ → App-Fenster → Browser, dass nach dem Schließen nichts weiterläuft, und dass ein
Browser, der die Seite an einen offenen Prozess abgibt, PollySort nicht vorzeitig beendet.
"""

from __future__ import annotations

import socket
import struct
import tomllib
from pathlib import Path

import pytest

from pollysort import config
from pollysort.web import app

STATIC = Path(__file__).resolve().parents[1] / "src" / "pollysort" / "web" / "static"
PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


@pytest.fixture(autouse=True)
def _eigenes_zuhause(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(config, "POLLYSORT_HOME", home)
    monkeypatch.setattr(config, "CONFIG_PATH", home / "config.toml")
    monkeypatch.setattr(config, "CREDENTIALS_PATH", home / "credentials")
    monkeypatch.setattr(config, "PROJECTS_PATH", home / "projects.txt")


class _Uhr:
    """Simulierte Zeit: ``sleep`` rückt die Uhr vor, statt zu warten."""

    def __init__(self):
        self.jetzt = 0.0

    def monotonic(self) -> float:
        return self.jetzt

    def sleep(self, dt: float) -> None:
        self.jetzt += dt


class _Bus:
    """Liefert je Abfrage eine vorgegebene Zahl verbundener Fenster (letzter Wert bleibt)."""

    def __init__(self, folge):
        self.folge = list(folge)

    def abonnenten(self) -> int:
        return self.folge.pop(0) if len(self.folge) > 1 else self.folge[0]


class _Prozess:
    def __init__(self, ende_nach: float | None, uhr: _Uhr):
        self.ende_nach, self.uhr = ende_nach, uhr

    def poll(self):
        return 0 if self.ende_nach is not None and self.uhr.jetzt >= self.ende_nach else None


@pytest.fixture
def uhr(monkeypatch):
    u = _Uhr()
    monkeypatch.setattr(app, "time", u)
    return u


# --------------------------------------------------------------------------- #
#  Warten, bis das Fenster zu ist
# --------------------------------------------------------------------------- #
def test_fenster_zu_wenn_der_prozess_endet(uhr):
    prozess = _Prozess(ende_nach=30, uhr=uhr)
    assert app.warten(_Bus([1]), prozess) == "prozess"
    assert 30 <= uhr.jetzt < 31


def test_abgegebene_seite_beendet_pollysort_nicht_vorzeitig(uhr):
    """Der Browser-Prozess endet sofort (Seite an offenen Browser abgegeben) — dann zählt,
    ob die Seite verbunden ist, nicht das Prozessende."""
    prozess = _Prozess(ende_nach=0.5, uhr=uhr)
    bus = _Bus([0, 0] + [1] * 200 + [0])          # verbindet sich, bleibt ~100 s, geht dann
    assert app.warten(bus, prozess, frist=12) == "leer"
    assert uhr.jetzt > 100, "trotz frühem Prozessende bis zum Schließen der Seite gewartet"


def test_neuladen_ist_kein_schliessen(uhr):
    bus = _Bus([1] * 10 + [0] * 6 + [1] * 10 + [0])  # 3 s weg (Neuladen), dann wirklich zu
    assert app.warten(bus, frist=12) == "leer"
    assert uhr.jetzt > 12 + 10


def test_ohne_verbindung_gibt_es_auf(uhr):
    assert app.warten(_Bus([0]), anlauf=60) == "nie"


# --------------------------------------------------------------------------- #
#  Fenster-Wahl & Aufräumen
# --------------------------------------------------------------------------- #
def _projekt(tmp_path: Path) -> Path:
    from pollysort.config import HiveSeed
    hive = tmp_path / "buero"
    hive.mkdir()
    config.write_seed(hive, HiveSeed(name="Büro"))
    return hive


def _port_frei(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def test_reihenfolge_nativ_app_browser_und_danach_ist_alles_aus(tmp_path, monkeypatch):
    versuche: list[str] = []
    ports: list[int] = []

    def nativ(url):
        versuche.append("nativ")
        ports.append(int(url.split(":")[2].split("/")[0]))
        return False

    def app_fenster(url, bus):
        versuche.append("app")
        return False

    def browser(url, bus):
        versuche.append("browser")
        assert "#t=" in url, "das Fenster bekommt das Sitzungs-Token"
        return True

    monkeypatch.setattr(app, "fenster_nativ", nativ)
    monkeypatch.setattr(app, "fenster_app", app_fenster)
    monkeypatch.setattr(app, "fenster_browser", browser)
    assert app.oeffnen(_projekt(tmp_path)) == "browser"
    assert versuche == ["nativ", "app", "browser"]
    assert _port_frei(ports[0]), "nach dem Schließen darf kein Server weiterlaufen"


def test_gewuenschte_fenster_art_ohne_umwege(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "fenster_nativ", lambda url: pytest.fail("nicht gewünscht"))
    monkeypatch.setattr(app, "fenster_app", lambda url, bus: True)
    assert app.oeffnen(_projekt(tmp_path), fenster="app") == "app"


def test_kein_fenster_moeglich(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "fenster_nativ", lambda url: False)
    monkeypatch.setattr(app, "fenster_app", lambda url, bus: False)
    monkeypatch.setattr(app, "fenster_browser", lambda url, bus: False)
    assert app.oeffnen(_projekt(tmp_path)) == "keins"


def test_app_fenster_mit_eigenem_profil(tmp_path):
    befehl = app.chromium_befehl(Path("msedge.exe"), "http://127.0.0.1:1/#t=x", tmp_path / "fenster")
    assert "--app=http://127.0.0.1:1/#t=x" in befehl
    assert any(a.startswith("--user-data-dir=") for a in befehl), \
        "ohne eigenes Profil gäbe Edge die Seite an ein offenes Fenster ab"


def test_chromium_finden_nimmt_den_ersten_vorhandenen(tmp_path, monkeypatch):
    da = tmp_path / "chrome.exe"
    da.write_text("")
    monkeypatch.setattr(app, "chromium_kandidaten", lambda: [tmp_path / "fehlt.exe", da])
    assert app.chromium_finden() == da
    monkeypatch.setattr(app, "chromium_kandidaten", lambda: [tmp_path / "fehlt.exe"])
    assert app.chromium_finden() is None


# --------------------------------------------------------------------------- #
#  Paket & Symbol
# --------------------------------------------------------------------------- #
def test_pollysort_app_ist_ein_gui_programm():
    daten = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert daten["project"]["gui-scripts"]["pollysort-app"] == "pollysort.web.app:main"
    assert any(d.startswith("pywebview") for d in daten["project"]["optional-dependencies"]["app"])


def test_app_symbol_ist_gueltig():
    ico = (STATIC / "pollysort.ico").read_bytes()
    reserviert, typ, anzahl = struct.unpack("<HHH", ico[:6])
    assert (reserviert, typ) == (0, 1) and anzahl >= 4
    groessen = {ico[6 + 16 * i] or 256 for i in range(anzahl)}
    assert {16, 32, 48, 256} <= groessen
    png = (STATIC / "pollysort.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", png[16:24]) == (256, 256)
    assert (STATIC / "pollysort.icns").read_bytes()[:4] == b"icns"

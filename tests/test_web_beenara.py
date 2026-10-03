"""Flugbrett × BeeNara — und die Wächter über die Verbindung von Seite und Dienst.

Das Flugbrett entstand, bevor BeeNara in PollySort kam. Nach dem Zusammenführen fehlten
Verbindungen, die kein Test bemerkt hat: Die Seite baute „Entschieden: …" mit Platzhaltern,
die der Text nicht mehr hatte („Entschieden: {teile}"), und ein Download aus dem Browser wäre
an ``progress(transfer=True)`` gescheitert. Die letzten beiden Tests hier fangen genau diese
Art von Bruch künftig ab — für alle Aktionen und alle Texte der Seite, nicht nur für BeeNara.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest
from test_beenara import Hub
from test_beenara_sortieren import FakeBee

from pollysort import beenara, config, i18n, pipeline
from pollysort.config import AppConfig
from pollysort.llm.client import OfflineClient
from pollysort.pipeline import CycleSummary
from pollysort.web.dienst import Dienst
from pollysort.web.konsole import Ereignisbus, WebKonsole

STATIC = Path(__file__).resolve().parents[1] / "src" / "pollysort" / "web" / "static"
APP_JS = (STATIC / "app.js").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _eigenes_zuhause(tmp_path, monkeypatch):
    """Wie in test_web: die globale Ablage liegt im Test-Ordner."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(config, "POLLYSORT_HOME", home)
    monkeypatch.setattr(config, "CONFIG_PATH", home / "config.toml")
    monkeypatch.setattr(config, "CREDENTIALS_PATH", home / "credentials")
    monkeypatch.setattr(config, "PROJECTS_PATH", home / "projects.txt")
    beenara.schliessen()
    yield
    i18n.set_language("de")


def _buero(tmp_path: Path) -> tuple[Dienst, Path]:
    buero = tmp_path / "buero"
    buero.mkdir()
    (buero / "rechnung.txt").write_text("RECHNUNG Nr. 4711\nBetrag 119,00 EUR", encoding="utf-8")
    (buero / "spesen.txt").write_text("REISEKOSTENABRECHNUNG\nVerpflegung 28,00 EUR",
                                      encoding="utf-8")
    (buero / "kuchen.txt").write_text("Apfelkuchen: 500 g Mehl, 3 Eier", encoding="utf-8")
    d = Dienst()
    d.einrichten(pfad=str(buero), name="Büro", modus="offline",
                 kategorien=["rechnungen", "spesen", "kontoauszuege"], wache="off")
    return d, buero


def _herunterladen_ohne_netz(monkeypatch, hub: Hub) -> None:
    """``beenara.einrichten`` gegen den nachgebauten Hub, Laufzeit als vorhanden."""
    echt = beenara.laden
    monkeypatch.setattr(beenara, "laufzeit_fehlt", lambda: [])

    def einrichten(con, *, client=None):
        with hub.client() as c:
            return echt(con, client=c) and beenara.laufzeit_installieren(con)

    monkeypatch.setattr(beenara, "einrichten", einrichten)


def _beenara_bereit(monkeypatch, bee=None):
    """Für Sortierläufe: BeeNara „geladen" — als Doppelgänger, ohne ONNX."""
    monkeypatch.setattr(beenara, "warum_nicht", lambda _cfg: None)
    monkeypatch.setattr(beenara, "oeffnen", lambda: bee or FakeBee())


# --------------------------------------------------------------------------- #
#  Fortschritt in Bytes — der Download aus dem Browser
# --------------------------------------------------------------------------- #
def test_webkonsole_kann_bytes_und_drosselt_sie():
    bus = Ereignisbus()
    con = WebKonsole(bus.senden)
    with con.progress("x", transfer=True) as prog:
        tid = prog.add_task("BeeNara laden", total=10_000_000)
        for _ in range(1000):
            prog.advance(tid, 10_000)
    ereignisse = [e for e in bus.letzte() if e["art"] == "fortschritt"]
    assert len(ereignisse) <= 102, "ein Ereignis je Prozent — sonst ist das Protokoll weg"
    assert ereignisse[-1]["erledigt"] == ereignisse[-1]["gesamt"] == 10_000_000
    assert all(e["einheit"] == "bytes" for e in ereignisse)


def test_webkonsole_ohne_transfer_bleibt_wie_bisher():
    bus = Ereignisbus()
    with WebKonsole(bus.senden).progress("x") as prog:
        prog.advance(prog.add_task("sortiere", total=3))
    e = [e for e in bus.letzte() if e["art"] == "fortschritt"][-1]
    assert "einheit" not in e and e["erledigt"] == 1


def test_beenara_laden_im_flugbrett(tmp_path, monkeypatch):
    """Vorher: TypeError in WebKonsole.progress — jetzt Fortschritt in MB auf der Seite."""
    hub = Hub()
    _herunterladen_ohne_netz(monkeypatch, hub)
    d, _ = _buero(tmp_path)
    antwort = d.beenara_laden()
    assert antwort["ergebnis"]["ok"] is True
    assert antwort["ergebnis"]["beenara"]["bereit"] is True
    bytes_ = [e for e in d.bus.letzte() if e.get("einheit") == "bytes"]
    assert bytes_ and bytes_[-1]["erledigt"] == bytes_[-1]["gesamt"]
    assert any("geprüft" in m["text"] for m in antwort["meldungen"])


def test_ausfall_beim_laden_reisst_das_flugbrett_nicht_ab(tmp_path, monkeypatch):
    def boom(_con, **_k):
        raise RuntimeError("Platte voll")

    monkeypatch.setattr(beenara, "einrichten", boom)
    d, _ = _buero(tmp_path)
    antwort = d.beenara_laden()
    assert antwort["ergebnis"]["ok"] is False
    assert any("Platte voll" in m["text"] for m in antwort["meldungen"])


# --------------------------------------------------------------------------- #
#  Werkstatt, Kopfzeile, Schalter
# --------------------------------------------------------------------------- #
def test_werkstatt_zeigt_dieselben_zeilen_wie_die_konsole(tmp_path):
    d, buero = _buero(tmp_path)
    bn = d.werkstatt()["beenara"]
    erwartet = [text for _a, _e, text in beenara.bericht(config.load_config(), buero)]
    assert [z["text"] for z in bn["zeilen"]] == erwartet
    assert bn["vorhanden"] is False and bn["grund"] == "modell" and bn["bereit"] is False


def test_kopfzeile_kennt_beenara_ohne_lange_texte(tmp_path):
    d, _ = _buero(tmp_path)
    bn = d.zustand()["beenara"]
    assert bn["bereit"] is False and "zeilen" not in bn
    assert bn["ungefaehr_mb"] == beenara.UNGEFAEHR_MB


def test_schalten_und_entfernen(tmp_path, monkeypatch):
    hub = Hub()
    _herunterladen_ohne_netz(monkeypatch, hub)
    d, _ = _buero(tmp_path)
    d.beenara_laden()
    aus = d.beenara_schalten(an=False)["ergebnis"]
    assert aus["an"] is False and aus["grund"] == "aus" and not config.load_config().beenara
    assert d.beenara_schalten(an=True)["ergebnis"]["bereit"] is True
    weg = d.beenara_entfernen()["ergebnis"]
    assert weg["vorhanden"] is False and not beenara.ordner().exists()
    nochmal = d.beenara_entfernen()
    assert any("nicht geladen" in m["text"] for m in nochmal["meldungen"])


# --------------------------------------------------------------------------- #
#  Sortieren im Flugbrett: wer hat entschieden?
# --------------------------------------------------------------------------- #
def test_sortieren_nennt_beenara_wie_die_konsole(tmp_path, monkeypatch):
    _beenara_bereit(monkeypatch)
    d, buero = _buero(tmp_path)
    erg = d.sortieren()["ergebnis"]
    assert erg["quellen"] == {"beenara": 3}
    assert erg["quellen_text"] == "Entschieden: 3 von BeeNara"
    assert {z["quelle_text"] for z in erg["plan"]} == {"BeeNara"}
    assert (buero / "kuchen.txt").exists(), "„keiner passt“ bleibt auch im Flugbrett liegen"


def test_vorschau_zeigt_die_quelle_je_datei(tmp_path, monkeypatch):
    _beenara_bereit(monkeypatch)
    d, buero = _buero(tmp_path)
    plan = {z["datei"]: z for z in d.vorschau()["ergebnis"]["plan"]}
    assert plan["rechnung.txt"]["quelle_text"] == "BeeNara"
    assert (buero / "rechnung.txt").exists(), "die Vorschau bewegt nichts"


def test_ohne_beenara_heisst_der_rest_heuristik(tmp_path):
    d, _ = _buero(tmp_path)
    erg = d.sortieren()["ergebnis"]
    assert erg["quellen_text"] is None, "nur Heuristik — nichts zu unterscheiden"
    assert {z["quelle_text"] for z in erg["plan"] if z["quelle"]} == {"Heuristik"}


def test_quellen_text_ist_einer_fuer_alle():
    s = CycleSummary(quellen={"beenara": 2, "analyse": 1, "gedaechtnis": 4})
    spar = OfflineClient(["a", "b", "c"])
    assert pipeline.quellen_text(s, spar) == \
        "Entschieden: 4 aus dem Gedächtnis · 2 von BeeNara · 1 per Heuristik"
    assert "per Vollanalyse" in pipeline.quellen_text(s, object())
    assert pipeline.quellen_text(CycleSummary(quellen={"analyse": 5}), spar) is None


# --------------------------------------------------------------------------- #
#  Wächter: Seite und Dienst passen zusammen
# --------------------------------------------------------------------------- #
def _endpunkte() -> tuple[set[str], set[str]]:
    ansichten = {n for n, f in inspect.getmembers(Dienst) if getattr(f, "ansicht", None)}
    auftraege = {n for n, f in inspect.getmembers(Dienst) if getattr(f, "auftrag", None)}
    return ansichten, auftraege


def test_jeder_aufruf_der_seite_hat_einen_endpunkt_und_umgekehrt():
    ansichten, auftraege = _endpunkte()
    gelesen = set(re.findall(r"\blesen\(\s*'([a-z_]+)'", APP_JS))
    getan = set(re.findall(r"\b(?:tun|arbeit)\(\s*'([a-z_]+)'", APP_JS))
    # sortierenStarten wählt per Ausdruck zwischen den beiden:
    getan |= set(re.findall(r"arbeit\(\s*cache\s*\?\s*'([a-z_]+)'\s*:\s*'([a-z_]+)'", APP_JS)[0])
    assert gelesen <= ansichten, f"Seite liest, was der Dienst nicht anbietet: {gelesen - ansichten}"
    assert getan <= auftraege, f"Seite ruft Aktionen, die es nicht gibt: {getan - auftraege}"
    assert not ansichten - gelesen, f"Ansicht ohne Seite: {ansichten - gelesen}"
    assert not auftraege - getan, f"Aktion ohne Knopf: {auftraege - getan}"


def test_jeder_text_bekommt_alle_seine_platzhalter():
    """t('pl.quellen', { mem, num, voll }) gegen „Entschieden: {teile}" — so stand nach dem
    Zusammenführen wörtlich „{teile}" im Browser."""
    fehler = []
    for key, obj in re.findall(r"\bt\('([a-zA-Z0-9_.]+)',\s*\{([^{}]*)\}\s*\)", APP_JS):
        if key not in i18n._CATALOG:
            continue                            # fehlende Texte prüft test_web
        gegeben = set(re.findall(r"(\w+)\s*:", obj)) | set(re.findall(r"(?:^|,)\s*(\w+)\s*(?=,|$)", obj))
        for sprache in ("de", "en"):
            noetig = set(re.findall(r"\{(\w+)\}", i18n._CATALOG[key][sprache]))
            if noetig - gegeben:
                fehler.append(f"{key} ({sprache}): fehlt {sorted(noetig - gegeben)}")
    assert not fehler, "\n".join(fehler)


def test_ohne_platzhalter_aufgerufene_texte_haben_keine():
    """t('key') ohne Werte — dann darf der Text auch keine {platzhalter} erwarten."""
    fehler = []
    for key in set(re.findall(r"\bt\('([a-zA-Z0-9_.]+)'\)", APP_JS)):
        for sprache in ("de", "en"):
            if key in i18n._CATALOG and re.search(r"\{\w+\}", i18n._CATALOG[key][sprache]):
                fehler.append(f"{key} ({sprache})")
    assert not fehler, f"Platzhalter bleiben stehen: {fehler}"


def test_erststart_der_seite_bietet_beenara_an():
    """Wer über die App einsteigt, sieht den Konsolen-Erststart nie — die Frage gehört
    deshalb auch in den Assistenten des Flugbretts, und zwar nur auf Zusage."""
    assert "id=\"su-beenara\"" in APP_JS
    assert re.search(r"beenara:\s*false", APP_JS), "Vorauswahl: nicht laden"
    assert "arbeit('beenara_laden')" in APP_JS


def test_api_nimmt_die_beenara_aktionen(tmp_path):
    import http.client
    import json
    import threading

    from pollysort.web.server import Flugbrett
    d, _ = _buero(tmp_path)
    httpd = Flugbrett(("127.0.0.1", 0), d, "tok")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        def post(pfad, koerper):
            con = http.client.HTTPConnection("127.0.0.1", httpd.port, timeout=10)
            con.request("POST", pfad, body=json.dumps(koerper), headers={
                "Host": f"127.0.0.1:{httpd.port}", "X-Flugbrett-Token": "tok",
                "Content-Type": "application/json"})
            r = con.getresponse()
            daten = json.loads(r.read() or b"{}")
            con.close()
            return r.status, daten
        status, daten = post("/api/beenara_schalten", {"an": False})
        assert status == 200 and daten["ergebnis"]["an"] is False
        assert post("/api/beenara_schalten", {"pfad": "x"})[0] == 400, "nur bekannte Parameter"
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert AppConfig().beenara is True, "Voreinstellung bleibt: an"

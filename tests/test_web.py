"""Das Flugbrett — die Browser-Oberfläche (web/).

Geprüft wird, was nicht verhandelbar ist: Eine Vorschau bewegt nichts und zählt nicht,
gelöscht wird nur mit der getippten Anzahl, Schlüssel verlassen den Rechner nie (auch nicht
in Richtung Browser), und der Server nimmt nur Anfragen mit Token, vom richtigen Host und
ohne fremde Origin an. Dazu: Jeder Text, den die Seite benutzt, existiert in beiden Sprachen.
"""

from __future__ import annotations

import http.client
import json
import re
import threading
from pathlib import Path

import pytest

from pollysort import config, i18n, spiel
from pollysort.web.dienst import Beschaeftigt, Dienst, Ungueltig
from pollysort.web.konsole import Ereignisbus, WebKonsole
from pollysort.web.server import Flugbrett

STATIC = Path(__file__).resolve().parents[1] / "src" / "pollysort" / "web" / "static"


@pytest.fixture(autouse=True)
def _eigenes_zuhause(tmp_path, monkeypatch):
    """Globale Ablage (~/.pollysort) in den Test-Ordner verlegen — nie die echte anfassen."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(config, "POLLYSORT_HOME", home)
    monkeypatch.setattr(config, "CONFIG_PATH", home / "config.toml")
    monkeypatch.setattr(config, "CREDENTIALS_PATH", home / "credentials")
    monkeypatch.setattr(config, "PROJECTS_PATH", home / "projects.txt")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    yield
    i18n.set_language("de")


def _buero(tmp_path: Path) -> Path:
    buero = tmp_path / "buero"
    buero.mkdir()
    (buero / "rechnung_acme.txt").write_text("Rechnung ACME Betrag 4200 EUR UST Rechnungsdatum",
                                             encoding="utf-8")
    (buero / "mietvertrag.txt").write_text("Mietvertrag Vereinbarung Wohnung Vertrag", encoding="utf-8")
    (buero / "protokoll.md").write_text("# Protokoll Sitzung Beschluss", encoding="utf-8")
    (buero / "notiz.txt").write_text("hallo", encoding="utf-8")
    return buero


def _eingerichtet(tmp_path: Path) -> tuple[Dienst, Path]:
    buero = _buero(tmp_path)
    d = Dienst()
    d.einrichten(pfad=str(buero), name="Büro", modus="offline",
                 kategorien=["rechnungen", "vertraege", "protokolle"], wache="off")
    return d, buero


def _lose(buero: Path) -> set[str]:
    return {p.name for p in buero.iterdir() if p.is_file()}


# --------------------------------------------------------------------------- #
#  WebKonsole — Meldungen werden Ereignisse
# --------------------------------------------------------------------------- #
def test_webkonsole_macht_aus_meldungen_ereignisse():
    bus = Ereignisbus()
    con = WebKonsole(bus.senden)
    with con.sammeln() as meldungen:
        con.honey("[honey]s[/honey] sortiere")
        con.error("kaputt")
        con.celebrate("Sauber sortiert")
        with con.progress("x") as prog:
            tid = prog.add_task("sortiere", total=2)
            prog.advance(tid)
    assert [m["art"] for m in meldungen] == ["honey", "error", "feier"]
    assert meldungen[0]["text"] == "s sortiere", "Rich-Markup gehört nicht in den Browser"
    fortschritt = [e for e in bus.letzte() if e["art"] == "fortschritt"]
    assert fortschritt[-1]["erledigt"] == 1 and fortschritt[-1]["gesamt"] == 2


def test_webkonsole_schreibt_nichts_ins_terminal(capsys):
    con = WebKonsole()
    con.honey("hallo")
    con.raw("welt")
    con.apply_terminal_colors()
    assert capsys.readouterr().out == ""


# --------------------------------------------------------------------------- #
#  Dienst — dieselben Regeln wie die Konsole
# --------------------------------------------------------------------------- #
def test_einrichten_legt_projekt_und_waben_an(tmp_path):
    d, buero = _eingerichtet(tmp_path)
    z = d.zustand()
    assert z["projekt"]["name"] == "Büro" and z["projekt"]["modus"] == "offline"
    assert z["projekt"]["lose"] == 4
    assert (buero / "Rechnungen").is_dir() and (buero / "Vertraege").is_dir()
    assert config.list_projects() == [buero.resolve()]
    assert z["erststart"] is False, "der Assistent erledigt auch den Erststart"


def test_vorschau_bewegt_nichts_und_zaehlt_nicht(tmp_path):
    d, buero = _eingerichtet(tmp_path)
    vorher = _lose(buero)
    erg = d.vorschau()["ergebnis"]
    assert erg["vorschau"] is True and erg["spiel"] is None
    assert _lose(buero) == vorher, "eine Vorschau darf nichts verschieben"
    assert {p["datei"] for p in erg["plan"]} == vorher
    assert spiel.laden(buero).dokumente == 0, "eine Vorschau zählt nicht auf den Fortschritt"
    assert d.zustand()["projekt"]["vorschau_offen"] is True


def test_anwenden_sortiert_aus_dem_cache_und_bucht_fortschritt(tmp_path):
    d, buero = _eingerichtet(tmp_path)
    vorschau = d.vorschau()["ergebnis"]
    erg = d.anwenden()["ergebnis"]
    assert erg["eingelagert"] == vorschau["eingelagert"] > 0
    assert (buero / "rechnung_acme.txt").exists() is False
    assert any((buero / "Rechnungen").rglob("rechnung_acme.txt"))
    assert spiel.laden(buero).dokumente == erg["eingelagert"]
    assert "erste_wabe" in [a["key"] for a in erg["spiel"]["neue_abzeichen"]]
    assert d.zustand()["projekt"]["vorschau_offen"] is False


def test_rueckfrage_beantworten_zaehlt_als_korrektur(tmp_path):
    d, buero = _eingerichtet(tmp_path)
    d.sortieren()
    faelle = d.rueckfragen()["faelle"]
    assert faelle, "die nichtssagende Notiz bleibt als Rückfrage liegen"
    antwort = d.zuordnen(id=faelle[0]["id"], kategorie="protokolle", quelle="review")["ergebnis"]
    assert antwort["neu"]["name"] == "Protokolle" and antwort["datei"] == faelle[0]["datei"]
    assert spiel.laden(buero).korrekturen == 1
    assert "lehrmeister" in [a["key"] for a in antwort["spiel"]["neue_abzeichen"]]


def test_unbekannte_quelle_wird_abgewiesen(tmp_path):
    d, _ = _eingerichtet(tmp_path)
    with pytest.raises(Ungueltig):
        d.zuordnen(id="x", kategorie="y", quelle="hintertuer")


def test_rueckflug_macht_die_letzte_verschiebung_rueckgaengig(tmp_path):
    d, buero = _eingerichtet(tmp_path)
    d.sortieren()
    lose = _lose(buero)
    r = d.rueckflug()["ergebnis"]
    assert r.get("datei") and r["datei"] not in lose
    assert r["datei"] in _lose(buero), "die Datei liegt wieder im Eingang"


def test_leeren_nur_mit_der_richtigen_anzahl(tmp_path):
    d, buero = _eingerichtet(tmp_path)
    d.sortieren()
    eintrag = d.eintraege(kategorie="rechnungen")["eintraege"][0]
    d.papierkorb(id=eintrag["id"])
    papierkorb = config.honig(buero) / "papierkorb"
    assert len(list(papierkorb.iterdir())) == 1
    with pytest.raises(Ungueltig):
        d.leeren(anzahl=0)
    with pytest.raises(Ungueltig):
        d.leeren(anzahl="eins")
    assert len(list(papierkorb.iterdir())) == 1, "ohne passende Bestätigung wird nichts gelöscht"
    assert d.leeren(anzahl=1)["ergebnis"]["geloescht"] == 1


def test_eine_aktion_nach_der_anderen(tmp_path):
    d, _ = _eingerichtet(tmp_path)
    d._arbeit.acquire()
    try:
        with pytest.raises(Beschaeftigt):
            d.sortieren()
    finally:
        d._arbeit.release()


def test_schluessel_verlassen_den_rechner_nie(tmp_path):
    geheim = "sk-or-v1-supergeheim-1234567890abcd"
    config.save_credentials(geheim)
    d, _ = _eingerichtet(tmp_path)
    alles = json.dumps([d.werkstatt(), d.zustand(), d.texte()], ensure_ascii=False)
    assert geheim not in alles
    assert d.werkstatt()["schluessel"]["maskiert"] == "****abcd"


def test_einstellungen_und_arbeitsmodus(tmp_path):
    d = Dienst()
    e = d.einstellungen(arbeitsmodus=True)["ergebnis"]
    werte = (e["animationen"], e["fortschritt"], e["klartext"], e["arbeitsmodus"])
    assert werte == ("dezent", False, True, True)
    with pytest.raises(Ungueltig):
        d.einstellungen(animationen="disco")
    d.einstellungen(sprache="en")
    assert i18n.get_language() == "en" and config.load_config().language == "en"


def test_ohne_projekt_freundlicher_fehler():
    with pytest.raises(Ungueltig):
        Dienst().sortieren()


# --------------------------------------------------------------------------- #
#  Fortschritt — die Regel-Zählung kam vorher nie an
# --------------------------------------------------------------------------- #
def test_buchen_zaehlt_die_regeln_der_wachstafel(tmp_path):
    from pollysort.wachstafel import Wachstafel
    regeln = [(f"wort{i}", "rechnungen", 2, "") for i in range(5)]
    Wachstafel(tmp_path).schreiben(regeln, n_corrections=10)
    stand, neu, _ = spiel.buchen(tmp_path, None, korrekturen=1)
    assert stand.regeln == 5
    assert "weise" in neu, "„Weise Königin\" muss erreichbar sein"


# --------------------------------------------------------------------------- #
#  Server — Token, Host, Origin, nur erlaubte Aktionen
# --------------------------------------------------------------------------- #
@pytest.fixture
def server(tmp_path):
    d, _ = _eingerichtet(tmp_path)
    httpd = Flugbrett(("127.0.0.1", 0), d, "geheimes-token")
    faden = threading.Thread(target=httpd.serve_forever, daemon=True)
    faden.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def _anfrage(httpd, methode, pfad, *, token=True, koerper=None, kopf=None):
    con = http.client.HTTPConnection("127.0.0.1", httpd.port, timeout=10)
    h = {"Host": f"127.0.0.1:{httpd.port}"}
    if token:
        h["X-Flugbrett-Token"] = "geheimes-token"
    if koerper is not None:
        h["Content-Type"] = "application/json"
    h.update(kopf or {})
    con.request(methode, pfad, body=json.dumps(koerper) if koerper is not None else None, headers=h)
    antwort = con.getresponse()
    daten = antwort.read()
    con.close()
    return antwort, daten


def test_seite_kommt_mit_strenger_csp(server):
    antwort, daten = _anfrage(server, "GET", "/", token=False)
    assert antwort.status == 200 and b"app.js" in daten
    csp = antwort.getheader("Content-Security-Policy")
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp


def test_api_braucht_das_token(server):
    assert _anfrage(server, "GET", "/api/zustand", token=False)[0].status == 401
    antwort, daten = _anfrage(server, "GET", "/api/zustand")
    assert antwort.status == 200 and json.loads(daten)["projekt"]["name"] == "Büro"


def test_fremder_host_und_fremde_origin_werden_abgewiesen(server):
    assert _anfrage(server, "GET", "/api/zustand", kopf={"Host": "boese.example:80"})[0].status == 403
    antwort, _ = _anfrage(server, "POST", "/api/verwerfen", koerper={},
                          kopf={"Origin": "http://boese.example"})
    assert antwort.status == 403


def test_nur_json_und_nur_bekannte_parameter(server):
    con = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
    con.request("POST", "/api/verwerfen", body="a=b", headers={
        "Host": f"127.0.0.1:{server.port}", "X-Flugbrett-Token": "geheimes-token",
        "Content-Type": "application/x-www-form-urlencoded"})
    assert con.getresponse().status == 415
    con.close()
    assert _anfrage(server, "POST", "/api/sortieren", koerper={"rm": "-rf"})[0].status == 400
    assert _anfrage(server, "POST", "/api/__init__", koerper={})[0].status == 404


def test_geschlossenes_fenster_faellt_sofort_auf(server):
    """Die App beendet sich, wenn kein Fenster mehr zuhört — das muss der Server schnell merken."""
    import socket
    import time
    s = socket.create_connection(("127.0.0.1", server.port), timeout=5)
    s.sendall(f"GET /api/ereignisse HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n"
              f"X-Flugbrett-Token: geheimes-token\r\n\r\n".encode())
    assert b"200" in s.recv(200)
    bus = server.dienst.bus
    ende = time.monotonic() + 3
    while bus.abonnenten() == 0 and time.monotonic() < ende:
        time.sleep(0.05)
    assert bus.abonnenten() == 1
    s.close()
    ende = time.monotonic() + 3
    while bus.abonnenten() and time.monotonic() < ende:
        time.sleep(0.1)
    assert bus.abonnenten() == 0, "ein geschlossenes Fenster muss binnen Sekunden abgemeldet sein"


def test_keine_dateien_ausserhalb_von_static(server):
    for pfad in ("/../pyproject.toml", "/..%2f..%2fpyproject.toml", "/dienst.py"):
        assert _anfrage(server, "GET", pfad, token=False)[0].status == 404


def test_fehler_kommen_als_klartext(server):
    antwort, daten = _anfrage(server, "POST", "/api/leeren", koerper={"anzahl": 99})
    assert antwort.status == 200, "leere Quarantäne: nichts zu tun, kein Fehler"
    antwort, daten = _anfrage(server, "POST", "/api/zuordnen", koerper={"id": "", "kategorie": ""})
    assert antwort.status == 400 and json.loads(daten)["fehler"]


# --------------------------------------------------------------------------- #
#  Texte — alles, was die Seite benutzt, gibt es auf Deutsch UND Englisch
# --------------------------------------------------------------------------- #
def test_jeder_text_der_seite_existiert_in_beiden_sprachen():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    keys = set(re.findall(r"\bt\('([a-zA-Z0-9_.]+)'", js)) | set(re.findall(r"'(web\.[a-zA-Z0-9_.]+)'", js))
    # Zusammengesetzte Schlüssel (t('mode.' + modus)) mit allen Werten, die vorkommen können:
    dynamisch = {"mode.": ("offline", "ollama", "openrouter"), "su.watch.": ("off", "notify", "move"),
                 "web.watchmode.": ("off", "notify", "move"), "web.key.": ("env", "datei"),
                 "web.routes.": ("discord", "email", "kalender"),
                 "web.recommend.": ("para", "johnny", "dewey")}
    assert {k for k in keys if k.endswith(".")} <= set(dynamisch), "neuer dynamischer Schlüssel?"
    keys = {k for k in keys if not k.endswith(".")}
    keys |= {praefix + wert for praefix, werte in dynamisch.items() for wert in werte}
    fehlt = sorted(k for k in keys if k not in i18n._CATALOG)
    assert not fehlt, f"Texte fehlen im Katalog: {fehlt}"
    for k in keys:
        assert i18n._CATALOG[k].get("de") and i18n._CATALOG[k].get("en"), k


def test_seite_ohne_inline_skripte_und_inline_styles():
    """Die CSP erlaubt nur Dateien aus static/ — Inline-Code würde still blockiert."""
    for datei in ("index.html", "musterbuch.html"):
        html = (STATIC / datei).read_text(encoding="utf-8")
        assert not re.search(r"<script(?![^>]*\bsrc=)", html), datei
        assert 'style="' not in html, datei
    for datei in ("app.js", "musterbuch.js"):
        assert 'style="' not in (STATIC / datei).read_text(encoding="utf-8"), datei

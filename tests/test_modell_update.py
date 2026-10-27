"""Automatisches Update der Modelle (modell_update.py) — ohne Netz, mit dem Hub aus test_beenara.

Abgesichert ist:

* Nur schon geladene Modelle werden aktualisiert, und nur, wenn der Commit nicht mehr passt.
* Das Update nutzt den normalen Download (Prüfsummen, Tausch am Ende); danach sortiert BeeNara wieder mit.
* Zwei Downloads in denselben Ordner gleichzeitig gibt es nicht.
* Neuere Tags auf dem Hub werden gemeldet, nicht geladen — höchstens einmal am Tag gefragt.
* Die App startet ohne geladenes Modell keinen Faden und geht nicht ins Netz; ausgeschaltet bleibt
  alles still.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from test_beenara import SHA_B, Con, Hub, _laden

from pollysort import beenara, config, modell_update


@pytest.fixture
def ziel(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "POLLYSORT_HOME", tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.toml")
    monkeypatch.delenv("HF_ENDPOINT", raising=False)
    monkeypatch.setattr(beenara, "laufzeit_fehlt", lambda: [])
    return tmp_path / "modelle" / "BeeNara"


@pytest.fixture
def hub():
    return Hub()


def _pin_anheben(hub: Hub, monkeypatch) -> None:
    """Wie nach einem PollySort-Update: dieses PollySort braucht einen neueren Commit."""
    monkeypatch.setattr(beenara, "REVISION", SHA_B)
    hub.sha = SHA_B


def test_ohne_geladenes_modell_ist_nichts_veraltet(ziel):
    assert modell_update.veraltet() == [] and modell_update.geladen() == []


def test_passender_commit_ist_nicht_veraltet(ziel, hub):
    _laden(hub)
    assert modell_update.geladen() == ["klein"] and modell_update.veraltet() == []


def test_neuer_pin_wird_automatisch_nachgeladen(ziel, hub, monkeypatch):
    _laden(hub)
    _pin_anheben(hub, monkeypatch)
    assert modell_update.veraltet() == ["klein"]
    assert beenara.warum_nicht(config.AppConfig()) == "version"
    con = Con()
    with hub.client() as client:
        assert modell_update.aktualisieren(con, client=client) == {"klein": True}
    assert modell_update.veraltet() == []
    assert beenara.warum_nicht(config.AppConfig()) is None
    assert "BeeNara" in con.text and SHA_B[:7] in con.text


def test_fehlgeschlagenes_update_meldet_und_wirft_nicht(ziel, hub, monkeypatch):
    _laden(hub)
    _pin_anheben(hub, monkeypatch)
    hub.down = True
    con = Con()
    with hub.client() as client:
        assert modell_update.aktualisieren(con, client=client) == {"klein": False}
    assert modell_update.veraltet() == ["klein"]          # das alte Modell liegt unversehrt da
    assert not modell_update.laeuft()


def test_waehrend_des_updates_sagt_der_stand_es(ziel, hub, monkeypatch):
    _laden(hub)
    _pin_anheben(hub, monkeypatch)
    gesehen = []
    echt = beenara.laden

    def laden(con, client=None):
        gesehen.append([text for _, _, text in beenara.bericht(config.AppConfig())])
        return echt(con, client=client)

    monkeypatch.setattr(beenara, "laden", laden)
    with hub.client() as client:
        modell_update.aktualisieren(Con(), client=client)
    assert any("automatisch" in z or "automatically" in z for z in gesehen[0])


def test_zweiter_download_in_denselben_ordner_wartet_nicht_sondern_meldet(ziel, hub):
    sperre = beenara._ladesperre(ziel)
    sperre.acquire()
    try:
        con = Con()
        with hub.client() as client:
            assert beenara.laden(con, client=client) is False
        assert hub.requests == []
    finally:
        sperre.release()


def test_zweites_update_gleichzeitig_tut_nichts(ziel, hub, monkeypatch):
    _laden(hub)
    _pin_anheben(hub, monkeypatch)
    modell_update._SPERRE.acquire()
    try:
        assert modell_update.aktualisieren(Con()) == {}
    finally:
        modell_update._SPERRE.release()


# --------------------------------------------------------------------------- #
#  Neuere Versionen auf dem Hub — nur Hinweis
# --------------------------------------------------------------------------- #
class Refs:
    def __init__(self, tags):
        self.tags = tags
        self.anfragen = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.anfragen += 1
        assert request.url.path == f"/api/models/{beenara.REPO}/refs"
        return httpx.Response(200, json={"branches": [{"name": "main"}],
                                         "tags": [{"name": t} for t in self.tags]})

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


def test_neuerer_tag_wird_gemeldet_nicht_geladen(ziel, hub):
    _laden(hub)
    refs = Refs(["v0.2", "v0.3", beenara.VERSION, "v0.10", "kaputt"])
    with refs.client() as client:
        assert modell_update.neuere_pruefen(client=client) == {"klein": "v0.10"}
    assert modell_update.neuere() == {"klein": "v0.10"}
    assert modell_update.veraltet() == []                  # nichts geladen, nichts veraltet
    zeilen = " ".join(text for _, _, text in beenara.bericht(config.AppConfig()))
    assert "v0.10" in zeilen and beenara.VERSION in zeilen


def test_ohne_neueren_tag_kein_hinweis(ziel, hub):
    _laden(hub)
    with Refs(["v0.2", beenara.VERSION]).client() as client:
        assert modell_update.neuere_pruefen(client=client) == {}


def test_hub_wird_hoechstens_einmal_am_tag_gefragt(ziel, hub):
    _laden(hub)
    refs = Refs(["v9.0"])
    jetzt = datetime(2026, 10, 27, 12, tzinfo=UTC)
    with refs.client() as client:
        modell_update.neuere_pruefen(client=client, jetzt=jetzt)
        modell_update.neuere_pruefen(client=client, jetzt=jetzt + timedelta(hours=5))
        assert refs.anfragen == 1
        modell_update.neuere_pruefen(client=client, jetzt=jetzt + timedelta(days=1, minutes=1))
        assert refs.anfragen == 2


def test_ohne_geladenes_modell_geht_nichts_ins_netz(ziel):
    refs = Refs(["v9.0"])
    with refs.client() as client:
        assert modell_update.neuere_pruefen(client=client) == {}
    assert refs.anfragen == 0


def test_netzfehler_bleibt_still(ziel, hub):
    _laden(hub)

    def weg(request):
        raise httpx.ConnectError("offline", request=request)

    with httpx.Client(transport=httpx.MockTransport(weg)) as client:
        assert modell_update.neuere_pruefen(client=client) == {}


# --------------------------------------------------------------------------- #
#  Start der App
# --------------------------------------------------------------------------- #
def test_app_start_ohne_modell_startet_keinen_faden(ziel, tmp_path):
    from pollysort.web.dienst import Dienst
    assert Dienst(None).hintergrund_aktualisieren() is None


def test_app_start_mit_ausgeschaltetem_update_tut_nichts(ziel, hub):
    _laden(hub)
    cfg = config.AppConfig(beenara_auto_update=False)
    config.save_config(cfg)
    from pollysort.web.dienst import Dienst
    assert Dienst(None).hintergrund_aktualisieren() is None


def test_app_start_laedt_veraltetes_modell_im_hintergrund(ziel, hub, monkeypatch):
    _laden(hub)
    _pin_anheben(hub, monkeypatch)
    from pollysort.web.dienst import Dienst
    dienst = Dienst(None)
    gerufen = threading.Event()
    monkeypatch.setattr(modell_update, "neuere_pruefen", lambda **_: {})
    echt = modell_update.aktualisieren
    monkeypatch.setattr(modell_update, "aktualisieren",
                        lambda con, client=None: _mit_hub(echt, hub, con, gerufen))
    faden = dienst.hintergrund_aktualisieren()
    assert faden is not None
    faden.join(timeout=10)
    assert gerufen.is_set() and modell_update.veraltet() == []
    ereignisse = [(e["name"], e["zustand"]) for e in dienst.bus.letzte() if e.get("art") == "auftrag"]
    assert ereignisse == [("modelle_aktualisieren", "start"), ("modelle_aktualisieren", "ende")]


def _mit_hub(echt, hub, con, gerufen):
    with hub.client() as client:
        ergebnis = echt(con, client=client)
    gerufen.set()
    return ergebnis


def test_schalter_in_der_werkstatt(ziel):
    from pollysort.web.dienst import Dienst
    dienst = Dienst(None)
    antwort = dienst.beenara_auto_update(an=False)
    assert antwort["ergebnis"]["auto_update"] is False
    assert config.load_config().beenara_auto_update is False
    assert dienst.beenara_auto_update(an=True)["ergebnis"]["auto_update"] is True

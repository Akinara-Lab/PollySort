"""Das Gedächtnis-Modell über Ollama laden — Konsole, Skript-CLI und Werkstatt.

Ollama antwortet auf ``POST /api/pull`` mit einer Zeile JSON je Schritt. Ein nachgebauter Server
(``httpx.MockTransport``) spielt diese Zeilen ab; das echte Netz ist in den Tests gesperrt.
"""

from __future__ import annotations

import json
from contextlib import contextmanager

import httpx
import pytest

from pollysort import config, i18n, ollama_laden
from pollysort.config import AppConfig
from pollysort.llm import client as client_mod
from pollysort.llm.client import OLLAMA_EMBED_MODEL, OLLAMA_MODEL
from pollysort.web.dienst import Dienst

MB = 1_000_000


@pytest.fixture(autouse=True)
def _eigenes_zuhause(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(config, "POLLYSORT_HOME", home)
    monkeypatch.setattr(config, "CONFIG_PATH", home / "config.toml")
    monkeypatch.setattr(config, "CREDENTIALS_PATH", home / "credentials")
    monkeypatch.setattr(config, "PROJECTS_PATH", home / "projects.txt")
    yield
    i18n.set_language("de")


class Con:
    """Sammelt Meldungen; der Fortschritt merkt sich, was zuletzt gesetzt wurde."""

    def __init__(self) -> None:
        self.lines: list[tuple[str, str]] = []
        self.total = None
        self.completed = 0

    def _sammler(art):
        def melden(self, msg="", *_a, **_k):
            self.lines.append((art, str(msg)))
        return melden

    raw = _sammler("raw")
    info = _sammler("info")
    honey = _sammler("honey")
    error = _sammler("error")
    ask = _sammler("ask")
    bloom = _sammler("bloom")
    rule = _sammler("rule")

    @contextmanager
    def progress(self, *_a, **_k):
        yield self

    def add_task(self, _desc, total=None):
        return 0

    def update(self, _task, *, total=None, completed=None, **_k):
        if total is not None:
            self.total = total
        if completed is not None:
            self.completed = completed

    def advance(self, *_a, **_k):
        pass

    def text(self, art: str | None = None) -> str:
        return "\n".join(m for a, m in self.lines if art in (None, a))


def _zeilen(*schritte: dict) -> bytes:
    return b"".join(json.dumps(s).encode() + b"\n" for s in schritte)


ABLAUF = _zeilen(
    {"status": "pulling manifest"},
    {"status": "pulling aaa", "digest": "sha256:aaa", "total": 900 * MB, "completed": 0},
    {"status": "pulling aaa", "digest": "sha256:aaa", "total": 900 * MB, "completed": 450 * MB},
    {"status": "pulling aaa", "digest": "sha256:aaa", "total": 900 * MB, "completed": 900 * MB},
    {"status": "pulling bbb", "digest": "sha256:bbb", "total": 2 * MB, "completed": 2 * MB},
    {"status": "verifying sha256 digest"},
    {"status": "writing manifest"},
    {"status": "success"},
)


def _ollama(antwort: bytes = ABLAUF, *, status: int = 200, anfragen: list | None = None):
    """Ein nachgebauter Ollama-Server als httpx-Client."""
    def handler(request: httpx.Request) -> httpx.Response:
        if anfragen is not None:
            anfragen.append((request.url.path, json.loads(request.content)))
        return httpx.Response(status, content=antwort)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_laden_zeigt_fortschritt_in_bytes_und_meldet_erfolg():
    con, anfragen = Con(), []
    assert ollama_laden.laden(con, endpoint="http://ollama", client=_ollama(anfragen=anfragen))
    assert anfragen == [("/api/pull", {"model": OLLAMA_EMBED_MODEL, "name": OLLAMA_EMBED_MODEL,
                                       "stream": True})]
    # Summe aller Schichten, und am Ende ist alles da
    assert con.total == 902 * MB and con.completed == 902 * MB
    assert OLLAMA_EMBED_MODEL in con.text("honey")
    assert not con.text("error")


def test_ein_anderes_modell_geht_auch():
    con, anfragen = Con(), []
    assert ollama_laden.laden(con, "qwen3.5:9b", endpoint="http://ollama",
                              client=_ollama(anfragen=anfragen))
    assert anfragen[0][1]["model"] == "qwen3.5:9b"


def test_fehlerzeile_von_ollama_wird_gemeldet():
    con = Con()
    antwort = _zeilen({"status": "pulling manifest"},
                      {"error": "pull model manifest: file does not exist"})
    assert not ollama_laden.laden(con, endpoint="http://ollama", client=_ollama(antwort))
    assert "file does not exist" in con.text("error")


def test_http_fehler_wird_gemeldet_nicht_geworfen():
    con = Con()
    antwort = json.dumps({"error": "model not found"}).encode()
    assert not ollama_laden.laden(con, endpoint="http://ollama",
                                  client=_ollama(antwort, status=500))
    assert "model not found" in con.text("error")


def test_ohne_success_gilt_der_download_als_nicht_fertig():
    con = Con()
    antwort = _zeilen({"status": "pulling aaa", "digest": "sha256:aaa", "total": 10, "completed": 5})
    assert not ollama_laden.laden(con, endpoint="http://ollama", client=_ollama(antwort))
    assert con.text("error") == i18n.t("om.err.incomplete")


def test_ollama_laeuft_nicht():
    def handler(request):
        raise httpx.ConnectError("Verbindung abgelehnt", request=request)
    con = Con()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert not ollama_laden.laden(con, endpoint="http://127.0.0.1:11434", client=client)
    assert con.text("error") == i18n.t("om.err.offline", url="http://127.0.0.1:11434")


def test_kaputte_zeile_reisst_nichts_ab():
    con = Con()
    assert not ollama_laden.laden(con, endpoint="http://ollama", client=_ollama(b"{kaputt\n"))
    assert con.text("error")


def test_endpunkt_wie_im_modus_lokal(monkeypatch):
    assert ollama_laden.endpunkt() == "http://127.0.0.1:11434"
    monkeypatch.setattr(config, "load_config",
                        lambda: AppConfig(llm_endpoint="http://gpu-kiste:11434/v1/"))
    assert ollama_laden.endpunkt() == "http://gpu-kiste:11434"


@pytest.mark.parametrize("modelle, erreichbar, vorhanden, art", [
    (None, False, False, "ask"),
    ([], True, False, "ask"),
    (["qwen3.5:9b"], True, False, "ask"),
    ([f"{OLLAMA_EMBED_MODEL}:latest"], True, True, "honey"),
])
def test_stand_und_bericht(monkeypatch, modelle, erreichbar, vorhanden, art):
    monkeypatch.setattr(ollama_laden, "ollama_models", lambda *_a, **_k: modelle)
    s = ollama_laden.stand()
    assert (s.erreichbar, s.vorhanden) == (erreichbar, vorhanden)
    zeilen = ollama_laden.bericht(s)
    assert len(zeilen) == 1 and zeilen[0][0] == art


def test_beide_rollen_mit_einer_frage(monkeypatch):
    fragen = []
    monkeypatch.setattr(ollama_laden, "ollama_models",
                        lambda *a, **_k: fragen.append(a) or [f"{OLLAMA_EMBED_MODEL}:latest"])
    sprache, gedaechtnis = ollama_laden.staende()
    assert len(fragen) == 1
    assert (sprache.rolle, sprache.modell, sprache.vorhanden) == ("sprache", OLLAMA_MODEL, False)
    assert (gedaechtnis.rolle, gedaechtnis.vorhanden) == ("gedaechtnis", True)
    assert ollama_laden.bericht(sprache) == [
        ("ask", "🦙", i18n.t("om.missing.sprache", modell=OLLAMA_MODEL))]
    zeilen = ollama_laden.bericht_alle([sprache, gedaechtnis])
    assert [z[2].split(":")[0] for z in zeilen] == [i18n.t("om.rolle.sprache"),
                                                    i18n.t("om.rolle.gedaechtnis")]


def test_rolle_von_ist_tag_tolerant():
    assert ollama_laden.rolle_von(OLLAMA_MODEL) == "sprache"
    assert ollama_laden.rolle_von(f"{OLLAMA_EMBED_MODEL}:latest") == "gedaechtnis"
    assert ollama_laden.rolle_von("qwen3.5:0.8b") is None


def test_fertig_meldung_nach_rolle():
    for modell, schluessel in ((OLLAMA_MODEL, "om.done.sprache"),
                               (OLLAMA_EMBED_MODEL, "om.done.gedaechtnis"),
                               ("qwen3.5:0.8b", "om.done")):
        con = Con()
        assert ollama_laden.laden(con, modell, endpoint="http://ollama", client=_ollama())
        assert con.text("honey") == i18n.t(schluessel, modell=modell)


def test_fehlende_laden(monkeypatch):
    gezogen = []
    monkeypatch.setattr(ollama_laden, "laden", lambda _con, m, **_k: gezogen.append(m) or True)
    monkeypatch.setattr(ollama_laden, "ollama_models", lambda *_a, **_k: [])
    assert ollama_laden.fehlende_laden(Con())
    assert gezogen == [OLLAMA_MODEL, OLLAMA_EMBED_MODEL]

    gezogen.clear()
    monkeypatch.setattr(ollama_laden, "ollama_models",
                        lambda *_a, **_k: [OLLAMA_MODEL, OLLAMA_EMBED_MODEL])
    con = Con()
    assert ollama_laden.fehlende_laden(con) and gezogen == []
    assert con.text("honey") == i18n.t("om.all_present")

    monkeypatch.setattr(ollama_laden, "ollama_models", lambda *_a, **_k: None)
    con = Con()
    assert not ollama_laden.fehlende_laden(con, endpoint="http://x")
    assert con.text("error") == i18n.t("om.err.offline", url="http://x")


# --------------------------------------------------------------------------- #
#  Konsole und Skript-CLI
# --------------------------------------------------------------------------- #
def _shell(con):
    from pollysort.repl import BeehiveShell
    sh = BeehiveShell.__new__(BeehiveShell)
    sh.con = con
    sh.hive = None
    return sh


def test_konsole_laedt_was_fehlt_eine_rolle_oder_ein_genanntes(monkeypatch):
    gezogen = []
    monkeypatch.setattr(ollama_laden, "laden", lambda _con, m, **_k: gezogen.append(m) or True)
    monkeypatch.setattr(ollama_laden, "ollama_models", lambda *_a, **_k: [OLLAMA_MODEL])
    sh = _shell(Con())
    sh.do_ollama("laden")                         # fehlt nur das Gedächtnis-Modell
    sh.do_ollama("pull sprache")
    sh.do_ollama("laden RAG")
    sh.do_ollama("pull language")
    # Der Rat von 'doctor' („ollama pull qwen3.5:9b") klappt auch in der Konsole
    sh.do_ollama("pull qwen3.5:0.8b")
    assert gezogen == [OLLAMA_EMBED_MODEL, OLLAMA_MODEL, OLLAMA_EMBED_MODEL, OLLAMA_MODEL,
                       "qwen3.5:0.8b"]


def test_konsole_zeigt_den_stand_und_die_nutzung(monkeypatch):
    monkeypatch.setattr(ollama_laden, "ollama_models", lambda *_a, **_k: None)
    con = Con()
    _shell(con).do_ollama("")
    assert i18n.t("om.status.offline") in con.text("ask")
    _shell(con).do_ollama("quatsch")
    assert i18n.t("om.usage") in con.text("ask")

    monkeypatch.setattr(ollama_laden, "ollama_models", lambda *_a, **_k: [OLLAMA_EMBED_MODEL])
    con = Con()
    _shell(con).do_ollama("status")
    assert i18n.t("om.missing.sprache", modell=OLLAMA_MODEL) in con.text("ask")
    assert i18n.t("om.status.ready", modell=OLLAMA_EMBED_MODEL) in con.text("honey")


def test_konsole_unerwarteter_fehler_wird_gemeldet(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("kaputt")
    monkeypatch.setattr(ollama_laden, "nach_wunsch", boom)
    con = Con()
    _shell(con).do_ollama("laden")
    assert "kaputt" in con.text("error")


def test_skript_cli_exit_codes(monkeypatch):
    from typer.testing import CliRunner

    from pollysort.cli import app
    runner = CliRunner()
    monkeypatch.setattr(ollama_laden, "ollama_models",
                        lambda *_a, **_k: [OLLAMA_MODEL, f"{OLLAMA_EMBED_MODEL}:latest"])
    assert runner.invoke(app, ["ollama"]).exit_code == 0
    monkeypatch.setattr(ollama_laden, "ollama_models", lambda *_a, **_k: [OLLAMA_EMBED_MODEL])
    assert runner.invoke(app, ["ollama", "status"]).exit_code == 1, "Sprachmodell fehlt"
    gezogen = []
    monkeypatch.setattr(ollama_laden, "laden", lambda _con, m, **_k: gezogen.append(m) or True)
    assert runner.invoke(app, ["ollama", "pull"]).exit_code == 0
    assert runner.invoke(app, ["ollama", "pull", "memory"]).exit_code == 0
    assert runner.invoke(app, ["ollama", "pull", "qwen3.5:0.8b"]).exit_code == 0
    assert gezogen == [OLLAMA_MODEL, OLLAMA_EMBED_MODEL, "qwen3.5:0.8b"]
    assert runner.invoke(app, ["ollama", "quatsch"]).exit_code == 2


# --------------------------------------------------------------------------- #
#  Werkstatt (Flugbrett)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("rolle, modell", [("gedaechtnis", OLLAMA_EMBED_MODEL),
                                           ("sprache", OLLAMA_MODEL)])
def test_werkstatt_laedt_mit_fortschritt_in_mb(monkeypatch, rolle, modell):
    echt = ollama_laden.laden
    gezogen = []
    monkeypatch.setattr(ollama_laden, "laden", lambda con, m: gezogen.append(m) or echt(
        con, m, endpoint="http://ollama", client=_ollama()))
    monkeypatch.setattr(ollama_laden, "ollama_models", lambda *_a, **_k: [modell])
    d = Dienst()
    antwort = d.ollama_modell_laden(rolle=rolle)
    assert gezogen == [modell]
    assert antwort["ergebnis"]["ok"] is True
    stand = {m["rolle"]: m for m in antwort["ergebnis"]["ollama"]["modelle"]}
    assert stand[rolle]["vorhanden"] is True
    bytes_ = [e for e in d.bus.letzte() if e.get("einheit") == "bytes"]
    assert bytes_ and bytes_[-1]["erledigt"] == bytes_[-1]["gesamt"] == 902 * MB
    assert any(modell in m["text"] for m in antwort["meldungen"])


def test_werkstatt_kennt_nur_die_beiden_rollen():
    from pollysort.web.dienst import Ungueltig
    with pytest.raises(Ungueltig):
        Dienst().ollama_modell_laden(rolle="irgendwas")


def test_werkstatt_ausfall_reisst_nichts_ab(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("kaputt")
    monkeypatch.setattr(ollama_laden, "laden", boom)
    monkeypatch.setattr(ollama_laden, "ollama_models", lambda *_a, **_k: None)
    d = Dienst()
    antwort = d.ollama_modell_laden()
    assert antwort["ergebnis"]["ok"] is False
    assert antwort["ergebnis"]["ollama"]["erreichbar"] is False
    assert any("kaputt" in m["text"] for m in antwort["meldungen"])


def test_werkstatt_stand_ohne_projekt(monkeypatch):
    monkeypatch.setattr(ollama_laden, "ollama_models", lambda *_a, **_k: [OLLAMA_MODEL])
    stand = Dienst().ollama_modelle()
    assert stand["erreichbar"] is True
    sprache, gedaechtnis = stand["modelle"]
    assert (sprache["rolle"], sprache["vorhanden"], sprache["gb"]) == ("sprache", True, 6.6)
    assert (gedaechtnis["modell"], gedaechtnis["vorhanden"]) == (OLLAMA_EMBED_MODEL, False)
    assert gedaechtnis["zeilen"][0]["text"] == i18n.t("om.missing.gedaechtnis",
                                                      modell=OLLAMA_EMBED_MODEL)


def test_ollama_models_ist_der_echte_helfer():
    """``stand`` fragt über denselben Helfer wie ``doctor`` — nicht über einen eigenen Weg."""
    assert ollama_laden.ollama_models is client_mod.ollama_models

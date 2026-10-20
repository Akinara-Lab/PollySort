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
from pollysort.llm.client import OLLAMA_EMBED_MODEL
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


# --------------------------------------------------------------------------- #
#  Konsole und Skript-CLI
# --------------------------------------------------------------------------- #
def _shell(con):
    from pollysort.repl import BeehiveShell
    sh = BeehiveShell.__new__(BeehiveShell)
    sh.con = con
    sh.hive = None
    return sh


def test_konsole_laedt_das_gedaechtnis_modell_oder_ein_genanntes(monkeypatch):
    aufrufe = []
    monkeypatch.setattr(ollama_laden, "laden", lambda _con, *a: aufrufe.append(a) or True)
    sh = _shell(Con())
    for befehl in ("laden", "pull", "update"):
        sh.do_ollama(befehl)
    # Der Rat von 'doctor' („ollama pull qwen3.5:9b") klappt auch in der Konsole
    sh.do_ollama("pull qwen3.5:9b")
    assert aufrufe == [(), (), (), ("qwen3.5:9b",)]


def test_konsole_zeigt_den_stand_und_die_nutzung(monkeypatch):
    monkeypatch.setattr(ollama_laden, "ollama_models", lambda *_a, **_k: None)
    con = Con()
    _shell(con).do_ollama("")
    assert i18n.t("om.status.offline") in con.text("ask")
    _shell(con).do_ollama("quatsch")
    assert i18n.t("om.usage") in con.text("ask")


def test_konsole_unerwarteter_fehler_wird_gemeldet(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("kaputt")
    monkeypatch.setattr(ollama_laden, "laden", boom)
    con = Con()
    _shell(con).do_ollama("laden")
    assert "kaputt" in con.text("error")


def test_skript_cli_exit_codes(monkeypatch):
    from typer.testing import CliRunner

    from pollysort.cli import app
    runner = CliRunner()
    monkeypatch.setattr(ollama_laden, "ollama_models",
                        lambda *_a, **_k: [f"{OLLAMA_EMBED_MODEL}:latest"])
    assert runner.invoke(app, ["ollama"]).exit_code == 0
    monkeypatch.setattr(ollama_laden, "ollama_models", lambda *_a, **_k: [])
    assert runner.invoke(app, ["ollama", "status"]).exit_code == 1
    gezogen = []
    monkeypatch.setattr(ollama_laden, "laden", lambda _con, *a: gezogen.append(a) or True)
    assert runner.invoke(app, ["ollama", "pull"]).exit_code == 0
    assert runner.invoke(app, ["ollama", "pull", "qwen3.5:9b"]).exit_code == 0
    assert gezogen == [(), ("qwen3.5:9b",)]
    assert runner.invoke(app, ["ollama", "quatsch"]).exit_code == 2


# --------------------------------------------------------------------------- #
#  Werkstatt (Flugbrett)
# --------------------------------------------------------------------------- #
def test_werkstatt_laedt_mit_fortschritt_in_mb(monkeypatch):
    echt = ollama_laden.laden
    monkeypatch.setattr(ollama_laden, "laden",
                        lambda con: echt(con, endpoint="http://ollama", client=_ollama()))
    monkeypatch.setattr(ollama_laden, "ollama_models",
                        lambda *_a, **_k: [f"{OLLAMA_EMBED_MODEL}:latest"])
    d = Dienst()
    antwort = d.ollama_modell_laden()
    assert antwort["ergebnis"]["ok"] is True
    assert antwort["ergebnis"]["ollama"]["vorhanden"] is True
    bytes_ = [e for e in d.bus.letzte() if e.get("einheit") == "bytes"]
    assert bytes_ and bytes_[-1]["erledigt"] == bytes_[-1]["gesamt"] == 902 * MB
    assert any(OLLAMA_EMBED_MODEL in m["text"] for m in antwort["meldungen"])


def test_werkstatt_ausfall_reisst_nichts_ab(monkeypatch):
    def boom(_con):
        raise RuntimeError("kaputt")
    monkeypatch.setattr(ollama_laden, "laden", boom)
    monkeypatch.setattr(ollama_laden, "ollama_models", lambda *_a, **_k: None)
    d = Dienst()
    antwort = d.ollama_modell_laden()
    assert antwort["ergebnis"]["ok"] is False
    assert antwort["ergebnis"]["ollama"]["erreichbar"] is False
    assert any("kaputt" in m["text"] for m in antwort["meldungen"])


def test_werkstatt_stand_ohne_projekt(monkeypatch):
    monkeypatch.setattr(ollama_laden, "ollama_models", lambda *_a, **_k: ["qwen3.5:9b"])
    stand = Dienst().ollama_modell()
    assert stand["erreichbar"] is True and stand["vorhanden"] is False
    assert stand["modell"] == OLLAMA_EMBED_MODEL
    assert stand["zeilen"][0]["text"] == i18n.t("om.status.missing", modell=OLLAMA_EMBED_MODEL)


def test_ollama_models_ist_der_echte_helfer():
    """``stand`` fragt über denselben Helfer wie ``doctor`` — nicht über einen eigenen Weg."""
    assert ollama_laden.ollama_models is client_mod.ollama_models

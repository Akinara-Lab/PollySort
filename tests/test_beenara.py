"""BeeNara von Hugging Face laden (beenara.py) — gegen einen nachgebauten Hub, nie ins Netz.

Abgesichert ist, was beim echten Download schiefgehen kann: ein abgebrochener Download muss
fortsetzen statt neu anzufangen, eine kaputte Datei darf nie ihren endgültigen Namen
bekommen, ein Update lädt nur, was sich geändert hat, und Fehler werden gemeldet statt den
Erststart abzureißen.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager

import httpx
import pytest

from pollysort import beenara, config, doctor, i18n

SHA_A = beenara.REVISION          # der festgenagelte Commit
SHA_B = "b" * 40                  # ein späterer, auf den ein Update den Pin anhebt

DATEIEN = {
    "onnx/beenara.onnx": bytes(range(256)) * 40,              # 10 240 Bytes, LFS
    "onnx/calibration.json": b'{"option_temperature": 1.2}',
    "tokenizer/tokenizer.json": b'{"model": "x"}' * 300,      # LFS
    "tokenizer/tokenizer_config.json": b'{"mask_token": "[MASK]"}',
    "LICENSE": b"Apache License 2.0",
    "NOTICE": b"BeeNara - Akinara",
}
LFS = ("onnx/beenara.onnx", "tokenizer/tokenizer.json")


def _git_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


class Hub:
    """Ein Hugging-Face-Hub im Kleinen: Revision-API, ``resolve`` mit Umleitung aufs CDN,
    Range-Anfragen wie beim echten Xet-CDN."""

    def __init__(self) -> None:
        self.sha = SHA_A
        self.files = dict(DATEIEN)
        self.requests: list[httpx.Request] = []
        self.down = False
        self.ignore_range = False
        self.corrupt: set[str] = set()
        self.interrupt: set[str] = set()

    def _siblings(self) -> list[dict]:
        out = [{"rfilename": "README.md", "blobId": "0" * 40, "size": 10},
               {"rfilename": "beenara.py", "blobId": "1" * 40, "size": 10}]
        for p, data in self.files.items():
            s = {"rfilename": p, "blobId": _git_sha1(data), "size": len(data)}
            if p in LFS:
                s["lfs"] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                            "pointerSize": 134}
            out.append(s)
        return out

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            raise httpx.ConnectError("getaddrinfo failed", request=request)
        path = request.url.path
        if path == f"/api/models/{beenara.REPO}/revision/{beenara.REVISION}":
            assert request.url.params.get("blobs") == "true"
            return httpx.Response(200, json={"sha": self.sha, "siblings": self._siblings()})
        resolve = f"/{beenara.REPO}/resolve/{self.sha}/"
        if path.startswith(resolve):
            return httpx.Response(302, headers={
                "Location": f"https://cdn.example/xet/{path[len(resolve):]}?Signature=x"})
        if request.url.host == "cdn.example":
            p = path[len("/xet/"):]
            if p in self.interrupt:
                raise KeyboardInterrupt
            data = self.files[p]
            if p in self.corrupt:
                data = b"!" + data[1:]
            rng = request.headers.get("range")
            if rng and not self.ignore_range:
                return httpx.Response(206, content=data[int(rng.split("=")[1].rstrip("-")):])
            return httpx.Response(200, content=data)
        return httpx.Response(404)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self), follow_redirects=True)

    def geladen(self) -> list[str]:
        return [r.url.path[len("/xet/"):] for r in self.requests if r.url.host == "cdn.example"]

    def range_of(self, p: str) -> str | None:
        return next((r.headers.get("range") for r in self.requests
                     if r.url.host == "cdn.example" and r.url.path.endswith(p)), None)


class Con:
    """Sammelt die Ausgaben; der Fortschritt zählt mit, statt zu zeichnen."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.total: int | None = None
        self.done = 0

    def _add(self, msg="", *_a, **_k) -> None:
        self.lines.append(str(msg))

    raw = info = honey = error = ask = bloom = rule = _add

    @contextmanager
    def progress(self, *_a, **_k):
        yield self

    def add_task(self, _desc, total=None):
        self.total = total
        return 0

    def advance(self, _task, n):
        self.done += n

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@pytest.fixture
def ziel(tmp_path, monkeypatch):
    """Eigene globale Ablage je Test — nie die echte ~/.pollysort."""
    monkeypatch.setattr(config, "POLLYSORT_HOME", tmp_path)
    monkeypatch.delenv("HF_ENDPOINT", raising=False)
    return tmp_path / "modelle" / "BeeNara"


@pytest.fixture
def hub():
    return Hub()


def _laden(hub: Hub, con: Con | None = None) -> bool:
    with hub.client() as client:
        return beenara.laden(con or Con(), client=client)


# --------------------------------------------------------------------------- #
#  Download
# --------------------------------------------------------------------------- #
def test_laedt_alle_dateien_aus_einem_commit_und_prueft_sie(ziel, hub):
    con = Con()
    assert _laden(hub, con) is True
    for p, data in DATEIEN.items():
        assert (ziel / p).read_bytes() == data
    assert not list(ziel.rglob("*.part"))
    herkunft = json.loads((ziel / beenara.HERKUNFT).read_text(encoding="utf-8"))
    assert herkunft["repo"] == "Kwokou/BeeNara" and herkunft["revision"] == SHA_A
    assert beenara.stand().vollstaendig
    assert con.total == con.done == sum(len(d) for d in DATEIEN.values())


def test_fremder_code_und_modellkarte_bleiben_auf_dem_hub(ziel, hub):
    """``beenara.py`` aus dem Repo wird nie geladen — PollySort führt keinen Code aus dem Netz aus."""
    _laden(hub)
    assert "beenara.py" not in hub.geladen() and "README.md" not in hub.geladen()
    assert not (ziel / "beenara.py").exists()


def test_zweites_laden_fragt_nicht_einmal_nach(ziel, hub):
    """Der Commit ist fest — liegt er vollständig da, geht 'beenara laden' nicht ins Netz
    (und klappt so auch offline)."""
    _laden(hub)
    hub.requests.clear()
    con = Con()
    assert _laden(hub, con) is True
    assert hub.requests == []
    assert "aktuell" in con.text


def test_andere_version_wird_nachgeladen(ziel, hub, monkeypatch):
    """Liegt ein anderer Commit da als der, auf den die Laufzeit abgestimmt ist, sortiert
    BeeNara nicht mit, bis 'beenara laden' den passenden geholt hat."""
    _laden(hub)
    monkeypatch.setattr(beenara, "laufzeit_fehlt", lambda: [])
    monkeypatch.setattr(beenara, "REVISION", SHA_B)
    assert beenara.warum_nicht(config.AppConfig()) == "version"
    hub.sha = SHA_B
    assert _laden(hub) is True
    assert beenara.warum_nicht(config.AppConfig()) is None


def test_abgebrochener_download_setzt_fort(ziel, hub):
    onnx = DATEIEN["onnx/beenara.onnx"]
    part = ziel / "onnx" / "beenara.onnx.part"
    part.parent.mkdir(parents=True)
    part.write_bytes(onnx[:4000])
    con = Con()
    assert _laden(hub, con) is True
    assert hub.range_of("beenara.onnx") == "bytes=4000-", "Range muss die Umleitung überleben"
    assert (ziel / "onnx" / "beenara.onnx").read_bytes() == onnx
    assert con.done == con.total


def test_server_ohne_range_faengt_die_datei_von_vorn_an(ziel, hub):
    hub.ignore_range = True
    part = ziel / "onnx" / "beenara.onnx.part"
    part.parent.mkdir(parents=True)
    part.write_bytes(b"?" * 4000)                 # Rest eines anderen Versuchs
    assert _laden(hub) is True
    assert (ziel / "onnx" / "beenara.onnx").read_bytes() == DATEIEN["onnx/beenara.onnx"]


@pytest.mark.parametrize("datei", ["onnx/beenara.onnx", "onnx/calibration.json"])
def test_falsche_pruefsumme_bekommt_nie_den_endgueltigen_namen(ziel, hub, datei):
    """Gilt für LFS-Dateien (SHA-256) genauso wie für kleine Dateien (Git-Blob-ID)."""
    hub.corrupt.add(datei)
    con = Con()
    assert _laden(hub, con) is False
    assert not (ziel / datei).exists()
    assert not (ziel / (datei + ".part")).exists(), "Kaputtes darf nicht fortgesetzt werden"
    assert not (ziel / beenara.HERKUNFT).exists()
    assert "Prüfsumme" in con.text
    assert not beenara.stand().vollstaendig


def test_hub_nicht_erreichbar_meldet_und_legt_nichts_an(ziel, hub):
    hub.down = True
    con = Con()
    assert _laden(hub, con) is False
    assert "nicht erreichbar" in con.text and "getaddrinfo" in con.text
    assert not ziel.exists()


def test_repo_ohne_modelldatei_wird_abgelehnt(ziel, hub):
    del hub.files["onnx/beenara.onnx"]
    con = Con()
    assert _laden(hub, con) is False
    assert "onnx/beenara.onnx" in con.text
    assert hub.geladen() == []


def test_zu_wenig_platz_laedt_nicht_erst_an(ziel, hub, monkeypatch):
    class Voll:
        free = 10_000_000

    monkeypatch.setattr(beenara.shutil, "disk_usage", lambda _p: Voll())
    con = Con()
    assert _laden(hub, con) is False
    assert "Speicherplatz" in con.text
    assert hub.geladen() == []


def test_strg_c_behaelt_den_rest_fuer_das_naechste_mal(ziel, hub):
    hub.interrupt.add("tokenizer/tokenizer.json")
    con = Con()
    assert _laden(hub, con) is False
    assert "unterbrochen" in con.text
    assert (ziel / "onnx" / "beenara.onnx.part").exists(), "Geprüftes Teil bleibt liegen"
    assert not (ziel / "onnx" / "beenara.onnx").exists(), "Getauscht wird erst am Ende"
    assert beenara.stand().angefangen

    hub.interrupt.clear()
    hub.requests.clear()
    assert _laden(hub) is True
    assert "onnx/beenara.onnx" not in hub.geladen(), "Fertiges darf nicht noch einmal kommen"
    assert "tokenizer/tokenizer.json" in hub.geladen()


def test_update_laedt_nur_geaenderte_dateien(ziel, hub, monkeypatch):
    _laden(hub)
    monkeypatch.setattr(beenara, "REVISION", SHA_B)       # PollySort-Update hebt den Pin
    hub.sha = SHA_B
    hub.files["onnx/calibration.json"] = b'{"option_temperature": 1.3}'
    hub.requests.clear()
    assert _laden(hub) is True
    assert hub.geladen() == ["onnx/calibration.json"]
    assert (ziel / "onnx" / "calibration.json").read_bytes() == b'{"option_temperature": 1.3}'
    assert beenara.stand().revision == SHA_B


def test_abgebrochenes_update_mischt_keine_versionen(ziel, hub, monkeypatch):
    """Neues Modell neben alter Kalibrierung wäre schlimmer als ein altes Modell: Die
    Kalibrierung gehört zu genau einem Artefakt. Bricht das Update ab, bleibt v1 ganz."""
    _laden(hub)
    alt_onnx = DATEIEN["onnx/beenara.onnx"]
    monkeypatch.setattr(beenara, "REVISION", SHA_B)
    hub.sha = SHA_B
    hub.files["onnx/beenara.onnx"] = bytes(reversed(alt_onnx))
    hub.files["onnx/calibration.json"] = b'{"option_temperature": 1.3}'
    hub.interrupt.add("onnx/calibration.json")
    assert _laden(hub) is False
    assert (ziel / "onnx" / "beenara.onnx").read_bytes() == alt_onnx
    s = beenara.stand()
    assert s.vollstaendig and s.revision == SHA_A

    hub.interrupt.clear()
    assert _laden(hub) is True
    assert (ziel / "onnx" / "beenara.onnx").read_bytes() == bytes(reversed(alt_onnx))
    assert beenara.stand().revision == SHA_B


def test_hf_endpoint_lenkt_auf_einen_spiegel(ziel, hub, monkeypatch):
    monkeypatch.setenv("HF_ENDPOINT", "https://spiegel.example/")
    _laden(hub)
    assert hub.requests[0].url.host == "spiegel.example"


# --------------------------------------------------------------------------- #
#  Stand, Doctor, Entfernen
# --------------------------------------------------------------------------- #
def test_stand_ohne_modell(ziel):
    s = beenara.stand()
    assert not s.vollstaendig and not s.angefangen and s.belegt == 0


def test_stand_bemerkt_fehlende_datei(ziel, hub):
    _laden(hub)
    (ziel / "tokenizer" / "tokenizer.json").unlink()
    s = beenara.stand()
    assert not s.vollstaendig and s.angefangen


def test_doctor_zeigt_beenara(ziel, hub, monkeypatch):
    def check():
        return {c[0]: c for c in doctor.run_checks(None)}["BeeNara"]

    monkeypatch.setattr(doctor.config, "load_config",
                        lambda: config.AppConfig(llm_provider="offline"))
    _, status, detail = check()
    assert status == "ok", "Nicht geladen ist optional — kein Warnfall, kein Exit-Code 1"
    assert "beenara laden" in detail

    ziel.mkdir(parents=True)
    (ziel / "beenara.onnx.part").write_bytes(b"x")
    assert check()[1] == "warn"

    _laden(hub)
    monkeypatch.setattr(beenara, "laufzeit_fehlt", lambda: ["onnxruntime"])
    _, status, detail = check()
    assert status == "warn" and "Laufzeit fehlt" in detail, "Modell da, Laufzeit nicht"

    monkeypatch.setattr(beenara, "laufzeit_fehlt", lambda: [])
    _, status, detail = check()
    assert status == "ok" and SHA_A[:7] in detail

    monkeypatch.setattr(doctor.config, "load_config",
                        lambda: config.AppConfig(llm_provider="offline", beenara=False))
    _, status, detail = check()
    assert status == "ok" and "ausgeschaltet" in detail


def test_entfernen_loescht_nur_den_modellordner(ziel, hub):
    _laden(hub)
    (config.POLLYSORT_HOME / "config.toml").write_text("x", encoding="utf-8")
    beenara.entfernen()
    assert not ziel.exists()
    assert (config.POLLYSORT_HOME / "config.toml").exists()


# --------------------------------------------------------------------------- #
#  Konsole
# --------------------------------------------------------------------------- #
def _shell(con):
    from pollysort.repl import BeehiveShell
    sh = BeehiveShell.__new__(BeehiveShell)
    sh.con = con
    sh.hive = None
    return sh


def test_konsole_entfernen_fragt_vorher(ziel, hub, monkeypatch):
    import builtins
    _laden(hub)
    sh = _shell(Con())
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    sh.do_beenara("entfernen")
    assert ziel.exists(), "Ohne 'ja' bleibt das Modell liegen"
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "j")
    sh.do_beenara("remove")
    assert not ziel.exists()


def test_konsole_laden_ruft_den_download(ziel, monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(beenara, "einrichten", lambda _con: calls.append(1) or True)
    sh = _shell(Con())
    for wort in ("laden", "pull", "ziehen", "update"):
        sh.do_beenara(wort)
    assert calls == [1, 1, 1, 1]


def test_unerwarteter_fehler_reisst_den_erststart_nicht_ab(ziel, monkeypatch):
    def boom(_con):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(beenara, "einrichten", boom)
    con = Con()
    assert _shell(con)._beenara_laden() is False
    assert "kaputt" in con.text


def test_konsole_status_nennt_den_befehl(ziel):
    con = Con()
    i18n.set_language("en")
    try:
        _shell(con).do_beenara("")
    finally:
        i18n.set_language("de")
    assert "beenara pull" in con.text and "Kwokou/BeeNara" in con.text


def test_meldungen_ueberleben_rich_markup():
    """rich liest „[laden | entfernen]" als Markup-Tag und verschluckt es — so stand einmal
    nur „Nutzung: beenara " auf der Konsole. Die Ja/Nein-Frage geht an input(), nicht an rich."""
    from rich.text import Text
    for key, entry in i18n._CATALOG.items():
        if not key.startswith(("bn.", "fr.bn.", "fr.done.bn_", "doctor.bn.")) \
                or key == "bn.remove.confirm":
            continue
        for text in entry.values():
            assert Text.from_markup(text).plain == text, f"{key}: {text!r}"


# --------------------------------------------------------------------------- #
#  Laufzeit (onnxruntime, tokenizers, numpy) — nie ein echtes pip im Test
# --------------------------------------------------------------------------- #
class Lauf:
    """Ersatz für subprocess.run: merkt sich den Befehl, „installiert" auf Wunsch."""

    def __init__(self, code=0, stderr="", danach_da=True):
        self.code, self.stderr, self.danach_da = code, stderr, danach_da
        self.befehle: list[list[str]] = []

    def __call__(self, befehl, **_kw):
        import subprocess
        self.befehle.append(list(befehl))
        return subprocess.CompletedProcess(befehl, self.code, stdout="", stderr=self.stderr)


def _laufzeit(monkeypatch, lauf: Lauf, *, pip=True, uv=None):
    import importlib.util as iu
    fehlt = {"wert": ["onnxruntime", "tokenizers"]}
    echt = iu.find_spec

    def find_spec(name, *a, **k):
        if name in ("onnxruntime", "tokenizers", "numpy"):
            return None if name in fehlt["wert"] else object()
        if name == "pip":
            return object() if pip else None
        return echt(name, *a, **k)

    def run(befehl, **kw):
        res = lauf(befehl, **kw)
        if lauf.code == 0 and lauf.danach_da:
            fehlt["wert"] = []
        return res

    monkeypatch.setattr(beenara.importlib.util, "find_spec", find_spec)
    monkeypatch.setattr(beenara.shutil, "which", lambda _n: uv)
    monkeypatch.setattr(beenara.subprocess, "run", run)


def test_laufzeit_kommt_per_pip_in_die_eigene_umgebung(monkeypatch):
    import sys
    lauf = Lauf()
    _laufzeit(monkeypatch, lauf)
    con = Con()
    assert beenara.laufzeit_installieren(con) is True
    befehl = lauf.befehle[0]
    assert befehl[:4] == [sys.executable, "-m", "pip", "install"], "genau dieser Interpreter"
    assert set(beenara.PAKETE) <= set(befehl)
    assert "installiert" in con.text


def test_uv_tool_umgebung_ohne_pip_nimmt_uv(monkeypatch):
    import sys
    lauf = Lauf()
    _laufzeit(monkeypatch, lauf, pip=False, uv="C:/uv/uv.exe")
    assert beenara.laufzeit_installieren(Con()) is True
    assert lauf.befehle[0][:5] == ["C:/uv/uv.exe", "pip", "install", "--quiet", "--python"]
    assert sys.executable in lauf.befehle[0]


def test_ohne_pip_und_uv_nennt_den_befehl(monkeypatch):
    lauf = Lauf()
    _laufzeit(monkeypatch, lauf, pip=False, uv=None)
    con = Con()
    assert beenara.laufzeit_installieren(con) is False
    assert lauf.befehle == []
    assert "onnxruntime>=1.30" in con.text


def test_fehlgeschlagene_installation_zeigt_den_befehl(monkeypatch):
    lauf = Lauf(code=1, stderr="ERROR: No matching distribution found for onnxruntime")
    _laufzeit(monkeypatch, lauf)
    con = Con()
    assert beenara.laufzeit_installieren(con) is False
    assert "No matching distribution" in con.text and "pip install" in con.text


def test_installiert_aber_erst_nach_neustart_sichtbar(monkeypatch):
    _laufzeit(monkeypatch, Lauf(danach_da=False))
    con = Con()
    assert beenara.laufzeit_installieren(con) is False
    assert "neu starten" in con.text


def test_einrichten_holt_modell_und_laufzeit(ziel, hub, monkeypatch):
    lauf = Lauf()
    _laufzeit(monkeypatch, lauf)
    with hub.client() as client:
        assert beenara.einrichten(Con(), client=client) is True
    assert beenara.stand().passend and lauf.befehle
    assert beenara.warum_nicht(config.AppConfig()) is None


def test_einrichten_installiert_nichts_ohne_modell(ziel, hub, monkeypatch):
    lauf = Lauf()
    _laufzeit(monkeypatch, lauf)
    hub.down = True
    with hub.client() as client:
        assert beenara.einrichten(Con(), client=client) is False
    assert lauf.befehle == [], "Ohne Modell keine Pakete"


def test_warum_nicht_nennt_jeden_grund(ziel, hub, monkeypatch):
    assert beenara.warum_nicht(config.AppConfig()) == "modell"
    assert beenara.warum_nicht(config.AppConfig(beenara=False)) == "aus"
    _laden(hub)
    monkeypatch.setattr(beenara, "laufzeit_fehlt", lambda: ["onnxruntime"])
    assert beenara.warum_nicht(config.AppConfig()) == "laufzeit"
    monkeypatch.setattr(beenara, "laufzeit_fehlt", lambda: [])
    assert beenara.warum_nicht(config.AppConfig()) is None


def test_konsole_schaltet_an_und_aus(monkeypatch):
    gespeichert: list[bool] = []
    monkeypatch.setattr(config, "load_config", lambda: config.AppConfig())
    monkeypatch.setattr(config, "save_config", lambda cfg: gespeichert.append(cfg.beenara))
    sh = _shell(Con())
    sh.do_beenara("aus")
    sh.do_beenara("on")
    assert gespeichert == [False, True]


def test_extra_und_installationsliste_sind_gleich():
    """`pip install pollysort[beenara]` und `beenara laden` müssen dieselben Pakete holen."""
    import tomllib
    from pathlib import Path
    daten = tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml")
                          .read_text(encoding="utf-8"))
    extras = daten["project"]["optional-dependencies"]
    assert tuple(extras["beenara"]) == beenara.PAKETE
    assert any("beenara" in x for x in extras["full"])


def test_beenara_geht_auch_ohne_projekt():
    from pollysort.repl import BeehiveShell
    assert "beenara" in BeehiveShell._NO_PROJECT_OK

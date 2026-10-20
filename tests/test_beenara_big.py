"""BeeNara Big (beenara_big.py) — Modellwahl, GPU-Prüfung, Download beider Teile, Konsole, Werkstatt.

Ohne torch und ohne Netz: Der Hub ist nachgebaut, das Modell ein Doppelgänger. Abgesichert ist:

* Ohne Big ist alles wie vorher — ``auto`` wählt BeeNara bei 3–9 Ordnern, sonst nichts.
* Big macht nur Vorschläge: Sein Favorit wird eine Rückfrage, auch bei 50 Ordnern.
* Ohne passende GPU lädt ``beenara big laden`` nichts — nicht einmal die Dateiliste.
* Big-Teil und Basismodell kommen je aus ihrem festen Commit und werden geprüft.
"""

from __future__ import annotations

import hashlib

import httpx
import pytest
from test_beenara import Con
from test_beenara_sortieren import CATS, RECHNUNG, _ctx, _datei

from pollysort import beenara, beenara_big, config, entscheidung, pipeline
from pollysort.assigner import CONFLICT
from pollysort.beenara_big_laufzeit import BeeNaraBig, Suggestion
from pollysort.beenara_laufzeit import NONE, Decision
from pollysort.config import AppConfig, HiveSeed
from pollysort.llm.client import OfflineClient
from pollysort.models import Status
from pollysort.pipeline import run_cycle

VIELE = [f"ordner_{i:02d}" for i in range(40)] + ["rechnungen"]


@pytest.fixture(autouse=True)
def _eigene_config(tmp_path, monkeypatch):
    """CONFIG_PATH steht seit dem Import fest — ohne das schriebe die Modellwahl in die echte."""
    home = config.POLLYSORT_HOME
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "CONFIG_PATH", home / "config.toml")
    monkeypatch.setattr(config, "CREDENTIALS_PATH", home / "credentials")
    monkeypatch.setattr(config, "PROJECTS_PATH", home / "projects.txt")


class FakeBig:
    """Wie BeeNara Big: 3–500 Ordner, langer Text, immer nur ein Vorschlag."""

    ordner_bereich = (3, 500)
    text_zeichen = 12_000

    def __init__(self):
        self.calls: list[tuple[str, list[str]]] = []

    def decide(self, text, kategorien, *, language="de", **_kw):
        self.calls.append((text, list(kategorien)))
        favorit = "rechnungen" if "rechnung" in text.lower() and "rechnungen" in kategorien else NONE
        rest = 0.2 / len(kategorien)
        dist = {k: rest for k in kategorien} | {NONE: 0.0}
        dist[favorit] = 0.8
        return Decision(None, 0.8, True, dist, [favorit])


# --------------------------------------------------------------------------- #
#  Welches Modell entscheidet
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("modus,n,klein,big,erwartet", [
    ("auto", 5, True, False, "klein"),
    ("auto", 5, True, True, "klein"),        # bei 3–9 sortiert das kleine selbst
    ("auto", 5, False, True, "big"),
    ("auto", 40, True, True, "big"),
    ("auto", 40, True, False, None),         # ohne Big: wie vorher
    ("auto", 2, True, True, None),
    ("auto", 501, True, True, None),
    ("klein", 40, True, True, None),
    ("klein", 5, True, True, "klein"),
    ("big", 5, True, True, "big"),
    ("big", 5, True, False, None),
])
def test_modellwahl(modus, n, klein, big, erwartet):
    assert entscheidung.beenara_modell_fuer(modus, n, klein_bereit=klein, big_bereit=big) == erwartet


def test_voreinstellung_ist_automatisch():
    assert AppConfig().beenara_modell == "auto"


def test_big_schlaegt_bei_vielen_ordnern_vor_und_liest_mehr_text():
    bee = FakeBig()
    text = "Rechnung " + "x" * 20_000
    kat, conf = entscheidung.beenara_waehlen(bee, text, VIELE, {})
    assert kat == "rechnungen" and conf <= CONFLICT < HiveSeed().threshold_assign, "nur Vorschlag → Rückfrage"
    gelesen, kats = bee.calls[0]
    assert len(gelesen) == FakeBig.text_zeichen and len(kats) == len(VIELE)


def test_big_keiner_passt_wird_rueckfrage_ohne_vorschlag():
    assert entscheidung.beenara_waehlen(FakeBig(), "Apfelkuchen", VIELE, {}) == ("_unassigned", 0.0)


def test_kleines_beenara_bleibt_bei_3_bis_9():
    from test_beenara_sortieren import FakeBee
    assert entscheidung.beenara_waehlen(FakeBee(), "Rechnung", VIELE, {}) is None


def test_behutsam_reicht_bereich_und_textlaenge_durch():
    from pollysort.console import BeeConsole
    b = pipeline._Behutsam(FakeBig(), BeeConsole(quiet=True))
    assert b.ordner_bereich == (3, 500) and b.text_zeichen == 12_000
    assert not hasattr(pipeline._Behutsam(object(), BeeConsole(quiet=True)), "ordner_bereich")


def _bereit(monkeypatch, *, klein=True, big=True):
    geoeffnet: list[str] = []
    monkeypatch.setattr(beenara, "warum_nicht", lambda _c: None if klein else "modell")
    monkeypatch.setattr(beenara_big, "warum_nicht", lambda _c: None if big else "modell")
    monkeypatch.setattr(beenara, "oeffnen", lambda: geoeffnet.append("klein") or object())
    monkeypatch.setattr(beenara_big, "oeffnen", lambda: geoeffnet.append("big") or FakeBig())
    return geoeffnet


def test_sortierlauf_oeffnet_big_bei_vielen_ordnern(tmp_path, monkeypatch):
    geoeffnet = _bereit(monkeypatch)
    hive = tmp_path / "hive"
    ctx = _ctx(hive, OfflineClient(VIELE), kats=VIELE)
    _datei(hive, "r.txt", RECHNUNG.format(i=1))
    s = run_cycle(ctx, mode="move")
    assert geoeffnet == ["big"]
    assert s.quellen == {"beenara": 1} and s.needs_review == 1, "Big sortiert nie selbst"


def test_big_steht_im_katalog_als_beenara_big_und_im_gedaechtnis_als_unsicher(tmp_path, monkeypatch):
    """Feldmessung (2026-10-20): Der Katalog unterscheidet die beiden Modelle, die Lauf-
    Zusammenfassung zählt beide als BeeNara. Big-Vorschläge sind immer Rückfragen — im
    Gedächtnis also unsicher."""
    _bereit(monkeypatch)
    hive = tmp_path / "hive"
    ctx = _ctx(hive, OfflineClient(VIELE), kats=VIELE)
    _datei(hive, "r.txt", RECHNUNG.format(i=1))
    s = run_cycle(ctx, mode="move")
    zeile = ctx.store.query()[0]
    assert zeile["quelle"] == "beenara-big" and s.plan[0]["quelle"] == "beenara"
    assert ctx.mind.herkuenfte() == {zeile["id"]: ("rechnungen", "unsicher")}


def test_sortierlauf_nimmt_bei_wenigen_ordnern_das_kleine(tmp_path, monkeypatch):
    geoeffnet = _bereit(monkeypatch)
    pipeline._beenara(_ctx(tmp_path / "hive", OfflineClient(CATS)))
    assert geoeffnet == ["klein"]


def test_modell_big_erzwingt_big(tmp_path, monkeypatch):
    geoeffnet = _bereit(monkeypatch)
    ctx = _ctx(tmp_path / "hive", OfflineClient(CATS))
    ctx.cfg.beenara_modell = "big"
    pipeline._beenara(ctx)
    assert geoeffnet == ["big"]


def test_ohne_big_bleibt_alles_wie_vorher(tmp_path, monkeypatch):
    geoeffnet = _bereit(monkeypatch, big=False)
    assert pipeline._beenara(_ctx(tmp_path / "hive", OfflineClient(VIELE), kats=VIELE)) is None
    assert geoeffnet == []


def test_big_nicht_im_modus_cloud(tmp_path, monkeypatch):
    geoeffnet = _bereit(monkeypatch)
    assert pipeline._beenara(_ctx(tmp_path / "a", object(), kats=VIELE, provider="openrouter")) is None
    assert geoeffnet == []


# --------------------------------------------------------------------------- #
#  Laufzeit-Adapter (ohne torch: suggest ist ersetzt)
# --------------------------------------------------------------------------- #
def test_decide_liefert_eine_entscheidung_wie_das_kleine():
    big = BeeNaraBig.__new__(BeeNaraBig)
    dist = {"a": 0.5, "b": 0.3, "c": 0.1, NONE: 0.1}
    big.suggest = lambda *_a, **_k: Suggestion([("a", 0.5), ("b", 0.3), ("c", 0.1)], 0.1, dist, None, True)
    d = big.decide("text", ["a", "b", "c"])
    assert d == Decision(None, 0.5, True, dist, ["a", "b", "c"])


# --------------------------------------------------------------------------- #
#  GPU
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("treiber,index", [("591.44", "cu130"), ("580.10", "cu130"), ("566.03", "cu126"),
                                           ("552.22", "cpu"), (None, "cpu"), ("kaputt", "cpu")])
def test_torch_passend_zum_treiber(treiber, index):
    assert beenara_big.torch_index(treiber) == index


def test_gpu_pruefung(monkeypatch):
    assert beenara_big.gpu_grund() == "keine"
    klein = {"name": "RTX 4060", "mb": 6141, "treiber": "591.44"}
    gross = {"name": "RTX 4070", "mb": 12282, "treiber": "591.44"}
    monkeypatch.setattr(beenara_big, "gpus", lambda: (klein,))
    assert beenara_big.gpu_grund() == "klein"
    monkeypatch.setattr(beenara_big, "gpus", lambda: (gross,))
    assert beenara_big.gpu_grund() is None
    monkeypatch.setattr(beenara_big, "gpus", lambda: ())
    monkeypatch.setenv(beenara_big.CPU_ERLAUBT, "1")
    assert beenara_big.gpu_grund() is None, "ausdrücklich gewollt: CPU"


def test_ohne_gpu_wird_nichts_geladen():
    con = Con()
    hub = ZweiHubs()
    with hub.client() as client:
        assert beenara_big.laden(con, client=client) is False
    assert hub.requests == [], "nicht einmal die Dateiliste"
    assert "NVIDIA" in con.text and beenara_big.CPU_ERLAUBT in con.text


# --------------------------------------------------------------------------- #
#  Download: Big-Teil und Basismodell
# --------------------------------------------------------------------------- #
def _datei_fuer(p: str) -> bytes:
    return (p.encode() + b"|") * 50


class ZweiHubs:
    """Zwei Repos auf ihrem festen Commit, ohne Umleitung aufs CDN."""

    def __init__(self):
        self.repos = {
            (beenara_big.REPO, beenara_big.REVISION): (
                *beenara_big.PFLICHT, *beenara_big.BEILAGEN, "README.md"),
            (beenara_big.BASIS_REPO, beenara_big.BASIS_REVISION): (
                *beenara_big.BASIS_PFLICHT, *beenara_big.BASIS_BEILAGEN, "vocab.json"),
        }
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        for (repo, rev), dateien in self.repos.items():
            if path == f"/api/models/{repo}/revision/{rev}":
                sib = []
                for p in dateien:
                    data = _datei_fuer(p)
                    sib.append({"rfilename": p, "size": len(data), "blobId": "0" * 40,
                                "lfs": {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}})
                return httpx.Response(200, json={"sha": rev, "siblings": sib})
            if path.startswith(f"/{repo}/resolve/{rev}/"):
                return httpx.Response(200, content=_datei_fuer(path.split(f"/resolve/{rev}/", 1)[1]))
        return httpx.Response(404)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self), follow_redirects=True)

    def geladen(self) -> list[str]:
        return [r.url.path for r in self.requests if "/resolve/" in r.url.path]


@pytest.fixture
def gpu(monkeypatch):
    karte = {"name": "RTX A6000", "mb": 49140, "treiber": "591.44"}
    monkeypatch.setattr(beenara_big, "gpus", lambda: (karte,))


def test_laedt_beide_teile_aus_ihrem_commit(gpu):
    hub = ZweiHubs()
    with hub.client() as client:
        assert beenara_big.laden(Con(), client=client)
    s = beenara_big.stand()
    assert s.vollstaendig and s.passend and s.version == beenara_big.REVISION[:7]
    d = beenara_big.ordner()
    assert (d / "lora.safetensors").is_file() and (d / "basis" / "config.json").is_file()
    geladen = hub.geladen()
    assert not any(p.endswith(("README.md", "vocab.json")) for p in geladen), "nur, was gebraucht wird"
    assert all(beenara_big.REVISION in p or beenara_big.BASIS_REVISION in p for p in geladen)
    with hub.client() as client:
        assert beenara_big.laden(Con(), client=client)
    assert len(hub.geladen()) == len(geladen), "zweites Laden fragt nicht einmal nach"


def test_ohne_basismodell_unvollstaendig(gpu):
    hub = ZweiHubs()
    del hub.repos[(beenara_big.BASIS_REPO, beenara_big.BASIS_REVISION)]
    with hub.client() as client:
        assert beenara_big.laden(Con(), client=client) is False
    s = beenara_big.stand()
    assert s.big.vollstaendig and not s.vollstaendig and s.angefangen
    assert beenara_big.warum_nicht(AppConfig()) == "modell"


def test_stand_ohne_big():
    s = beenara_big.stand()
    assert not s.vollstaendig and not s.angefangen
    assert beenara_big.warum_nicht(AppConfig()) == "modell"
    assert beenara_big.warum_nicht(AppConfig(beenara=False)) == "aus"


def test_entfernen_loescht_nur_den_big_ordner(gpu):
    hub = ZweiHubs()
    with hub.client() as client:
        beenara_big.laden(Con(), client=client)
    klein = beenara.ordner()
    klein.mkdir(parents=True)
    beenara_big.entfernen()
    assert not beenara_big.ordner().exists() and klein.exists()


# --------------------------------------------------------------------------- #
#  Konsole und Werkstatt
# --------------------------------------------------------------------------- #
def test_konsole_modellwahl():
    from test_beenara import _shell
    con = Con()
    sh = _shell(con)
    sh.do_beenara("modell big")
    assert config.load_config().beenara_modell == "big"
    sh.do_beenara("model small")
    assert config.load_config().beenara_modell == "klein"
    sh.do_beenara("modell irgendwas")
    assert config.load_config().beenara_modell == "klein" and "beenara modell" in con.text


def test_konsole_big_status_ohne_gpu():
    from test_beenara import _shell
    con = Con()
    _shell(con).do_beenara("big")
    assert "BeeNara Big" in con.text and "beenara big laden" in con.text


def test_werkstatt_zeigt_big_und_nimmt_die_modellwahl(tmp_path):
    from pollysort.web.dienst import Dienst, Ungueltig
    d = Dienst()
    bb = d.werkstatt()["beenara_big"]
    assert bb["vorhanden"] is False and bb["gpu_grund"] == "keine" and bb["modus"] == "auto"
    assert d.beenara_modell(modell="big")["ergebnis"]["modus"] == "big"
    with pytest.raises(Ungueltig):
        d.beenara_modell(modell="riesig")


def test_doctor_schweigt_ohne_big_und_meldet_halbes():
    from pollysort import doctor
    assert "BeeNara Big" not in {c[0] for c in doctor.run_checks(None)}
    (beenara_big.ordner()).mkdir(parents=True)
    (beenara_big.ordner() / "lora.safetensors.part").write_bytes(b"x")
    assert ("BeeNara Big", "warn") in {c[:2] for c in doctor.run_checks(None)}


def test_eintrag_bleibt_rueckfrage(tmp_path, monkeypatch):
    _bereit(monkeypatch)
    hive = tmp_path / "hive"
    ctx = _ctx(hive, OfflineClient(VIELE), kats=VIELE)
    _datei(hive, "r.txt", RECHNUNG.format(i=2))
    run_cycle(ctx, mode="move")
    zeile = next(r for r in ctx.store.query() if r["filename"] == "r.txt")
    assert zeile["status"] == Status.NEEDS_REVIEW.value


# --------------------------------------------------------------------------- #
#  Auf der Grafikkarte rechnen
# --------------------------------------------------------------------------- #
def _torch(monkeypatch, version: str | None, *, plattform: str = "win32"):
    import importlib.metadata as md

    def v(name):
        if name == "torch" and version is not None:
            return version
        raise md.PackageNotFoundError(name)
    monkeypatch.setattr(beenara_big.importlib.metadata, "version", v)
    monkeypatch.setattr(beenara_big.sys, "platform", plattform)


@pytest.mark.parametrize("version,plattform,ohne", [
    ("2.14.0", "win32", True),            # PyPI-Rad unter Windows: nur CPU
    ("2.14.0+cpu", "linux", True),
    ("2.14.0+cu130", "win32", False),
    ("2.14.0", "linux", False),           # PyPI unter Linux bringt CUDA mit
    (None, "win32", False),               # nicht installiert: fehlt ohnehin
])
def test_cpu_torch_wird_erkannt(monkeypatch, gpu, version, plattform, ohne):
    _torch(monkeypatch, version, plattform=plattform)
    assert beenara_big.torch_ohne_cuda() is ohne


def test_ohne_passende_karte_ist_cpu_torch_kein_mangel(monkeypatch):
    _torch(monkeypatch, "2.14.0")
    assert beenara_big.torch_ohne_cuda() is False and beenara_big.auf_gpu() is False
    klein = {"name": "MX 550", "mb": 2048, "treiber": "591.44"}
    monkeypatch.setattr(beenara_big, "gpus", lambda: (klein,))
    assert beenara_big.cuda_index() == "cpu" and beenara_big.torch_ohne_cuda() is False


def _spezifiziert(monkeypatch, *, torch_da: bool, pip: bool):
    echt = beenara_big.importlib.util.find_spec

    def find_spec(name, *a):
        if name == "torch":
            return object() if torch_da else None
        if name == "pip":
            return object() if pip else None
        return echt(name, *a)
    monkeypatch.setattr(beenara_big.importlib.util, "find_spec", find_spec)
    monkeypatch.setattr(beenara_big.shutil, "which", lambda n: "uv" if n == "uv" else None)


def test_cpu_torch_wird_gegen_cuda_getauscht_pip(monkeypatch, gpu):
    _torch(monkeypatch, "2.14.0")
    _spezifiziert(monkeypatch, torch_da=True, pip=True)
    assert "torch (CUDA)" in beenara_big.laufzeit_fehlt()
    torch_befehl, rest = beenara_big.installationsbefehle()
    assert "--force-reinstall" in torch_befehl and "--no-deps" in torch_befehl
    assert torch_befehl[torch_befehl.index("--index-url") + 1].endswith("/cu130")
    assert not any(a.startswith("torch") for a in rest) and "--index-url" not in rest


def test_cpu_torch_wird_gegen_cuda_getauscht_uv(monkeypatch, gpu):
    _torch(monkeypatch, "2.14.0")
    _spezifiziert(monkeypatch, torch_da=True, pip=False)
    torch_befehl, rest = beenara_big.installationsbefehle()
    assert torch_befehl[:3] == ["uv", "pip", "install"]
    assert torch_befehl[torch_befehl.index("--reinstall-package") + 1] == "torch"
    assert torch_befehl[torch_befehl.index("--index-url") + 1].endswith("/cu130")
    assert "--extra-index-url" not in rest and "--index-url" not in rest


def test_ohne_torch_kommt_es_aus_dem_cuda_index(monkeypatch, gpu):
    _torch(monkeypatch, None)
    _spezifiziert(monkeypatch, torch_da=False, pip=False)
    torch_befehl, _rest = beenara_big.installationsbefehle()
    assert "--reinstall-package" not in torch_befehl and torch_befehl[-1].startswith("torch")


def test_passendes_torch_wird_nicht_angefasst(monkeypatch, gpu):
    _torch(monkeypatch, "2.14.0+cu130")
    _spezifiziert(monkeypatch, torch_da=True, pip=True)
    assert len(beenara_big.installationsbefehle()) == 1, "nur der Rest von PyPI"


@pytest.mark.parametrize("karte,geraet", [(49140, None), (6141, "cpu")])
def test_oeffnen_nimmt_die_grafikkarte_nur_wenn_sie_reicht(monkeypatch, karte, geraet):
    from pollysort import beenara_big_laufzeit
    gesehen = {}

    class Big:
        def __init__(self, pfad, **kw):
            gesehen.update(kw)
    monkeypatch.setattr(beenara_big_laufzeit, "BeeNaraBig", Big)
    monkeypatch.setattr(beenara_big, "gpus", lambda: ({"name": "x", "mb": karte, "treiber": "591.44"},))
    beenara_big.oeffnen()
    assert gesehen["device"] == geraet


def test_sortierlauf_sagt_einmal_worauf_big_rechnet(tmp_path, monkeypatch, capsys):
    _bereit(monkeypatch)
    monkeypatch.setattr(FakeBig, "device", "cuda", raising=False)
    from pollysort.console import BeeConsole
    ctx = _ctx(tmp_path / "hive", OfflineClient(VIELE), kats=VIELE)
    ctx.console = BeeConsole()
    pipeline._beenara(ctx)
    assert "Grafikkarte" in capsys.readouterr().out


def test_bericht_nennt_das_rechengeraet(monkeypatch, gpu):
    monkeypatch.setattr(beenara_big, "warum_nicht", lambda _c: None)
    _torch(monkeypatch, "2.14.0+cu130")
    texte = [t for _a, _e, t in beenara_big.bericht(AppConfig())]
    assert any("Grafikkarte." in t for t in texte)
    _torch(monkeypatch, "2.14.0")
    texte = [t for _a, _e, t in beenara_big.bericht(AppConfig())]
    assert any("CPU" in t for t in texte)


def test_cli_big_und_modellwahl():
    from typer.testing import CliRunner

    from pollysort.cli import app
    r = CliRunner().invoke(app, ["beenara", "modell", "big"])
    assert r.exit_code == 0 and config.load_config().beenara_modell == "big"
    assert CliRunner().invoke(app, ["beenara", "modell", "riesig"]).exit_code == 2
    r = CliRunner().invoke(app, ["beenara", "big"])
    assert r.exit_code == 1 and "beenara big laden" in r.output


def test_zu_altes_torch_wird_erneuert(monkeypatch, gpu):
    _torch(monkeypatch, "2.9.0+cu130")
    _spezifiziert(monkeypatch, torch_da=True, pip=True)
    assert "torch>=2.14" in beenara_big.laufzeit_fehlt()
    torch_befehl, _rest = beenara_big.installationsbefehle()
    assert torch_befehl[-1] == "torch>=2.14" and "--force-reinstall" not in torch_befehl

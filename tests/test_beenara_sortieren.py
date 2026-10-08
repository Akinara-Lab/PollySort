"""BeeNara im Sortierlauf (entscheidung.py, pipeline.py) — mit einem Doppelgänger, ohne ONNX.

Abgesichert sind die Regeln, die beim echten Modell den Unterschied machen:

* Sparmodus: BeeNara entscheidet statt der Heuristik; Modus Lokal: nach dem Gedächtnis,
  statt des Sprachmodells. Cloud bleibt, wie es war.
* „keiner passt" und Unsicherheit werden Rückfragen — kein zweites Modell rät nach.
* Eine gelernte Wachstafel-Regel und ein widersprechendes Gedächtnis haben Vorrang.
* Außerhalb von 3–9 Ordnern und bei einem Ausfall entscheidet der bisherige Weg.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pollysort import beenara, config, entscheidung, nacherfassung, pipeline
from pollysort.beenara_laufzeit import NONE, Decision
from pollysort.config import AppConfig, HiveSeed
from pollysort.console import BeeConsole
from pollysort.extractor import gedaechtnis_text
from pollysort.journal import Journal
from pollysort.llm.client import OfflineClient, Usage
from pollysort.models import BeeAnalysis, Status, embedding_text_for
from pollysort.pipeline import Context, run_cycle

CATS = ["rechnungen", "spesen", "kontoauszuege"]
RECHNUNG = "RECHNUNG Nr. {i}\nStadtwerke Musterstadt\nBetrag 120,00 EUR zahlbar bis 30.09."
SPESEN = "REISEKOSTENABRECHNUNG\nMitarbeiter Jonas Bergmann\nVerpflegung 28,00 EUR"
KUCHEN = "Apfelkuchen: 500 g Mehl, 3 Eier, 200 g Zucker"
UNKLAR = "Unklar: Übersicht der Zahlungen im September"


class FakeBee:
    """Entscheidet wie BeeNara, nach Stichwort: sicher, „keiner passt" oder unsicher."""

    def __init__(self, *, fest: str | None = None, kaputt: bool = False):
        self.fest = fest
        self.kaputt = kaputt
        self.calls: list[tuple[str, list[str], str]] = []
        self.regeln: list[str | None] = []

    @staticmethod
    def _sicher(kat: str, kategorien: list[str], p: float = 0.99) -> Decision:
        rest = (1 - p) / len(kategorien)
        dist = {k: rest for k in kategorien} | {NONE: rest}
        dist[kat] = p
        return Decision(kat, p, False, dist, [kat])

    def decide(self, text: str, kategorien: list[str], *, language: str = "de", **kw):
        self.calls.append((text, list(kategorien), language))
        self.regeln.append(kw.get("rule"))
        if self.kaputt:
            raise RuntimeError("ONNX kaputt")
        if self.fest:
            return self._sicher(self.fest, kategorien)
        t = text.lower()
        if "unklar" in t:
            dist = {k: 0.03 for k in kategorien} | {"kontoauszuege": 0.6, "rechnungen": 0.3, NONE: 0.04}
            return Decision(None, 0.6, True, dist, ["kontoauszuege", "rechnungen"])
        for wort, kat in (("reisekosten", "spesen"), ("rechnung", "rechnungen"),
                          ("kontoauszug", "kontoauszuege")):
            if wort in t and kat in kategorien:
                return self._sicher(kat, kategorien)
        dist = {k: 0.02 for k in kategorien} | {NONE: 0.94}
        return Decision(None, 0.94, True, dist, [NONE])


class FakeOllama:
    """Der OllamaClient im Kleinen (wie in test_entscheidung): Stichwort-Embedding, Nummer."""

    memory_basis = "auszug"
    embed_model = "fake-embed#auszug"

    def __init__(self, *, wachstafel: str = ""):
        self.usage = Usage()
        self._wachstafel = wachstafel
        self.decide_calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        t = text.lower()
        if "reisekosten" in t:
            return [0.0, 1.0, 0.0]
        if "rechnung" in t:
            return [1.0, 0.0, 0.0]
        return [0.0, 0.0, 1.0]

    def decide(self, text: str, categories: list[str]):
        self.decide_calls.append(text)
        return ("rechnungen", 0.97) if "rechnung" in text.lower() else ("_unassigned", 0.9)

    def analyze(self, *, text=None, file_path=None) -> BeeAnalysis:
        return BeeAnalysis(title="KI-Titel", summary="", keywords=[], funktion_aufgabe="",
                           kategorie="rechnungen")

    def suggest_subrouting(self, categories):
        return {}


def _ctx(hive: Path, client, *, kats=CATS, provider="offline", bee=None) -> Context:
    seed = HiveSeed(categories=list(kats), provider=provider)
    hive.mkdir(parents=True, exist_ok=True)
    config.write_seed(hive, seed)
    ctx = Context.build(hive=hive, cfg=AppConfig(llm_provider=provider), seed=seed, client=client,
                        console=BeeConsole(quiet=True), journal=Journal(hive))
    if bee is not None:                    # wie _beenara() es täte — ohne echtes Modell
        ctx.beenara, ctx.beenara_geprueft = bee, True
    return ctx


def _datei(hive: Path, name: str, inhalt: str) -> Path:
    p = hive / name
    p.write_text(inhalt, encoding="utf-8")
    return p


def _zeile(ctx, name: str) -> dict:
    return next(r for r in ctx.store.query() if r["filename"] == name)


# --------------------------------------------------------------------------- #
#  Die Regel selbst
# --------------------------------------------------------------------------- #
def test_sicher_sortiert_mit_kalibrierter_konfidenz():
    assert entscheidung.beenara_waehlen(FakeBee(), RECHNUNG, CATS, {}) == ("rechnungen", 0.99)


def test_keiner_passt_wird_rueckfrage_ohne_vorschlag():
    assert entscheidung.beenara_waehlen(FakeBee(), KUCHEN, CATS, {}) == ("_unassigned", 0.0)


def test_unsicher_wird_rueckfrage_mit_favorit():
    from pollysort.assigner import CONFLICT
    kat, conf = entscheidung.beenara_waehlen(FakeBee(), UNKLAR, CATS, {})
    assert kat == "kontoauszuege" and conf <= CONFLICT < 0.75


def test_gedaechtnis_widerspricht_deckelt():
    from pollysort.assigner import CONFLICT
    beste = {"spesen": 0.92, "rechnungen": 0.40}
    assert entscheidung.beenara_waehlen(FakeBee(), RECHNUNG, CATS, beste) == ("rechnungen", CONFLICT)
    zustimmend = {"rechnungen": 0.92, "spesen": 0.40}
    assert entscheidung.beenara_waehlen(FakeBee(), RECHNUNG, CATS, zustimmend) == ("rechnungen", 0.99)


@pytest.mark.parametrize("kats", [["rechnungen", "spesen"], [f"k{i}" for i in range(10)]])
def test_ausserhalb_von_3_bis_9_ordnern_traegt_beenara_nicht(kats):
    bee = FakeBee()
    assert entscheidung.beenara_waehlen(bee, RECHNUNG, kats, {}) is None
    assert bee.calls == [], "gar nicht erst fragen"


def test_unassigned_zaehlt_nicht_als_ordner():
    assert not entscheidung.beenara_passt(["rechnungen", "spesen", "_unassigned"])
    assert entscheidung.beenara_passt(CATS + ["_unassigned"])


def test_text_wird_gekappt_und_sprache_weitergereicht():
    bee = FakeBee()
    entscheidung.beenara_waehlen(bee, "Rechnung " * 2000, CATS, {}, sprache="en")
    text, kats, sprache = bee.calls[0]
    assert len(text) == entscheidung.BEENARA_ZEICHEN and kats == CATS and sprache == "en"


def test_beenara_entscheidet_mit_risiko_regel():
    """v0.3: selbst einsortiert wird nur über der Risiko-Schwelle (≤ 1 % falsch)."""
    bee = FakeBee()
    entscheidung.beenara_waehlen(bee, RECHNUNG, CATS, {})
    assert bee.regeln == ["risk"] == [entscheidung.BEENARA_REGEL]


def test_langer_text_behaelt_anfang_und_ende():
    """v0.3 ist auf Anfang + Ende trainiert: das Dokumentende (Summe, Unterschrift) muss mit."""
    text = "Kopf " + "x" * 10_000 + " Gesamtbetrag 119,00 EUR"
    kurz = entscheidung.beenara_text(text)
    assert len(kurz) == entscheidung.BEENARA_ZEICHEN
    assert kurz.startswith("Kopf ") and kurz.endswith("Gesamtbetrag 119,00 EUR")
    assert entscheidung.beenara_text("kurz") == "kurz"


def test_ausgefallenes_beenara_traegt_nicht():
    class Aus:
        def decide(self, *_a, **_k):
            return None

    assert entscheidung.beenara_waehlen(Aus(), RECHNUNG, CATS, {}) is None


def test_cloud_bleibt_ohne_beenara():
    assert entscheidung.beenara_weg(OfflineClient(CATS)) == "spar"
    assert entscheidung.beenara_weg(FakeOllama()) == "lokal"
    assert entscheidung.beenara_weg(object()) is None


# --------------------------------------------------------------------------- #
#  Sparmodus — BeeNara statt der Heuristik
# --------------------------------------------------------------------------- #
def test_sparmodus_sortiert_mit_beenara(tmp_path):
    hive = tmp_path / "hive"
    bee = FakeBee()
    ctx = _ctx(hive, OfflineClient(CATS), bee=bee)
    _datei(hive, "r.txt", RECHNUNG.format(i=1))
    _datei(hive, "s.txt", SPESEN)
    _datei(hive, "kuchen.txt", KUCHEN)
    s = run_cycle(ctx, mode="move")
    assert len(list((hive / "Rechnungen").glob("*.txt"))) == 1
    assert len(list((hive / "Spesen").glob("*.txt"))) == 1
    assert (hive / "kuchen.txt").exists(), "„keiner passt“ bleibt liegen und wird Rückfrage"
    assert s.needs_review == 1 and s.quellen == {"beenara": 3}
    assert len(bee.calls) == 3


def test_beenara_schlaegt_die_heuristik(tmp_path):
    """Die Heuristik sähe „Rechnung" — BeeNara sagt Spesen, und BeeNara entscheidet."""
    hive = tmp_path / "hive"
    ctx = _ctx(hive, OfflineClient(CATS), bee=FakeBee(fest="spesen"))
    _datei(hive, "r.txt", RECHNUNG.format(i=1))
    run_cycle(ctx, mode="move")
    assert (hive / "Spesen" / "r.txt").exists()
    zeile = _zeile(ctx, "r.txt")
    assert zeile["kategorie"] == "spesen" and zeile["funktion"] == "spesen"
    assert ctx.mind.count("spesen") == 1, "das Gedächtnis lernt BeeNaras Wahl"


def test_unsicher_bleibt_liegen_mit_vorschlag(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, OfflineClient(CATS), bee=FakeBee())
    _datei(hive, "u.txt", UNKLAR)
    s = run_cycle(ctx, mode="move")
    assert s.needs_review == 1 and (hive / "u.txt").exists()
    assert _zeile(ctx, "u.txt")["kategorie"] == "kontoauszuege", "Favorit als Vorschlag"


def test_wachstafel_regel_schlaegt_beenara(tmp_path):
    hive = tmp_path / "hive"
    bee = FakeBee()
    client = OfflineClient(CATS, wachstafel="- **stadtwerke** → Wabe **kontoauszuege**")
    ctx = _ctx(hive, client, bee=bee)
    _datei(hive, "r.txt", RECHNUNG.format(i=1))
    s = run_cycle(ctx, mode="move")
    assert (hive / "Kontoauszuege" / "r.txt").exists()
    assert bee.calls == [] and s.quellen == {"analyse": 1}


def test_korrektur_im_gedaechtnis_bremst_beenara(tmp_path):
    """Hat der Nutzer ein fast gleiches Dokument woanders einsortiert, wird gefragt —
    so wirken Korrekturen weiter, obwohl BeeNara sie nicht kennt."""
    hive = tmp_path / "hive"
    client = OfflineClient(CATS)
    ctx = _ctx(hive, client, bee=FakeBee())
    pfad = _datei(hive, "r.txt", RECHNUNG.format(i=1))
    a = client.analyze(text=RECHNUNG.format(i=1), file_path=str(pfad))
    vec = client.embed(gedaechtnis_text(client, pfad, embedding_text_for(a)))
    for i in range(2):
        ctx.mind.remember(f"alt{i}", "spesen", vec, client.embed_model)
    s = run_cycle(ctx, mode="move")
    assert s.needs_review == 1 and pfad.exists()
    assert s.quellen == {"beenara": 1}, "BeeNara hat gewählt, das Gedächtnis hat gebremst"
    assert _zeile(ctx, "r.txt")["kategorie"] == "rechnungen", "BeeNaras Wahl bleibt Vorschlag"


def test_zwei_ordner_bleiben_bei_der_heuristik(tmp_path):
    hive = tmp_path / "hive"
    bee = FakeBee()
    ctx = _ctx(hive, OfflineClient(["rechnungen", "spesen"]), kats=["rechnungen", "spesen"],
               bee=bee)
    _datei(hive, "r.txt", RECHNUNG.format(i=1))
    s = run_cycle(ctx, mode="move")
    assert bee.calls == [] and s.quellen == {"analyse": 1}
    assert (hive / "Rechnungen" / "r.txt").exists()


def test_vorschau_und_anwenden_fragen_beenara_nur_einmal(tmp_path):
    hive = tmp_path / "hive"
    bee = FakeBee()
    ctx = _ctx(hive, OfflineClient(CATS), bee=bee)
    _datei(hive, "r.txt", RECHNUNG.format(i=1))
    _datei(hive, "s.txt", SPESEN)
    cache: dict = {}
    run_cycle(ctx, mode="move", dry_run=True, cache=cache)
    assert len(bee.calls) == 2
    run_cycle(ctx, mode="move", cache=cache)
    assert len(bee.calls) == 2, "Anwenden nutzt die Analyse der Vorschau"
    assert (hive / "Rechnungen" / "r.txt").exists()


def test_ultra_swarm_mit_beenara(tmp_path):
    """Parallel vorgewärmt: BeeNara wird vorher geöffnet, das Gedächtnis als Kopie gelesen
    (SQLite-Verbindungen dürfen nicht zwischen Threads wandern)."""
    hive = tmp_path / "hive"
    ctx = _ctx(hive, OfflineClient(CATS), bee=FakeBee())
    for i in range(6):
        _datei(hive, f"r{i}.txt", RECHNUNG.format(i=i))
    s = run_cycle(ctx, mode="move", workers=4)
    assert s.errors == 0 and len(list((hive / "Rechnungen").glob("*.txt"))) == 6
    assert s.quellen == {"beenara": 6}


def test_zusammenfassung_nennt_beenara_und_heuristik(tmp_path, capsys):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, OfflineClient(CATS), bee=FakeBee())
    ctx.console = BeeConsole(plain=True)
    ctx.console._c.width = 200
    _datei(hive, "r.txt", RECHNUNG.format(i=1))
    # Ohne lokalen Text → Heuristik. Echte PNG-Bytes: Mit dem Extra [extract] erkennt libmagic den
    # Typ am Inhalt — eine Textdatei namens bild.png wäre dort Text, kein Bild.
    (hive / "bild.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(64))
    run_cycle(ctx, mode="move")
    out = capsys.readouterr().out
    assert "1 von BeeNara" in out and "per Heuristik" in out and "Vollanalyse" not in out


# --------------------------------------------------------------------------- #
#  Modus Lokal — nach dem Gedächtnis, statt des Sprachmodells
# --------------------------------------------------------------------------- #
def test_lokal_beenara_statt_nummer_gedaechtnis_zuerst(tmp_path):
    hive = tmp_path / "hive"
    bee = FakeBee()
    ctx = _ctx(hive, FakeOllama(), provider="ollama", bee=bee)
    for i in range(3):
        _datei(hive, f"r{i}.txt", RECHNUNG.format(i=i))
    s = run_cycle(ctx, mode="move")
    # 1 und 2: BeeNara (das Gedächtnis kennt noch keine zwei). 3: das Gedächtnis allein.
    assert s.quellen == {"beenara": 2, "gedaechtnis": 1}
    assert len(bee.calls) == 2 and ctx.client.decide_calls == []
    assert len(list((hive / "Rechnungen").glob("*.txt"))) == 3
    # Titel kommen wie bei der Nummer erst kurz — die KI verfeinert sie danach.
    assert len(nacherfassung.offen(hive)) == 3


def test_lokal_keiner_passt_fragt_nicht_noch_das_sprachmodell(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, FakeOllama(), provider="ollama", bee=FakeBee())
    _datei(hive, "kuchen.txt", KUCHEN)
    s = run_cycle(ctx, mode="move")
    assert s.needs_review == 1 and ctx.client.decide_calls == []


def test_lokal_regel_geht_ans_sprachmodell(tmp_path):
    hive = tmp_path / "hive"
    bee = FakeBee()
    client = FakeOllama(wachstafel="- **stadtwerke** → Wabe **kontoauszuege**")
    ctx = _ctx(hive, client, provider="ollama", bee=bee)
    _datei(hive, "r.txt", RECHNUNG.format(i=1))
    run_cycle(ctx, mode="move")
    assert bee.calls == [] and client.decide_calls, "die Regel steht im Prompt des Modells"


def test_lokal_zwei_ordner_nimmt_die_nummer(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, FakeOllama(), kats=["rechnungen", "spesen"], provider="ollama",
               bee=FakeBee())
    _datei(hive, "r.txt", RECHNUNG.format(i=1))
    s = run_cycle(ctx, mode="move")
    assert s.quellen == {"nummer": 1}


def test_ausfall_wird_einmal_gemeldet_dann_der_bisherige_weg(tmp_path, capsys):
    hive = tmp_path / "hive"
    bee = FakeBee(kaputt=True)
    ctx = _ctx(hive, FakeOllama(), provider="ollama",
               bee=pipeline._Behutsam(bee, BeeConsole(quiet=True)))
    for i in range(3):
        _datei(hive, f"r{i}.txt", RECHNUNG.format(i=i))
    s = run_cycle(ctx, mode="move")
    assert s.errors == 0 and len(bee.calls) == 1, "nach dem ersten Fehler nicht mehr fragen"
    assert "nummer" in s.quellen
    assert capsys.readouterr().out.count("ONNX kaputt") == 1


# --------------------------------------------------------------------------- #
#  Wann BeeNara überhaupt geöffnet wird
# --------------------------------------------------------------------------- #
def _bereit(monkeypatch, *, grund=None, oeffnen=None):
    geoeffnet: list[int] = []
    monkeypatch.setattr(beenara, "warum_nicht", lambda _cfg: grund)

    def auf():
        geoeffnet.append(1)
        if oeffnen is not None:
            return oeffnen()
        return FakeBee()

    monkeypatch.setattr(beenara, "oeffnen", auf)
    return geoeffnet


def test_bereit_wird_geoeffnet_und_eingepackt(tmp_path, monkeypatch):
    geoeffnet = _bereit(monkeypatch)
    ctx = _ctx(tmp_path / "hive", OfflineClient(CATS))
    bee = pipeline._beenara(ctx)
    assert isinstance(bee, pipeline._Behutsam)
    assert pipeline._beenara(ctx) is bee and geoeffnet == [1], "einmal je Kontext"


@pytest.mark.parametrize("grund", ["aus", "modell", "version", "laufzeit"])
def test_nicht_bereit_wird_nicht_geoeffnet(tmp_path, monkeypatch, grund):
    geoeffnet = _bereit(monkeypatch, grund=grund)
    ctx = _ctx(tmp_path / "hive", OfflineClient(CATS))
    assert pipeline._beenara(ctx) is None and geoeffnet == []


def test_cloud_und_ordnerzahl_oeffnen_nicht(tmp_path, monkeypatch):
    geoeffnet = _bereit(monkeypatch)
    assert pipeline._beenara(_ctx(tmp_path / "a", object(), provider="openrouter")) is None
    assert pipeline._beenara(_ctx(tmp_path / "b", OfflineClient(["x", "y"]), kats=["x", "y"])) \
        is None
    assert geoeffnet == []


def test_kaputtes_modell_wird_gemeldet_und_der_lauf_geht_weiter(tmp_path, monkeypatch, capsys):
    def boom():
        raise RuntimeError("Protobuf parsing failed")

    _bereit(monkeypatch, oeffnen=boom)
    hive = tmp_path / "hive"
    ctx = _ctx(hive, OfflineClient(CATS))
    _datei(hive, "r.txt", RECHNUNG.format(i=1))
    s = run_cycle(ctx, mode="move")
    assert s.errors == 0 and s.quellen == {"analyse": 1}
    assert "Protobuf parsing failed" in capsys.readouterr().out


def test_status_eines_eintrags_bleibt_wie_bisher(tmp_path):
    """BeeNara ändert nur, WER entscheidet — nicht, was mit einer Entscheidung passiert."""
    hive = tmp_path / "hive"
    ctx = _ctx(hive, OfflineClient(CATS), bee=FakeBee())
    _datei(hive, "r.txt", RECHNUNG.format(i=1))
    run_cycle(ctx, mode="index")
    assert _zeile(ctx, "r.txt")["status"] == Status.INDEXED.value
    assert (hive / "r.txt").exists(), "im Index-Modus wird nichts bewegt"

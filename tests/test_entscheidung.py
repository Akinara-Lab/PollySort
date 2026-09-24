"""Dreistufige Entscheidung — Gedächtnis → Nummer → Rückfrage — und die Nacherfassung.

Plan §8.3, gemessen §8.13 (2026-09-24). Die Tests laufen mit einem Ollama-Doppelgänger:
Er bettet nach Stichwort ein (Rechnung / Reisekosten / Rest) und entscheidet per Nummer,
ohne Netz. Offline- und OpenRouter-Weg sind durch die übrigen Tests abgedeckt und hier nur
insoweit Thema, als sie unverändert bleiben müssen.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from pollysort import config, entscheidung, nacherfassung
from pollysort.config import AppConfig, HiveSeed
from pollysort.console import BeeConsole
from pollysort.heuristics import kurz_titel
from pollysort.journal import Journal
from pollysort.llm import LLMError
from pollysort.llm.client import OfflineClient, Usage
from pollysort.models import BeeAnalysis, Status
from pollysort.pipeline import Context, reindex_memory, run_cycle

CATS = ["rechnungen", "spesen", "kontoauszuege"]
RECHNUNG = "RECHNUNG Nr. {i}\nStadtwerke Musterstadt\nBetrag 120,00 EUR zahlbar bis 30.09."
SPESEN = "REISEKOSTENABRECHNUNG\nMitarbeiter Jonas Bergmann\nVerpflegung 28,00 EUR"


class FakeOllama:
    """Tut, was der OllamaClient für die Entscheidung tut — ohne Netz."""

    memory_basis = "auszug"
    embed_model = "fake-embed#auszug"

    def __init__(self, *, kann_nummer: bool = True, wachstafel: str = ""):
        self.usage = Usage()
        self._wachstafel = wachstafel
        self.kann_nummer = kann_nummer
        self.decide_calls: list[str] = []
        self.analyze_calls = 0
        self.embedded: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.embedded.append(text)
        t = text.lower()
        if "reisekosten" in t:            # zuerst: „Reisekostenab-RECHNUNG" enthält „rechnung"
            return [0.0, 1.0, 0.0]
        if "rechnung" in t:
            return [1.0, 0.0, 0.0]
        return [0.0, 0.0, 1.0]

    def decide(self, text: str, categories: list[str]):
        self.decide_calls.append(text)
        self.usage.add(10, 1)
        if not self.kann_nummer:
            return None
        t = text.lower()
        if "reisekosten" in t:
            return "spesen", 0.95
        if "rechnung" in t:
            return "rechnungen", 0.97
        return "_unassigned", 0.9

    def analyze(self, *, text=None, file_path=None) -> BeeAnalysis:
        self.analyze_calls += 1
        self.usage.add(100, 50)
        return BeeAnalysis(title="KI-Titel", summary="KI-Zusammenfassung", keywords=["ki"],
                           funktion_aufgabe="Zahlung anstoßen", kategorie="rechnungen")

    def suggest_subrouting(self, categories):
        return {}


def _ctx(hive: Path, client, seed: HiveSeed | None = None) -> Context:
    seed = seed or HiveSeed(categories=list(CATS))
    hive.mkdir(parents=True, exist_ok=True)
    config.write_seed(hive, seed)
    return Context.build(hive=hive, cfg=AppConfig(llm_provider="ollama"), seed=seed,
                         client=client, console=BeeConsole(quiet=True), journal=Journal(hive))


def _datei(hive: Path, name: str, inhalt: str) -> Path:
    p = hive / name
    p.write_text(inhalt, encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
#  Stufe A — die Regel selbst
# --------------------------------------------------------------------------- #
def _zaehle(n):
    return lambda _kat: n


def test_gedaechtnis_entscheidet_bei_klarem_treffer():
    assert entscheidung.aus_gedaechtnis({"rechnungen": 0.91, "spesen": 0.40}, _zaehle(2), CATS) \
        == ("rechnungen", 0.91)


@pytest.mark.parametrize("beste, n, grund", [
    ({"rechnungen": 0.70, "spesen": 0.20}, 5, "zu wenig ähnlich"),
    ({"rechnungen": 0.90, "spesen": 0.87}, 5, "zu knapp vor der nächsten Kategorie"),
    ({"rechnungen": 0.95}, 1, "erst ein Beispiel"),
    ({"mahnungen": 0.95}, 5, "keine Projekt-Kategorie"),
    ({}, 5, "leeres Gedächtnis"),
])
def test_gedaechtnis_entscheidet_nicht(beste, n, grund):
    assert entscheidung.aus_gedaechtnis(beste, _zaehle(n), CATS) is None, grund


def test_schwellen_sind_die_gemessenen():
    """Aus Plan §8.13: Fehlte eine Kategorie ganz, kam kein fremdes Dokument über 0,67."""
    assert entscheidung.AEHNLICH == 0.75
    assert entscheidung.ABSTAND == 0.05
    assert entscheidung.MINDEST == 2


def test_schnappschuss_rechnet_wie_das_gedaechtnis():
    s = entscheidung.Schnappschuss([("a", "rechnungen", [1.0, 0.0]),
                                    ("b", "spesen", [0.0, 1.0]),
                                    ("c", "_unassigned", [1.0, 0.0])])
    beste = s.beste_je_kategorie([1.0, 0.0])
    assert beste == {"rechnungen": 1.0, "spesen": 0.0}
    assert s.count("rechnungen") == 1 and s.count("mahnungen") == 0


# --------------------------------------------------------------------------- #
#  Der Weg durch den Sortierlauf
# --------------------------------------------------------------------------- #
def test_erst_nummer_dann_gedaechtnis(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, FakeOllama())
    for i in range(3):
        _datei(hive, f"r{i}.txt", RECHNUNG.format(i=i))
    s = run_cycle(ctx, mode="move")
    # Dokument 1 und 2: Nummer (das Gedächtnis kennt noch keine zwei Rechnungen).
    # Dokument 3: Das Gedächtnis entscheidet allein — kein KI-Aufruf.
    assert len(ctx.client.decide_calls) == 2
    assert s.quellen == {"nummer": 2, "gedaechtnis": 1}
    assert ctx.client.analyze_calls == 0, "beim Sortieren keine volle Analyse mehr"
    assert len(list((hive / "Rechnungen").glob("*.txt"))) == 3
    rows = ctx.store.query(status=Status.ASSIGNED.value)
    assert {r["title"] for r in rows} == {"RECHNUNG Nr. 0", "RECHNUNG Nr. 1", "RECHNUNG Nr. 2"}
    # Alle drei warten auf die KI-Verfeinerung von Titel und Zusammenfassung.
    assert sorted(nacherfassung.offen(hive)) == sorted(r["id"] for r in rows)


def test_gedaechtnis_bettet_den_auszug_ein(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, FakeOllama())
    _datei(hive, "r.txt", RECHNUNG.format(i=7))
    run_cycle(ctx, mode="move")
    assert ctx.client.embedded == [RECHNUNG.format(i=7)]      # genau einmal, der Auszug
    assert ctx.mind.model() == "fake-embed#auszug"


def test_keine_passt_wird_rueckfrage(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, FakeOllama())
    _datei(hive, "kuchen.txt", "Apfelkuchen: 500 g Mehl, 3 Eier")
    s = run_cycle(ctx, mode="move")
    assert s.needs_review == 1
    assert (hive / "kuchen.txt").exists(), "unsichere Fälle bleiben liegen"
    assert ctx.mind.count() == 0, "'keine passt' wird nicht als Kategorie gelernt"


def test_ohne_nummer_volle_analyse_wie_bisher(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, FakeOllama(kann_nummer=False))
    _datei(hive, "r.txt", RECHNUNG.format(i=1))
    s = run_cycle(ctx, mode="move")
    assert ctx.client.analyze_calls == 1
    assert s.quellen == {"analyse": 1}
    assert nacherfassung.offen(hive) == [], "voll analysiert → nichts nachzuerfassen"
    assert ctx.store.query(status=Status.ASSIGNED.value)[0]["title"] == "KI-Titel"


def test_gedaechtnis_aus_anderer_textbasis_entscheidet_nicht(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, FakeOllama())
    for i in range(3):     # alte Vektoren: gleiches Modell, ALTE Textbasis (ohne „#auszug")
        ctx.mind.remember(f"alt{i}", "rechnungen", [1.0, 0.0, 0.0], "fake-embed")
    for i in range(2):
        _datei(hive, f"r{i}.txt", RECHNUNG.format(i=i))
    s = run_cycle(ctx, mode="move")
    assert len(ctx.client.decide_calls) == 2, "Stufe A bleibt aus, bis 'gedaechtnis neu' lief"
    assert "gedaechtnis" not in s.quellen


def test_wachstafel_regel_hat_vorrang_vor_dem_gedaechtnis(tmp_path):
    hive = tmp_path / "hive"
    client = FakeOllama(wachstafel="- **stadtwerke** → Wabe **kontoauszuege**")
    ctx = _ctx(hive, client)
    for i in range(3):
        ctx.mind.remember(f"m{i}", "rechnungen", [1.0, 0.0, 0.0], client.embed_model)
    _datei(hive, "r.txt", RECHNUNG.format(i=1))
    run_cycle(ctx, mode="move")
    assert client.decide_calls, "eine gelernte Regel soll das Modell sehen, nicht übergangen werden"


def test_widerspruch_zum_gedaechtnis_fuehrt_zur_rueckfrage(tmp_path):
    """Das Gedächtnis sieht eine ANDERE Kategorie deutlich näher → mehrdeutig → nachfragen."""
    p = _datei(tmp_path, "r.txt", RECHNUNG.format(i=1))
    f = SimpleNamespace(path=p, mime_type="text/plain", size_bytes=p.stat().st_size)
    gedaechtnis = entscheidung.Schnappschuss([
        ("a", "spesen", [0.8, 0.6, 0.0]), ("b", "spesen", [0.8, 0.6, 0.0]),   # 0,80 ähnlich
        ("c", "rechnungen", [0.78, 0.6258, 0.0]),                              # 0,78 ähnlich
    ])
    v = entscheidung.analysieren(FakeOllama(), f, max_file_mb=100, kategorien=CATS,
                                 gedaechtnis=gedaechtnis, memory_ok=True)
    assert v.quelle == "nummer" and v.kategorie == "rechnungen"
    assert v.confidence <= 0.55


def test_provider_fehler_bleibt_error_und_wird_wiederholt(tmp_path):
    class Weg(FakeOllama):
        def embed(self, text):
            raise LLMError("Ollama nicht erreichbar")

    p = _datei(tmp_path, "r.txt", RECHNUNG.format(i=1))
    f = SimpleNamespace(path=p, mime_type="text/plain", size_bytes=p.stat().st_size)
    v = entscheidung.analysieren(Weg(), f, max_file_mb=100, kategorien=CATS,
                                 gedaechtnis=entscheidung.Schnappschuss([]), memory_ok=True)
    assert v.ext_status == Status.ERROR


def test_bilder_und_fremde_clients_nehmen_den_alten_weg(tmp_path):
    img = tmp_path / "foto.png"
    img.write_bytes(b"\x89PNG....")
    f = SimpleNamespace(path=img, mime_type="image/png", size_bytes=8)
    kw = {"max_file_mb": 100, "kategorien": CATS,
          "gedaechtnis": entscheidung.Schnappschuss([]), "memory_ok": True}
    assert entscheidung.analysieren(FakeOllama(), f, **kw) is None       # kein lokaler Text
    assert entscheidung.analysieren(OfflineClient(CATS), f, **kw) is None
    assert not entscheidung.unterstuetzt(OfflineClient(CATS))


def test_vorschau_ist_nebenwirkungsfrei_und_anwenden_fragt_nicht_nochmal(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, FakeOllama())
    _datei(hive, "r.txt", RECHNUNG.format(i=1))
    cache: dict = {}
    run_cycle(ctx, mode="move", dry_run=True, cache=cache)
    assert nacherfassung.offen(hive) == [] and ctx.mind.count() == 0
    calls = len(ctx.client.decide_calls)
    run_cycle(ctx, mode="move", cache=cache)
    assert len(ctx.client.decide_calls) == calls, "Anwenden nutzt die Entscheidung der Vorschau"
    assert (hive / "Rechnungen" / "r.txt").exists()


def test_ultra_swarm_entscheidet_genauso(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, FakeOllama())
    for i in range(4):
        _datei(hive, f"r{i}.txt", RECHNUNG.format(i=i))
    _datei(hive, "s.txt", SPESEN)
    run_cycle(ctx, mode="move", workers=4)
    assert len(list((hive / "Rechnungen").glob("*.txt"))) == 4
    assert (hive / "Spesen" / "s.txt").exists()


# --------------------------------------------------------------------------- #
#  Nacherfassung
# --------------------------------------------------------------------------- #
def test_nacherfassung_verfeinert_ohne_umzusortieren(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, FakeOllama())
    _datei(hive, "s.txt", SPESEN)
    run_cycle(ctx, mode="move")
    vorher = ctx.store.query()[0]
    # Die volle Analyse behauptet „rechnungen" — das darf nichts umsortieren.
    fertig, grund = nacherfassung.nacherfassen(ctx)
    assert (fertig, grund) == (1, None)
    nachher = ctx.store.by_id(vorher["id"])
    assert nachher["title"] == "KI-Titel" and nachher["summary"] == "KI-Zusammenfassung"
    assert nachher["kategorie"] == "spesen" and nachher["path"] == vorher["path"]
    assert nachher["status"] == vorher["status"]
    assert nacherfassung.offen(hive) == []


def test_nacherfassung_bricht_bei_providerfehler_ab_und_verliert_nichts(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, FakeOllama())
    for i in range(2):
        _datei(hive, f"r{i}.txt", RECHNUNG.format(i=i))
    run_cycle(ctx, mode="move")

    def weg(**_kw):
        raise LLMError("Ollama nicht erreichbar")

    ctx.client.analyze = weg
    fertig, grund = nacherfassung.nacherfassen(ctx)
    assert fertig == 0 and "nicht erreichbar" in grund
    assert len(nacherfassung.offen(hive)) == 2


def test_nacherfassung_ueberspringt_verschwundene_eintraege(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, FakeOllama())
    nacherfassung.vormerken(hive, ["gibtsnicht"])
    assert nacherfassung.nacherfassen(ctx) == (0, None)
    assert nacherfassung.offen(hive) == []


def test_warteschlange_ohne_doppelte(tmp_path):
    hive = tmp_path / "hive"
    hive.mkdir()
    nacherfassung.vormerken(hive, ["a", "b"])
    nacherfassung.vormerken(hive, ["b", "c"])
    assert nacherfassung.offen(hive) == ["a", "b", "c"]
    nacherfassung.austragen(hive, "b")
    assert nacherfassung.offen(hive) == ["a", "c"]


def test_schalter_steht_in_der_projekt_config(tmp_path):
    hive = tmp_path / "hive"
    hive.mkdir()
    config.write_seed(hive, HiveSeed(nacherfassung=False))
    assert config.load_seed(hive).nacherfassung is False
    config.write_seed(hive, HiveSeed())
    assert config.load_seed(hive).nacherfassung is True       # Standard: an


def test_befehl_schaltet_um(tmp_path):
    from pollysort.repl import BeehiveShell
    hive = tmp_path / "hive"
    hive.mkdir()
    config.write_seed(hive, HiveSeed())
    sh = BeehiveShell.__new__(BeehiveShell)
    sh.con = BeeConsole(quiet=True)
    sh.hive = hive
    sh.do_nacherfassen("aus")
    assert config.load_seed(hive).nacherfassung is False
    sh.do_enrich("on")
    assert config.load_seed(hive).nacherfassung is True


# --------------------------------------------------------------------------- #
#  Eine Textbasis überall: Neuaufbau, Korrektur, Saat
# --------------------------------------------------------------------------- #
def test_neuaufbau_bettet_den_auszug_ein(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, FakeOllama())
    _datei(hive, "r.txt", RECHNUNG.format(i=3))
    run_cycle(ctx, mode="move")
    ctx.client.embedded.clear()
    ok, fail = reindex_memory(ctx)
    assert (ok, fail) == (1, 0)
    assert ctx.client.embedded == [RECHNUNG.format(i=3)], "aus der Datei, nicht aus dem Titel"


def test_korrektur_bettet_den_auszug_ein(tmp_path):
    from pollysort.review import apply_correction
    hive = tmp_path / "hive"
    ctx = _ctx(hive, FakeOllama())
    _datei(hive, "r.txt", RECHNUNG.format(i=4))
    run_cycle(ctx, mode="move")
    bee = ctx.store.query()[0]["id"]
    ctx.client.embedded.clear()
    apply_correction(ctx, bee, "kontoauszuege")
    assert ctx.client.embedded == [RECHNUNG.format(i=4)]


def test_saat_nutzt_die_textbasis_des_clients(tmp_path):
    from pollysort import vorwaermen as vw
    from pollysort.hive_mind import HiveMind

    finding = SimpleNamespace(content_hash="sha256:abcdef1234", path=tmp_path / "x.txt")
    analyse = BeeAnalysis(title="T", summary="S", kategorie="rechnungen")
    texte: list[str] = []
    vw.vorwaermen([(finding, analyse)], CATS, mind=HiveMind(tmp_path / "h"),
                  embed=lambda t: texte.append(t) or [1.0],
                  text_fuer=lambda f, a: "AUSZUG")
    assert texte == ["AUSZUG"]


# --------------------------------------------------------------------------- #
#  Kurz-Erfassung
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text, erwartet", [
    ("REISEKOSTENABRECHNUNG\nMitarbeiter …", "Reisekostenabrechnung"),
    ("\n\n  Rechnung Nr. R-40137  \nBetrag", "Rechnung Nr. R-40137"),
    ("=====\n--- Kontoauszug 3/2026 ---", "Kontoauszug 3/2026"),
    ("12.03.2026\n\n42", "Dok 7"),                       # keine Wortzeile → Dateiname
])
def test_kurz_titel(text, erwartet):
    assert kurz_titel("dok_7", text) == erwartet


# --------------------------------------------------------------------------- #
#  Modell je Vektor (der Fehler, den die Tests oben aufgedeckt haben)
# --------------------------------------------------------------------------- #
def test_altes_gedaechtnis_bekommt_modell_je_vektor(tmp_path):
    """Früher gab es nur EINEN Meta-Wert fürs Modell. Der erste neue Vektor überschrieb ihn —
    danach galt der ganze Altbestand als passend und Stufe A hätte darauf entschieden."""
    import sqlite3

    from pollysort.hive_mind import HiveMind

    hive = tmp_path / "hive"
    db = config.honig(hive) / "gedaechtnis.db"
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)                       # Schema wie vor dem 2026-09-24
    con.execute("CREATE TABLE vectors (bee_id TEXT PRIMARY KEY, kategorie TEXT, vec TEXT)")
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO vectors VALUES ('a', 'rechnungen', '[1.0, 0.0]')")
    con.execute("INSERT INTO meta VALUES ('embed_model', 'nomic-embed-text-v2-moe')")
    con.commit()
    con.close()

    neu = "nomic-embed-text-v2-moe#auszug"
    mind = HiveMind(hive)                           # rüstet die Spalte nach
    assert [e[0] for e in mind.eintraege("nomic-embed-text-v2-moe")] == ["a"]
    assert mind.eintraege(neu) == []
    mind.remember("b", "rechnungen", [0.0, 1.0], neu)
    assert mind.mismatch(neu) == "nomic-embed-text-v2-moe", "Altbestand bleibt erkannt"
    assert [e[0] for e in mind.eintraege(neu)] == ["b"], "Stufe A sieht nur den neuen Vektor"
    mind.forget("a")
    assert mind.mismatch(neu) is None


# --------------------------------------------------------------------------- #
#  analysiere <id> (F2) — ein falsch eingeordneter Altfall
# --------------------------------------------------------------------------- #
def _shell_mit_projekt(tmp_path, monkeypatch, antwort: bool):
    from pollysort.repl import BeehiveShell
    hive = tmp_path / "hive"
    hive.mkdir()
    config.write_seed(hive, HiveSeed(categories=list(CATS), provider="offline"))
    (hive / "auszug.txt").write_text("KONTOAUSZUG Nr. 3/2026\nSaldo 1.234,00 EUR\nIBAN DE12",
                                     encoding="utf-8")
    sh = BeehiveShell.__new__(BeehiveShell)
    sh.con = BeeConsole(quiet=True)
    sh.hive = hive
    monkeypatch.setattr(sh, "_ja_default", lambda _p: antwort, raising=False)
    ctx = sh._ctx()
    run_cycle(ctx, mode="move")
    bee = ctx.store.query()[0]["id"]
    from pollysort.review import apply_correction
    apply_correction(ctx, bee, "rechnungen")          # Altfall: falsch eingeordnet
    return sh, hive, bee


def test_analysiere_ordnet_nach_rueckfrage_neu_ein(tmp_path, monkeypatch):
    sh, hive, bee = _shell_mit_projekt(tmp_path, monkeypatch, antwort=True)
    sh.do_analysiere(bee)
    from pollysort.store import Store
    row = Store(hive).by_id(bee)
    assert row["kategorie"] == "kontoauszuege"
    assert (hive / "Kontoauszuege" / "auszug.txt").exists()


def test_analysiere_ohne_zustimmung_bleibt_alles_liegen(tmp_path, monkeypatch):
    sh, hive, bee = _shell_mit_projekt(tmp_path, monkeypatch, antwort=False)
    sh.do_reanalyze(bee)
    from pollysort.store import Store
    assert Store(hive).by_id(bee)["kategorie"] == "rechnungen"
    assert (hive / "Rechnungen" / "auszug.txt").exists()


def test_kalender_schreibt_die_ics_auch_ohne_termine(tmp_path):
    from pollysort.repl import BeehiveShell
    hive = tmp_path / "hive"
    hive.mkdir()
    config.write_seed(hive, HiveSeed(provider="offline"))
    sh = BeehiveShell.__new__(BeehiveShell)
    sh.con = BeeConsole(quiet=True)
    sh.hive = hive
    sh.do_kalender("")
    assert (config.honig(hive) / "kalender.ics").exists()

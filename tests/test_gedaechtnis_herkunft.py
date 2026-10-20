"""Herkunft je Gedächtnis-Eintrag (2026-10-20).

Das Gedächtnis merkt sich jedes analysierte Dokument mit Label, auch die unsicheren: Rückfragen
und jeden Vorschlag von BeeNara Big. Bis heute zählten diese Einträge in Stufe A und im
Assigner genauso wie bestätigte. Der Fehlerweg: Zwei ähnliche Dokumente bekommen denselben
falschen, unsicheren Vorschlag. Damit ist MINDEST erfüllt, und das Gedächtnis sortiert ein
drittes, sehr ähnliches Dokument ohne Rückfrage ein — auf Grundlage zweier Vermutungen.

Seitdem trägt jeder Eintrag seine Herkunft: ``bestaetigt`` (Nutzer), ``sicher`` (automatisch
einsortiert) oder ``unsicher`` (Rückfrage). Stützen dürfen eine Kategorie nur die ersten beiden;
unsichere Einträge wirken weiter als Gegenstimme.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from test_entscheidung import CATS, RECHNUNG, FakeOllama

from pollysort import config, entscheidung
from pollysort.assigner import BASE_KNOWN, CONFLICT, assign
from pollysort.config import AppConfig, HiveSeed
from pollysort.console import BeeConsole
from pollysort.feedback import Feedback
from pollysort.hive_mind import HiveMind, Taxonomy
from pollysort.hive_mind import memory as gedaechtnis
from pollysort.journal import Journal
from pollysort.llm.client import OfflineClient
from pollysort.models import BeeEntry, Funktion, Status
from pollysort.pipeline import Context, reindex_memory, run_cycle
from pollysort.review import apply_correction, review
from pollysort.store import Store

MAHNUNG = "MAHNUNG Nr. {i}\nZahlungserinnerung: offener Betrag 80,00 EUR\nBitte bis Monatsende begleichen."


class Unsicher(FakeOllama):
    """Schlägt für Mahnungen „kontoauszuege" vor — falsch und unsicher (0,6 < Schwelle 0,75)."""

    def decide(self, text: str, categories: list[str]):
        if "mahnung" in text.lower():
            self.decide_calls.append(text)
            self.usage.add(10, 1)
            return "kontoauszuege", 0.6
        return super().decide(text, categories)


def _ctx(hive: Path, client, seed: HiveSeed | None = None, provider: str = "ollama") -> Context:
    seed = seed or HiveSeed(categories=list(CATS))
    hive.mkdir(parents=True, exist_ok=True)
    config.write_seed(hive, seed)
    return Context.build(hive=hive, cfg=AppConfig(llm_provider=provider), seed=seed,
                         client=client, console=BeeConsole(quiet=True), journal=Journal(hive))


def _datei(hive: Path, name: str, inhalt: str) -> Path:
    p = hive / name
    p.write_text(inhalt, encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
#  Der Fehlerweg
# --------------------------------------------------------------------------- #
def test_zwei_unsichere_vorschlaege_sortieren_kein_drittes_dokument_im_selben_lauf(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, Unsicher())
    for i in range(3):
        _datei(hive, f"m{i}.txt", MAHNUNG.format(i=i))
    s = run_cycle(ctx, mode="move")
    assert s.needs_review == 3, "die dritte Mahnung darf nicht auf zwei Vermutungen hin wandern"
    assert s.quellen == {"nummer": 3}
    assert len(ctx.client.decide_calls) == 3
    assert not (hive / "Kontoauszuege").exists()
    assert all((hive / f"m{i}.txt").exists() for i in range(3))


def test_zwei_unsichere_vorschlaege_sortieren_kein_drittes_dokument_im_naechsten_lauf(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, Unsicher())
    for i in range(2):
        _datei(hive, f"m{i}.txt", MAHNUNG.format(i=i))
    assert run_cycle(ctx, mode="move").needs_review == 2
    # Neuer Kontext: das Gedächtnis kommt diesmal aus der Datenbank, nicht aus der Kopie.
    ctx = _ctx(hive, Unsicher())
    _datei(hive, "m2.txt", MAHNUNG.format(i=2))
    s = run_cycle(ctx, mode="move")
    assert s.needs_review == 1 and s.quellen == {"nummer": 1}
    assert (hive / "m2.txt").exists()


def test_assigner_hebt_die_konfidenz_nicht_mit_unsicheren_eintraegen(tmp_path):
    """Derselbe Weg ohne Stufe A (Offline, voller Analyse-Weg): „Gedächtnis bestätigt" hob die
    Konfidenz über die Schwelle — schon mit EINER Rückfrage als einziger Bestätigung."""
    hive = tmp_path / "hive"
    seed = HiveSeed(categories=list(CATS), threshold_assign=0.9, provider="offline")
    ctx = _ctx(hive, OfflineClient(CATS), seed, provider="offline")
    for i in range(3):
        _datei(hive, f"r{i}.txt", RECHNUNG.format(i=i))
    s = run_cycle(ctx, mode="move")
    assert s.needs_review == 3, "Label allein (0,80) liegt unter 0,9; Rückfragen bestätigen nichts"
    assert all((hive / f"r{i}.txt").exists() for i in range(3))
    assert {r["status"] for r in ctx.store.query()} == {Status.NEEDS_REVIEW.value}
    assert max(r["confidence"] for r in ctx.store.query()) < 0.9


def test_beantwortete_rueckfragen_machen_das_gedaechtnis_belastbar(tmp_path):
    """Die Kehrseite: Hat der Nutzer geantwortet, entscheidet das Gedächtnis wieder allein."""
    hive = tmp_path / "hive"
    ctx = _ctx(hive, Unsicher())
    for i in range(2):
        _datei(hive, f"m{i}.txt", MAHNUNG.format(i=i))
    run_cycle(ctx, mode="move")
    assert set(ctx.mind.herkuenfte().values()) == {("kontoauszuege", "unsicher")}
    assert review(ctx, ask=lambda _p: "rechnungen") == 2
    assert set(ctx.mind.herkuenfte().values()) == {("rechnungen", "bestaetigt")}
    _datei(hive, "m2.txt", MAHNUNG.format(i=2))
    s = run_cycle(ctx, mode="move")
    assert s.quellen == {"gedaechtnis": 1} and s.assigned == 1
    assert (hive / "Rechnungen" / "m2.txt").exists()


def test_sortierlauf_merkt_sicher_und_unsicher(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, Unsicher())
    _datei(hive, "m.txt", MAHNUNG.format(i=1))
    for i in range(3):
        _datei(hive, f"r{i}.txt", RECHNUNG.format(i=i))
    run_cycle(ctx, mode="move")
    herkunft = {r["filename"]: ctx.mind.herkuenfte()[r["id"]] for r in ctx.store.query()}
    assert herkunft == {"m.txt": ("kontoauszuege", "unsicher"), "r0.txt": ("rechnungen", "sicher"),
                        "r1.txt": ("rechnungen", "sicher"), "r2.txt": ("rechnungen", "sicher")}


# --------------------------------------------------------------------------- #
#  Die Regeln: stützen nur belastbar, widersprechen darf jeder
# --------------------------------------------------------------------------- #
def _zaehle(n):
    return lambda _kat: n


def test_stufe_a_entscheidet_nur_mit_belastbarer_stuetze():
    aus = entscheidung.aus_gedaechtnis
    assert aus({"rechnungen": 0.95}, _zaehle(0), CATS, belastbar={}) is None
    # Eine unsichere Spesen-Abrechnung liegt zu nah → Gegenstimme, keine Entscheidung.
    assert aus({"rechnungen": 0.90, "spesen": 0.88}, _zaehle(2), CATS,
               belastbar={"rechnungen": 0.90}) is None
    assert aus({"rechnungen": 0.90, "spesen": 0.40}, _zaehle(2), CATS,
               belastbar={"rechnungen": 0.90}) == ("rechnungen", 0.9)
    # Eine nähere unsichere Rechnung hebt die Ähnlichkeit nicht über die Schwelle.
    assert aus({"rechnungen": 0.99}, _zaehle(2), CATS, belastbar={"rechnungen": 0.70}) is None


def test_konflikt_deckelung_unsichere_widersprechen_stuetzen_aber_nicht():
    deckel = entscheidung.gedeckelt
    assert deckel("rechnungen", 0.97, {"spesen": 0.90, "rechnungen": 0.50},
                  {"rechnungen": 0.50}) == CONFLICT
    # Die eigene Kategorie kennt nur ein unsicherer Eintrag — gegen eine sichere Spesen-Abrechnung.
    assert deckel("rechnungen", 0.97, {"spesen": 0.85, "rechnungen": 0.95},
                  {"spesen": 0.85}) == CONFLICT
    assert deckel("rechnungen", 0.97, {"spesen": 0.85, "rechnungen": 0.95},
                  {"spesen": 0.85, "rechnungen": 0.95}) == 0.97
    assert deckel("rechnungen", 0.97, {"rechnungen": 0.95}, {}) == 0.97


@pytest.mark.parametrize("mit_numpy", [True, False])
def test_schnappschuss_zaehlt_nur_belastbare(monkeypatch, mit_numpy):
    if mit_numpy:
        pytest.importorskip("numpy")
    else:
        monkeypatch.setattr(entscheidung, "_numpy", lambda: None)
    s = entscheidung.Schnappschuss([("a", "rechnungen", [1.0, 0.0], "unsicher"),
                                    ("b", "rechnungen", [1.0, 0.0], "unsicher"),
                                    ("c", "spesen", [0.0, 1.0], "bestaetigt"),
                                    ("d", "spesen", [0.0, 1.0], "sicher")])
    assert (s.count("rechnungen"), s.count("spesen")) == (0, 2)
    n = s.naehe([1.0, 0.0])
    assert n.alle == pytest.approx({"rechnungen": 1.0, "spesen": 0.0}, abs=1e-6)
    assert n.belastbar == pytest.approx({"spesen": 0.0}, abs=1e-6)
    s.merken("a", "rechnungen", [1.0, 0.0], "bestaetigt")          # Rückfrage beantwortet
    s.merken("e", "rechnungen", [1.0, 0.0], "unsicher")
    assert s.count("rechnungen") == 1
    assert s.naehe([1.0, 0.0]).belastbar["rechnungen"] == pytest.approx(1.0, abs=1e-6)
    assert s.beste_je_kategorie([1.0, 0.0]) == s.naehe([1.0, 0.0]).alle


def _taxonomie(hive: Path) -> Taxonomy:
    return Taxonomy.bootstrap(hive, HiveSeed(categories=list(CATS)))


def test_assigner_unsichere_nachbarn_widersprechen_stuetzen_aber_nicht(tmp_path):
    hive = tmp_path / "hive"
    mind, tax = HiveMind(hive), _taxonomie(hive)
    for i in range(3):
        mind.remember(f"s{i}", "spesen", [1.0, 0.0], herkunft="unsicher")
    vec = [1.0, 0.0]
    assert assign(embedding=vec, llm_kategorie="rechnungen", hive=mind,
                  taxonomy=tax).confidence == CONFLICT
    assert assign(embedding=vec, llm_kategorie="spesen", hive=mind,
                  taxonomy=tax).confidence == BASE_KNOWN
    a = assign(embedding=vec, llm_kategorie="_unassigned", hive=mind, taxonomy=tax)
    assert (a.kategorie, a.quelle) == ("_unassigned", "keine") and a.confidence < 0.3
    # Mit belastbaren Einträgen wie vor dem 2026-10-20.
    for i in range(3):
        mind.remember(f"s{i}", "spesen", [1.0, 0.0], herkunft="sicher")
    a = assign(embedding=vec, llm_kategorie="_unassigned", hive=mind, taxonomy=tax)
    assert (a.kategorie, a.quelle, a.confidence) == ("spesen", "gedaechtnis", 1.0)
    assert assign(embedding=vec, llm_kategorie="spesen", hive=mind,
                  taxonomy=tax).confidence == 1.0


def test_herkunft_wird_hochgestuft_aber_nie_herabgestuft(tmp_path):
    mind = HiveMind(tmp_path / "hive")
    assert mind.remember("a", "rechnungen", [1.0], "m", herkunft="unsicher") == "unsicher"
    assert mind.remember("a", "rechnungen", [1.0], "m", herkunft="sicher") == "sicher"
    assert mind.remember("a", "rechnungen", [1.0], "m", herkunft="bestaetigt") == "bestaetigt"
    assert mind.remember("a", "rechnungen", [1.0], "m", herkunft="unsicher") == "bestaetigt"
    # Ein anderes Label ersetzt das alte samt Herkunft.
    assert mind.remember("a", "spesen", [1.0], "m", herkunft="unsicher") == "unsicher"
    assert mind.eintraege("m") == [("a", "spesen", [1.0], "unsicher")]
    with pytest.raises(ValueError):
        mind.remember("b", "spesen", [1.0], "m", herkunft="vielleicht")


def test_relabel_setzt_label_und_herkunft_ohne_neuen_vektor(tmp_path):
    """Für Hand-Verschiebungen beim Scan: kein Embedding, der Vektor bleibt stehen."""
    mind = HiveMind(tmp_path / "hive")
    mind.remember("a", "rechnungen", [1.0, 2.0], "m", herkunft="sicher")
    assert mind.relabel("a", "spesen", herkunft="bestaetigt") is True
    assert mind.eintraege("m") == [("a", "spesen", [1.0, 2.0], "bestaetigt")]
    # Gleiche Kategorie: hochstufen ja, herabstufen nie — wie bei remember.
    assert mind.relabel("a", "spesen", herkunft="unsicher") is True
    assert mind.herkuenfte() == {"a": ("spesen", "bestaetigt")}
    # Ohne Herkunft (Migration) bleibt sie; eine andere Kategorie bringt die neue mit.
    assert mind.relabel("a", "kontoauszuege") is True
    assert mind.herkuenfte() == {"a": ("kontoauszuege", "bestaetigt")}
    assert mind.relabel("a", "rechnungen", herkunft="unsicher") is True
    assert mind.herkuenfte() == {"a": ("rechnungen", "unsicher")}
    # Ohne Vektor nichts — auch kein leerer Eintrag.
    version = mind.version
    assert mind.relabel("fehlt", "spesen", herkunft="bestaetigt") is False
    assert "fehlt" not in mind.herkuenfte() and mind.version == version
    with pytest.raises(ValueError):
        mind.relabel("a", "spesen", herkunft="vielleicht")


def test_saat_bleibt_bestaetigt_wenn_der_lauf_unsicher_ist(tmp_path):
    """Vorwärmen legt die Saat unter der ID ab, die der echte Eintrag bekommt."""
    from pollysort import vorwaermen as vw
    from pollysort.models import BeeAnalysis
    from pollysort.scout import scout
    hive = tmp_path / "hive"
    ctx = _ctx(hive, Unsicher())
    p = _datei(hive, "m.txt", MAHNUNG.format(i=1))
    funde = scout([p])
    vw.vorwaermen([(funde[0], BeeAnalysis(title="Mahnung", kategorie="kontoauszuege"))], CATS,
                  mind=ctx.mind, embed=ctx.client.embed, embed_model=ctx.client.embed_model)
    run_cycle(ctx, mode="move")
    assert list(ctx.mind.herkuenfte().values()) == [("kontoauszuege", "bestaetigt")]


# --------------------------------------------------------------------------- #
#  Altbestand und Neuaufbau
# --------------------------------------------------------------------------- #
def _eintrag(bid: str, kat: str, status: Status, conf: float = 0.0) -> BeeEntry:
    return BeeEntry(id=bid, path=f"/nirgends/{bid}.txt", filename=f"{bid}.txt",
                    content_hash=f"sha256:{bid}", funktion=Funktion(kategorie=kat),
                    confidence=conf, status=status)


def _altes_gedaechtnis(hive: Path, vektoren: dict[str, str]) -> None:
    """``gedaechtnis.db`` wie vor dem 2026-10-20: Modell je Vektor, keine Herkunft."""
    db = config.honig(hive) / "gedaechtnis.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE vectors (bee_id TEXT PRIMARY KEY, kategorie TEXT, vec TEXT, model TEXT)")
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.executemany("INSERT INTO vectors VALUES (?, ?, '[1.0]', 'm')", list(vektoren.items()))
    con.commit()
    con.close()


def test_altbestand_wird_aus_katalog_und_korrekturen_eingestuft(tmp_path):
    hive = tmp_path / "hive"
    store = Store(hive)
    for e in [_eintrag("auto", "rechnungen", Status.ASSIGNED, 0.97),
              _eintrag("frage", "spesen", Status.NEEDS_REVIEW, 0.55),
              _eintrag("antwort", "spesen", Status.ASSIGNED, 0.55),
              _eintrag("hand", "spesen", Status.ASSIGNED, 0.97),
              _eintrag("idx_hoch", "rechnungen", Status.INDEXED, 0.9),
              _eintrag("idx_tief", "rechnungen", Status.INDEXED, 0.5)]:
        store.save(e)
    # Eine Korrektur im alten Format (ohne die Felder der Feldmessung).
    zeile = {"ts": "2026-10-01T10:00:00+00:00", "bee_id": "antwort", "title": "", "funktion": "",
             "kategorie_alt": "rechnungen", "kategorie_neu": "spesen", "quelle": "review"}
    (config.honig(hive) / "korrekturen.jsonl").write_text(json.dumps(zeile) + "\n",
                                                          encoding="utf-8")
    _altes_gedaechtnis(hive, {"saat": "kontoauszuege", "auto": "rechnungen", "frage": "spesen",
                              "antwort": "spesen", "hand": "rechnungen",   # von Hand verschoben
                              "idx_hoch": "rechnungen", "idx_tief": "rechnungen"})
    erwartet = {"saat": "bestaetigt", "auto": "sicher", "frage": "unsicher",
                "antwort": "bestaetigt", "hand": "unsicher", "idx_hoch": "sicher",
                "idx_tief": "unsicher"}
    assert {b: h for b, (_k, h) in HiveMind(hive).herkuenfte().items()} == erwartet
    assert {b: h for b, (_k, h) in HiveMind(hive).herkuenfte().items()} == erwartet  # stabil


def test_altbestand_ohne_lesbaren_katalog_zaehlt_unsicher_bis_zum_naechsten_versuch(
        tmp_path, monkeypatch):
    hive = tmp_path / "hive"
    _altes_gedaechtnis(hive, {"a": "rechnungen"})

    def kaputt(_hive):
        raise OSError("Katalog gesperrt")

    monkeypatch.setattr(gedaechtnis, "_katalog_einstufung", kaputt)
    assert HiveMind(hive).eintraege("m") == [("a", "rechnungen", [1.0], "unsicher")]
    monkeypatch.undo()
    assert HiveMind(hive).eintraege("m") == [("a", "rechnungen", [1.0], "bestaetigt")]


def test_neuaufbau_behaelt_die_herkunft(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, Unsicher())
    for i in range(3):
        _datei(hive, f"r{i}.txt", RECHNUNG.format(i=i))
    run_cycle(ctx, mode="move")
    ids = {r["filename"]: r["id"] for r in ctx.store.query()}
    apply_correction(ctx, ids["r0.txt"], "rechnungen")             # bestätigt
    vorher = ctx.mind.herkuenfte()
    assert vorher[ids["r0.txt"]] == ("rechnungen", "bestaetigt")
    assert reindex_memory(ctx) == (3, 0)
    assert ctx.mind.herkuenfte() == vorher
    # Fehlt ein Eintrag im Gedächtnis, kommt die Herkunft aus Katalog und Korrekturen.
    ctx.mind.forget(ids["r0.txt"])
    ctx.mind.forget(ids["r1.txt"])
    assert reindex_memory(ctx) == (3, 0)
    assert ctx.mind.herkuenfte() == vorher


# --------------------------------------------------------------------------- #
#  Feldmessung: wer lag vorher wie sicher daneben?
# --------------------------------------------------------------------------- #
def test_korrektur_haelt_fest_wer_vorher_wie_sicher_entschieden_hatte(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, Unsicher())
    _datei(hive, "m.txt", MAHNUNG.format(i=1))
    for i in range(3):
        _datei(hive, f"r{i}.txt", RECHNUNG.format(i=i))
    run_cycle(ctx, mode="move")
    zeilen = {r["filename"]: r for r in ctx.store.query()}
    assert {n: z["quelle"] for n, z in zeilen.items()} == {
        "m.txt": "nummer", "r0.txt": "nummer", "r1.txt": "nummer", "r2.txt": "gedaechtnis"}

    review(ctx, ask=lambda _p: "rechnungen")                        # die Mahnung fragte nach
    r2 = zeilen["r2.txt"]["id"]
    apply_correction(ctx, r2, "spesen")                             # eine falsch einsortierte
    k = {c["bee_id"]: c for c in ctx.feedback.all()}
    m = k[zeilen["m.txt"]["id"]]
    assert (m["quelle"], m["quelle_vorher"], m["konfidenz_vorher"], m["status_vorher"]) == \
        ("review", "nummer", 0.6, "needs_review")
    assert (k[r2]["quelle"], k[r2]["quelle_vorher"], k[r2]["konfidenz_vorher"],
            k[r2]["status_vorher"]) == ("assign", "gedaechtnis", 1.0, "assigned")
    # Die Antwort ist jetzt selbst die Quelle — eine zweite Korrektur misst sie.
    assert ctx.store.by_id(r2)["quelle"] == "assign"
    apply_correction(ctx, r2, "rechnungen")
    assert ctx.feedback.all()[-1]["quelle_vorher"] == "assign"


def test_assigner_weg_steht_im_katalog(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive, OfflineClient(CATS), HiveSeed(categories=list(CATS), provider="offline"),
               provider="offline")
    _datei(hive, "r.txt", RECHNUNG.format(i=1))
    _datei(hive, "kuchen.txt", "Apfelkuchen: 500 g Mehl, 3 Eier")
    run_cycle(ctx, mode="move")
    assert {r["filename"]: r["quelle"] for r in ctx.store.query()} == {
        "r.txt": "label", "kuchen.txt": "keine"}


def test_alter_katalog_bekommt_die_spalte_und_bleibt_lesbar(tmp_path):
    hive = tmp_path / "hive"
    store = Store(hive)
    store.save(_eintrag("alt", "rechnungen", Status.ASSIGNED, 0.97))
    store.engine.dispose()
    con = sqlite3.connect(config.honig(hive) / "katalog.db")      # Schema vor dem 2026-10-20
    con.execute("ALTER TABLE bees DROP COLUMN quelle")
    con.commit()
    con.close()
    store = Store(hive)
    zeile = store.by_id("alt")
    assert zeile["quelle"] is None and zeile["kategorie"] == "rechnungen"
    store.save(_eintrag("neu", "spesen", Status.ASSIGNED, 0.9).model_copy(update={"quelle": "nummer"}))
    assert store.by_id("neu")["quelle"] == "nummer"


def test_alte_und_neue_korrekturen_lesen_sich_gemeinsam(tmp_path):
    """Wachstafel und Few-Shots lesen dieselbe Datei — alte Zeilen ohne die neuen Felder."""
    from pollysort.wachstafel import Wachstafel
    hive = tmp_path / "hive"
    hive.mkdir()
    fb = Feedback(hive)
    alt = {"ts": "2026-10-01T10:00:00+00:00", "bee_id": "x", "title": "Rechnung Telekom Festnetz",
           "funktion": "", "kategorie_alt": "rechnungen", "kategorie_neu": "kontoauszuege",
           "quelle": "assign"}
    fb.path.write_text(json.dumps(alt) + "\n", encoding="utf-8")
    fb.record(bee_id="y", title="Telekom Rechnung Mobilfunk", funktion="",
              kategorie_alt="rechnungen", kategorie_neu="kontoauszuege", quelle="review",
              quelle_vorher="beenara", konfidenz_vorher=0.98, status_vorher="assigned")
    assert [c.get("quelle_vorher") for c in fb.all()] == [None, "beenara"]
    assert [c["title"] for c in fb.few_shots()] == ["Telekom Rechnung Mobilfunk",
                                                    "Rechnung Telekom Festnetz"]
    Wachstafel(hive).reflektiere(fb, categories=CATS)
    assert ("telekom", "kontoauszuege") in Wachstafel(hive).regeln()

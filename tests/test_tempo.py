"""Tempo ohne andere Ergebnisse (2026-10-02).

Gemessen über den Dienst des Flugbretts: 0,74 s je Datei im Sparmodus mit BeeNara, davon
~0,45 s im Modell. Der Rest ging an drei Stellen verloren, die hier abgesichert sind — jeweils
mit der Bedingung, dass dieselben Entscheidungen herauskommen wie vorher:

* Das Gedächtnis wurde für **jede** Datei komplett aus SQLite geladen und in reinem Python
  verglichen. Jetzt einmal je Lauf, danach nachgetragen; mit numpy als Matrix-Produkt.
* Der Sparmodus las jede Datei zweimal (Heuristik, dann BeeNara).
* BeeNara rechnete mit 4 Threads; 6 sind auf dem Laptop 23 % schneller, mehr bremsen.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from pollysort import beenara, entscheidung, extractor
from pollysort.config import AppConfig, HiveSeed
from pollysort.console import BeeConsole
from pollysort.journal import Journal
from pollysort.pipeline import Context, _gedaechtnis_sicht, run_cycle


def _eintraege(n: int, dim: int = 64, seed: int = 7):
    rnd = random.Random(seed)
    kats = ["rechnungen", "spesen", "kontoauszuege", "_unassigned"]
    return [(f"b{i}", kats[i % 4], [rnd.uniform(-1, 1) for _ in range(dim)]) for i in range(n)]


def _gleich(a: dict, b: dict) -> None:
    assert a.keys() == b.keys()
    for k in a:
        assert a[k] == pytest.approx(b[k], abs=1e-5), k


# --------------------------------------------------------------------------- #
#  Gedächtnis-Kopie
# --------------------------------------------------------------------------- #
def test_numpy_rechnet_wie_reines_python():
    pytest.importorskip("numpy")
    eintraege = _eintraege(40)
    q = [random.Random(1).uniform(-1, 1) for _ in range(64)]
    _gleich(entscheidung.Schnappschuss(eintraege).beste_je_kategorie(q),
            entscheidung.beste_je_kategorie(q, eintraege))


@pytest.mark.parametrize("mit_numpy", [True, False])
def test_merken_ergibt_dasselbe_wie_neu_laden(monkeypatch, mit_numpy):
    """Auch über die Reserve von 64 Zeilen hinaus (die Matrix wächst) und beim Ersetzen."""
    if mit_numpy:
        pytest.importorskip("numpy")
    else:
        monkeypatch.setattr(entscheidung, "_numpy", lambda: None)
    alle = _eintraege(150)
    s = entscheidung.Schnappschuss(alle[:10])
    q = alle[0][2]
    s.beste_je_kategorie(q)                         # baut die Matrix
    for bid, kat, v in alle[10:]:
        s.merken(bid, kat, v)
    _gleich(s.beste_je_kategorie(q), entscheidung.Schnappschuss(alle).beste_je_kategorie(q))
    assert s.count("rechnungen") == sum(1 for _b, k, _v in alle if k == "rechnungen")
    # Dieselbe Datei ein zweites Mal (Wiederholung nach Fehler): ersetzt, nicht doppelt.
    s.merken("b1", "rechnungen", alle[1][2])
    erwartet = [(b, "rechnungen" if b == "b1" else k, v) for b, k, v in alle]
    _gleich(s.beste_je_kategorie(q), entscheidung.Schnappschuss(erwartet).beste_je_kategorie(q))
    assert s.count("spesen") == sum(1 for _b, k, _v in erwartet if k == "spesen")


def test_gemischte_dimensionen_rechnen_wie_bisher():
    eintraege = [("a", "rechnungen", [1.0, 0.0]), ("b", "spesen", [0.0, 1.0, 0.0])]
    assert entscheidung.Schnappschuss(eintraege).beste_je_kategorie([1.0, 0.0]) == \
        entscheidung.beste_je_kategorie([1.0, 0.0], eintraege)


class _Fake:
    """Ollama im Kleinen: Stichwort-Embedding, entscheidet per Nummer (wie test_entscheidung)."""

    memory_basis = "auszug"
    embed_model = "fake#auszug"

    def __init__(self):
        from pollysort.llm.client import Usage
        self.usage = Usage()
        self._wachstafel = ""

    def embed(self, text):
        return [1.0, 0.0, 0.0] if "rechnung" in text.lower() else [0.0, 0.0, 1.0]

    def decide(self, text, categories):
        return ("rechnungen", 0.97) if "rechnung" in text.lower() else ("_unassigned", 0.9)

    def suggest_subrouting(self, categories):
        return {}


def _ctx(hive: Path) -> Context:
    from pollysort import config
    seed = HiveSeed(categories=["rechnungen", "spesen", "kontoauszuege"], provider="ollama")
    hive.mkdir(parents=True, exist_ok=True)
    config.write_seed(hive, seed)
    return Context.build(hive=hive, cfg=AppConfig(llm_provider="ollama"), seed=seed,
                         client=_Fake(), console=BeeConsole(quiet=True), journal=Journal(hive))


def test_gedaechtnis_wird_einmal_je_lauf_geladen(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    for i in range(6):
        (hive / f"r{i}.txt").write_text(f"RECHNUNG Nr. {i}\nBetrag {i}0,00 EUR", encoding="utf-8")
    geladen: list[int] = []
    echt = ctx.mind.eintraege
    ctx.mind.eintraege = lambda modell: geladen.append(1) or echt(modell)
    s = run_cycle(ctx, mode="move")
    assert len(geladen) == 1, "vorher: einmal je Datei"
    # Und es entscheidet wie vorher: Ab der dritten Rechnung kennt das Gedächtnis zwei.
    assert s.quellen == {"nummer": 2, "gedaechtnis": 4}


def test_aenderung_am_gedaechtnis_laedt_neu(tmp_path):
    """Korrektur, Papierkorb, Umbenennen ändern das Gedächtnis an der Kopie vorbei — dann
    darf die alte Kopie nicht weiter benutzt werden."""
    ctx = _ctx(tmp_path / "hive")
    ctx.mind.remember("x", "rechnungen", [1.0, 0.0, 0.0], ctx.client.embed_model)
    erste = _gedaechtnis_sicht(ctx)
    assert _gedaechtnis_sicht(ctx) is erste, "unverändert: dieselbe Kopie"
    for aendern in (lambda: ctx.mind.relabel("x", "spesen"), lambda: ctx.mind.forget("x"),
                    lambda: ctx.mind.relabel_category("spesen", "rechnungen"),
                    lambda: ctx.mind.reset()):
        vorher = _gedaechtnis_sicht(ctx)
        aendern()
        assert _gedaechtnis_sicht(ctx) is not vorher


def test_anderes_modell_laedt_neu(tmp_path):
    ctx = _ctx(tmp_path / "hive")
    erste = _gedaechtnis_sicht(ctx)
    ctx.client.embed_model = "anderes#auszug"
    assert _gedaechtnis_sicht(ctx) is not erste


# --------------------------------------------------------------------------- #
#  Text nur einmal lesen
# --------------------------------------------------------------------------- #
def _zaehlen(monkeypatch) -> list[Path]:
    gelesen: list[Path] = []
    echt = extractor._extract_text_neu
    monkeypatch.setattr(extractor, "_extract_text_neu",
                        lambda path: gelesen.append(path) or echt(path))
    return gelesen


def test_in_einer_analyse_wird_jede_datei_nur_einmal_gelesen(tmp_path, monkeypatch):
    p = tmp_path / "rechnung.txt"
    p.write_text("RECHNUNG Nr. 1", encoding="utf-8")
    gelesen = _zaehlen(monkeypatch)
    with extractor.einmal_lesen():
        assert extractor.volltext(p) == extractor.volltext(p) == "RECHNUNG Nr. 1"
        with extractor.einmal_lesen():           # verschachtelt: derselbe Speicher
            extractor.volltext(p)
    assert len(gelesen) == 1


def test_ausserhalb_einer_analyse_wird_frisch_gelesen(tmp_path, monkeypatch):
    """Kein Zwischenspeicher über die Analyse hinaus — eine gleich groß überschriebene Datei
    (Windows löst Änderungszeiten nur grob auf) darf nie alt aussehen."""
    p = tmp_path / "rechnung.txt"
    p.write_text("RECHNUNG Nr. 1", encoding="utf-8")
    gelesen = _zaehlen(monkeypatch)
    with extractor.einmal_lesen():
        extractor.volltext(p)
    p.write_text("RECHNUNG Nr. 2", encoding="utf-8")             # gleiche Größe
    assert extractor.volltext(p) == "RECHNUNG Nr. 2"
    assert len(gelesen) == 2


def test_jeder_thread_hat_seinen_eigenen_speicher(tmp_path, monkeypatch):
    import threading
    p = tmp_path / "rechnung.txt"
    p.write_text("RECHNUNG Nr. 1", encoding="utf-8")
    gelesen = _zaehlen(monkeypatch)
    with extractor.einmal_lesen():
        extractor.volltext(p)
        t = threading.Thread(target=extractor.volltext, args=(p,))
        t.start()
        t.join()
    assert len(gelesen) == 2, "der andere Thread (Ultra Swarm) liest selbst"


def test_sparmodus_liest_jede_datei_einmal(tmp_path, monkeypatch):
    from test_beenara_sortieren import FakeBee

    from pollysort import config
    from pollysort.llm.client import OfflineClient
    hive = tmp_path / "hive"
    seed = HiveSeed(categories=["rechnungen", "spesen", "kontoauszuege"], provider="offline")
    hive.mkdir()
    config.write_seed(hive, seed)
    ctx = Context.build(hive=hive, cfg=AppConfig(llm_provider="offline"), seed=seed,
                        client=OfflineClient(seed.categories), console=BeeConsole(quiet=True),
                        journal=Journal(hive))
    ctx.beenara, ctx.beenara_geprueft = FakeBee(), True
    for i in range(3):
        (hive / f"r{i}.txt").write_text(f"RECHNUNG Nr. {i}", encoding="utf-8")
    gelesen = _zaehlen(monkeypatch)
    s = run_cycle(ctx, mode="move")
    assert s.quellen == {"beenara": 3}
    assert len(gelesen) == 3, "vorher 6: Heuristik und BeeNara lasen je einmal"


# --------------------------------------------------------------------------- #
#  Threads
# --------------------------------------------------------------------------- #
def test_threads_gemessen_und_ueberschreibbar(monkeypatch):
    monkeypatch.delenv("POLLYSORT_BEENARA_THREADS", raising=False)
    monkeypatch.setattr(beenara.os, "cpu_count", lambda: 16)
    assert beenara.threads() == 6, "gemessen: 6 schneller als 4 und als 8+"
    monkeypatch.setattr(beenara.os, "cpu_count", lambda: 4)
    assert beenara.threads() == 4
    monkeypatch.setattr(beenara.os, "cpu_count", lambda: None)
    assert beenara.threads() == 1
    monkeypatch.setenv("POLLYSORT_BEENARA_THREADS", "8")
    assert beenara.threads() == 8
    monkeypatch.setenv("POLLYSORT_BEENARA_THREADS", "viele")
    monkeypatch.setattr(beenara.os, "cpu_count", lambda: 16)
    assert beenara.threads() == 6, "Unsinn in der Variable: Standard"


def test_knoepfe_der_karte_sind_waehrend_langer_aktionen_gesperrt():
    """Sonst startet „Herunterladen" während des Downloads ein zweites Mal (Server: beschäftigt)."""
    js = (Path(__file__).resolve().parents[1] / "src" / "pollysort" / "web" / "static"
          / "app.js").read_text(encoding="utf-8")
    arbeit = js[js.index("async function arbeit("):]
    arbeit = arbeit[:arbeit.index("\n  }\n")]
    assert "karteSperren()" in arbeit and "freigeben()" in arbeit.split("finally")[1]

"""Regressionstests für die in der QA-Session gefundenen Fehler & Optimierungen.

Deckt ab:
- BUG-1: centroid() robust bei gemischten Vektor-Dimensionen (kein IndexError).
- BUG-3: Dry-run (vorschau) ist nebenwirkungsfrei (kein DB-Eintrag, kein Move, kein Merken).
- OPT-1: Offline-Heuristik erbt Regeln über den Wortstamm (Singular) und greift bei
         Mehrwort-Kategorien über deren Einzelwörter.
- OPT-2: leeren/bury entfernt verwaiste Katalog-Einträge (mit Store).
"""

from __future__ import annotations

from pathlib import Path

from bumble.config import AppConfig, HiveSeed
from bumble.console import BeeConsole
from bumble.heuristics import classify
from bumble.hive_mind import HiveMind
from bumble.journal import Journal
from bumble.llm.client import OfflineClient
from bumble.models import Status
from bumble.pipeline import Context, run_cycle


def _ctx(hive: Path, seed: HiveSeed | None = None) -> Context:
    seed = seed or HiveSeed()
    hive.mkdir(parents=True, exist_ok=True)
    return Context.build(
        hive=hive, cfg=AppConfig(llm_provider="offline"), seed=seed,
        client=OfflineClient(seed.categories), console=BeeConsole(quiet=True),
        journal=Journal(hive),
    )


# ---- BUG-3: Dry-run ist nebenwirkungsfrei --------------------------------
def test_dry_run_has_no_side_effects(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    f = hive / "rechnung_1.txt"
    f.write_text("Rechnung ACME Betrag 100 EUR UST zahlbar", encoding="utf-8")

    s = run_cycle(ctx, mode="move", dry_run=True)
    # Vorschau würde einsortieren, aber NICHTS persistieren/bewegen.
    assert s.stored >= 1
    assert ctx.store.query() == []                 # kein DB-Eintrag
    assert ctx.mind.count() == 0                    # kein Gedächtnis-Vektor
    assert f.exists()                               # Datei unverschoben
    assert not list((hive / "Rechnungen").glob("*")) if (hive / "Rechnungen").exists() else True

    # Danach echter Lauf: jetzt wird persistiert & verschoben (Datei war NICHT „verbraucht").
    s2 = run_cycle(ctx, mode="move", dry_run=False)
    assert s2.moved >= 1
    assert len(ctx.store.query()) == 1
    assert list((hive / "Rechnungen").glob("rechnung_1.txt"))


# ---- BUG-1: centroid() robust bei gemischten Dimensionen -----------------
def test_centroid_survives_mixed_dimensions(tmp_path):
    mind = HiveMind(tmp_path / "hive")
    # Zwei 3-dim + ein 2-dim Vektor in derselben Kategorie (z. B. nach Modellwechsel).
    mind.remember("a", "rechnung", [1.0, 0.0, 0.0])
    mind.remember("b", "rechnung", [0.0, 1.0, 0.0])
    mind.remember("c", "rechnung", [1.0, 1.0])           # Fremd-Dimension
    c = mind.centroid("rechnung")                        # früher: IndexError
    assert c is not None and len(c) == 3                 # häufigste Dimension gewinnt
    # Auch die Paarbildung (Reflection/Merge) darf nicht crashen:
    assert isinstance(mind.centroid_pairs(), list)


# ---- OPT-2: leeren/bury räumt Katalog-Einträge mit auf -------------------
def test_bury_purges_catalog(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    (hive / "weg.txt").write_text("Rechnung ACME Betrag 1 EUR", encoding="utf-8")
    run_cycle(ctx, mode="index")
    bee_id = ctx.store.query()[0]["id"]

    from bumble.undertaker import bury, undertake
    undertake(hive, ctx.store, bee_id)
    assert ctx.store.by_id(bee_id)["status"] == Status.QUARANTINED.value

    removed = bury(hive, ctx.store)
    assert removed
    assert ctx.store.by_id(bee_id) is None                       # keine Waise mehr
    assert not (ctx.store.honig / f"{bee_id}.json").exists()      # Export mit entfernt


# ---- OPT-1: Offline-Heuristik für reale Projekt-Kategorien ----------------
def test_offline_heuristic_singular_and_multiword():
    cats = ["angebot", "technische dokumentation", "rechnung", "finanzen"]
    # Singular „rechnung" erbt die Regeln des kanonischen „rechnungen" (invoice/betrag).
    assert classify("Invoice-2024", "betrag 100 eur", ".pdf", allowed=cats) == "rechnung"
    assert classify("quittung_bar", "", ".pdf", allowed=cats) == "rechnung"
    # Mehrwort-Kategorie greift über ein Einzelwort im Dateinamen.
    assert classify("technisches_dokument", "", ".pdf", allowed=cats) == "technische dokumentation"
    # „finanzen" ist selbst RULES-Schlüssel (steuer/bilanz).
    assert classify("steuerbescheid", "bilanz", ".pdf", allowed=cats) == "finanzen"
    # Kein Signal → offen.
    assert classify("random_notiz", "nichts", ".pdf", allowed=cats) == "_unassigned"
    # Onboarding-Pfad (allowed=None) bleibt unverändert an den RULES-Schlüsseln.
    assert classify("x", "invoice betrag", ".pdf", allowed=None) == "rechnungen"

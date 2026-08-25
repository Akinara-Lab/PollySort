"""Phase 5: Ultra Swarm — parallele KI-Analyse, gleiches Ergebnis wie sequenziell.

Der Worker-Pool wärmt nur die (teuren, read-only) KI-Analysen parallel vor; DB, Move und
Gedächtnis bleiben einthreadig → kein SQLite-/Ordner-/MoveLog-Race. Das Ergebnis muss
Datei für Datei identisch zum sequenziellen Lauf sein.
"""

from __future__ import annotations

from pathlib import Path

from bumble.config import AppConfig, HiveSeed
from bumble.console import BeeConsole
from bumble.journal import Journal
from bumble.llm.client import OfflineClient
from bumble.pipeline import Context, run_cycle


def _ctx(hive: Path) -> Context:
    seed = HiveSeed(categories=["rechnungen", "vertraege", "protokolle", "recherche"])
    hive.mkdir(parents=True, exist_ok=True)
    return Context.build(
        hive=hive, cfg=AppConfig(llm_provider="offline"), seed=seed,
        client=OfflineClient(seed.categories), console=BeeConsole(quiet=True),
        journal=Journal(hive),
    )


def _fill(hive: Path, n: int) -> None:
    texts = ["Rechnung Betrag {} EUR UST", "Mietvertrag Vereinbarung Nr {}",
             "Protokoll der Sitzung {}", "Studie Analyse Recherche {}"]
    for i in range(n):
        (hive / f"doc_{i}.txt").write_text(texts[i % 4].format(i), encoding="utf-8")


def _result_map(ctx: Context) -> dict[str, str]:
    return {r["filename"]: r["kategorie"] for r in ctx.store.query()}


def test_swarm_matches_sequential(tmp_path):
    seq = _ctx(tmp_path / "seq")
    _fill(seq.hive, 12)
    s_seq = run_cycle(seq, mode="move", workers=1)

    par = _ctx(tmp_path / "par")
    _fill(par.hive, 12)
    s_par = run_cycle(par, mode="move", workers=8)

    assert s_par.stored == s_seq.stored
    assert s_par.errors == 0
    # Datei-für-Datei identische Zuordnung.
    assert _result_map(par) == _result_map(seq)
    # Jede sicher zugeordnete Datei liegt in ihrer Wabe (einthreadiges Einlagern klappte).
    assert len(par.store.query()) == 12


def test_swarm_no_duplicate_processing(tmp_path):
    """Dubletten & bekannte Dateien werden im Vorwärmen übersprungen (kein Doppel-Ingest)."""
    ctx = _ctx(tmp_path / "hive")
    _fill(ctx.hive, 4)
    run_cycle(ctx, mode="move", workers=4)
    n_after_first = len(ctx.store.query())
    # Zweiter Lauf: nichts Neues → keine neuen Einträge, kein Absturz.
    s2 = run_cycle(ctx, mode="move", workers=4)
    assert len(ctx.store.query()) == n_after_first
    assert s2.stored == 0

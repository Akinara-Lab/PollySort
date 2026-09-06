"""Phase 3: Self-Learning aus manuellen Verschiebungen (Scan/Sweep).

Zieht der Nutzer eine Datei von Hand aus Wabe A in Wabe B, soll ein `scan` das als
Zuordnungs-Korrektur A→B verstehen: Kategorie/Status nachziehen und als Nektar-Feedback
(`quelle: manuell`) festhalten — die Rohdaten für die Wachstafel-Regeln.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from pollysort.config import AppConfig, HiveSeed, pretty_category
from pollysort.console import BeeConsole
from pollysort.journal import Journal
from pollysort.llm.client import OfflineClient
from pollysort.models import Status
from pollysort.pipeline import Context, run_cycle
from pollysort.sweeper import sweep


def _ctx(hive: Path, seed: HiveSeed | None = None) -> Context:
    seed = seed or HiveSeed(categories=["rechnungen", "finanzen"])
    hive.mkdir(parents=True, exist_ok=True)
    return Context.build(
        hive=hive, cfg=AppConfig(llm_provider="offline"), seed=seed,
        client=OfflineClient(seed.categories), console=BeeConsole(quiet=True),
        journal=Journal(hive),
    )


def test_manual_move_between_categories_is_learned(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    # Eine Datei einsortieren lassen → landet in einer Wabe.
    (hive / "telekom_rechnung.txt").write_text("Rechnung Telekom Betrag 40 EUR", encoding="utf-8")
    run_cycle(ctx, mode="move")
    row = ctx.store.query()[0]
    bee_id = row["id"]
    start_cat = row["kategorie"]
    src = Path(row["path"])
    assert src.parent.name == pretty_category(start_cat)

    # Nutzer verschiebt die Datei VON HAND in eine andere Wabe (finanzen).
    target = "finanzen" if start_cat != "finanzen" else "rechnungen"
    dest_dir = hive / pretty_category(target)
    dest_dir.mkdir(exist_ok=True)
    shutil.move(str(src), str(dest_dir / src.name))

    # scan/sweep erkennt den Move und lernt daraus.
    report = sweep(ctx, mode="index")
    assert report.learned == 1

    updated = ctx.store.by_id(bee_id)
    assert updated["kategorie"] == target
    assert updated["status"] == Status.ASSIGNED.value

    corrections = ctx.feedback.all()
    assert any(c.get("quelle") == "manuell" and c.get("kategorie_neu") == target
               for c in corrections)


def test_move_within_same_category_is_not_learned(tmp_path):
    """Nur Kreuz-Waben-Moves sind Korrekturen; ein Pfad-Fix allein lernt nichts."""
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    (hive / "r.txt").write_text("Rechnung Betrag 10 EUR", encoding="utf-8")
    run_cycle(ctx, mode="move")
    row = ctx.store.query()[0]
    src = Path(row["path"])

    # Innerhalb derselben Wabe umbenennen (kein Kategorie-Wechsel).
    shutil.move(str(src), str(src.parent / "r_umbenannt.txt"))
    report = sweep(ctx, mode="index")
    assert report.moved == 1
    assert report.learned == 0

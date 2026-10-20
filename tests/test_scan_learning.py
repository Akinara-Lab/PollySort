"""Phase 3: Self-Learning aus manuellen Verschiebungen (Scan/Sweep).

Zieht der Nutzer eine Datei von Hand aus Wabe A in Wabe B, soll ein `scan` das als
Zuordnungs-Korrektur A→B verstehen: Kategorie/Status nachziehen und als Nektar-Feedback
(`quelle: manuell`) festhalten — die Rohdaten für die Wachstafel-Regeln.

Seit 2026-10-20 zieht auch das Gedächtnis nach: Der Eintrag heißt B und gilt als bestätigt.
Vorher hieß er weiter A, stützte A für ähnliche Dokumente und stand als Gegenstimme gegen B.
Der Scan bettet dafür nichts neu ein.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from test_entscheidung import CATS, RECHNUNG, FakeOllama

from pollysort import config
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


def _kein_embedding(_text: str) -> list[float]:
    raise AssertionError("der Scan darf nichts einbetten")


def test_manual_move_between_categories_is_learned(tmp_path, monkeypatch):
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
    modell = ctx.client.embed_model
    [(_, kat, vec, _)] = ctx.mind.eintraege(modell)
    assert kat == start_cat

    # Nutzer verschiebt die Datei VON HAND in eine andere Wabe (finanzen).
    target = "finanzen" if start_cat != "finanzen" else "rechnungen"
    dest_dir = hive / pretty_category(target)
    dest_dir.mkdir(exist_ok=True)
    shutil.move(str(src), str(dest_dir / src.name))

    # scan/sweep erkennt den Move und lernt daraus — ohne einen einzigen Embedding-Aufruf.
    monkeypatch.setattr(ctx.client, "embed", _kein_embedding)
    report = sweep(ctx, mode="index")
    assert report.learned == 1
    # Das Gedächtnis zieht nach: neues Label, bestätigt, derselbe Vektor.
    assert ctx.mind.eintraege(modell) == [(bee_id, target, vec, "bestaetigt")]

    updated = ctx.store.by_id(bee_id)
    assert updated["kategorie"] == target
    assert updated["status"] == Status.ASSIGNED.value

    corrections = ctx.feedback.all()
    assert any(c.get("quelle") == "manuell" and c.get("kategorie_neu") == target
               for c in corrections)
    # Feldmessung (2026-10-20): wer vorher entschieden hatte — und jetzt: der Nutzer von Hand.
    c = next(c for c in corrections if c.get("quelle") == "manuell")
    assert row["quelle"] and c["quelle_vorher"] == row["quelle"]
    assert (c["konfidenz_vorher"], c["status_vorher"]) == (row["confidence"], row["status"])
    assert updated["quelle"] == "manuell"


def test_move_within_same_category_is_not_learned(tmp_path):
    """Nur Kreuz-Waben-Moves sind Korrekturen; ein Pfad-Fix allein lernt nichts."""
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    (hive / "r.txt").write_text("Rechnung Betrag 10 EUR", encoding="utf-8")
    run_cycle(ctx, mode="move")
    row = ctx.store.query()[0]
    src = Path(row["path"])

    # Innerhalb derselben Wabe umbenennen (kein Kategorie-Wechsel).
    vorher = ctx.mind.herkuenfte()
    shutil.move(str(src), str(src.parent / "r_umbenannt.txt"))
    report = sweep(ctx, mode="index")
    assert report.moved == 1
    assert report.learned == 0
    assert ctx.mind.herkuenfte() == vorher


# --------------------------------------------------------------------------- #
#  Das Gedächtnis zieht nach (2026-10-20)
# --------------------------------------------------------------------------- #
def _ollama_ctx(hive: Path) -> Context:
    """Mit Stufe A: ein Ollama-Doppelgänger, der seine Embedding-Aufrufe mitschreibt."""
    seed = HiveSeed(categories=list(CATS))
    hive.mkdir(parents=True, exist_ok=True)
    config.write_seed(hive, seed)
    return Context.build(hive=hive, cfg=AppConfig(llm_provider="ollama"), seed=seed,
                         client=FakeOllama(), console=BeeConsole(quiet=True),
                         journal=Journal(hive))


def _rechnungen(hive: Path, n: int) -> None:
    for i in range(n):
        (hive / f"r{i}.txt").write_text(RECHNUNG.format(i=i), encoding="utf-8")


def _von_hand(hive: Path, pfad: str, kategorie: str) -> None:
    ziel = hive / pretty_category(kategorie)
    ziel.mkdir(exist_ok=True)
    shutil.move(pfad, str(ziel / Path(pfad).name))


def test_hand_verschiebung_lenkt_stufe_a_um(tmp_path):
    """Zwei Rechnungen, beide von Hand nach Spesen gezogen. Vorher schickte das Gedächtnis eine
    dritte, gleichartige Rechnung in Stufe A trotzdem nach Rechnungen — auf zwei überholte
    Labels hin. Jetzt folgt es dem Nutzer."""
    hive = tmp_path / "hive"
    ctx = _ollama_ctx(hive)
    _rechnungen(hive, 2)
    run_cycle(ctx, mode="move")
    zeilen = ctx.store.query()
    assert {ctx.mind.herkuenfte()[z["id"]] for z in zeilen} == {("rechnungen", "sicher")}
    for z in zeilen:
        _von_hand(hive, z["path"], "spesen")

    eingebettet = len(ctx.client.embedded)
    report = sweep(ctx, mode="index")
    assert report.learned == 2
    assert len(ctx.client.embedded) == eingebettet, "der Scan darf nichts einbetten"
    assert {ctx.mind.herkuenfte()[z["id"]] for z in zeilen} == {("spesen", "bestaetigt")}

    (hive / "r2.txt").write_text(RECHNUNG.format(i=2), encoding="utf-8")
    s = run_cycle(ctx, mode="move")
    assert s.quellen == {"gedaechtnis": 1} and s.assigned == 1
    assert (hive / "Spesen" / "r2.txt").exists()


def test_eine_hand_verschiebung_ist_gegenstimme(tmp_path):
    """Drei Rechnungen, eine davon nach Spesen gezogen. Zwei stützen weiter Rechnungen, aber der
    bestätigte Spesen-Eintrag liegt gleich nah: Stufe A entscheidet nicht mehr allein."""
    hive = tmp_path / "hive"
    ctx = _ollama_ctx(hive)
    _rechnungen(hive, 3)
    assert run_cycle(ctx, mode="move").quellen == {"nummer": 2, "gedaechtnis": 1}
    _von_hand(hive, ctx.store.query()[0]["path"], "spesen")
    assert sweep(ctx, mode="index").learned == 1

    (hive / "r3.txt").write_text(RECHNUNG.format(i=3), encoding="utf-8")
    assert run_cycle(ctx, mode="move").quellen == {"nummer": 1}


def test_hand_verschiebung_ohne_vektor_merkt_nichts(tmp_path):
    """Gibt es für die Datei keinen Vektor, legt der Scan auch keinen an."""
    hive = tmp_path / "hive"
    ctx = _ollama_ctx(hive)
    _rechnungen(hive, 2)
    run_cycle(ctx, mode="move")
    ohne, mit = ctx.store.query()
    ctx.mind.forget(ohne["id"])
    _von_hand(hive, ohne["path"], "spesen")

    eingebettet = len(ctx.client.embedded)
    assert sweep(ctx, mode="index").learned == 1
    assert len(ctx.client.embedded) == eingebettet
    assert ctx.store.by_id(ohne["id"])["kategorie"] == "spesen"
    assert ctx.mind.herkuenfte() == {mit["id"]: ("rechnungen", "sicher")}

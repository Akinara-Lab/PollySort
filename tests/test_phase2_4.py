"""Akzeptanz: Gedächtnis/Confidence, Move/Recovery/Undertaker, Lernen — neues .honig-Layout."""

from __future__ import annotations

from pathlib import Path

from pollysort import config
from pollysort.config import AppConfig, HiveSeed
from pollysort.console import BeeConsole
from pollysort.journal import Journal
from pollysort.llm.client import OfflineClient
from pollysort.models import Status
from pollysort.pipeline import Context, run_cycle


def _ctx(hive: Path, seed: HiveSeed | None = None) -> Context:
    seed = seed or HiveSeed(responsibility={"rechnungen": ["nik"]})
    hive.mkdir(parents=True, exist_ok=True)
    return Context.build(
        hive=hive, cfg=AppConfig(llm_provider="offline"), seed=seed,
        client=OfflineClient(seed.categories), console=BeeConsole(quiet=True),
        journal=Journal(hive),
    )


def _rechnung(hive: Path, i: int) -> None:
    (hive / f"rechnung_{i}.txt").write_text(
        f"Rechnung Nr {i} ACME Betrag {i}00 EUR UST 19 Prozent zahlbar", encoding="utf-8")


# ---- Gedächtnis, Confidence, Schwelle, Zuständigkeit ----------------------
def test_confidence_learns_and_thresholds(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    for i in range(20):
        _rechnung(hive, i)
    run_cycle(ctx, mode="index")

    # 21. Rechnung wird mit >= 0.75 automatisch zugeordnet
    from pollysort.assigner import assign
    vec = ctx.client.embed("Rechnung Nr 999 ACME Betrag 99900 EUR UST zahlbar")
    a = assign(embedding=vec, llm_kategorie="rechnungen", hive=ctx.mind, taxonomy=ctx.taxonomy)
    assert a.kategorie == "rechnungen"
    assert a.confidence >= 0.75
    assert a.zustaendigkeit == ["nik"]

    # Themenfremdes Dokument landet in der Rückfrage (< Schwelle)
    vec2 = ctx.client.embed("Mondlicht Sterne Traum Poesie Wolken Wind")
    a2 = assign(embedding=vec2, llm_kategorie="_unassigned", hive=ctx.mind, taxonomy=ctx.taxonomy)
    assert a2.confidence < 0.75


def test_assign_moves_centroid(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    (hive / "unklar.txt").write_text("voellig neutrale zeilen ohne signal wort", encoding="utf-8")
    run_cycle(ctx, mode="index")
    row = ctx.store.query()[0]

    before = ctx.mind.count("vertraege")
    from pollysort.review import apply_correction
    apply_correction(ctx, row["id"], "vertraege", mode="index", source="assign")
    assert ctx.mind.count("vertraege") == before + 1          # Zentroid verschoben
    assert (config.honig(hive) / "korrekturen.jsonl").exists()


# ---- Move, Kategorie-Ordner, Undertaker ----------------------------------
def test_move_into_category_folder(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    for i in range(6):
        _rechnung(hive, i)
    run_cycle(ctx, mode="index")                 # Gedächtnis füllen → confident
    (hive / "rechnung_neu.txt").write_text(
        "Rechnung ACME Betrag 500 EUR UST zahlbar frisch", encoding="utf-8")
    s = run_cycle(ctx, mode="move")
    assert s.moved >= 1
    # Sicher zugeordnete Datei liegt jetzt im sichtbaren Ordner 'Rechnungen'
    assert list((hive / "Rechnungen").glob("rechnung_neu.txt"))


def test_sweep_detects_drift(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    _rechnung(hive, 1)
    run_cycle(ctx, mode="index")                 # bleibt lose im Root liegen

    from pollysort.sweeper import sweep
    (hive / "rechnung_1.txt").unlink()           # verschwunden
    (hive / "Rechnungen").mkdir(exist_ok=True)   # neu: direkt in einen Kategorie-Ordner gelegt
    (hive / "Rechnungen" / "direkt.txt").write_text(
        "Rechnung direkt abgelegt Betrag 10 EUR", encoding="utf-8")
    rep = sweep(ctx, mode="index")
    assert rep.missing == 1
    assert rep.new == 1
    assert rep.exit_code() == 4


def test_undertaker_roundtrip(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    (hive / "weg.txt").write_text("Rechnung ACME Betrag 1 EUR", encoding="utf-8")
    run_cycle(ctx, mode="index")
    row = ctx.store.query()[0]

    from pollysort.undertaker import buried_candidates, bury, resurrect, undertake
    dest = undertake(hive, ctx.store, row["id"])
    assert dest and dest.exists() and dest.parent.name == "papierkorb"
    assert ctx.store.by_id(row["id"])["status"] == Status.QUARANTINED.value

    back = resurrect(hive, ctx.store, row["id"])
    assert back and back.exists()
    undertake(hive, ctx.store, row["id"])
    assert buried_candidates(hive)
    removed = bury(hive, ctx.store)
    assert removed and not buried_candidates(hive)


# ---- Empfehlungen & Reflection -------------------------------------------
def test_reflection_and_suggest(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    for i in range(6):
        (hive / f"foerder_{i}.txt").write_text(
            f"Foerderantrag {i} Zuschuss Antrag Behoerde foerderung", encoding="utf-8")
    run_cycle(ctx, mode="index")

    from pollysort.hive_mind.reflection import Reflection
    proposals = Reflection(hive).reflect(ctx.store, ctx.mind)
    assert any(p.kind == "new" for p in proposals)

    from pollysort.recommender import suggest
    hints = suggest(ctx, "para")
    assert hints and any("Dynamisch" in h for h in hints)

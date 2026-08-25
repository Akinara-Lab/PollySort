"""Kern-Akzeptanz: Sortieren, Dedupe, Robustheit, .honig-Layout."""

from __future__ import annotations

from pathlib import Path

from bumble import config
from bumble.config import AppConfig, HiveSeed
from bumble.console import BeeConsole
from bumble.journal import Journal
from bumble.llm.client import OfflineClient
from bumble.pipeline import Context, run_cycle
from bumble.store import Store


def _make_hive(tmp_path: Path) -> Path:
    """Ein Arbeitsordner mit losen Dateien direkt im Root (der 'Posteingang')."""
    hive = tmp_path / "arbeitsordner"
    hive.mkdir(parents=True, exist_ok=True)
    (hive / "rechnung_acme.txt").write_text("Rechnung ACME Betrag 4200 EUR UST", encoding="utf-8")
    (hive / "mietvertrag.txt").write_text("Mietvertrag Vereinbarung Wohnung", encoding="utf-8")
    (hive / "protokoll.md").write_text("# Protokoll Sitzung Beschluss", encoding="utf-8")
    (hive / "kaputt.pdf").write_bytes(b"%PDF broken \x00\x01 not valid")   # 'korrupt'
    (hive / "kopie.txt").write_text("Rechnung ACME Betrag 4200 EUR UST", encoding="utf-8")  # Dublette
    return hive


def _run(hive: Path, mode: str = "index"):
    seed = HiveSeed(responsibility={"rechnungen": ["nik"]})
    ctx = Context.build(
        hive=hive, cfg=AppConfig(llm_provider="offline"), seed=seed,
        client=OfflineClient(seed.categories), console=BeeConsole(quiet=True),
        journal=Journal(hive),
    )
    return run_cycle(ctx, mode=mode), ctx.client


def test_index_and_dedupe(tmp_path):
    hive = _make_hive(tmp_path)

    s1, _ = _run(hive)
    # 4 eindeutige Inhalte (rechnung, mietvertrag, protokoll, pdf); kopie.txt = Dublette
    assert s1.stored == 4
    assert s1.duplicates == 1
    assert s1.errors == 0
    assert s1.exit_code() == 0

    # Zweiter Lauf: kein neuer Inhalt → 0 KI-Anfragen (Dedupe)
    s2, client2 = _run(hive)
    assert s2.stored == 0
    assert client2.usage.calls == 0


def test_honig_layout_keeps_root_clean(tmp_path):
    hive = _make_hive(tmp_path)
    _run(hive)

    # Alles Generierte liegt in EINEM versteckten Ordner .honig
    hon = config.honig(hive)
    assert (hon / "katalog.db").exists()
    assert list((hon / "eintraege").glob("*.md"))
    assert list((hon / "eintraege").glob("*.json"))
    # Im Arbeitsverzeichnis entstehen NUR .honig + die losen Dateien (kein waben/flugloch/…)
    top = {p.name for p in hive.iterdir()}
    assert ".honig" in top
    assert not (top & {"waben", "flugloch", "pollen", "friedhof", "honig", "hive_mind"})


def test_query_and_responsibility(tmp_path):
    hive = _make_hive(tmp_path)
    _run(hive)
    store = Store(hive)
    assert store.status_counts().get("indexed") == 4
    assert len(store.query(kategorie="rechnungen")) == 1
    assert store.query(person="nik")     # Zuständigkeit aus dem Seed abgeleitet


def test_move_puts_files_into_category_folders(tmp_path):
    hive = _make_hive(tmp_path)
    # Genug Rechnungen fürs Gedächtnis, dann move
    for i in range(6):
        (hive / f"rechnung_{i}.txt").write_text(
            f"Rechnung Nr {i} ACME Betrag {i}00 EUR UST zahlbar Beleg", encoding="utf-8")
    _run(hive, mode="move")
    # Sicher zugeordnete Rechnungen landen im sichtbaren Ordner 'Rechnungen'
    assert (hive / "Rechnungen").is_dir()
    assert list((hive / "Rechnungen").glob("*.txt"))

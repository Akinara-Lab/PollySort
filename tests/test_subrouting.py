"""Phase 4: Dynamische Unterordner (Sub-Routing), z. B. Rechnungen nach Jahr/Monat."""

from __future__ import annotations

from pathlib import Path

from pollysort.config import AppConfig, HiveSeed
from pollysort.console import BeeConsole
from pollysort.journal import Journal
from pollysort.llm.client import OfflineClient
from pollysort.models import BeeEntry
from pollysort.mover import resolve_subpath, target_dir
from pollysort.pipeline import Context, run_cycle


def _entry(tmp_path: Path, filename: str, kategorie: str) -> BeeEntry:
    e = BeeEntry(id="a1b2c3d4", path=str(tmp_path / filename), filename=filename,
                 content_hash="sha256:deadbeef")
    e.funktion.kategorie = kategorie
    return e


def test_target_dir_appends_year_month(tmp_path):
    e = _entry(tmp_path, "Rechnung_2026-07-14.pdf", "rechnungen")
    d = target_dir(tmp_path, e, {"rechnungen": "{jahr}/{monat}"})
    assert d == tmp_path / "Rechnungen" / "2026" / "07"


def test_target_dir_without_pattern_is_flat(tmp_path):
    e = _entry(tmp_path, "Rechnung.pdf", "rechnungen")
    assert target_dir(tmp_path, e, {}) == tmp_path / "Rechnungen"
    assert target_dir(tmp_path, e, {"finanzen": "{jahr}"}) == tmp_path / "Rechnungen"


def test_resolve_subpath_rejects_traversal(tmp_path):
    e = _entry(tmp_path, "x_2026-07-14.pdf", "rechnungen")
    out = resolve_subpath("../../etc/{jahr}", e)
    assert ".." not in out
    assert out.endswith("2026")


def test_date_from_dotted_format(tmp_path):
    e = _entry(tmp_path, "Beleg 14.07.2026.pdf", "rechnungen")
    d = target_dir(tmp_path, e, {"rechnungen": "{jahr}/{monat}/{tag}"})
    assert d == tmp_path / "Rechnungen" / "2026" / "07" / "14"


def test_suggest_subrouting_heuristic():
    from pollysort.heuristics import suggest_subrouting
    subs = suggest_subrouting(["rechnungen", "finanzen", "vertraege", "kontoauszug"])
    assert subs.get("rechnungen") == "{jahr}/{monat}"
    assert subs.get("finanzen") == "{jahr}/{monat}"
    assert subs.get("kontoauszug") == "{jahr}/{monat}"
    assert "vertraege" not in subs           # Verträge sind nicht datums-laufend


def test_offline_client_suggest_subrouting():
    from pollysort.llm.client import OfflineClient
    c = OfflineClient(["rechnungen", "protokolle"])
    subs = c.suggest_subrouting(["rechnungen", "protokolle"])
    assert subs == {"rechnungen": "{jahr}/{monat}"}


def test_online_suggest_falls_back_to_heuristic_on_error(monkeypatch):
    from pollysort.llm.client import OpenRouterClient
    c = OpenRouterClient("k", "m", "e", ["rechnungen", "vertraege"])

    def boom(*a, **k):
        raise RuntimeError("netz weg")
    monkeypatch.setattr(c, "_post", boom)
    subs = c.suggest_subrouting(["rechnungen", "vertraege"])
    assert subs == {"rechnungen": "{jahr}/{monat}"}   # Fehler → Heuristik


def test_correction_respects_subrouting(tmp_path):
    """Auch `zuordnen` legt in den dynamischen Unterordner (nicht nur in den Waben-Root)."""
    from pollysort.review import apply_correction
    hive = tmp_path / "hive"
    hive.mkdir()
    seed = HiveSeed(categories=["rechnungen", "sonstiges"],
                    subrouting={"rechnungen": "{jahr}/{monat}"})
    ctx = Context.build(
        hive=hive, cfg=AppConfig(llm_provider="offline"), seed=seed,
        client=OfflineClient(seed.categories), console=BeeConsole(quiet=True),
        journal=Journal(hive),
    )
    # Neutraler Inhalt → landet als Rückfrage (needs_review) im Root.
    (hive / "dok_2026-05-10.txt").write_text("neutraler inhalt ohne stichworte", encoding="utf-8")
    run_cycle(ctx, mode="move")
    bee_id = ctx.store.query()[0]["id"]
    apply_correction(ctx, bee_id, "rechnungen", mode="move")
    hits = list((hive / "Rechnungen").rglob("dok_2026-05-10.txt"))
    assert hits
    assert hits[0].relative_to(hive / "Rechnungen").parts[:2] == ("2026", "05")


def test_pipeline_sorts_into_subfolder(tmp_path):
    hive = tmp_path / "hive"
    hive.mkdir()
    seed = HiveSeed(categories=["rechnungen"], subrouting={"rechnungen": "{jahr}/{monat}"})
    ctx = Context.build(
        hive=hive, cfg=AppConfig(llm_provider="offline"), seed=seed,
        client=OfflineClient(seed.categories), console=BeeConsole(quiet=True),
        journal=Journal(hive),
    )
    (hive / "rechnung_2026-07-14.txt").write_text("Rechnung Betrag 99 EUR", encoding="utf-8")
    run_cycle(ctx, mode="move")
    hits = list((hive / "Rechnungen").rglob("rechnung_2026-07-14.txt"))
    assert hits, "Datei sollte in einem Unterordner der Wabe liegen"
    # relativ zur Wabe: 2026/07/<datei>
    rel = hits[0].relative_to(hive / "Rechnungen")
    assert rel.parts[:2] == ("2026", "07")

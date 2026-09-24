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


# --------------------------------------------------------------------------- #
#  Das echte Dokumentdatum (2026-09-24)
# --------------------------------------------------------------------------- #
import pytest  # noqa: E402

from pollysort.heuristics import dokument_datum  # noqa: E402


@pytest.mark.parametrize("text, erwartet", [
    ("RECHNUNG Nr. 4\nzahlbar bis 30.10.2026\nRechnungsdatum: 2026-10-10", "2026-10-10"),
    ("Leistungszeitraum: 01.09.2026 – 30.09.2026\nDatum: 05.10.2026", "2026-10-05"),
    ("Kontoauszug vom 3. März 2026\nSaldo", "2026-03-03"),
    ("Invoice date: July 14, 2026\nDue: 2026-08-14", "2026-07-14"),
    ("Musterstadt, 14.07.2026\nSehr geehrte Damen und Herren", "2026-07-14"),
    ("Kündigung fällig bis 31.12.2026\nIhr Vertrag vom 01.02.2026", "2026-02-01"),
])
def test_dokument_datum(text, erwartet):
    assert dokument_datum(text).isoformat() == erwartet


def test_dokument_datum_ohne_datum_oder_unsinn():
    assert dokument_datum("Keine Zahl hier") is None
    assert dokument_datum("Artikel 31.13.2026 und 1850-01-01") is None


def test_unterordner_folgt_dem_rechnungsdatum(tmp_path):
    """Früher gewann das erste Datum — hier die Zahlungsfrist im Oktober."""
    f = tmp_path / "rechnung.txt"
    f.write_text("RECHNUNG\nzahlbar bis 15.10.2026\nRechnungsdatum: 28.09.2026", encoding="utf-8")
    e = _entry(tmp_path, "rechnung.txt", "rechnungen")
    assert target_dir(tmp_path, e, {"rechnungen": "{jahr}/{monat}"}) == \
        tmp_path / "Rechnungen" / "2026" / "09"


def test_beschriftetes_datum_schlaegt_den_dateinamen(tmp_path):
    f = tmp_path / "scan_2026-11-02.txt"
    f.write_text("Rechnungsdatum: 2026-10-10\nBetrag", encoding="utf-8")
    e = _entry(tmp_path, "scan_2026-11-02.txt", "rechnungen")
    assert target_dir(tmp_path, e, {"rechnungen": "{jahr}/{monat}"}) == \
        tmp_path / "Rechnungen" / "2026" / "10"


def test_dateiname_schlaegt_ein_unbeschriftetes_datum(tmp_path):
    f = tmp_path / "beleg_2026-05-20.txt"
    f.write_text("Irgendwas 01.01.2025 notiert", encoding="utf-8")
    e = _entry(tmp_path, "beleg_2026-05-20.txt", "rechnungen")
    assert target_dir(tmp_path, e, {"rechnungen": "{jahr}/{monat}"}) == \
        tmp_path / "Rechnungen" / "2026" / "05"

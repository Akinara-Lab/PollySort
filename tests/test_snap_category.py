"""Fix (2026-07-15): LLM-Kategorien beim Sortieren auf die bekannten Projekt-Kategorien
einrasten — es entstehen keine Ordner außerhalb der vorgeschlagenen Menge.
"""

from __future__ import annotations

from bumble.assigner import assign
from bumble.config import HiveSeed
from bumble.heuristics import snap_category
from bumble.hive_mind import HiveMind, Taxonomy


def test_snap_exact_and_case():
    known = ["rechnungen", "vertraege", "technische dokumentation"]
    assert snap_category("Rechnungen", known) == "rechnungen"
    assert snap_category("  vertraege  ", known) == "vertraege"


def test_snap_stem_singular_plural():
    known = ["rechnungen", "vertraege"]
    assert snap_category("rechnung", known) == "rechnungen"   # Singular → Plural
    assert snap_category("vertrag", known) == "vertraege"


def test_snap_multiword_shared_word():
    known = ["technische dokumentation", "rechnungen"]
    assert snap_category("technische doku", known) == "technische dokumentation"
    assert snap_category("dokumentation", known) == "technische dokumentation"


def test_snap_synonym_via_rules():
    known = ["rechnungen", "finanzen"]
    assert snap_category("invoice", known) == "rechnungen"        # engl. Synonym
    assert snap_category("steuerbescheid", known) == "finanzen"   # steuer* → finanzen


def test_snap_no_match_returns_none():
    known = ["rechnungen", "vertraege"]
    assert snap_category("kochrezepte", known) is None
    assert snap_category("", known) is None
    assert snap_category("_unassigned", known) is None
    assert snap_category("rechnungen", []) is None               # keine bekannten → None


def test_assign_snaps_unknown_label_to_known(tmp_path):
    hive = HiveMind(tmp_path / "hive")                # leeres Gedächtnis
    tax = Taxonomy.bootstrap(tmp_path / "hive", HiveSeed(categories=["rechnungen", "finanzen"]))
    # LLM liefert „invoice" → muss auf „rechnungen" einrasten (kein neuer Ordner).
    a = assign(embedding=[0.0], llm_kategorie="invoice", hive=hive, taxonomy=tax)
    assert a.kategorie == "rechnungen"


def test_assign_unknown_label_without_match_becomes_review(tmp_path):
    hive = HiveMind(tmp_path / "hive")
    tax = Taxonomy.bootstrap(tmp_path / "hive", HiveSeed(categories=["rechnungen", "finanzen"]))
    # Kein sicherer Treffer → _unassigned (wird zur Rückfrage), KEIN Rogue-Ordner.
    a = assign(embedding=[0.0], llm_kategorie="kochrezepte", hive=hive, taxonomy=tax)
    assert a.kategorie == "_unassigned"


def test_prompt_builds_strict_and_free(monkeypatch):
    from bumble.llm.client import OpenRouterClient
    strict = OpenRouterClient("k", "m", "e", ["rechnungen", "vertraege"])
    parts = strict._build_content(text="hallo", file_path=None)
    txt = parts[0]["text"]
    assert "ausschliesslich" in txt and "rechnungen, vertraege" in txt

    free = OpenRouterClient("k", "m", "e", [])
    txt2 = free._build_content(text="hallo", file_path=None)[0]["text"]
    assert "ausschliesslich" not in txt2         # Vorschlag: keine strikte Vorgabe

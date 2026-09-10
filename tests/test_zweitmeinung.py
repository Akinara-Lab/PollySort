"""Zweitmeinung der Heuristik (2026-09-10).

Rastet das Modell-Label auf keine Projekt-Kategorie ein („gehaltsabrechnung" für eine
Reisekostenabrechnung), entscheidet die Offline-Heuristik auf der Zusammenfassung, die das
Modell selbst geschrieben hat — aber nur bei einem spezifischen Fachbegriff, und nie gegen
ein brauchbares Label. Die Quelle wird ausgewiesen, damit der Nutzer sieht, wer entschieden hat.
"""

from __future__ import annotations

from pollysort.assigner import ZWEITMEINUNG_MIN, assign, zweitmeinung
from pollysort.config import HiveSeed
from pollysort.heuristics import classify_scored
from pollysort.hive_mind import HiveMind, Taxonomy

CATS = ["rechnungen", "spesen", "kontoauszuege"]
REISEKOSTEN = ("Reisekostenabrechnung Jonas Bergmann\nErstattung von Reisekosten\n"
               "Fahrtkosten, Verpflegung, Übernachtung")


def _tax(tmp_path):
    return Taxonomy.bootstrap(tmp_path / "hive", HiveSeed(categories=CATS))


def test_classify_scored_reports_points():
    kat, punkte = classify_scored("", REISEKOSTEN, "", allowed=CATS)
    assert kat == "spesen" and punkte >= ZWEITMEINUNG_MIN
    assert classify_scored("", "Mondlicht und Sterne", "", allowed=CATS) == ("_unassigned", 0)


def test_zweitmeinung_needs_a_specific_term():
    assert zweitmeinung(REISEKOSTEN, CATS) == "spesen"
    assert zweitmeinung("Kontoauszug Nr. 3", CATS) == "kontoauszuege"   # ein Begriff, 11 Zeichen
    assert zweitmeinung("Ein Beleg.", CATS) is None                       # „beleg" (5) reicht nie
    assert zweitmeinung("", CATS) is None
    assert zweitmeinung(REISEKOSTEN, []) is None


def test_assign_uses_second_opinion_when_label_does_not_snap(tmp_path):
    hive = HiveMind(tmp_path / "hive")                    # leeres Gedächtnis
    a = assign(embedding=[0.0], llm_kategorie="gehaltsabrechnung", hive=hive,
               taxonomy=_tax(tmp_path), analysis_text=REISEKOSTEN)
    assert a.kategorie == "spesen"
    assert a.quelle == "zweitmeinung"
    assert a.confidence >= 0.75                           # wird einsortiert, nicht nachgefragt


def test_assign_second_opinion_also_rescues_an_empty_label(tmp_path):
    hive = HiveMind(tmp_path / "hive")
    a = assign(embedding=[0.0], llm_kategorie="", hive=hive,
               taxonomy=_tax(tmp_path), analysis_text=REISEKOSTEN)
    assert (a.kategorie, a.quelle) == ("spesen", "zweitmeinung")


def test_assign_keeps_review_without_specific_term(tmp_path):
    hive = HiveMind(tmp_path / "hive")
    a = assign(embedding=[0.0], llm_kategorie="kochrezepte", hive=hive,
               taxonomy=_tax(tmp_path), analysis_text="Ein Text ohne Fachbegriff, nur ein Beleg.")
    assert (a.kategorie, a.quelle) == ("_unassigned", "keine")
    assert a.confidence < 0.75


def test_second_opinion_never_overrides_a_usable_label(tmp_path):
    """Das Modell hat entschieden — die Heuristik darf höchstens ergänzen, nie umstoßen."""
    hive = HiveMind(tmp_path / "hive")
    a = assign(embedding=[0.0], llm_kategorie="rechnungen", hive=hive,
               taxonomy=_tax(tmp_path), analysis_text=REISEKOSTEN)   # widerspricht dem Label
    assert (a.kategorie, a.quelle) == ("rechnungen", "label")


def test_assign_without_analysis_text_behaves_as_before(tmp_path):
    hive = HiveMind(tmp_path / "hive")
    a = assign(embedding=[0.0], llm_kategorie="kochrezepte", hive=hive, taxonomy=_tax(tmp_path))
    assert (a.kategorie, a.quelle) == ("_unassigned", "keine")

"""Der wachsende Bienenstock — Fortschritt, Abzeichen, Serien.

Der wichtigste Test hier ist der, der nichts passieren lässt: Wer nur zuschaut, sammelt
nichts ein. Eine Fortschrittsanzeige, die für das bloße Öffnen des Programms Punkte
vergibt, ist wertlos — dann misst sie nicht mehr die Arbeit, sondern die Anwesenheit.
"""

from __future__ import annotations

from datetime import date

from pollysort import i18n, spiel


# --------------------------------------------------------------------------- #
#  Stufen
# --------------------------------------------------------------------------- #
def test_stufen_steigen_mit_der_arbeit():
    assert spiel.stufe_fuer(0)[1] == "schwarm"
    assert spiel.stufe_fuer(9)[1] == "schwarm"
    assert spiel.stufe_fuer(10)[1] == "jung"
    assert spiel.stufe_fuer(5000)[1] == "legendaer"


def test_naechste_stufe_zaehlt_richtig_herunter():
    fehlt, schwelle = spiel.naechste_stufe(7)
    assert (fehlt, schwelle) == (3, 10)
    assert spiel.naechste_stufe(99999) is None


# --------------------------------------------------------------------------- #
#  Fortschreiben — nur echte Arbeit zählt
# --------------------------------------------------------------------------- #
def test_ohne_arbeit_passiert_nichts(tmp_path):
    """Ein Lauf, der nichts einsortiert hat, darf den Stand NICHT verändern."""
    stand, neu, auf = spiel.nach_lauf(tmp_path, sortiert=0, korrekturen=0)
    assert (stand.dokumente, neu, auf) == (0, [], False)
    assert not (tmp_path / ".honig" / "spiel.json").exists(), "es darf nichts geschrieben werden"


def test_erster_lauf_vergibt_die_ersten_abzeichen(tmp_path):
    stand, neu, auf = spiel.nach_lauf(tmp_path, sortiert=12, waben=3, eingang_leer=True)
    assert stand.dokumente == 12
    assert set(neu) == {"erste_wabe", "zehn", "blitzblank"}
    assert auf is True, "12 Dokumente = Aufstieg von 'schwarm' auf 'jung'"


def test_abzeichen_gibt_es_nur_einmal(tmp_path):
    spiel.nach_lauf(tmp_path, sortiert=12, eingang_leer=True)
    _stand, neu, _auf = spiel.nach_lauf(tmp_path, sortiert=3, eingang_leer=True)
    assert neu == [], "bereits verdiente Abzeichen dürfen nicht erneut gefeiert werden"


def test_korrektur_zaehlt_auch_ohne_sortierte_datei(tmp_path):
    stand, neu, _ = spiel.nach_lauf(tmp_path, sortiert=0, korrekturen=1)
    assert stand.korrekturen == 1
    assert "lehrmeister" in neu


def test_stand_ueberlebt_neu_laden(tmp_path):
    spiel.nach_lauf(tmp_path, sortiert=7, waben=2)
    stand = spiel.laden(tmp_path)
    assert stand.dokumente == 7 and stand.waben == 2


def test_kaputte_datei_kostet_nur_den_fortschritt(tmp_path):
    (tmp_path / ".honig").mkdir(parents=True)
    (tmp_path / ".honig" / "spiel.json").write_text("{kein json", encoding="utf-8")
    assert spiel.laden(tmp_path).dokumente == 0        # kein Absturz


# --------------------------------------------------------------------------- #
#  Serie
# --------------------------------------------------------------------------- #
def test_serie_waechst_an_folgetagen(tmp_path):
    spiel.nach_lauf(tmp_path, sortiert=1, heute=date(2026, 5, 1))
    spiel.nach_lauf(tmp_path, sortiert=1, heute=date(2026, 5, 2))
    stand, _, _ = spiel.nach_lauf(tmp_path, sortiert=1, heute=date(2026, 5, 3))
    assert stand.serie == 3


def test_zweiter_lauf_am_selben_tag_zaehlt_nicht_doppelt(tmp_path):
    spiel.nach_lauf(tmp_path, sortiert=1, heute=date(2026, 5, 1))
    stand, _, _ = spiel.nach_lauf(tmp_path, sortiert=1, heute=date(2026, 5, 1))
    assert stand.serie == 1


def test_luecke_setzt_die_serie_zurueck(tmp_path):
    spiel.nach_lauf(tmp_path, sortiert=1, heute=date(2026, 5, 1))
    stand, _, _ = spiel.nach_lauf(tmp_path, sortiert=1, heute=date(2026, 5, 9))
    assert stand.serie == 1


def test_serie_abzeichen_nach_sieben_tagen(tmp_path):
    neu = []
    for tag in range(1, 8):
        _stand, n, _ = spiel.nach_lauf(tmp_path, sortiert=1, heute=date(2026, 5, tag))
        neu += n
    assert "serie" in neu


# --------------------------------------------------------------------------- #
#  Anzeige
# --------------------------------------------------------------------------- #
def test_balken_bleibt_immer_gleich_breit():
    for anteil in (-1.0, 0.0, 0.37, 1.0, 5.0):
        assert len(spiel.balken(anteil, breite=10)) == 10


def test_uebersicht_ist_zweisprachig(tmp_path):
    spiel.nach_lauf(tmp_path, sortiert=12, waben=3, eingang_leer=True)
    stand = spiel.laden(tmp_path)
    try:
        i18n.set_language("de")
        assert "Junger Stock" in "\n".join(spiel.uebersicht(stand))
        i18n.set_language("en")
        text = "\n".join(spiel.uebersicht(stand))
        assert "Young hive" in text
        assert "Stufe" not in text, "im EN-Modus darf keine deutsche Zeile stehen bleiben"
    finally:
        i18n.set_language("de")


def test_jedes_abzeichen_hat_einen_grund_text():
    """Ohne Begründung ist ein Abzeichen nur ein Aufkleber."""
    for schluessel in spiel.ABZEICHEN:
        for sprache in ("de", "en"):
            i18n.set_language(sprache)
            assert i18n.t(f"spiel.abzeichen.{schluessel}") != f"spiel.abzeichen.{schluessel}"
            assert i18n.t(f"spiel.grund.{schluessel}") != f"spiel.grund.{schluessel}"
    i18n.set_language("de")

"""Taxonomie-Konsolidierung — keine Doppelordner, aber echte Gruppen bleiben getrennt.

Der Fehler, um den es geht: Jedes Dokument wird **einzeln** analysiert, also antwortet
dasselbe Modell für denselben Stapel Rechnungen mal „rechnungen", mal „finanzen", mal
„belege" — drei Ordner für eine Sache. Diese Tests halten beide Richtungen fest: Was
dasselbe meint, wird zusammengelegt; was wirklich verschieden ist, bleibt getrennt.
"""

from __future__ import annotations

from pollysort.taxonomie import (
    MAX_KATEGORIEN,
    SYSTEM_REGELN,
    konsolidieren,
    pruefe,
)


# --------------------------------------------------------------------------- #
#  Zusammenlegen — der Doppelordner-Fehler
# --------------------------------------------------------------------------- #
def test_oberbegriff_verschwindet_neben_unterbegriff():
    """Der Kernfall des Nutzers: nur Rechnungen → NICHT auch noch 'Finanzen'."""
    ergebnis, protokoll = konsolidieren({"rechnungen": 11, "finanzen": 3})
    assert list(ergebnis) == ["rechnungen"]
    assert ergebnis["rechnungen"] == 14, "die Dokumente dürfen nicht verloren gehen"
    assert any("Oberbegriff" in z for z in protokoll)


def test_synonyme_werden_eins():
    ergebnis, protokoll = konsolidieren({"rechnungen": 8, "rechnung": 4, "eingangsrechnungen": 3})
    assert len(ergebnis) == 1
    assert sum(ergebnis.values()) == 15
    assert len(protokoll) == 2


def test_haeufigstes_label_gewinnt_den_namen():
    """Der Name, den das Modell am häufigsten für richtig hielt, setzt sich durch."""
    ergebnis, _ = konsolidieren({"rechnung": 3, "rechnungen": 12})
    assert list(ergebnis) == ["rechnungen"]


def test_zu_kleine_kategorie_wird_einsortiert():
    ergebnis, protokoll = konsolidieren({"rechnungen": 12, "versicherung": 1})
    assert list(ergebnis) == ["rechnungen"]
    assert any("zu wenige" in z for z in protokoll)


# --------------------------------------------------------------------------- #
#  Getrennt lassen — die andere Richtung
# --------------------------------------------------------------------------- #
def test_echte_gruppen_bleiben_getrennt():
    """Rechnungen, Reisekosten und Kontoauszüge sind drei Sachen — und bleiben drei."""
    ergebnis, _ = konsolidieren({"rechnungen": 6, "spesen": 5, "kontoauszuege": 5})
    assert set(ergebnis) == {"rechnungen", "spesen", "kontoauszuege"}


def test_oberbegriff_allein_darf_bleiben():
    """Ohne Unterbegriff daneben ist 'Finanzen' die einzig sinnvolle Klammer."""
    ergebnis, _ = konsolidieren({"finanzen": 9, "protokolle": 4})
    assert set(ergebnis) == {"finanzen", "protokolle"}


def test_letzte_kategorie_bleibt_auch_wenn_klein():
    """Ein einziger kleiner Ordner ist besser als gar keiner."""
    ergebnis, _ = konsolidieren({"rechnungen": 1})
    assert ergebnis == {"rechnungen": 1}


# --------------------------------------------------------------------------- #
#  Randfälle
# --------------------------------------------------------------------------- #
def test_leere_eingabe_und_unassigned():
    assert konsolidieren({})[0] == {}
    assert konsolidieren({"_unassigned": 7})[0] == {}


def test_keine_dokumente_gehen_je_verloren():
    roh = {"rechnungen": 9, "finanzen": 4, "belege": 2, "protokolle": 5, "sitzungen": 3}
    ergebnis, _ = konsolidieren(roh)
    assert sum(ergebnis.values()) == sum(roh.values())


def test_obergrenze_wird_eingehalten():
    viele = {f"kategorie{i}": 10 for i in range(MAX_KATEGORIEN + 4)}
    ergebnis, protokoll = konsolidieren(viele)
    assert len(ergebnis) <= MAX_KATEGORIEN
    assert sum(ergebnis.values()) == sum(viele.values())
    assert protokoll


# --------------------------------------------------------------------------- #
#  Die Regeln selbst
# --------------------------------------------------------------------------- #
def test_pruefe_findet_die_klassischen_fehler():
    assert pruefe(["rechnungen", "finanzen"]), "Oberbegriff neben Unterbegriff"
    assert pruefe(["rechnung", "rechnungen"]), "Synonyme"
    assert not pruefe(["rechnungen", "protokolle", "vertraege"])


def test_systemregeln_nennen_den_konkreten_fall():
    """Kleine Modelle folgen Beispielen, nicht Prinzipien — der Fall muss drinstehen."""
    text = SYSTEM_REGELN.lower()
    assert "rechnungen" in text and "finanzen" in text
    assert "dokumenttyp" in text


def test_familie_nimmt_den_laengsten_treffer_nicht_den_ersten():
    """Aus einem echten Ollama-Lauf: 'reisekostenabrechnungen' gehört zu 'spesen'.

    Vorher gewann die Familie, die im Regelwerk zufällig weiter oben stand — 'reisen',
    nur weil 'reise' ein Präfix des Wortes ist. Die viel genauere Übereinstimmung mit
    'reisekostenabrechnung' unter 'spesen' blieb ungenutzt, und die Dokumente landeten
    beim größten Nachbarn statt bei ihresgleichen.
    """
    from pollysort.taxonomie import _familie
    assert _familie("reisekostenabrechnungen") == "spesen"

    ergebnis, _ = konsolidieren({"rechnungen": 8, "kontoauszuege": 5, "spesen": 3,
                                 "reisekostenabrechnungen": 2})
    assert ergebnis == {"rechnungen": 8, "kontoauszuege": 5, "spesen": 5}


def test_deutsche_komposita_mit_und_ohne_fugenlaut():
    """'eingangsrechnungen' ist eine Rechnung, 'reisekostenabrechnung' nicht."""
    from pollysort.taxonomie import _gleichbedeutend
    assert _gleichbedeutend("eingangsrechnungen", "rechnungen")
    assert _gleichbedeutend("jahresprotokolle", "protokolle")
    assert not _gleichbedeutend("reisekostenabrechnung", "rechnungen")

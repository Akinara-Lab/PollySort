"""Gedächtnis aus dem Struktur-Vorschlag vorwärmen.

Der Fall, um den es geht — gemessen in einem echten Ollama-Lauf: Sobald die ersten zwei
Rechnungen im Gedächtnis liegen, ist „rechnungen" für *jedes* weitere Dokument der
kNN-Gewinner. Die erste Reisekostenabrechnung bekommt dann Widerspruch statt Bestätigung,
der Assigner wertet das als Mehrdeutigkeit (CONFLICT, 0,55) und die Datei landet in der
Rückfrage — obwohl ihre Kategorie stimmt.

Wichtig zum Verständnis: Ein **leeres** Gedächtnis ist harmlos (dann greift BASE_KNOWN,
0,80). Gefährlich ist ein **einseitig gefülltes**. Genau das verhindert das Vorwärmen.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from pollysort.models import BeeAnalysis
from pollysort.vorwaermen import auswaehlen, vorwaermen


@dataclass
class FakeFinding:
    content_hash: str


class FakeMind:
    """Merkt sich, was gespeichert wurde — ohne Datenbank."""

    def __init__(self) -> None:
        self.gespeichert: list[tuple[str, str, list[float], str | None]] = []

    def remember(self, bee_id, kategorie, vec, model=None):
        self.gespeichert.append((bee_id, kategorie, vec, model))


def probe(nr: int, kategorie: str, titel: str = "") -> tuple:
    return (FakeFinding(content_hash=f"sha256:{nr:064d}"),
            BeeAnalysis(title=titel or f"Dokument {nr}", summary="Zusammenfassung",
                        keywords=["a", "b"], funktion_aufgabe="Aufgabe",
                        kategorie=kategorie))


# --------------------------------------------------------------------------- #
#  Auswahl
# --------------------------------------------------------------------------- #
def test_von_jeder_kategorie_wird_gesaet():
    """Der Kern: JEDE gewählte Kategorie braucht einen Vertreter, nicht nur die größte."""
    proben = [probe(1, "rechnungen"), probe(2, "rechnungen"), probe(3, "rechnungen"),
              probe(4, "spesen"), probe(5, "kontoauszuege")]
    gewaehlt = auswaehlen(proben, ["rechnungen", "spesen", "kontoauszuege"])
    assert {k for _, _, k in gewaehlt} == {"rechnungen", "spesen", "kontoauszuege"}


def test_hoechstens_zwei_je_kategorie():
    proben = [probe(i, "rechnungen") for i in range(6)]
    assert len(auswaehlen(proben, ["rechnungen"])) == 2
    assert len(auswaehlen(proben, ["rechnungen"], je_kategorie=1)) == 1


def test_labels_werden_auf_die_gewaehlten_kategorien_eingerastet():
    """Das Modell sagt 'eingangsrechnungen', gewählt wurde 'rechnungen'."""
    gewaehlt = auswaehlen([probe(1, "invoice")], ["rechnungen"])
    assert [k for _, _, k in gewaehlt] == ["rechnungen"]


def test_verworfener_vorschlag_saet_nichts_falsches():
    """Wer eigene Kategorien eingibt, darf kein Gedächtnis voller toter Labels bekommen."""
    proben = [probe(1, "rechnungen"), probe(2, "spesen")]
    assert auswaehlen(proben, ["kochrezepte", "urlaubsfotos"]) == []


def test_unassigned_wird_uebersprungen():
    assert auswaehlen([probe(1, "_unassigned"), probe(2, "")], ["rechnungen"]) == []


def test_ohne_kategorien_passiert_nichts():
    assert auswaehlen([probe(1, "rechnungen")], []) == []


# --------------------------------------------------------------------------- #
#  Säen
# --------------------------------------------------------------------------- #
def test_saat_liegt_unter_der_id_des_spaeteren_eintrags():
    """Sonst entstünden Dubletten: Saat und echter Eintrag müssen dieselbe ID teilen."""
    from pollysort.pipeline import bee_id
    mind = FakeMind()
    p = probe(7, "rechnungen")
    vorwaermen([p], ["rechnungen"], mind=mind, embed=lambda _t: [0.1, 0.2])
    assert mind.gespeichert[0][0] == bee_id(p[0].content_hash)


def test_gesaeter_text_ist_derselbe_wie_beim_echten_eintrag():
    """Saat und Echteintrag müssen im selben Vektorraum liegen, sonst hilft die Saat nicht."""
    from pollysort.models import BeeAnalysis, BeeEntry, embedding_text_for
    a = BeeAnalysis(title="Telekom Rechnung", summary="Monatsrechnung",
                    keywords=["telekom", "rechnung"], funktion_aufgabe="Zahlung anfordern",
                    kategorie="rechnungen")
    eintrag = BeeEntry.from_analysis(
        id="x", path="p", original_path="p", filename="f.txt", mime_type="text/plain",
        size_bytes=1, content_hash="sha256:abc", analysis=a)
    assert embedding_text_for(a) == eintrag.embedding_text()


def test_modellname_wird_mitgeschrieben():
    mind = FakeMind()
    vorwaermen([probe(1, "rechnungen")], ["rechnungen"], mind=mind,
               embed=lambda _t: [0.5], embed_model="nomic-embed-text-v2-moe")
    assert mind.gespeichert[0][3] == "nomic-embed-text-v2-moe"


def test_rueckgabe_zaehlt_je_kategorie():
    mind = FakeMind()
    gesaet = vorwaermen([probe(1, "rechnungen"), probe(2, "rechnungen"), probe(3, "spesen")],
                        ["rechnungen", "spesen"], mind=mind, embed=lambda _t: [1.0])
    assert gesaet == {"rechnungen": 2, "spesen": 1}


# --------------------------------------------------------------------------- #
#  Robustheit — Vorwärmen ist eine Verbesserung, kein Muss
# --------------------------------------------------------------------------- #
def test_fehlende_einbettung_bricht_nichts_ab():
    """Ist der Provider weg oder das Embedding-Modell nicht gezogen, geht es ohne weiter."""
    mind = FakeMind()

    def kaputt(_t):
        raise RuntimeError("Modell nicht gefunden")

    assert vorwaermen([probe(1, "rechnungen")], ["rechnungen"], mind=mind, embed=kaputt) == {}
    assert mind.gespeichert == []


def test_ein_fehler_stoppt_die_uebrigen_nicht():
    mind = FakeMind()
    aufrufe = {"n": 0}

    def mal_so_mal_so(_t):
        aufrufe["n"] += 1
        if aufrufe["n"] == 1:
            raise RuntimeError("einmal daneben")
        return [0.3]

    gesaet = vorwaermen([probe(1, "rechnungen"), probe(2, "spesen")],
                        ["rechnungen", "spesen"], mind=mind, embed=mal_so_mal_so)
    assert gesaet == {"spesen": 1}


def test_leerer_vektor_wird_nicht_gespeichert():
    mind = FakeMind()
    assert vorwaermen([probe(1, "rechnungen")], ["rechnungen"],
                      mind=mind, embed=lambda _t: []) == {}


@pytest.mark.parametrize("proben", [None, []])
def test_ohne_proben_passiert_nichts(proben):
    mind = FakeMind()
    assert vorwaermen(proben, ["rechnungen"], mind=mind, embed=lambda _t: [1.0]) == {}


# --------------------------------------------------------------------------- #
#  Offline: warum der Vorschlag über den Client laufen muss
# --------------------------------------------------------------------------- #
def test_offline_client_ohne_kategorien_nutzt_alle_regeln():
    """`None` heißt „alle Regeln", eine LEERE Liste heißt „keine Kategorie erlaubt".

    Genau daran scheiterte das Offline-Vorwärmen zuerst: Der Struktur-Vorschlag baute den
    Client mit `categories=[]`, und `classify(allowed=[])` liefert für jedes Dokument
    `_unassigned` — es gäbe also nichts zu säen.
    """
    from pollysort.llm.client import OfflineClient

    text = ("RECHNUNG Nr. R-4711\nRechnungsdatum: 2026-03-01\n"
            "Rechnungsbetrag 119,00 EUR\nZahlbar ohne Abzug bis 2026-03-15.")
    assert OfflineClient(None).analyze(text=text, file_path="dok.txt").kategorie == "rechnungen"
    assert OfflineClient([]).analyze(text=text, file_path="dok.txt").kategorie == "_unassigned"


def test_offline_analyse_liefert_die_felder_fuer_den_vektor():
    """Ohne Titel/Summary läge die Saat in einem anderen Textraum als die echten Einträge."""
    from pollysort.llm.client import OfflineClient
    from pollysort.models import embedding_text_for

    a = OfflineClient(None).analyze(text="Kontoauszug Nr. 3\nKontostand 1.200 EUR",
                                    file_path="auszug_maerz.txt")
    text = embedding_text_for(a)
    assert a.title and a.summary and a.keywords
    assert "Auszug" in text or "auszug" in text.lower()


def test_offline_embedding_stellt_aehnliche_dokumente_nebeneinander():
    """Das Offline-Embedding ist ein Hash-Bag-of-Words — aber kein Rauschen.

    Nur wenn verwandte Texte tatsächlich näher beieinanderliegen, hilft die Saat dem kNN.
    """
    from pollysort.hive_mind.memory import _cosine
    from pollysort.llm.client import OfflineClient

    c = OfflineClient(None)
    rechnung_a = c.embed("Rechnung Betrag Umsatzsteuer zahlbar Rechnungsnummer")
    rechnung_b = c.embed("Rechnung Rechnungsbetrag Umsatzsteuer zahlbar Frist")
    protokoll = c.embed("Protokoll Sitzung Teilnehmende Beschluss Tagesordnung")
    assert _cosine(rechnung_a, rechnung_b) > _cosine(rechnung_a, protokoll)

"""Das Gedächtnis aus dem Struktur-Vorschlag vorwärmen.

Warum das nötig ist — der Fall, der es ausgelöst hat:

Beim Einrichten schaut sich der Assistent die Dokumente an und leitet daraus die Kategorien
ab. Dieses Wissen wurde danach **weggeworfen**. Der anschließende Sortierlauf startete mit
leerem Gedächtnis, und das hat eine unangenehme Folge: Sobald die ersten zwei Rechnungen
gespeichert sind, ist „rechnungen" für *jedes* weitere Dokument der kNN-Gewinner. Trifft
dann die erste Reisekostenabrechnung ein, **widerspricht** das Gedächtnis ihrem Label —
und der Assigner wertet Widerspruch als Mehrdeutigkeit (``CONFLICT``, 0,55). Die Datei
landet in der Rückfrage, obwohl ihre Kategorie richtig erkannt wurde und der Nutzer sie
Sekunden vorher selbst bestätigt hat.

Ein leeres Gedächtnis ist also **nicht** das Problem (dann greift ``BASE_KNOWN``, 0,80) —
ein *einseitig gefülltes* ist es. Die Abhilfe ist entsprechend: von jeder akzeptierten
Kategorie ein paar Vertreter hinterlegen, **bevor** der erste Lauf startet. Danach findet
jedes Dokument seinesgleichen.

Zwei Eigenschaften, die dabei wichtig sind:

* Die Saat liegt unter **derselben ID**, die der echte Eintrag später bekommt (aus dem
  Inhalts-Hash). Der reale Lauf überschreibt sie also, statt Dubletten anzulegen.
* Gesät wird nur, was per ``snap_category`` auf eine **tatsächlich gewählte** Kategorie
  passt. Wer den Vorschlag verwirft und eigene Kategorien eingibt, bekommt kein Gedächtnis
  voller Labels, die es gar nicht mehr gibt.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

#: Wie viele Vertreter je Kategorie. Einer genügte meist; zwei federn den Fall ab, dass
#: ausgerechnet das erste Dokument einer Sorte ein Ausreißer ist. Mehr kostet nur
#: Einbettungs-Aufrufe, ohne die Nachbarschaft wesentlich zu verbessern.
JE_KATEGORIE = 2


def auswaehlen(proben: Iterable[tuple], kategorien: list[str], *,
               je_kategorie: int = JE_KATEGORIE) -> list[tuple]:
    """Aus den Vorschlags-Proben die Saat wählen: ``[(finding, analyse, kategorie)]``.

    Die Reihenfolge der Proben bleibt erhalten — das erste untersuchte Dokument einer
    Kategorie ist auch das erste, das gesät wird.
    """
    from .heuristics import snap_category

    bekannt = [k for k in (kategorien or []) if k and k.strip()]
    if not bekannt:
        return []

    gewaehlt: list[tuple] = []
    pro_kategorie: dict[str, int] = {}
    for finding, analyse in proben or []:
        roh = (getattr(analyse, "kategorie", "") or "").strip().lower()
        if not roh or roh == "_unassigned":
            continue
        ziel = snap_category(roh, bekannt)
        if not ziel or pro_kategorie.get(ziel, 0) >= je_kategorie:
            continue
        pro_kategorie[ziel] = pro_kategorie.get(ziel, 0) + 1
        gewaehlt.append((finding, analyse, ziel))
    return gewaehlt


def vorwaermen(proben: Iterable[tuple], kategorien: list[str], *,
               mind, embed: Callable[[str], list[float]],
               embed_model: str | None = None,
               je_kategorie: int = JE_KATEGORIE,
               text_fuer: Callable[[object, object], str] | None = None) -> dict[str, int]:
    """Saat-Vektoren ablegen. Gibt ``{kategorie: anzahl}`` der wirklich gesäten zurück.

    ``text_fuer(finding, analyse)`` bestimmt den eingebetteten Text — er muss derselbe sein,
    den der Sortierlauf später nimmt (``extractor.gedaechtnis_text``), sonst liegt die Saat in
    einem anderen Raum als die echten Einträge. Ohne Angabe: der kanonische Analysetext.

    Jedes Dokument ist für sich isoliert: Scheitert eine Einbettung (Provider weg, Modell
    fehlt), wird sie übersprungen. Vorwärmen ist eine Verbesserung, kein Muss — es darf
    die Einrichtung unter keinen Umständen abbrechen.

    Die Saat zählt als bestätigt: Der Nutzer hat die Kategorien eben selbst angenommen. Ein
    späterer unsicherer Lauf derselben Datei stuft sie nicht herab (``HiveMind.remember``).
    """
    from .hive_mind.memory import BESTAETIGT
    from .models import embedding_text_for
    from .pipeline import bee_id

    gesaet: dict[str, int] = {}
    for finding, analyse, kategorie in auswaehlen(proben, kategorien,
                                                  je_kategorie=je_kategorie):
        text = text_fuer(finding, analyse) if text_fuer else embedding_text_for(analyse)
        if not text:
            continue
        try:
            vec = embed(text)
        except Exception:
            continue
        if not vec:
            continue
        try:
            mind.remember(bee_id(finding.content_hash), kategorie, vec, embed_model,
                          herkunft=BESTAETIGT)
        except Exception:
            continue
        gesaet[kategorie] = gesaet.get(kategorie, 0) + 1
    return gesaet

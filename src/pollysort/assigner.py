"""Assigner — Kategorie + Zuständigkeit + Confidence.

Leitidee (UX-first): Ein **klares Kategorie-Label vom Extractor wird direkt vertraut** und die
Datei sofort einsortiert. Das Gedächtnis (kNN) *bestätigt* die Zuordnung (macht sie sicherer)
oder *widerspricht* ihr (dann wird der Fall mehrdeutig → Rückfrage). Nur wirklich unklare
Dokumente (kein Label, oder Gedächtnis widerspricht) landen in der Rückfrage — nicht der
ganze Stapel beim ersten Lauf.

    - Klares Label, kein/zustimmendes Gedächtnis  → hohe Confidence (wird sortiert)
    - Klares Label, Gedächtnis widerspricht        → mittlere Confidence (Rückfrage)
    - Kein Label (_unassigned)                     → Zweitmeinung der Heuristik, sonst nur
                                                     das Gedächtnis kann retten

Die **Zweitmeinung**: Rastet das Modell-Label auf keine Projekt-Kategorie ein (das Modell
antwortet etwa „gehaltsabrechnung" für eine Reisekostenabrechnung), schaut die
Offline-Heuristik auf die *Zusammenfassung, die das Modell selbst geschrieben hat*. Steht
dort ein spezifischer Fachbegriff („Reisekostenabrechnung", „Kontoauszug"), ist das kein
Raten — dieselbe Heuristik entscheidet im Offline-Modus jeden Lauf. Sie greift nur bei
einem unbrauchbaren Label, verändert also nie eine Zuordnung, die das Modell getroffen hat,
und wird als Quelle ausgewiesen.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .heuristics import classify_scored, snap_category
from .hive_mind import HiveMind, Taxonomy

K = 7
BASE_KNOWN = 0.80         # ein eindeutiges Extractor-Label ist von sich aus vertrauenswürdig
CONFLICT = 0.55           # Label vs. abweichendes Gedächtnis → mehrdeutig, lieber nachfragen
MIN_KNN_TRUST = 0.30      # ab hier darf das Gedächtnis ein fehlendes Label ersetzen
#: Ab so vielen Heuristik-Punkten darf die Zweitmeinung ein unbrauchbares Label ersetzen.
#: Ein Punkt je Zeichen eines Treffers: „kontoauszug" (11) oder „reisekosten" (11) reichen
#: allein, „rechnung" (8) braucht ein zweites Stichwort dazu, „beleg" (5) nie allein.
ZWEITMEINUNG_MIN = 10


@dataclass
class Assignment:
    kategorie: str
    confidence: float
    zustaendigkeit: list[str]
    knn_score: float
    winner_docs: int
    #: Woher die Kategorie stammt: ``label`` (Modell/Extractor), ``zweitmeinung``
    #: (Heuristik auf der Modell-Zusammenfassung), ``gedaechtnis`` (nur kNN), ``keine``.
    quelle: str = "label"


def _knn(embedding: list[float], hive: HiveMind) -> tuple[str | None, float]:
    """kNN-Gewinnerkategorie + Stärke (Stimmenanteil × mittlere Ähnlichkeit)."""
    neighbors = hive.neighbors(embedding, k=K)
    votes: dict[str, float] = defaultdict(float)
    for n in neighbors:
        if n.kategorie != "_unassigned":
            votes[n.kategorie] += max(n.score, 0.0)
    total = sum(votes.values())
    if total <= 0:
        return None, 0.0
    winner = max(votes, key=votes.get)
    share = votes[winner] / total
    sims = [max(n.score, 0.0) for n in neighbors if n.kategorie == winner]
    mean_cos = sum(sims) / len(sims) if sims else 0.0
    return winner, round(share * min(mean_cos, 1.0), 4)


def zweitmeinung(analysis_text: str, categories: list[str]) -> str | None:
    """Heuristische Zweitmeinung auf dem Analyse-Text — nur bei klarem Fachbegriff."""
    if not (analysis_text or "").strip():
        return None
    kat, punkte = classify_scored("", analysis_text, "", allowed=categories)
    if kat == "_unassigned" or punkte < ZWEITMEINUNG_MIN:
        return None
    return kat


def assign(*, embedding: list[float], llm_kategorie: str,
           hive: HiveMind, taxonomy: Taxonomy, analysis_text: str = "") -> Assignment:
    """Beste Kategorie + Confidence bestimmen.

    ``analysis_text`` ist der kanonische Eintragstext (Titel, Aufgabe, Zusammenfassung,
    Stichworte) — die Grundlage der Zweitmeinung, falls das Label nicht einrastet.
    """
    llm_kategorie = (llm_kategorie or "_unassigned").strip().lower()
    quelle = "label"
    # Das LLM-Label auf die bekannten Projekt-Kategorien einrasten, damit beim Sortieren
    # NIE ein Ordner außerhalb der vorgeschlagenen Menge entsteht (Nutzer-Wunsch). Rastet
    # nichts sicher ein, wird es zu _unassigned → landet als Rückfrage, statt einen
    # abweichenden Ordner anzulegen. (Neue Kategorien nur bewusst über 'zuordnen'/'gedaechtnis'.)
    if llm_kategorie != "_unassigned":
        llm_kategorie = snap_category(llm_kategorie, taxonomy.categories) or "_unassigned"
    if llm_kategorie == "_unassigned":
        zweite = zweitmeinung(analysis_text, taxonomy.categories)
        if zweite is not None:
            llm_kategorie, quelle = zweite, "zweitmeinung"
    knn_winner, knn_score = _knn(embedding, hive)
    llm_known = llm_kategorie != "_unassigned"

    if llm_known:
        if knn_winner is None or knn_score < MIN_KNN_TRUST:
            # Kein aussagekräftiges Gedächtnis → dem klaren Label vertrauen (sortieren).
            kategorie, confidence = llm_kategorie, BASE_KNOWN
        elif knn_winner == llm_kategorie:
            # Gedächtnis bestätigt → noch sicherer.
            kategorie, confidence = llm_kategorie, min(1.0, BASE_KNOWN + 0.20 * knn_score)
        else:
            # Label und Gedächtnis uneinig → mehrdeutig, nachfragen (Label bleibt Vorschlag).
            kategorie, confidence = llm_kategorie, CONFLICT
    else:
        # Kein Label vom Extractor → nur das Gedächtnis kann eine Kategorie liefern.
        if knn_winner is not None and knn_score >= MIN_KNN_TRUST:
            kategorie, confidence, quelle = knn_winner, knn_score, "gedaechtnis"
        else:
            kategorie, confidence, quelle = "_unassigned", knn_score, "keine"

    return Assignment(
        kategorie=kategorie,
        confidence=round(confidence, 4),
        zustaendigkeit=taxonomy.persons_for(kategorie),
        knn_score=knn_score,
        winner_docs=hive.count(knn_winner) if knn_winner else 0,
        quelle=quelle,
    )

"""Assigner — Kategorie + Zuständigkeit + Confidence.

Leitidee (UX-first): Ein **klares Kategorie-Label vom Extractor wird direkt vertraut** und die
Datei sofort einsortiert. Das Gedächtnis (kNN) *bestätigt* die Zuordnung (macht sie sicherer)
oder *widerspricht* ihr (dann wird der Fall mehrdeutig → Rückfrage). Nur wirklich unklare
Dokumente (kein Label, oder Gedächtnis widerspricht) landen in der Rückfrage — nicht der
ganze Stapel beim ersten Lauf.

    - Klares Label, kein/zustimmendes Gedächtnis  → hohe Confidence (wird sortiert)
    - Klares Label, Gedächtnis widerspricht        → mittlere Confidence (Rückfrage)
    - Kein Label (_unassigned)                     → nur das Gedächtnis kann retten
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .hive_mind import HiveMind, Taxonomy

K = 7
BASE_KNOWN = 0.80         # ein eindeutiges Extractor-Label ist von sich aus vertrauenswürdig
CONFLICT = 0.55           # Label vs. abweichendes Gedächtnis → mehrdeutig, lieber nachfragen
MIN_KNN_TRUST = 0.30      # ab hier darf das Gedächtnis ein fehlendes Label ersetzen


@dataclass
class Assignment:
    kategorie: str
    confidence: float
    zustaendigkeit: list[str]
    knn_score: float
    winner_docs: int


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


def assign(*, embedding: list[float], llm_kategorie: str,
           hive: HiveMind, taxonomy: Taxonomy) -> Assignment:
    """Beste Kategorie + Confidence bestimmen."""
    from .heuristics import snap_category
    llm_kategorie = (llm_kategorie or "_unassigned").strip().lower()
    # Das LLM-Label auf die bekannten Projekt-Kategorien einrasten, damit beim Sortieren
    # NIE ein Ordner außerhalb der vorgeschlagenen Menge entsteht (Nutzer-Wunsch). Rastet
    # nichts sicher ein, wird es zu _unassigned → landet als Rückfrage, statt einen
    # abweichenden Ordner anzulegen. (Neue Kategorien nur bewusst über 'zuordnen'/'gedaechtnis'.)
    if llm_kategorie != "_unassigned":
        llm_kategorie = snap_category(llm_kategorie, taxonomy.categories) or "_unassigned"
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
            kategorie, confidence = knn_winner, knn_score
        else:
            kategorie, confidence = "_unassigned", knn_score

    return Assignment(
        kategorie=kategorie,
        confidence=round(confidence, 4),
        zustaendigkeit=taxonomy.persons_for(kategorie),
        knn_score=knn_score,
        winner_docs=hive.count(knn_winner) if knn_winner else 0,
    )

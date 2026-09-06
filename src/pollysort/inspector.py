"""Inspector — Schwellenlogik (§9). >= 75 % → automatisch, darunter Rückfrage."""

from __future__ import annotations

from .models import Status


def decide(*, confidence: float, threshold: float, mode: str, extractor_status: Status) -> Status:
    """Endgültigen Status aus Confidence + Modus ableiten.

    - Extractor-Fehler/Metadaten-Fälle (error/needs_review) haben Vorrang (§16).
    - Index-Modus: erfolgreiche Analyse → immer ``indexed``; Kategorie & Confidence sind
      nur ein *Vorschlag* (§7), es wird nichts bewegt, also keine Rückfrage-Schranke.
    - Move-Modus: ``confidence >= threshold`` → ``assigned``, darunter → ``needs_review``
      (Ablage in ``_unassigned/``, gebündelte Rückfrage) (§9).
    """
    if extractor_status in (Status.ERROR, Status.NEEDS_REVIEW):
        return extractor_status
    if mode != "move":
        return Status.INDEXED
    return Status.ASSIGNED if confidence >= threshold else Status.NEEDS_REVIEW

"""Der Bienenschwarm (§v0.3) — Königin (Orchestrator) + spezialisierte Sub-Agenten.

- ``Koenigin``       — delegiert Aufträge an die Bienen, hält den Schwarm-Status.
- ``Spurbiene``      — Scout Agent: fliegt aus, beschnuppert & sortiert (Stufe 1).
- ``Baubiene``       — Project Agent: Wabenbau/Charter (Stufe 2).
- ``Sammelbiene``    — Memory/RAG Agent: lernt Ablage-Gewohnheiten.
- ``Waechterbiene``  — Communication Agent: überwacht Eingang & Deadlines, meldet (gemockt).
"""

from __future__ import annotations

from .baubiene import Baubiene, Charter
from .kalender import Kalender, Termin
from .koenigin import Koenigin
from .sammelbiene import Sammelbiene
from .spurbiene import Spurbiene
from .waechterbiene import Waechterbiene

__all__ = [
    "Koenigin", "Spurbiene", "Baubiene", "Charter", "Sammelbiene",
    "Waechterbiene", "Kalender", "Termin",
]

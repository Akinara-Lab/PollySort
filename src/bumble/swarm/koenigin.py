"""Die Königin (§v0.3) — Orchestrator des Schwarms.

Nimmt Aufträge entgegen und **delegiert** an die spezialisierten Bienen. Sie kapselt den
Zugriff auf Spur-, Bau-, Sammel- und Wächterbienen und liefert den Schwarm-Status. Der
eigentliche Sortier-Kern bleibt in der Pipeline; die Königin gibt ihm eine Kommandostruktur.
"""

from __future__ import annotations

from .baubiene import Baubiene
from .sammelbiene import Sammelbiene
from .spurbiene import Spurbiene
from .waechterbiene import Waechterbiene


class Koenigin:
    def __init__(self, ctx):
        self.ctx = ctx
        # Der Schwarm — jede Biene mit klarem Auftrag.
        self.spurbiene = Spurbiene(ctx)              # Stufe 1: fliegen & sortieren
        self.baubiene = Baubiene(ctx)                # Stufe 2: Wabenbau/Charter
        self.sammelbiene = Sammelbiene(ctx.hive, ctx.store)   # Gewohnheiten lernen
        self.waechterbiene = Waechterbiene(ctx)      # Eingang & Deadlines melden

    def reflektieren(self) -> list:
        """RISE + ACE: aus den Korrekturen des Projekts Wachstafel-Regeln ableiten & schreiben.

        Strikt projektgebunden — liest/schreibt nur im ``.honig/`` DIESES Bienenstocks.
        """
        from ..feedback import Feedback
        from ..wachstafel import Wachstafel
        return Wachstafel(self.ctx.hive).reflektiere(
            Feedback(self.ctx.hive), categories=self.ctx.taxonomy.categories)

    def schwarm_status(self) -> dict:
        """Überblick, woran der Schwarm gerade arbeitet (nur Metadaten)."""
        counts = self.ctx.store.status_counts()
        gewohnheiten = self.sammelbiene.beobachten()
        due = self.waechterbiene.kalender.faellig(innerhalb_tage=7)
        projekte = list((self.ctx.hive / ".honig" / "projekte").glob("*.toml")) \
            if (self.ctx.hive / ".honig" / "projekte").exists() else []
        return {
            "waben": len(self.ctx.taxonomy.categories),
            "dokumente": sum(counts.values()),
            "assigned": counts.get("assigned", 0),
            "needs_review": counts.get("needs_review", 0),
            "error": counts.get("error", 0),
            "projekte": len(projekte),
            "deadlines_faellig": len(due),
            "gewohnheiten": gewohnheiten,
        }

"""Spurbienen (Scout Agents, §v0.3) — fliegen aus, beschnuppern & sortieren.

Kapselt den bestehenden Flugzyklus (Stufe 1). Der Kern liegt weiterhin in
``pipeline.run_cycle``; diese Fassade gibt den Spurbienen einen Namen und einen klaren
Auftrag im Schwarm, an den die Königin delegiert.
"""

from __future__ import annotations

from pathlib import Path

from ..pipeline import run_cycle


class Spurbiene:
    def __init__(self, ctx):
        self.ctx = ctx

    def ausfliegen(self, *, mode: str = "move", roots: list[Path] | None = None,
                   recursive: bool | None = None, dry_run: bool = False):
        """Ein Ausflug: Posteingang (oder ``roots``) beschnuppern und einsortieren."""
        return run_cycle(self.ctx, mode=mode, roots=roots, recursive=recursive, dry_run=dry_run)

    def beschnuppern(self, roots: list[Path]):
        """Vorschau eines fremden Ordners (Dry-run, nichts wird bewegt)."""
        return run_cycle(self.ctx, mode="move", roots=roots, recursive=True, dry_run=True)

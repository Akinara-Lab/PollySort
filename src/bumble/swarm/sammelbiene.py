"""Sammelbienen (Memory/RAG Agents, §v0.3) — lernen Nutzergewohnheiten über das kNN hinaus.

Das bestehende ``HiveMind`` schlägt Kategorien per kNN vor. Die Sammelbienen ergänzen das um
**Ablage-Gewohnheiten**: Wo legt der Nutzer eine Kategorie tatsächlich ab? Aus dem realen
Bestand (Store) wird der dominante Ziel-Ordner je Kategorie abgeleitet und in
``.honig/gewohnheiten.toml`` gemerkt — Grundlage für spätere Ablage-Empfehlungen.
"""

from __future__ import annotations

import tomllib
from collections import Counter
from pathlib import Path

from ..config import _toml_val, honig


class Sammelbiene:
    def __init__(self, hive: Path, store):
        self.hive = hive
        self.store = store
        self.path = honig(hive) / "gewohnheiten.toml"

    def beobachten(self) -> dict[str, str]:
        """Dominanten Ablage-Ordner je Kategorie aus dem Bestand ableiten & merken."""
        orte: dict[str, Counter] = {}
        for row in self.store.query():
            kat = row.get("kategorie") or "_unassigned"
            if kat == "_unassigned":
                continue
            parent = Path(row["path"]).parent
            try:
                rel = parent.relative_to(self.hive).as_posix() or "."
            except ValueError:
                rel = parent.name
            orte.setdefault(kat, Counter())[rel] += 1
        gewohnheiten = {kat: c.most_common(1)[0][0] for kat, c in orte.items() if c}
        self._save(gewohnheiten)
        return gewohnheiten

    def bevorzugter_ort(self, kategorie: str) -> str | None:
        """Gelernter Ablage-Ort einer Kategorie (oder None)."""
        return self._load().get(kategorie)

    # -- Persistenz ---------------------------------------------------------
    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("rb") as fh:
                return tomllib.load(fh).get("orte", {})
        except (tomllib.TOMLDecodeError, OSError):
            return {}

    def _save(self, orte: dict[str, str]) -> None:
        lines = "\n".join(f"{_toml_val(k)} = {_toml_val(v)}" for k, v in sorted(orte.items()))
        self.path.write_text(
            "# Sammelbienen-Gedächtnis — gelernte Ablage-Gewohnheiten je Kategorie (§v0.3)\n"
            "# Abgeleitet aus dem realen Bestand; wächst mit jeder Sortierung.\n\n"
            f"[orte]\n{lines}\n",
            encoding="utf-8",
        )

"""Taxonomie-Gedächtnis (§14.2) — die lebende Kategorien-Liste + Person↔Kategorie.

``taxonomy.toml`` startet aus dem ``hive.toml``-Seed und wächst über die Zeit.
``hive.toml`` bleibt unangetastet (reiner Seed); die Wahrheit lebt hier.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from ..config import HiveSeed, _toml_val


class Taxonomy:
    def __init__(self, hive: Path):
        from ..config import honig
        self.path = honig(hive) / "taxonomie.toml"
        self.categories: list[str] = []
        self.responsibility: dict[str, list[str]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("rb") as fh:
                data = tomllib.load(fh)
        except (tomllib.TOMLDecodeError, OSError):
            return
        self.categories = data.get("categories", [])
        self.responsibility = data.get("responsibility", {})

    @classmethod
    def bootstrap(cls, hive: Path, seed: HiveSeed) -> Taxonomy:
        """Beim ersten Lauf aus dem Seed erzeugen; danach nur noch laden."""
        tax = cls(hive)
        if not tax.path.exists():
            tax.categories = list(seed.categories)
            tax.responsibility = dict(seed.responsibility)
            tax.save()
        return tax

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Kategorienamen können Leerzeichen enthalten → quotierte TOML-Schlüssel.
        resp = "\n".join(f"{_toml_val(k)} = {_toml_val(v)}"
                         for k, v in self.responsibility.items())
        self.path.write_text(
            "# Bumble Beebliothek — taxonomy.toml (LEBENDES Gedächtnis, §14.2)\n"
            "# Wächst über den hive.toml-Seed hinaus. Nicht von Hand nötig zu pflegen.\n\n"
            f"categories = {_toml_val(self.categories)}\n\n"
            f"[responsibility]\n{resp}\n",
            encoding="utf-8",
        )

    # -- Mutationen ---------------------------------------------------------
    def add_category(self, kategorie: str, persons: list[str] | None = None) -> bool:
        kategorie = kategorie.strip().lower()
        if kategorie in self.categories or kategorie == "_unassigned":
            return False
        self.categories.append(kategorie)
        if persons:
            self.responsibility[kategorie] = list(persons)
        self.save()
        return True

    def merge_category(self, src: str, dst: str) -> None:
        """src → dst zusammenlegen (Zuständigkeiten vereinen)."""
        if src in self.categories:
            self.categories.remove(src)
        merged = set(self.responsibility.pop(src, [])) | set(self.responsibility.get(dst, []))
        if merged:
            self.responsibility[dst] = sorted(merged)
        self.save()

    def rename_category(self, old: str, new: str) -> None:
        new = new.strip().lower()
        self.categories = [new if c == old else c for c in self.categories]
        if old in self.responsibility:
            self.responsibility[new] = self.responsibility.pop(old)
        self.save()

    def persons_for(self, kategorie: str) -> list[str]:
        return list(self.responsibility.get(kategorie, []))

    def set_persons(self, kategorie: str, persons: list[str]) -> None:
        self.responsibility[kategorie] = list(persons)
        if kategorie not in self.categories and kategorie != "_unassigned":
            self.categories.append(kategorie)
        self.save()

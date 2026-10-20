"""Feedback-Loop (§14.4) — corrections.jsonl.

Jede beantwortete Rückfrage (< 75 %) und jede manuelle Korrektur (``pollysort assign``)
landet hier und fließt zurück: als Few-Shot im Extraction-Prompt UND als Zentroid-Update
im Vektor-Store (Letzteres über ``HiveMind.remember`` beim erneuten Einlagern).

**Feldmessung** (seit 2026-10-20): Jede Korrektur hält zusätzlich fest, wer die Kategorie
vorher gesetzt hatte (``quelle_vorher``: ``gedaechtnis`` · ``beenara`` · ``beenara-big`` ·
``nummer`` · ``label`` · ``zweitmeinung`` · ``keine``, nach einer früheren Korrektur deren
Quelle), mit welcher Konfidenz (``konfidenz_vorher``) und in welchem Status (``status_vorher``:
``assigned`` heißt, die Datei war schon automatisch einsortiert — ein echter Fehler der Stufe;
``needs_review`` heißt, sie hatte nachgefragt). So zeigt die Beta, welche Stufe draußen wie oft
danebenliegt. Nur gemessen, nichts wird danach automatisch nachgeregelt. Ältere Zeilen haben
diese Felder nicht; alle Leser nehmen ``.get``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


def vorher(row: dict) -> dict:
    """Aus einer Katalog-Zeile, wer die Kategorie gesetzt hatte, mit welcher Konfidenz und in
    welchem Status — als Schlüsselwörter für :meth:`Feedback.record`."""
    return {"quelle_vorher": row.get("quelle"), "konfidenz_vorher": row.get("confidence"),
            "status_vorher": row.get("status")}


class Feedback:
    def __init__(self, hive: Path):
        from .config import honig
        self.path = honig(hive) / "korrekturen.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, *, bee_id: str, title: str, funktion: str,
               kategorie_alt: str, kategorie_neu: str, quelle: str,
               quelle_vorher: str | None = None, konfidenz_vorher: float | None = None,
               status_vorher: str | None = None) -> None:
        rec = {
            "ts": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "bee_id": bee_id,
            "title": title,
            "funktion": funktion,
            "kategorie_alt": kategorie_alt,
            "kategorie_neu": kategorie_neu,
            "quelle": quelle,          # "review" | "assign" | "analysiere" | "manuell"
            "quelle_vorher": quelle_vorher,
            "konfidenz_vorher": konfidenz_vorher,
            "status_vorher": status_vorher,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def all(self) -> list[dict]:
        """Alle Korrekturen (für die Reflexion der Wachstafel, §Meta-Learning)."""
        if not self.path.exists():
            return []
        out: list[dict] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def few_shots(self, limit: int = 3) -> list[dict]:
        """Bis zu N jüngste Korrekturen als Few-Shot-Beispiele (§15)."""
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        out = []
        for line in reversed(lines):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(out) >= limit:
                break
        return out

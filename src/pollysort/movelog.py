"""Move-Log — Sicherheitsnetz für ``pollysort undo`` ('Rückflug', §19).

Jede vom System durchgeführte Verschiebung wird angehängt; ``undo`` macht die jüngste
rückgängig. Rein additiv; Nutzerdateien werden nie gelöscht.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


class MoveLog:
    def __init__(self, hive: Path):
        from .config import honig
        self.path = honig(hive) / ".moves.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, *, bee_id: str, src: str, dst: str, action: str = "move") -> None:
        rec = {
            "ts": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "bee_id": bee_id, "src": src, "dst": dst, "action": action,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def last_for(self, bee_id: str, *, action: str | None = None) -> dict | None:
        """Jüngsten Log-Eintrag zu einer ID finden (ohne ihn zu entfernen)."""
        if not self.path.exists():
            return None
        for line in reversed(self.path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("bee_id") == bee_id and (action is None or rec.get("action") == action):
                return rec
        return None

    def pop_last(self) -> dict | None:
        if not self.path.exists():
            return None
        lines = self.path.read_text(encoding="utf-8").splitlines()
        if not lines:
            return None
        last = json.loads(lines[-1])
        self.path.write_text("\n".join(lines[:-1]) + ("\n" if lines[:-1] else ""),
                             encoding="utf-8")
        return last

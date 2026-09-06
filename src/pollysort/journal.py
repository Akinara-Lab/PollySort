"""Royal Journal (queen_log.md, menschlich) + beehive.log (JSON-Lines, maschinell) (§3, §17).

Wichtig (§17): In keiner Stufe landen Dokumentinhalte im Log — nur Metadaten.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

# 🔒 Wachssiegel: Felder mit diesen Schlüssel-Bestandteilen werden im Log maskiert —
# selbst wenn versehentlich ein Secret durchgereicht würde, landet es nie im Klartext.
_SECRET_HINTS = ("token", "password", "passwort", "secret", "key", "auth", "credential")


def _redact(fields: dict) -> dict:
    """Sensible Felder (Token/Passwort/…) zu '***' maskieren, bevor sie ins Log gehen."""
    out = {}
    for k, v in fields.items():
        if any(h in str(k).lower() for h in _SECRET_HINTS):
            out[k] = "***"
        else:
            out[k] = v
    return out


class Journal:
    def __init__(self, hive: Path):
        from .config import honig
        honig(hive).mkdir(parents=True, exist_ok=True)
        self.md = honig(hive) / "journal.md"
        self.log = honig(hive) / "log.jsonl"

    def _ts(self) -> str:
        return datetime.now(UTC).replace(microsecond=0).isoformat()

    def entry(self, title: str, lines: list[str]) -> None:
        """Datierter Abschnitt im Royal Journal."""
        block = [f"\n## {self._ts()} — {title}", ""] + [f"- {ln}" for ln in lines] + [""]
        with self.md.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(block))

    def event(self, kind: str, **fields) -> None:
        """Strukturierte JSON-Zeile (nur Metadaten; sensible Felder werden maskiert)."""
        rec = {"ts": self._ts(), "event": kind, **_redact(fields)}
        with self.log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def init_header(self, hive: Path) -> None:
        if not self.md.exists():
            self.md.write_text(
                f"# 🐝 Royal Journal — {hive}\n\n"
                f"Master-Journal für Fortschritt, Entscheidungen und Sweep-Berichte.\n\n"
                f"> ⚠️ Datenschutz (Stufe 1): Dokumentinhalte werden zur Analyse an "
                f"OpenRouter/Google übertragen (§17).\n",
                encoding="utf-8",
            )

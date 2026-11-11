"""Bienen-Kalender — Deadlines & Benachrichtigungs-Trigger der Wächterbienen (§v0.3).

Termine liegen als JSON-Lines in ``.honig/kalender.jsonl``. Es gibt hier **keinen** externen
API-Call: verschickt wird ausschließlich über die Flugrouten (``waechterbiene.py``,
``kanaele.py``), und nur, wenn der Nutzer welche eingerichtet hat. ``gemeldet`` heißt
„wirklich verschickt". So verlässt kein Termin unbemerkt den Bienenstock.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path


@dataclass
class Termin:
    """Ein Kalender-Eintrag (Deadline) einer Wabe/eines Projekts."""

    id: str
    titel: str
    faellig: str                 # ISO-Datum YYYY-MM-DD
    projekt: str = ""
    notiz: str = ""
    erledigt: bool = False
    gemeldet: bool = False

    def tage_bis(self, *, heute: date | None = None) -> int:
        heute = heute or datetime.now(UTC).date()
        try:
            return (date.fromisoformat(self.faellig) - heute).days
        except ValueError:
            return 9999


class Kalender:
    """Schlanker, dateibasierter Terminspeicher — bewusst ohne externe Abhängigkeit."""

    def __init__(self, hive: Path):
        from ..config import honig
        self.path = honig(hive) / "kalender.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _all(self) -> list[Termin]:
        if not self.path.exists():
            return []
        out: list[Termin] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(Termin(**json.loads(line)))
                except (json.JSONDecodeError, TypeError):
                    continue
        return out

    def _write(self, termine: list[Termin]) -> None:
        body = "\n".join(json.dumps(asdict(t), ensure_ascii=False) for t in termine)
        self.path.write_text(body + ("\n" if termine else ""), encoding="utf-8")

    def eintragen(self, titel: str, faellig: str, *, projekt: str = "", notiz: str = "") -> Termin:
        """Deadline anlegen/aktualisieren (idempotent über projekt+titel+faellig)."""
        tid = hashlib.sha1(f"{projekt}|{titel}|{faellig}".encode()).hexdigest()[:8]
        termine = self._all()
        for t in termine:
            if t.id == tid:
                t.titel, t.faellig, t.notiz = titel, faellig, notiz
                self._write(termine)
                return t
        t = Termin(id=tid, titel=titel, faellig=faellig, projekt=projekt, notiz=notiz)
        termine.append(t)
        self._write(termine)
        return t

    def offen(self) -> list[Termin]:
        return sorted((t for t in self._all() if not t.erledigt), key=lambda t: t.faellig)

    def faellig(self, *, innerhalb_tage: int = 7) -> list[Termin]:
        """Offene Termine, die in <= N Tagen fällig (oder überfällig) sind."""
        return [t for t in self.offen() if t.tage_bis() <= innerhalb_tage]

    def markiere_gemeldet(self, tid: str) -> None:
        termine = self._all()
        for t in termine:
            if t.id == tid:
                t.gemeldet = True
        self._write(termine)

    # -- Zustellung je Flugroute ---------------------------------------------
    # Wer eine Deadline schon bekommen hat, steht in einer eigenen kleinen Datei neben dem
    # Kalender — nicht im Termin selbst: Ältere PollySort-Versionen verwerfen Termine mit
    # Feldern, die sie nicht kennen.
    @property
    def _zustellung_pfad(self) -> Path:
        return self.path.with_name("kalender.zustellung.json")

    def _zustellungen(self) -> dict:
        try:
            daten = json.loads(self._zustellung_pfad.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return daten if isinstance(daten, dict) else {}

    def zustellung(self, tid: str) -> tuple[set[str], set[str]]:
        """``(angekommen, abgelehnt)`` — die Kennungen der Flugrouten für diesen Termin."""
        stand = self._zustellungen().get(tid) or {}
        return set(stand.get("an") or []), set(stand.get("abgelehnt") or [])

    def zustellung_merken(self, tid: str, an: set[str], abgelehnt: set[str]) -> None:
        alle = self._zustellungen()
        alle[tid] = {"an": sorted(an), "abgelehnt": sorted(abgelehnt)}
        offen = {t.id for t in self._all() if not t.erledigt}
        alle = {k: v for k, v in alle.items() if k in offen}      # Erledigtes räumt sich weg
        self._zustellung_pfad.write_text(json.dumps(alle, ensure_ascii=False, indent=1) + "\n",
                                         encoding="utf-8")

    def gemeldet_abgleichen(self, belegt: set[str]) -> int:
        """``gemeldet`` zurücknehmen, wo kein Versand belegt ist. Gibt die Anzahl zurück."""
        termine = self._all()
        zurueck = [t for t in termine if t.gemeldet and t.id not in belegt]
        for t in zurueck:
            t.gemeldet = False
        if zurueck:
            self._write(termine)
        return len(zurueck)

    def erledigen(self, tid: str) -> bool:
        termine = self._all()
        hit = False
        for t in termine:
            if t.id == tid:
                t.erledigt = hit = True
        self._write(termine)
        return hit

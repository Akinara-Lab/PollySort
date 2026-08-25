"""Undertaker Bee — Löschung, bewusst SEPARAT vom Auto-Flow (§13).

- ``undertake`` verschiebt nach ``friedhof/`` (Quarantäne), löscht nichts.
- ``bury`` löscht ``friedhof/`` endgültig — getrennter, bestätigungspflichtiger Schritt.
- ``resurrect`` holt eine Datei zurück in den Stock.
Im Normalbetrieb kann so nie versehentlich etwas vernichtet werden.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .models import Status
from .mover import collision_safe_name
from .store import Store


def _papierkorb(hive: Path) -> Path:
    from .config import honig
    d = honig(hive) / "papierkorb"
    d.mkdir(parents=True, exist_ok=True)
    return d


def undertake(hive: Path, store: Store, ident: str) -> Path | None:
    """Eintrag als Löschkandidat markieren und in die Quarantäne (.honig/papierkorb) legen."""
    from .movelog import MoveLog
    row = _resolve(store, ident)
    if not row:
        return None
    src = Path(row["path"])
    friedhof = _papierkorb(hive)
    dest = collision_safe_name(friedhof, src.name, row["id"])
    if src.exists():
        shutil.move(str(src), str(dest))
    # Herkunft merken, damit 'zurueckholen' die Datei in ihre Wabe zurücklegt (BUG-10).
    MoveLog(hive).record(bee_id=row["id"], src=str(src), dst=str(dest), action="papierkorb")
    store.update_path(row["id"], str(dest))
    store.set_status(row["id"], Status.QUARANTINED)
    return dest


def resurrect(hive: Path, store: Store, ident: str) -> Path | None:
    """Datei aus der Quarantäne zurücklegen — bevorzugt an ihren vorherigen Platz (Wabe).

    Nur wenn die Herkunft unbekannt ist (Alt-Bestand ohne Log), landet die Datei im Root
    und wird wieder zur offenen Frage (needs_review).
    """
    from .movelog import MoveLog
    row = _resolve(store, ident)
    if not row or row["status"] != Status.QUARANTINED.value:
        return None
    src = Path(row["path"])

    rec = MoveLog(hive).last_for(row["id"], action="papierkorb")
    origin = Path(rec["src"]) if rec else None
    if (origin is not None and origin.parent.exists()
            and origin.parent.resolve() != Path(hive).resolve()):
        # Zurück in die Wabe, aus der sie kam — sie war dort schon zugeordnet.
        dest = collision_safe_name(origin.parent, src.name, row["id"])
        status = Status.ASSIGNED
    else:
        dest = collision_safe_name(hive, src.name, row["id"])   # Root → wieder offene Frage
        status = Status.NEEDS_REVIEW
    if src.exists():
        shutil.move(str(src), str(dest))
    store.update_path(row["id"], str(dest))
    store.set_status(row["id"], status)
    return dest


def bury(hive: Path, store: Store | None) -> list[str]:
    """Quarantäne ENDGÜLTIG leeren. Nur nach expliziter Bestätigung aufrufen (§13)."""
    friedhof = _papierkorb(hive)
    removed: list[str] = []
    buried_paths: set[str] = set()
    for p in sorted(friedhof.iterdir()):
        if p.is_file():
            removed.append(p.name)
            buried_paths.add(str(p))
            p.unlink()   # der EINZIGE erlaubte Löschpfad auf Nutzerdateien (§13)
    # Verwaiste Katalog-Einträge (Status quarantined, Datei jetzt weg) mit aufräumen.
    if store is not None:
        for row in store.query(status=Status.QUARANTINED.value):
            if row["path"] in buried_paths:
                store.delete(row["id"])
    return removed


def buried_candidates(hive: Path) -> list[Path]:
    friedhof = _papierkorb(hive)
    return sorted(p for p in friedhof.iterdir() if p.is_file())


def _resolve(store: Store, ident: str) -> dict | None:
    row = store.by_id(ident)
    if row:
        return row
    hits = store.query(keyword=None)
    for r in hits:
        if r["filename"] == ident or r["path"] == ident:
            return r
    return None

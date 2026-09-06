"""Kollisionssicheres Verschieben (§6). Move-only: nie löschen, nie überschreiben.

Es gibt in diesem Modul KEINEN Aufruf von ``os.remove``/``unlink`` auf Nutzerdateien.
Existiert am Ziel schon eine Datei gleichen Namens, wird ein ID-basiertes Suffix angehängt
(``rechnung.pdf`` → ``rechnung__a1b2c3d4.pdf``).
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from .models import BeeEntry

# Ein Datum aus Dateiname/Titel/Zusammenfassung ziehen (für {jahr}/{monat}-Unterordner).
_DATE_RES = [
    (re.compile(r"(?P<y>\d{4})[-./](?P<m>\d{2})[-./](?P<d>\d{2})"), None),   # 2026-07-14
    (re.compile(r"(?P<d>\d{2})[-./](?P<m>\d{2})[-./](?P<y>\d{4})"), None),   # 14.07.2026
]


def _entry_date(entry: BeeEntry) -> datetime:
    """Bestes verfügbares Datum: aus dem Dokument, sonst Katalog-Zeitpunkt, sonst heute."""
    blob = f"{entry.filename} {entry.content.title} {entry.content.summary}"
    for rx, _ in _DATE_RES:
        m = rx.search(blob)
        if m:
            try:
                return datetime(int(m.group("y")), int(m.group("m")), int(m.group("d")))
            except ValueError:
                continue
    try:
        return datetime.fromisoformat((entry.scanned_at or "").replace("Z", ""))
    except (ValueError, AttributeError):
        return datetime.now()


def resolve_subpath(pattern: str, entry: BeeEntry) -> str:
    """Ein Muster wie ``{jahr}/{monat}`` in einen sicheren relativen Unterpfad auflösen."""
    d = _entry_date(entry)
    repl = {
        "jahr": f"{d.year:04d}", "year": f"{d.year:04d}",
        "monat": f"{d.month:02d}", "month": f"{d.month:02d}",
        "tag": f"{d.day:02d}", "day": f"{d.day:02d}",
    }
    out = pattern
    for key, val in repl.items():
        out = out.replace("{" + key + "}", val)
    # Sicherheit: nur relative Segmente, kein '..', keine absoluten Pfade.
    segs = [s for s in re.split(r"[\\/]+", out) if s and s not in (".", "..")]
    return "/".join(segs)


def target_dir(hive: Path, entry: BeeEntry, subrouting: dict[str, str] | None = None) -> Path:
    """Zielordner: sichtbarer Kategorie-Ordner, optional mit dynamischem Unterpfad."""
    from .config import pretty_category
    base = hive / pretty_category(entry.funktion.kategorie)
    pattern = (subrouting or {}).get(entry.funktion.kategorie.strip().lower())
    if pattern:
        sub = resolve_subpath(pattern, entry)
        if sub:
            return base / sub
    return base


def collision_safe_name(dest_dir: Path, filename: str, bee_id: str) -> Path:
    """Zielpfad ohne Überschreiben (Suffix bei Namenskollision)."""
    dest = dest_dir / filename
    if not dest.exists():
        return dest
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    return dest_dir / f"{stem}__{bee_id}{suffix}"


def plan_move(hive: Path, entry: BeeEntry, subrouting: dict[str, str] | None = None) -> Path:
    """Wohin würde verschoben (für --dry-run)."""
    return collision_safe_name(target_dir(hive, entry, subrouting), entry.filename, entry.id)


def move(hive: Path, entry: BeeEntry, *, dry_run: bool = False,
         subrouting: dict[str, str] | None = None) -> Path:
    """Datei einsortieren. Reihenfolge des Aufrufers: Eintrag persistieren → move → Pfad-Update.

    Bricht der Prozess zwischen persist und move ab, findet der nächste Lauf die Datei
    über den Hash wieder und repariert nur den Pfad (§9/§16) — nichts geht verloren.
    """
    src = Path(entry.path)
    dest_dir = target_dir(hive, entry, subrouting)
    dest = collision_safe_name(dest_dir, entry.filename, entry.id)
    if dry_run:
        return dest
    if src.resolve() == dest.resolve():
        return dest
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))     # move, kein copy+delete auf Nutzerinhalt
    return dest

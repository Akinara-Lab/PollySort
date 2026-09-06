"""The Guards — Flugloch-Validierung (§9, §16).

Typ-Erkennung (MIME), Größenlimit, Lande-Check (Stabilität), Ausschlussmuster (.beeignore).
"""

from __future__ import annotations

import fnmatch
import time
from pathlib import Path

# MIME inhaltsbasiert, mit Fallback auf Endungs-Raterei (§3)
try:  # python-magic braucht libmagic; auf Windows via python-magic-bin
    import magic as _magic  # type: ignore

    _HAVE_MAGIC = True
except Exception:  # pragma: no cover - hängt von der Plattform ab
    import mimetypes as _mimetypes

    _HAVE_MAGIC = False


def detect_mime(path: Path) -> str | None:
    if _HAVE_MAGIC:
        try:
            return _magic.from_file(str(path), mime=True)
        except Exception:
            pass
    else:
        guess, _ = _mimetypes.guess_type(str(path))
        if guess:
            return guess
    # letzter Fallback
    import mimetypes
    guess, _ = mimetypes.guess_type(str(path))
    return guess


def has_landed(path: Path, *, settle_seconds: float = 5.0, quick: bool = False) -> bool:
    """Datei gilt erst als angekommen, wenn ihre Größe stabil ist (§9).

    ``quick=True`` (für Sweep/Erst-Scan über Bestand) prüft nur Existenz & Lesbarkeit,
    ohne die 5-Sekunden-Wartezeit — dort sind Dateien bereits 'gelandet'.
    """
    if not path.is_file():
        return False
    if quick:
        return _readable(path)
    try:
        first = path.stat().st_size
        time.sleep(min(settle_seconds, 5.0))
        return first == path.stat().st_size and _readable(path)
    except OSError:
        return False


def _readable(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            fh.read(1)
        return True
    except OSError:
        return False


def within_size_limit(path: Path, max_file_mb: int) -> bool:
    try:
        return path.stat().st_size <= max_file_mb * 1024 * 1024
    except OSError:
        return False


class IgnoreMatcher:
    """Vereint ``.beeignore`` (§6) und die ``exclude``-Liste der Config (§17)."""

    def __init__(self, hive: Path, extra: list[str] | None = None):
        self.hive = hive
        patterns: list[str] = list(extra or [])
        beeignore = hive / ".beeignore"
        if beeignore.exists():
            for line in beeignore.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
        # Der versteckte Metadaten-Ordner, übliche Stördateien und die von den Baubienen
        # erzeugten Projekt-Charter (Bienenstock.md) werden nie eingelesen/sortiert.
        patterns += [".honig/*", "*.tmp", ".DS_Store", "Thumbs.db", "desktop.ini",
                     "Bienenstock.md"]
        self.patterns = patterns

    def ignored(self, path: Path) -> bool:
        try:
            rel = path.relative_to(self.hive).as_posix()
        except ValueError:
            rel = path.name
        # Versteckte Dateien/Ordner (mit '.' beginnend) generell überspringen.
        if any(part.startswith(".") for part in Path(rel).parts):
            return True
        for pat in self.patterns:
            p = pat.rstrip("/")
            if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, f"{p}/*"):
                return True
            if fnmatch.fnmatch(path.name, p):
                return True
        return False

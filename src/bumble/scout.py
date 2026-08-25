"""Scout Bees — Scanner + SHA-256-Dedupe (§6, §9)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .guards import IgnoreMatcher, detect_mime


@dataclass
class Finding:
    """Ein vom Scout entdecktes Datei-Vorkommen."""

    path: Path
    content_hash: str
    size_bytes: int
    mime_type: str | None


def sha256(path: Path, *, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while data := fh.read(chunk):
            h.update(data)
    return "sha256:" + h.hexdigest()


def walk(roots: list[Path], matcher: IgnoreMatcher, *, recursive: bool = False) -> list[Path]:
    """Nicht-ignorierte Dateien unter den Wurzeln sammeln.

    Standard (``recursive=False``): nur die **losen Dateien** direkt in der Wurzel — der
    natürliche 'Posteingang'. Bereits einsortierte Kategorie-Ordner und Unterordner bleiben
    unangetastet. Mit ``recursive=True`` wird ein ganzer Ordnerbaum eingelesen (Import).
    """
    out: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        items = sorted(root.rglob("*")) if recursive else sorted(root.iterdir())
        for p in items:
            if p.is_file() and not matcher.ignored(p):
                out.append(p)
    return out


def scout(paths: list[Path]) -> list[Finding]:
    """Hasht Kandidaten und liefert Findings (deduped werden sie erst gegen die DB, §9)."""
    findings: list[Finding] = []
    for p in paths:
        try:
            findings.append(
                Finding(
                    path=p,
                    content_hash=sha256(p),
                    size_bytes=p.stat().st_size,
                    mime_type=detect_mime(p),
                )
            )
        except OSError:
            continue  # unlesbar -> vom Guard/Extractor als needs_review behandelt
    return findings

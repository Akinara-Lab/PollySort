"""Die Pollen-Uhr (§v0.3) — iCalendar-Export (.ics) der Baubienen.

Übersetzt die Projekt-Deadlines (Termine des Bienen-Kalenders) in eine echte ``.ics``-Datei
nach RFC 5545 — abonnierbar in Apple/Outlook/Google. Bewusst abhängigkeitsfrei per
String-Formatting; die Datei wird bei jedem Wabenbau neu geschrieben (Spiegel des Ist-Stands).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

PRODID = "-//PollySort//Pollen-Uhr//DE"


def _escape(text: str) -> str:
    """RFC-5545-Textescaping für SUMMARY/DESCRIPTION."""
    return (str(text or "")
            .replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def _date_compact(iso_date: str) -> str | None:
    """'2026-07-20' → '20260720' (Ganztags-Termin). Ungültig → None."""
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%Y%m%d")
    except (ValueError, TypeError):
        return None


def build_ics(termine, *, name: str = "PollySort — Pollen-Kalender") -> str:
    """Eine Liste ``Termin`` als iCalendar-String (RFC 5545) rendern."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(name)}",
    ]
    for t in termine:
        tag = _date_compact(getattr(t, "faellig", ""))
        if not tag:
            continue
        titel = getattr(t, "titel", "Deadline")
        projekt = getattr(t, "projekt", "")
        tid = getattr(t, "id", tag)
        # Präfix nur ergänzen, wenn der Titel ihn nicht ohnehin schon trägt (kein Doppel).
        summary = titel if titel.lower().startswith("deadline") else f"Deadline: {titel}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{tid}@pollysort",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{tag}",
            f"SUMMARY:{_escape(summary)}",
            f"DESCRIPTION:{_escape('Bumble-Wabenbau' + (f' · Projekt {projekt}' if projekt else ''))}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"      # RFC 5545: CRLF-Zeilenenden


def write_ics(path: Path, termine) -> Path:
    """Die Pollen-Uhr (``kalender.ics``) mit dem aktuellen Terminstand überschreiben."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_ics(termine), encoding="utf-8", newline="")
    return path

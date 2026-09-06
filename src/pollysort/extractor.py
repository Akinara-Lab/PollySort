"""Extractor — Roh-Extrakt + multimodaler LLM-Call → BeeAnalysis (§9, §16).

Isoliert pro Larve: ein kaputtes Dokument oder LLM-Schluckauf bricht nie den Zyklus ab.
Rückgabe: (analysis, status, error_reason). Der Aufrufer baut daraus den BeeEntry.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import ValidationError

from .llm import LLMError, LLMRequestError
from .models import BeeAnalysis, Status
from .scout import Finding

# markitdown ist optional (Textformate → Markdown). Fehlt es, lesen wir Text roh.
try:
    from markitdown import MarkItDown  # type: ignore

    _MD = MarkItDown()
except Exception:  # pragma: no cover
    _MD = None

TEXT_MIME_PREFIXES = ("text/",)
TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json", ".log", ".html", ".htm", ".xml",
                 ".yaml", ".yml", ".docx"}
IMAGE_PREFIXES = ("image/",)
PDF_MIME = "application/pdf"


# Marker für eingebettete Font-/Lizenzblöcke (OPT-5): DOCX mit eingebetteten Schriften
# liefern sonst den Lizenztext als vermeintlichen Inhalt („Fira Mono Font Lizenz") —
# der verfälscht Titel, Kategorie und später die Wachstafel-Regeln.
_FONT_NOISE = re.compile(
    r"(?i)(SIL Open Font License|Reserved Font Name|Font Software|font license"
    r"|schriftlizenz|dieser Font|diese Schriftart|typeface|glyph)"
)


def _strip_font_blocks(text: str) -> str:
    """Absätze, die nach eingebettetem Font-Lizenztext aussehen, vor der Analyse entfernen.

    Konservativ: Es fliegen nur Absätze mit eindeutigen Lizenz-Markern raus; bleibt danach
    nichts übrig, wird der Originaltext unverändert zurückgegeben (lieber Müll analysieren
    als gar nichts)."""
    paragraphs = re.split(r"\n{2,}", text)
    kept = [p for p in paragraphs if not _FONT_NOISE.search(p)]
    if not kept or not "".join(kept).strip():
        return text
    return "\n\n".join(kept)


def _extract_text(path: Path) -> str | None:
    """Textformate → String (markitdown für DOCX/CSV/HTML, sonst roh)."""
    text: str | None = None
    if _MD is not None:
        try:
            text = _MD.convert(str(path)).text_content
        except Exception:
            text = None
    if text is None:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
    if path.suffix.lower() == ".docx":
        text = _strip_font_blocks(text)
    return text


def _is_textual(finding: Finding) -> bool:
    if finding.mime_type and finding.mime_type.startswith(TEXT_MIME_PREFIXES):
        return True
    return finding.path.suffix.lower() in TEXT_SUFFIXES


def _metadata_only(finding: Finding, reason: str) -> tuple[BeeAnalysis, Status, str]:
    """Fallback-Eintrag nur aus Datei-Metadaten (§16)."""
    analysis = BeeAnalysis(
        title=finding.path.stem.replace("_", " ").title(),
        summary=f"Nicht inhaltlich analysiert: {reason}",
        keywords=[],
        funktion_aufgabe="unbekannt (Metadaten-Eintrag)",
        kategorie="_unassigned",
    )
    return analysis, Status.NEEDS_REVIEW, reason


def extract(finding: Finding, client, *, max_file_mb: int) -> tuple[BeeAnalysis, Status, str | None]:
    # Größenlimit → kein LLM-Call (§16)
    if finding.size_bytes > max_file_mb * 1024 * 1024:
        return _metadata_only(finding, f"Datei > {max_file_mb} MB")

    text: str | None = None
    file_path: str | None = None
    if _is_textual(finding):
        text = _extract_text(finding.path)
        if text is None:
            return _metadata_only(finding, "Text nicht lesbar / korrupt")
        if not text.strip():
            return _metadata_only(finding, "Datei leer")
        # Dateiname mitgeben: OpenRouter nutzt weiter den Text, Offline nutzt den Namen.
        file_path = str(finding.path)
    else:
        # PDF/Bild/Binär direkt ans multimodale Modell (§15)
        file_path = str(finding.path)

    # LLM mit bis zu 2 Repair-Retries bei ungültigem JSON/Schema (§16)
    last_err: Exception | None = None
    for _attempt in range(3):
        try:
            analysis = client.analyze(text=text, file_path=file_path)
            return analysis, Status.INDEXED, None
        except (ValidationError, json.JSONDecodeError) as exc:
            # ungültiges/abgeschnittenes/kein passendes JSON → Repair-Retry (OPT-8)
            last_err = exc
            continue
        except LLMRequestError as exc:
            # Anfrage/Datei dauerhaft abgelehnt (z. B. Format nicht unterstützt) —
            # ein Auto-Retry würde identisch scheitern → Rückfrage statt error-Schleife.
            return _metadata_only(finding, f"Analyse abgelehnt: {exc}")
        except LLMError as exc:  # Netz/Provider — Backoff steckt im Client
            last_err = exc
            break
        except Exception as exc:  # unbekannter/exotischer MIME-Typ o. Ä.
            last_err = exc
            if file_path:  # Binär-Anhang gescheitert → Metadaten-Eintrag
                return _metadata_only(finding, f"Analyse fehlgeschlagen: {exc}")
            break

    # Parse-Probleme (Modell lieferte kein brauchbares JSON) → Metadaten-Eintrag mit
    # Rückfrage: die Datei bleibt sichtbar und manuell zuordenbar. Netz-/Provider-Fehler
    # bleiben ERROR — die werden beim nächsten Lauf automatisch erneut versucht (BUG-5).
    if isinstance(last_err, (ValidationError, json.JSONDecodeError)):
        return _metadata_only(finding, f"Analyse fehlgeschlagen: {last_err}")
    return (
        BeeAnalysis(title=finding.path.stem, kategorie="_unassigned"),
        Status.ERROR,
        f"LLM-Extraktion fehlgeschlagen: {last_err}",
    )

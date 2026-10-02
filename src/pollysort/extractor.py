"""Extractor — Roh-Extrakt + multimodaler LLM-Call → BeeAnalysis (§9, §16).

Isoliert pro Larve: ein kaputtes Dokument oder LLM-Schluckauf bricht nie den Zyklus ab.
Rückgabe: (analysis, status, error_reason). Der Aufrufer baut daraus den BeeEntry.
"""

from __future__ import annotations

import json
import re
import threading
from contextlib import contextmanager
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


_lokal = threading.local()


@contextmanager
def einmal_lesen():
    """Innerhalb dieses Blocks wird jede Datei höchstens einmal gelesen (je Thread).

    Im Sparmodus liest erst die Heuristik eine Datei und gleich danach BeeNara dieselbe noch
    einmal; ohne diesen Block arbeitet markitdown zweimal. Bewusst nur für die Dauer einer
    Analyse und nicht über Änderungszeiten: Die löst Windows nur auf Millisekunden auf, eine
    kurz darauf gleich groß überschriebene Datei sähe sonst alt aus.
    """
    aussen = getattr(_lokal, "texte", None)
    if aussen is None:
        _lokal.texte = {}
    try:
        yield
    finally:
        if aussen is None:
            _lokal.texte = None


def _extract_text(path: Path) -> str | None:
    """Textformate → String (markitdown für DOCX/CSV/HTML, sonst roh)."""
    texte = getattr(_lokal, "texte", None)
    if texte is None:
        return _extract_text_neu(path)
    schluessel = str(path)
    if schluessel not in texte:
        texte[schluessel] = _extract_text_neu(path)
    return texte[schluessel]


def _extract_text_neu(path: Path) -> str | None:
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


#: So viel Text lesen Gedächtnis und Nummer-Entscheidung (Plan §8.3): den Kopf des
#: Dokuments. Der Dokumenttyp steht fast immer oben — so wurde es auch gemessen (§8.13).
AUSZUG_ZEICHEN = 1500


def volltext(path: Path, mime_type: str | None = None) -> str | None:
    """Der lokal lesbare Text eines Dokuments — ohne KI. ``None`` für Bilder & Unlesbares.

    Textformate über markitdown bzw. roh, PDFs über markitdown/pypdf (derselbe Weg, den die
    lokale KI ohnehin braucht, weil Ollama keine Datei-Anhänge kennt).
    """
    suffix = path.suffix.lower()
    if (mime_type or "").startswith(TEXT_MIME_PREFIXES) or suffix in TEXT_SUFFIXES:
        text = _extract_text(path)
    elif suffix == ".pdf" or mime_type == PDF_MIME:
        from .llm.client import _local_file_text
        text = _local_file_text(path)
    else:
        return None
    return text if text and text.strip() else None


def auszug(path: Path, mime_type: str | None = None, limit: int = AUSZUG_ZEICHEN) -> str | None:
    """Der Kopf des Dokuments für Gedächtnis und Entscheidung."""
    text = volltext(path, mime_type)
    return text.strip()[:limit] if text else None


def gedaechtnis_text(client, path, fallback: str) -> str:
    """Aus welchem Text das Gedächtnis den Vektor eines Eintrags bildet.

    Das hängt an der Textbasis des Clients: Der Ollama-Modus bettet seit 2026-09-24 den
    Dokument-**Auszug** ein — nur so kann das Gedächtnis entscheiden, bevor die KI etwas
    geschrieben hat. Alle anderen (und Dateien ohne lokalen Text, etwa Bilder) nutzen weiter
    den kanonischen Eintragstext aus Titel, Aufgabe, Zusammenfassung und Stichworten.
    Saat, Einträge, Korrekturen und Neuaufbau gehen alle hier durch — sonst lägen ihre
    Vektoren in verschiedenen Räumen und fänden einander nicht.
    """
    if getattr(client, "memory_basis", None) == "auszug" and path:
        try:
            text = auszug(Path(path))
        except Exception:
            text = None
        if text:
            return text
    return fallback


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

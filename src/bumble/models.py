"""Datenmodelle (§7, §8) — ein pydantic-Schema für JSON-Export, DB-Mapping & LLM-Validierung."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class Status(str, Enum):
    """Lebenszyklus eines Eintrags (§8)."""

    PENDING = "pending"
    INDEXED = "indexed"
    ASSIGNED = "assigned"
    NEEDS_REVIEW = "needs_review"
    SUPERSEDED = "superseded"
    MISSING = "missing"
    QUARANTINED = "quarantined"
    ERROR = "error"


class BeeAnalysis(BaseModel):
    """Rohantwort des Extractors/LLM — genau das, was das Modell liefern MUSS (§15)."""

    title: str = Field(..., description="kurzer Titel")
    summary: str = Field("", description="3–5 Sätze Kernaussage")
    keywords: list[str] = Field(default_factory=list, description="~5 Stichworte")
    funktion_aufgabe: str = Field("", description="welche Aufgabe hat das Dokument (1 Satz)")
    kategorie: str = Field("_unassigned", description="kleingeschriebenes Label")


class Content(BaseModel):
    title: str = ""
    summary: str = ""
    keywords: list[str] = Field(default_factory=list)


class Funktion(BaseModel):
    """Funktion = welche Aufgabe das Dokument hat (§21.1)."""

    aufgabe: str = ""
    kategorie: str = "_unassigned"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class BeeEntry(BaseModel):
    """Ein Eintrag = eine 'Biene' im Stock (§7). Identisch für JSON, DB und Export."""

    id: str
    path: str
    original_path: str | None = None
    filename: str
    mime_type: str | None = None
    size_bytes: int = 0
    content_hash: str
    supersedes: str | None = None

    content: Content = Field(default_factory=Content)
    funktion: Funktion = Field(default_factory=Funktion)
    zustaendigkeit: list[str] = Field(default_factory=list)

    confidence: float = 0.0
    status: Status = Status.PENDING
    error_reason: str | None = None
    scanned_at: str = Field(default_factory=_now_iso)

    # -- Ableitungen -------------------------------------------------------
    @property
    def kategorie(self) -> str:
        return self.funktion.kategorie

    def embedding_text(self) -> str:
        """Kanonischer Eintragstext fürs Hive Mind (§14): titel+aufgabe+summary+keywords."""
        parts = [
            self.content.title,
            self.funktion.aufgabe,
            self.content.summary,
            " ".join(self.content.keywords),
        ]
        return "\n".join(p for p in parts if p).strip()

    @classmethod
    def from_analysis(
        cls,
        *,
        id: str,
        path: str,
        original_path: str,
        filename: str,
        mime_type: str | None,
        size_bytes: int,
        content_hash: str,
        analysis: BeeAnalysis,
    ) -> BeeEntry:
        return cls(
            id=id,
            path=path,
            original_path=original_path,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            content_hash=content_hash,
            content=Content(
                title=analysis.title,
                summary=analysis.summary,
                keywords=analysis.keywords,
            ),
            funktion=Funktion(
                aufgabe=analysis.funktion_aufgabe,
                kategorie=(analysis.kategorie or "_unassigned").strip().lower(),
            ),
        )

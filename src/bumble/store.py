"""Metadata Store — SQL-Index (§8) + MD/JSON-Export nach honig/ (§7).

SQLAlchemy 2 Core: SQLite jetzt, PostgreSQL später (nur die URL ändert sich).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import (
    REAL,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    func,
    select,
)
from sqlalchemy.engine import Engine

from .models import BeeEntry, Content, Funktion, Status

metadata = MetaData()

bees = Table(
    "bees", metadata,
    Column("id", String, primary_key=True),
    Column("path", Text, nullable=False),
    Column("original_path", Text),
    Column("filename", Text, nullable=False),
    Column("mime_type", Text),
    Column("size_bytes", Integer),
    Column("content_hash", Text, unique=True),          # Dedupe (§8)
    Column("supersedes", String),
    Column("title", Text),
    Column("summary", Text),
    Column("keywords", Text),                            # CSV in SQLite
    Column("funktion", Text),
    Column("kategorie", Text),
    Column("confidence", REAL),
    Column("status", Text, default="pending"),
    Column("error_reason", Text),
    Column("scanned_at", Text),
)

responsibilities = Table(
    "responsibilities", metadata,
    Column("bee_id", String, nullable=False),
    Column("person", String, nullable=False),
)

duplicate_paths = Table(
    "duplicate_paths", metadata,
    Column("bee_id", String, nullable=False),
    Column("path", Text, nullable=False),
)


def _sqlite_pragmas(dbapi_con, _record):
    cur = dbapi_con.cursor()
    cur.execute("PRAGMA journal_mode=WAL")      # nebenläufige Leser (§16)
    cur.execute("PRAGMA busy_timeout=5000")     # DB-Lock freundlich abwarten (§16)
    cur.close()


class Store:
    """Kapselt Engine + Tabellen. URL-getauscht wird nur der Connection-String."""

    def __init__(self, hive: Path):
        from .config import honig
        self.hive = hive
        self.honig = honig(hive) / "eintraege"          # pro Datei MD+JSON, versteckt
        honig(hive).mkdir(parents=True, exist_ok=True)
        # SQLite (Prototyp) → PostgreSQL (Skalierung): nur die URL wechselt.
        db = honig(hive) / "katalog.db"
        url = os.environ.get("DATABASE_URL") or f"sqlite:///{db.as_posix()}"
        self.engine: Engine = create_engine(url, future=True)
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine, "connect", _sqlite_pragmas)
        metadata.create_all(self.engine)

    # -- Lesen ---------------------------------------------------------------
    def by_hash(self, content_hash: str) -> dict | None:
        with self.engine.connect() as c:
            row = c.execute(select(bees).where(bees.c.content_hash == content_hash)).mappings().first()
            return dict(row) if row else None

    def by_id(self, bee_id: str) -> dict | None:
        with self.engine.connect() as c:
            row = c.execute(select(bees).where(bees.c.id == bee_id)).mappings().first()
            return dict(row) if row else None

    def status_counts(self) -> dict[str, int]:
        with self.engine.connect() as c:
            rows = c.execute(
                select(bees.c.status, func.count()).group_by(bees.c.status)
            ).all()
        return {status: n for status, n in rows}

    def query(self, *, status: str | None = None, kategorie: str | None = None,
              keyword: str | None = None, person: str | None = None) -> list[dict]:
        stmt = select(bees)
        if status:
            stmt = stmt.where(bees.c.status == status)
        if kategorie:
            stmt = stmt.where(bees.c.kategorie == kategorie)
        if keyword:
            like = f"%{keyword.lower()}%"
            stmt = stmt.where(
                func.lower(bees.c.title).like(like)
                | func.lower(bees.c.keywords).like(like)
                | func.lower(bees.c.summary).like(like)
            )
        if person:
            ids = select(responsibilities.c.bee_id).where(responsibilities.c.person == person)
            stmt = stmt.where(bees.c.id.in_(ids))
        with self.engine.connect() as c:
            return [dict(r) for r in c.execute(stmt.order_by(bees.c.scanned_at.desc())).mappings()]

    # -- Schreiben -----------------------------------------------------------
    def save(self, entry: BeeEntry) -> None:
        """Eintrag persistieren (SQL + honig/MD + honig/JSON), inkl. Zuständigkeiten."""
        row = {
            "id": entry.id,
            "path": entry.path,
            "original_path": entry.original_path,
            "filename": entry.filename,
            "mime_type": entry.mime_type,
            "size_bytes": entry.size_bytes,
            "content_hash": entry.content_hash,
            "supersedes": entry.supersedes,
            "title": entry.content.title,
            "summary": entry.content.summary,
            "keywords": ",".join(entry.content.keywords),
            "funktion": entry.funktion.aufgabe,
            "kategorie": entry.funktion.kategorie,
            "confidence": entry.confidence,
            "status": entry.status.value,
            "error_reason": entry.error_reason,
            "scanned_at": entry.scanned_at,
        }
        with self.engine.begin() as c:
            exists = c.execute(select(bees.c.id).where(bees.c.id == entry.id)).first()
            if exists:
                c.execute(bees.update().where(bees.c.id == entry.id).values(**row))
            else:
                c.execute(bees.insert().values(**row))
            c.execute(responsibilities.delete().where(responsibilities.c.bee_id == entry.id))
            for person in entry.zustaendigkeit:
                c.execute(responsibilities.insert().values(bee_id=entry.id, person=person))
        self._export(entry)

    def add_duplicate_path(self, bee_id: str, path: str) -> None:
        """Gleicher Inhalt an zweitem Pfad — kein neuer Eintrag, kein LLM-Call (§7)."""
        with self.engine.begin() as c:
            dup = c.execute(
                select(duplicate_paths).where(
                    (duplicate_paths.c.bee_id == bee_id) & (duplicate_paths.c.path == path)
                )
            ).first()
            if not dup:
                c.execute(duplicate_paths.insert().values(bee_id=bee_id, path=path))

    def duplicate_rows(self) -> list[dict]:
        """Alle registrierten Dubletten-Pfade samt Original-Eintrag (für 'dubletten')."""
        with self.engine.connect() as c:
            rows = c.execute(
                select(duplicate_paths.c.bee_id, duplicate_paths.c.path,
                       bees.c.filename, bees.c.kategorie)
                .select_from(duplicate_paths.join(bees, duplicate_paths.c.bee_id == bees.c.id))
            ).mappings().all()
            return [dict(r) for r in rows]

    def remove_duplicate_path(self, path: str) -> None:
        with self.engine.begin() as c:
            c.execute(duplicate_paths.delete().where(duplicate_paths.c.path == path))

    def set_status(self, bee_id: str, status: Status) -> None:
        with self.engine.begin() as c:
            c.execute(bees.update().where(bees.c.id == bee_id).values(status=status.value))

    def update_path(self, bee_id: str, path: str) -> None:
        with self.engine.begin() as c:
            c.execute(bees.update().where(bees.c.id == bee_id).values(path=path))

    def delete(self, bee_id: str) -> None:
        """Einen Eintrag vollständig entfernen: DB-Zeilen + exportierte MD/JSON.

        Für das endgültige Leeren der Quarantäne (§13): keine verwaisten Katalog-
        Einträge, die auf gelöschte Dateien zeigen. Das Gedächtnis wird beim
        Einliefern in die Quarantäne bereits vergessen.
        """
        with self.engine.begin() as c:
            c.execute(bees.delete().where(bees.c.id == bee_id))
            c.execute(responsibilities.delete().where(responsibilities.c.bee_id == bee_id))
            c.execute(duplicate_paths.delete().where(duplicate_paths.c.bee_id == bee_id))
        for ext in (".json", ".md"):
            f = self.honig / f"{bee_id}{ext}"
            if f.exists():
                f.unlink()

    # -- Export (§7) ---------------------------------------------------------
    def _export(self, entry: BeeEntry) -> None:
        self.honig.mkdir(parents=True, exist_ok=True)
        (self.honig / f"{entry.id}.json").write_text(
            entry.model_dump_json(indent=2), encoding="utf-8"
        )
        (self.honig / f"{entry.id}.md").write_text(to_markdown(entry), encoding="utf-8")


def to_markdown(entry: BeeEntry) -> str:
    """PKM-kompatibler MD-Export mit YAML-Frontmatter (§7) — Obsidian/Logseq/Notion-ready."""
    kws = ", ".join(entry.content.keywords)
    resp = ", ".join(entry.zustaendigkeit)
    fm = [
        "---",
        f"id: {entry.id}",
        f"title: {json.dumps(entry.content.title, ensure_ascii=False)}",
        f"kategorie: {entry.funktion.kategorie}",
        f"funktion: {json.dumps(entry.funktion.aufgabe, ensure_ascii=False)}",
        f"keywords: [{kws}]",
        f"zustaendigkeit: [{resp}]",
        f"status: {entry.status.value}",
        f"confidence: {entry.confidence}",
        f"mime_type: {entry.mime_type or ''}",
        f"size_bytes: {entry.size_bytes}",
        f"content_hash: {entry.content_hash}",
        f"path: {json.dumps(entry.path, ensure_ascii=False)}",
        f"scanned_at: {entry.scanned_at}",
        "---",
        "",
    ]
    body = [
        f"# {entry.content.title or entry.filename}",
        "",
        f"**Funktion (Aufgabe):** {entry.funktion.aufgabe or '—'}",
        f"**Kategorie:** {entry.funktion.kategorie}   ",
        f"**Zuständig:** {resp or '—'}",
        "",
        "## Zusammenfassung",
        "",
        entry.content.summary or "_(keine Zusammenfassung)_",
        "",
    ]
    if entry.error_reason:
        body += ["## Hinweis", "", f"⚠️ {entry.error_reason}", ""]
    return "\n".join(fm + body)


def row_to_entry(row: dict) -> BeeEntry:
    """DB-Zeile zurück in ein BeeEntry (für Re-Export / Move / Sweep)."""
    return BeeEntry(
        id=row["id"],
        path=row["path"],
        original_path=row.get("original_path"),
        filename=row["filename"],
        mime_type=row.get("mime_type"),
        size_bytes=row.get("size_bytes") or 0,
        content_hash=row["content_hash"],
        supersedes=row.get("supersedes"),
        content=Content(
            title=row.get("title") or "",
            summary=row.get("summary") or "",
            keywords=[k for k in (row.get("keywords") or "").split(",") if k],
        ),
        funktion=Funktion(
            aufgabe=row.get("funktion") or "",
            kategorie=row.get("kategorie") or "_unassigned",
        ),
        confidence=row.get("confidence") or 0.0,
        status=Status(row.get("status") or "pending"),
        error_reason=row.get("error_reason"),
        scanned_at=row.get("scanned_at") or "",
    )

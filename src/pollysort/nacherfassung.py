"""Nacherfassung — die KI verfeinert Titel und Zusammenfassung, NACHDEM sortiert ist.

Die dreistufige Entscheidung (:mod:`pollysort.entscheidung`) legt eine Datei ab, ohne dass
das Modell eine Zusammenfassung schreibt — genau das war der teure Teil. Titel und
Zusammenfassung stammen zunächst aus einer Heuristik (erste Zeile, Textanfang). Hier holt
die KI sie nach: eine volle Analyse je Eintrag, deren **Kategorie ignoriert** wird — die
Einordnung ist längst entschieden, und eine Nacherfassung darf nie still umsortieren.

Die Warteschlange liegt als ``.honig/nacherfassung.json`` im Projekt. Jeder erledigte
Eintrag verlässt sie sofort; ein Abbruch (Strg-C, Ollama weg) verliert also nichts, der
nächste Lauf macht dort weiter.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from . import config, i18n
from .models import Content, Status

DATEI = "nacherfassung.json"
#: Nur Einträge in diesen Zuständen werden nacherfasst — Quarantäne & Co. fallen heraus.
ZUSTAENDE = {Status.ASSIGNED.value, Status.INDEXED.value, Status.NEEDS_REVIEW.value}


def _pfad(hive: Path) -> Path:
    return config.honig(hive) / DATEI


def offen(hive: Path) -> list[str]:
    try:
        daten = json.loads(_pfad(hive).read_text(encoding="utf-8"))
        return [str(x) for x in daten.get("ids", [])]
    except (OSError, ValueError):
        return []


def _schreiben(hive: Path, ids: list[str]) -> None:
    p = _pfad(hive)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"ids": ids}, ensure_ascii=False, indent=1), encoding="utf-8")


def vormerken(hive: Path, bee_ids: Iterable[str]) -> None:
    ids = offen(hive)
    neu = [i for i in bee_ids if i not in ids]
    if neu:
        _schreiben(hive, ids + neu)


def austragen(hive: Path, bee_id: str) -> None:
    ids = offen(hive)
    if bee_id in ids:
        _schreiben(hive, [i for i in ids if i != bee_id])


def nacherfassen(ctx) -> tuple[int, str | None]:
    """Die Warteschlange abarbeiten. Gibt ``(verfeinert, abbruchgrund)``.

    Ein Provider-Fehler beendet die Runde (der Rest bleibt vorgemerkt); ``KeyboardInterrupt``
    reicht die Funktion an den Aufrufer weiter — der erledigte Teil ist dann schon gesichert.
    """
    from pydantic import ValidationError

    from .extractor import volltext
    from .llm import LLMError
    from .store import row_to_entry

    ids = offen(ctx.hive)
    fertig = 0
    con = ctx.console
    with con.progress(i18n.t("nx.progress")) as prog:
        task = prog.add_task(i18n.t("nx.progress"), total=len(ids))
        for bee_id in ids:
            row = ctx.store.by_id(bee_id)
            path = Path(row["path"]) if row else None
            text = None
            if row and row.get("status") in ZUSTAENDE and path.exists():
                try:
                    text = volltext(path, row.get("mime_type"))
                except Exception:
                    text = None
            if not text:
                austragen(ctx.hive, bee_id)            # nichts (mehr) zu verfeinern
                prog.advance(task)
                continue
            prog.update(task, description=f"✍️ {path.name}")
            analyse = None
            for _ in range(3):                         # Repair-Retry wie im Extractor
                try:
                    analyse = ctx.client.analyze(text=text, file_path=str(path))
                    break
                except (ValidationError, ValueError):
                    continue
                except LLMError as exc:
                    return fertig, str(exc)
            if analyse is not None:
                entry = row_to_entry(row)
                entry.content = Content(title=analyse.title, summary=analyse.summary,
                                        keywords=list(analyse.keywords))
                entry.funktion.aufgabe = analyse.funktion_aufgabe
                # Kategorie, Status, Pfad und Zuständigkeit bleiben unangetastet.
                entry.zustaendigkeit = ctx.taxonomy.persons_for(entry.kategorie)
                ctx.store.save(entry)                  # schreibt auch MD/JSON neu
                fertig += 1
            austragen(ctx.hive, bee_id)
            prog.advance(task)
    return fertig, None

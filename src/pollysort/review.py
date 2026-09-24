"""Rückfragen (§9/§21.13) — gebündelt & interaktiv, plus Korrektur-Logik für ``assign``.

``watch``/Daemon fragt NIE interaktiv; Fälle < 75 % landen still in ``_unassigned/`` und
werden hier gebündelt abgearbeitet. Jede Antwort trainiert das Gedächtnis (§14.4).
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from . import i18n
from .models import Status
from .mover import collision_safe_name
from .pipeline import Context


def apply_correction(ctx: Context, bee_id: str, kategorie: str, *,
                     mode: str = "move", source: str = "assign") -> str | None:
    """Kategorie korrigieren → DB + Feedback + Zentroid-Update (+ ggf. Move) (§14.4)."""
    row = ctx.store.by_id(bee_id)
    if not row:
        return None
    kategorie = kategorie.strip().lower()
    old = row["kategorie"]

    # Kategorie ggf. neu in die lebende Taxonomie aufnehmen
    if kategorie not in ctx.taxonomy.categories and kategorie != "_unassigned":
        ctx.taxonomy.add_category(kategorie)

    from .store import bees, row_to_entry
    persons = ctx.taxonomy.persons_for(kategorie)
    with ctx.store.engine.begin() as c:
        c.execute(bees.update().where(bees.c.id == bee_id).values(
            kategorie=kategorie, status=Status.ASSIGNED.value))
    _set_persons(ctx, bee_id, persons)

    # Feedback + Gedächtnis: Zentroid verschiebt sich nachweislich (§14.4)
    entry = row_to_entry({**row, "kategorie": kategorie})
    from .extractor import gedaechtnis_text
    vec = ctx.client.embed(gedaechtnis_text(ctx.client, row.get("path"), entry.embedding_text()))
    ctx.mind.remember(bee_id, kategorie, vec, getattr(ctx.client, "embed_model", None))
    ctx.feedback.record(bee_id=bee_id, title=row.get("title") or "",
                        funktion=row.get("funktion") or "", kategorie_alt=old,
                        kategorie_neu=kategorie, quelle=source)

    # Datei aus _unassigned/ in die richtige Wabe holen (falls im Stock)
    _move_into_category(ctx, bee_id, kategorie, mode=mode)
    return old


def _set_persons(ctx: Context, bee_id: str, persons: list[str]) -> None:
    from .store import responsibilities
    with ctx.store.engine.begin() as c:
        c.execute(responsibilities.delete().where(responsibilities.c.bee_id == bee_id))
        for p in persons:
            c.execute(responsibilities.insert().values(bee_id=bee_id, person=p))


def _move_into_category(ctx: Context, bee_id: str, kategorie: str, *, mode: str) -> None:
    from . import mover
    from .store import row_to_entry
    row = ctx.store.by_id(bee_id)
    src = Path(row["path"])
    if not src.exists() or mode != "move":
        return
    # Über mover.target_dir routen, damit auch Korrekturen den dynamischen Unterordner
    # ({jahr}/{monat}) treffen — nicht nur den Waben-Root (Konsistenz mit dem Sortier-Pfad).
    entry = row_to_entry({**row, "kategorie": kategorie})
    dest_dir = mover.target_dir(ctx.hive, entry, getattr(ctx.seed, "subrouting", None))
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = collision_safe_name(dest_dir, src.name, bee_id)
    if src.resolve() != dest.resolve():
        import shutil
        shutil.move(str(src), str(dest))
        ctx.store.update_path(bee_id, str(dest))
        # Auch Korrektur-Moves ins Move-Log — sonst macht 'rueckflug' statt der
        # jüngsten Korrektur eine uralte System-Verschiebung rückgängig (BUG-8).
        ctx.movelog.record(bee_id=bee_id, src=str(src), dst=str(dest), action="korrektur")


def open_file(path: str) -> None:
    """'Das Auge der Biene' (§19): Original mit dem OS-Standardbetrachter öffnen."""
    try:
        if sys.platform.startswith("win"):
            import os
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception:
        pass


def review(ctx: Context, *, mode: str = "move",
           ask: Callable[[str], str] | None = None) -> int:
    """Alle offenen Rückfragen gebündelt abarbeiten. Gibt die Zahl der Korrekturen zurück.

    ``ask`` ist injizierbar (Tests); Default liest interaktiv von der Konsole.
    """
    ask = ask or (lambda prompt: input(prompt))
    con = ctx.console
    rows = ctx.store.query(status="needs_review")
    if not rows:
        con.info(i18n.t("rv.none"), "🐝")
        return 0

    con.rule(i18n.t("rv.title", n=len(rows)))
    known = ", ".join(ctx.taxonomy.categories)
    corrected = 0
    for i, row in enumerate(rows, 1):
        con.raw(f"\n[{i}/{len(rows)}] {row['filename']}  (conf {row.get('confidence') or 0:.2f})")
        con.raw(i18n.t("rv.titel", title=row.get("title")))
        con.raw(i18n.t("rv.funktion", f=row.get("funktion")))
        con.raw(i18n.t("rv.vorschlag", cat=row.get("kategorie"), known=known))
        answer = ask(i18n.t("rv.prompt")).strip()
        if answer.lower() in ("s", ""):
            continue
        if answer.lower() == "q":
            break
        if answer.lower() in ("v", "o"):
            open_file(row["path"])
            answer = ask(i18n.t("rv.prompt2")).strip()
            if answer.lower() in ("s", ""):
                continue
        old = apply_correction(ctx, row["id"], answer, mode=mode, source="review")
        if old is not None:
            corrected += 1
            con.honey(f"{row['filename']}: {old} → {answer.lower()}", "🍯")
    con.info(i18n.t("rv.done", n=corrected), "🐝")
    return corrected

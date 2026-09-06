"""Kategorie-Migration bei ``pollysort-cli hive approve`` (§6, §14.3).

In einem Zug: Ordner in ``waben/`` verschieben, DB-``kategorie`` updaten, Zentroide im
Vektor-Store neu labeln, Eintrag im Journal. Nie halbfertig — Move-Log macht Wiederanlauf
möglich; Nutzerdateien werden nie gelöscht/überschrieben.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .hive_mind.reflection import Proposal
from .models import Status
from .mover import collision_safe_name
from .pipeline import Context


def approve(ctx: Context, proposal: Proposal) -> str:
    if proposal.kind == "new":
        return _approve_new(ctx, proposal)
    if proposal.kind == "merge":
        return _approve_merge(ctx, proposal)
    return "unbekannter Vorschlagstyp"


def _approve_new(ctx: Context, p: Proposal) -> str:
    name = p.payload["name"]
    ctx.taxonomy.add_category(name)
    moved = 0
    for bee_id in p.payload["members"]:
        row = ctx.store.by_id(bee_id)
        if not row:
            continue
        _relabel_row(ctx, row, name)
        moved += _move_into_category(ctx, row, name)
    ctx.journal.entry("hive approve (neu)", [
        f"kategorie: {name}", f"dokumente: {len(p.payload['members'])}", f"verschoben: {moved}"])
    return f"Neue Kategorie '{name}' übernommen ({len(p.payload['members'])} Dokumente)."


def _approve_merge(ctx: Context, p: Proposal) -> str:
    src, dst = p.payload["src"], p.payload["dst"]
    ctx.taxonomy.merge_category(src, dst)
    ctx.mind.relabel_category(src, dst)
    moved = 0
    for row in ctx.store.query(kategorie=src):
        _relabel_row(ctx, row, dst, remember=False)
        moved += _move_into_category(ctx, row, dst)
    ctx.journal.entry("hive approve (merge)", [f"{src} → {dst}", f"verschoben: {moved}"])
    return f"'{src}' → '{dst}' zusammengeführt ({moved} Dateien migriert)."


def _relabel_row(ctx: Context, row: dict, kategorie: str, *, remember: bool = True) -> None:
    from .store import bees
    with ctx.store.engine.begin() as c:
        new_status = row["status"]
        if new_status in (Status.NEEDS_REVIEW.value, Status.INDEXED.value):
            new_status = Status.ASSIGNED.value
        c.execute(bees.update().where(bees.c.id == row["id"]).values(
            kategorie=kategorie, status=new_status))
    if remember:
        ctx.mind.relabel(row["id"], kategorie)


def _move_into_category(ctx: Context, row: dict, kategorie: str) -> int:
    """Datei in den Kategorie-Ordner im Root verschieben, falls sie im Stock liegt."""
    from .config import pretty_category
    src = Path(row["path"])
    if not src.exists():
        return 0
    dest_dir = ctx.hive / pretty_category(kategorie)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = collision_safe_name(dest_dir, src.name, row["id"])
    if src.resolve() == dest.resolve():
        return 0
    shutil.move(str(src), str(dest))
    ctx.store.update_path(row["id"], str(dest))
    return 1

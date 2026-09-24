"""Empfehlungs-Engine (§18) — 3 Strategie-Presets + immer 2–3 dynamische Vorschläge.

Konsolen-Hinweise, kein Auto-Eingriff. Der Nutzer wählt ein Preset als 'Brille'; zusätzlich
kommen datengetriebene Hinweise aus dem realen Bestand.
"""

from __future__ import annotations

from collections import Counter

from . import i18n
from .pipeline import Context

#: Strategie → (Name, i18n-Schlüssel der Kurzidee).
PRESETS = {
    "para": ("PARA (Tiago Forte)", "rec.para"),
    "johnny": ("Johnny Decimal", "rec.johnny"),
    "dewey": ("Dewey Decimal", "rec.dewey"),
}


def suggest(ctx: Context, strategy: str = "para") -> list[str]:
    strategy = strategy.lower()
    name, idea_key = PRESETS.get(strategy, PRESETS["para"])
    con = ctx.console
    store = ctx.store
    rows = store.query()

    con.rule(i18n.t("rec.title", name=name))
    hints: list[str] = [i18n.t("rec.preset", idea=i18n.t(idea_key))]

    # -- Dynamische Vorschläge (immer 2–3) ---------------------------------
    # Rückfrage-Stau
    nr = [r for r in rows if r["status"] == "needs_review"]
    if nr:
        hints.append(i18n.t("rec.review", n=len(nr)))

    # Fehler-Stau
    err = [r for r in rows if r["status"] == "error"]
    if err:
        hints.append(i18n.t("rec.errors", n=len(err)))

    # Häufungen ohne Kategorie → neue Kategorie denkbar
    unassigned = [r for r in rows if r["kategorie"] == "_unassigned"]
    if len(unassigned) >= 3:
        hints.append(i18n.t("rec.unassigned", n=len(unassigned)))

    # Dubletten
    dup = _duplicate_count(store)
    if dup:
        hints.append(i18n.t("rec.dups", n=dup))

    # Preset-spezifisch: alte Dokumente in einer Kategorie
    cats = Counter(r["kategorie"] for r in rows if r["kategorie"] != "_unassigned")
    if strategy == "para" and cats:
        top, n = cats.most_common(1)[0]
        hints.append(i18n.t("rec.para_top", top=top, n=n))

    for h in hints[:5]:
        con.raw(f"  {h}")
    return hints


def _duplicate_count(store) -> int:
    from sqlalchemy import func, select

    from .store import duplicate_paths
    with store.engine.connect() as c:
        return c.execute(select(func.count()).select_from(duplicate_paths)).scalar() or 0

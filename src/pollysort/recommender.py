"""Empfehlungs-Engine (§18) — 3 Strategie-Presets + immer 2–3 dynamische Vorschläge.

Konsolen-Hinweise, kein Auto-Eingriff. Der Nutzer wählt ein Preset als 'Brille'; zusätzlich
kommen datengetriebene Hinweise aus dem realen Bestand.
"""

from __future__ import annotations

from collections import Counter

from .pipeline import Context

PRESETS = {
    "para": ("PARA (Tiago Forte)",
             "Nach Lebenszyklus gruppieren: Abgeschlossenes → Archive, Laufendes → Projects."),
    "johnny": ("Johnny Decimal",
               "Nummerierte Bereiche AC.ID (max. 10×10) — flache, eindeutige Ordner-IDs."),
    "dewey": ("Dewey Decimal",
              "Themenbasierte Dezimalklassen — passt zur Beebliothek."),
}


def suggest(ctx: Context, strategy: str = "para") -> list[str]:
    strategy = strategy.lower()
    name, idea = PRESETS.get(strategy, PRESETS["para"])
    con = ctx.console
    store = ctx.store
    rows = store.query()

    con.rule(f"🍯 Empfehlungen (Strategie: {name})")
    hints: list[str] = [f"▸ Preset: {idea}"]

    # -- Dynamische Vorschläge (immer 2–3) ---------------------------------
    # Rückfrage-Stau
    nr = [r for r in rows if r["status"] == "needs_review"]
    if nr:
        hints.append(f"▸ Dynamisch: {len(nr)} Einträge unter der Schwelle → pollysort-cli review")

    # Fehler-Stau
    err = [r for r in rows if r["status"] == "error"]
    if err:
        hints.append(f"▸ Dynamisch: {len(err)} Fehler-Einträge → pollysort list --status error")

    # Häufungen ohne Kategorie → neue Kategorie denkbar
    unassigned = [r for r in rows if r["kategorie"] == "_unassigned"]
    if len(unassigned) >= 3:
        hints.append(f"▸ Dynamisch: {len(unassigned)} Dokumente ohne passende Kategorie → "
                     f"neue Kategorie prüfen (pollysort-cli hive review)")

    # Dubletten
    dup = _duplicate_count(store)
    if dup:
        hints.append(f"▸ Dynamisch: {dup} Dublette(n) gefunden → zusammenführen")

    # Preset-spezifisch: alte Dokumente in einer Kategorie
    cats = Counter(r["kategorie"] for r in rows if r["kategorie"] != "_unassigned")
    if strategy == "para" and cats:
        top, n = cats.most_common(1)[0]
        hints.append(f"▸ Preset (PARA): '{top}' ist die größte Kategorie ({n}) — "
                     f"Abgeschlossenes nach Archive verschieben?")

    for h in hints[:5]:
        con.raw(f"  {h}")
    return hints


def _duplicate_count(store) -> int:
    from sqlalchemy import func, select

    from .store import duplicate_paths
    with store.engine.connect() as c:
        return c.execute(select(func.count()).select_from(duplicate_paths)).scalar() or 0

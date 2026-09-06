"""Onboarding — schaut die Dokumente an und schlägt eine Ordnerstruktur vor.

Zwei Wege:
- **KI-Vorschlag** (online): eine echte Analyse einer Stichprobe durch das Modell — es
  vergibt selbst Kategorie-Labels, aus denen die Struktur aggregiert wird.
- **Heuristik** (offline): schnelle, kostenlose Voranalyse aus Name, Textanfang und Dateityp.
Das eigentliche, lernende Sortieren übernimmt später ``sortiere``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path

from .guards import IgnoreMatcher
from .heuristics import classify, keywords, read_snippet
from .scout import Finding, scout, walk


def _heuristic(f: Finding) -> tuple[str, list[str]]:
    snippet = read_snippet(f.path)
    cat = classify(f.path.stem, snippet, f.path.suffix.lower(), allowed=None)
    return cat, keywords(f"{f.path.stem} {snippet}", limit=6)


def existing_structure(hive: Path) -> dict[str, int]:
    """Die BESTEHENDE Ordnerstruktur eines Projekts: sichtbare Unterordner → Anzahl Dateien.

    Der Nutzer hat sein Archiv vielleicht schon (teilweise) sortiert — diese Ordnernamen sind
    starke Kategorie-Signale, die der Vorschlag übernimmt (adaptiv statt starr). System-Ordner
    (``.honig``, ``_Unsortiert`` …) werden übersprungen.
    """
    matcher = IgnoreMatcher(hive)
    found: dict[str, int] = {}
    for sub in sorted(p for p in hive.iterdir() if p.is_dir()):
        if sub.name.startswith((".", "_")):
            continue
        # Auch LEERE Ordner zählen als gelebte Kategorien — sie wurden bewusst angelegt
        # und sollen im Vorschlag als „Wabe existiert" auftauchen statt zu verschwinden.
        found[sub.name.strip().lower()] = len(walk([sub], matcher, recursive=True))
    return found


def propose_structure(
    hive: Path,
    *,
    ai_analyze: Callable[[Finding], tuple[str, list[str]]] | None = None,
    ai_sample: int = 15,
    sample: int = 400,
    konsolidieren: bool = True,
) -> tuple[list[tuple[str, int]], int, bool, set[str], list[str]]:
    """Bestehende Struktur + lose Dateien anschauen und Kategorien mit Anzahl vorschlagen.

    Zuerst wird die **vorhandene Ordnerstruktur** erfasst (Unterordner = bereits gelebte
    Kategorien), dann werden die losen Dateien im Root analysiert (KI wenn ``ai_analyze``
    gesetzt, sonst heuristisch) und beides zusammengeführt.

    Zum Schluss läuft die **Konsolidierung** (:mod:`pollysort.taxonomie`): Weil jedes
    Dokument einzeln analysiert wird, liefert dieselbe Sorte Papier sonst mal
    „rechnungen", mal „finanzen", mal „belege" — drei Ordner für einen Stapel. Erst der
    Blick auf die Gesamtmenge kann das zusammenlegen.

    Returns: ([(kategorie, anzahl)], gescannt, ki_genutzt, {vorhandene}, [protokoll]).
    """
    existing = existing_structure(hive)                       # bestehende Struktur mit ansehen

    findings = scout(walk([hive], IgnoreMatcher(hive), recursive=False))[:sample]
    counts: Counter[str] = Counter()
    rest_kw: Counter[str] = Counter()
    rest = 0
    used_ai = False

    for i, f in enumerate(findings):
        cat, kws = None, []
        if ai_analyze is not None and i < ai_sample:
            try:
                cat, kws = ai_analyze(f)
                used_ai = True
            except Exception:
                cat = None
        if not cat:
            cat, kws = _heuristic(f)
        cat = (cat or "_unassigned").strip().lower()
        if cat == "_unassigned":
            rest += 1
            for w in set(kws[:6]):
                rest_kw[w] += 1
        else:
            counts[cat] += 1

    proposals: dict[str, int] = dict(counts)
    if rest:
        top = rest_kw.most_common(1)
        if top and top[0][1] >= max(3, rest // 3):
            proposals[top[0][0]] = proposals.get(top[0][0], 0) + rest
        else:
            proposals["sonstiges"] = rest

    # Erst konsolidieren, DANN die bestehenden Ordner einmischen. Andersherum würde die
    # Zählung eines Modell-Labels verloren gehen, sobald schon ein gleichnamiger Ordner
    # existiert — und die Konsolidierung sähe eine verfälschte Verteilung.
    protokoll: list[str] = []
    if konsolidieren:
        from .taxonomie import konsolidieren as _konsolidieren
        proposals, protokoll = _konsolidieren(proposals)

    # Bereits gelebte Ordner sind gesetzt: sie stammen vom Nutzer, nicht vom Modell, und
    # werden nie wegkonsolidiert.
    for name, n in existing.items():
        proposals[name] = proposals.get(name, 0) + n

    ordered = sorted(proposals.items(), key=lambda kv: -kv[1])
    scanned = len(findings) + sum(existing.values())
    return ordered, scanned, used_ai, set(existing), protokoll

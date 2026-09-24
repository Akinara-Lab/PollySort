"""Semantisches Gedächtnis (§14) — Kern des Hive Mind.

Gekapselt hinter dem ``HiveMind``-Interface (``remember``/``neighbors``/``centroid``),
sodass später Cognee/Mem0 oder ``sqlite-vec`` eingehängt werden kann — analog zum
swappbaren LLM-Layer. Der Prototyp speichert Embeddings als JSON in ``vectors.db`` und
rechnet Cosine-Similarity in Python (robust & abhängigkeitsarm; für Prototyp-Größen genug).

`pplx-embed` liefert int8-unnormalisierte Vektoren → immer per **Cosine** vergleichen.
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Neighbor:
    bee_id: str
    kategorie: str
    score: float          # Cosine-Similarity [-1, 1]


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class HiveMind:
    """Vektor-Store + kNN-Abstimmung. Ein Prozess, liegt mit im Stock (``vectors.db``)."""

    def __init__(self, hive: Path):
        from ..config import honig
        self.path = honig(hive) / "gedaechtnis.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(self.path)
        self._con.execute(
            "CREATE TABLE IF NOT EXISTS vectors ("
            "  bee_id TEXT PRIMARY KEY, kategorie TEXT, vec TEXT)"
        )
        # Kleiner Schlüssel/Wert-Speicher, u. a. für das Embedding-Modell, das die aktuellen
        # Vektoren erzeugt hat (F1: Wechsel des Modells erkennen → Reindex anbieten).
        self._con.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        # Modell JE VEKTOR (seit 2026-09-24). Vorher gab es nur den einen Meta-Wert — und der
        # wurde vom ersten neuen Vektor überschrieben: Ab da galt das ganze Gedächtnis als
        # „passend", auch die alten Vektoren aus einem anderen Modell oder einer anderen
        # Textbasis. Altbestände bekommen beim Nachrüsten das Modell aus dem Meta-Wert.
        spalten = {row[1] for row in self._con.execute("PRAGMA table_info(vectors)")}
        if "model" not in spalten:
            self._con.execute("ALTER TABLE vectors ADD COLUMN model TEXT")
            alt = self._con.execute("SELECT value FROM meta WHERE key='embed_model'").fetchone()
            if alt:
                self._con.execute("UPDATE vectors SET model=? WHERE model IS NULL", (alt[0],))
        self._con.commit()

    # -- Schreiben ----------------------------------------------------------
    def remember(self, bee_id: str, kategorie: str, vec: list[float],
                 model: str | None = None) -> None:
        """Eintrag einbetten/aktualisieren (§14.1).

        ``model`` merkt das erzeugende Embedding-Modell — so lässt sich später ein
        Modellwechsel erkennen (F1), ohne den Wechsel selbst abfangen zu müssen.
        """
        self._con.execute(
            "INSERT INTO vectors(bee_id, kategorie, vec, model) VALUES(?,?,?,?) "
            "ON CONFLICT(bee_id) DO UPDATE SET kategorie=excluded.kategorie, vec=excluded.vec, "
            "model=excluded.model",
            (bee_id, kategorie, json.dumps(vec), model),
        )
        if model:
            self._con.execute(
                "INSERT INTO meta(key, value) VALUES('embed_model', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (model,),
            )
        self._con.commit()

    def forget(self, bee_id: str) -> None:
        self._con.execute("DELETE FROM vectors WHERE bee_id=?", (bee_id,))
        self._con.commit()

    def reset(self) -> None:
        """Alle Vektoren verwerfen (für den Reindex). Das Modell-Meta wird beim
        Neu-Einbetten ohnehin überschrieben."""
        self._con.execute("DELETE FROM vectors")
        self._con.commit()

    # -- Embedding-Modell / Gesundheit (F1) --------------------------------
    def model(self) -> str | None:
        """Embedding-Modell, das die (zuletzt geschriebenen) Vektoren erzeugt hat, oder None."""
        row = self._con.execute("SELECT value FROM meta WHERE key='embed_model'").fetchone()
        return row[0] if row else None

    def _dims(self) -> list[int]:
        rows = self._con.execute("SELECT vec FROM vectors").fetchall()
        return [len(json.loads(v)) for (v,) in rows]

    def mismatch(self, current_model: str | None) -> str | None:
        """Erkennt einen Embedding-Modellwechsel (alte Vektoren = totes Gewicht), sonst None.

        Zwei kostenlose Signale — kein KI-Call nötig:
        1. das gespeicherte Modell weicht vom aktuell konfigurierten ab, oder
        2. im Gedächtnis liegen Vektoren **verschiedener Dimension** nebeneinander (fängt auch
           Alt-Bestände ohne gespeicherten Modellnamen; eine Kategorie kann nur eine Dimension
           haben — Mischung ⇒ es wurden verschiedene Modelle benutzt).

        Rückgabe: ein kurzer Beschreibungs-Text des Alt-Zustands (für die Warnung).
        """
        dims = self._dims()
        if not dims:
            return None
        if current_model:
            fremd = self._con.execute(
                "SELECT model FROM vectors WHERE model IS NOT NULL AND model != ? LIMIT 1",
                (current_model,)).fetchone()
            if fremd:
                return fremd[0]
            # Ganz alte Bestände ohne Modell je Vektor: wie früher über den Meta-Wert.
            ohne = self._con.execute("SELECT 1 FROM vectors WHERE model IS NULL LIMIT 1").fetchone()
            old = self.model()
            if ohne and old and old != current_model:
                return old
        if len(set(dims)) > 1:
            return "gemischte Dimensionen"
        return None

    def relabel(self, bee_id: str, kategorie: str) -> None:
        """Kategorie eines Eintrags im Gedächtnis ändern (Migration/Korrektur, §14.3)."""
        self._con.execute("UPDATE vectors SET kategorie=? WHERE bee_id=?", (kategorie, bee_id))
        self._con.commit()

    def relabel_category(self, src: str, dst: str) -> None:
        """Alle Vektoren einer Kategorie umhängen (Merge, §14.3)."""
        self._con.execute("UPDATE vectors SET kategorie=? WHERE kategorie=?", (dst, src))
        self._con.commit()

    # -- Lesen --------------------------------------------------------------
    def _all(self) -> list[tuple[str, str, list[float]]]:
        rows = self._con.execute("SELECT bee_id, kategorie, vec FROM vectors").fetchall()
        return [(bid, kat, json.loads(v)) for bid, kat, v in rows]

    def eintraege(self, modell: str | None) -> list[tuple[str, str, list[float]]]:
        """Nur die Vektoren EINES Modells (samt Textbasis) — die einzigen, deren Ähnlichkeiten
        zu einem frischen Vektor dieses Modells etwas bedeuten."""
        rows = self._con.execute(
            "SELECT bee_id, kategorie, vec FROM vectors WHERE model = ?", (modell,)).fetchall()
        return [(bid, kat, json.loads(v)) for bid, kat, v in rows]

    def neighbors(self, vec: list[float], k: int = 7) -> list[Neighbor]:
        """k-nächste Nachbarn per Cosine (§14.1)."""
        scored = [Neighbor(bid, kat, _cosine(vec, v)) for bid, kat, v in self._all()]
        scored.sort(key=lambda n: n.score, reverse=True)
        return scored[:k]

    def count(self, kategorie: str | None = None) -> int:
        if kategorie is None:
            return self._con.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
        return self._con.execute(
            "SELECT COUNT(*) FROM vectors WHERE kategorie=?", (kategorie,)
        ).fetchone()[0]

    def categories(self) -> list[str]:
        rows = self._con.execute("SELECT DISTINCT kategorie FROM vectors").fetchall()
        return [r[0] for r in rows]

    def centroid(self, kategorie: str) -> list[float] | None:
        """Mittelwert-Vektor einer Kategorie (für Merge-Vorschläge & Drift, §14.3).

        Nach einem Wechsel des Embedding-Modells (§17) können in einer Kategorie Vektoren
        unterschiedlicher Dimension nebeneinander liegen. Wir mitteln nur die **häufigste
        Dimension** — sonst sprengt ein fremd-dimensionaler Altvektor den Zentroiden
        (früher: ``IndexError``). Analog zu ``_cosine``, das Dimensions-Mismatch abfängt.
        """
        from collections import Counter
        vecs = [v for _, kat, v in self._all() if kat == kategorie]
        if not vecs:
            return None
        dim = Counter(len(v) for v in vecs).most_common(1)[0][0]
        vecs = [v for v in vecs if len(v) == dim]
        acc = [0.0] * dim
        for v in vecs:
            for i in range(dim):
                acc[i] += v[i]
        return [x / len(vecs) for x in acc]

    def centroid_pairs(self) -> list[tuple[str, str, float]]:
        """Alle Kategorie-Paare mit Zentroid-Cosine — Basis für Merge-Vorschläge (§14.3)."""
        cats = self.categories()
        cents = {c: self.centroid(c) for c in cats}
        out: list[tuple[str, str, float]] = []
        for i, a in enumerate(cats):
            for b in cats[i + 1 :]:
                if cents[a] and cents[b]:
                    out.append((a, b, _cosine(cents[a], cents[b])))
        return out

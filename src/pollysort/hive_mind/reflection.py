"""Reflection & Elder Bee (§14.3) — neue Kategorien vorschlagen & Merges (Human-in-the-Loop).

Vorschläge landen als JSON in ``hive_mind/reflections/`` und warten auf ``pollysort-cli hive approve``
— NIE automatisch ins laufende Schema.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

MERGE_SIM = 0.92          # Zentroid-Cosine-Schwelle für Merge-Vorschlag (§14.3)
NEW_CATEGORY_MIN = 5      # so viele ähnliche _unassigned-Dokumente lösen einen Vorschlag aus


@dataclass
class Proposal:
    kind: str             # "new" | "merge"
    slug: str             # Dateiname ohne Endung
    payload: dict

    def describe(self) -> str:
        from .. import i18n
        p = self.payload
        if self.kind == "new":
            return i18n.t("refl.new", name=p["name"], n=len(p["members"]),
                          kw=", ".join(p["keywords"][:5]))
        return i18n.t("refl.merge", src=p["src"], dst=p["dst"], sim=f"{p['sim']:.2f}")


class Reflection:
    def __init__(self, hive: Path):
        from ..config import honig
        self.dir = honig(hive) / "vorschlaege"
        self.dir.mkdir(parents=True, exist_ok=True)

    # -- Erzeugen ----------------------------------------------------------
    def reflect(self, store, mind) -> list[Proposal]:
        """Periodische Konsolidierung: Vorschläge erzeugen & persistieren."""
        proposals: list[Proposal] = []
        proposals += self._propose_new(store)
        proposals += self._propose_merges(mind)
        for p in proposals:
            self._write(p)
        return proposals

    def _propose_new(self, store) -> list[Proposal]:
        rows = [r for r in store.query() if r["kategorie"] == "_unassigned"
                and r["status"] in ("needs_review", "indexed")]
        if len(rows) < NEW_CATEGORY_MIN:
            return []
        # einfache Heuristik: häufigstes gemeinsames Keyword als Kategorie-Name
        kw = Counter()
        for r in rows:
            for k in (r.get("keywords") or "").split(","):
                if k.strip():
                    kw[k.strip().lower()] += 1
        if not kw:
            return []
        name, _ = kw.most_common(1)[0]
        payload = {
            "name": name,
            "members": [r["id"] for r in rows],
            "keywords": [k for k, _ in kw.most_common(8)],
        }
        return [Proposal("new", f"new_{name}", payload)]

    def _propose_merges(self, mind) -> list[Proposal]:
        out = []
        for a, b, sim in mind.centroid_pairs():
            if sim >= MERGE_SIM:
                out.append(Proposal("merge", f"merge_{a}_{b}",
                                    {"src": a, "dst": b, "sim": round(sim, 4)}))
        return out

    # -- Persistenz --------------------------------------------------------
    def _write(self, p: Proposal) -> None:
        rec = {"kind": p.kind, "created": datetime.now(UTC).isoformat(), **p.payload}
        (self.dir / f"{p.slug}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    def pending(self) -> list[Proposal]:
        out = []
        for f in sorted(self.dir.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            out.append(Proposal(data["kind"], f.stem, data))
        return out

    def get(self, slug: str) -> Proposal | None:
        f = self.dir / f"{slug}.json"
        if not f.exists():
            return None
        data = json.loads(f.read_text(encoding="utf-8"))
        return Proposal(data["kind"], slug, data)

    def resolve(self, slug: str) -> None:
        f = self.dir / f"{slug}.json"
        if f.exists():
            f.unlink()

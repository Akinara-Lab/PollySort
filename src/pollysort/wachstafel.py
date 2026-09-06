"""Die lernende Wachstafel (§v0.3) — projektspezifische Regel-Evolution (ACE + RISE).

Sicheres Meta-Learning OHNE Code-Generierung: Die Königin liest die Korrekturen des Projekts
(``korrekturen.jsonl``), analysiert die Differenz zwischen falscher LLM-Annahme und
Nutzerkorrektur (**RISE — Recursive Introspection**) und schreibt daraus natürlichsprachliche
Ablageregeln in ``.honig/wachstafel.md`` (**ACE — Agentic Context Engineering**). Diese Regeln
werden beim Sortieren in den LLM-Prompt injiziert und von der Offline-Heuristik direkt angewandt.

🔒 Strikte Direktiven:
- KEIN Code-Harnessing: es wird niemals ``.py``-Code erzeugt/verändert, nur diese Textdatei.
- Projekt-Isolation: die Wachstafel liegt im ``.honig/`` ihres Projekts und gilt NUR dort.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

# Eine Regel-Zeile: **<stichwort>** → Wabe **<kategorie>**  (Zusatztext ohne ** ist erlaubt).
RULE_RE = re.compile(r"\*\*(.+?)\*\*\s*(?:→|->)\s*[^*]*\*\*(.+?)\*\*")

# Generische Wörter, die nie eine Regel bilden (zu unspezifisch).
# Enthält bewusst auch Funktionswörter (de/en): eine Regel wie „dieses → wabe X"
# würde künftige Dokumente aktiv falsch sortieren (QA-Befund BUG-7).
_STOP = {
    "rechnung", "rechnungen", "dokument", "dokumente", "datei", "dateien", "nummer",
    "betrag", "summe", "gmbh", "vom", "der", "die", "das", "und", "für", "mit", "über",
    "eur", "euro", "usd", "seite", "kunde", "kundennummer", "sehr", "geehrte",
    # deutsche Funktions-/Allerweltswörter
    "aber", "alle", "allem", "allen", "aller", "alles", "auch", "beim", "bereits",
    "bzw", "damit", "dann", "dass", "dein", "deine", "dem", "den", "denen", "deren",
    "dessen", "diese", "diesem", "diesen", "dieser", "dieses", "dient", "doch", "durch",
    "eine", "einem", "einen", "einer", "eines", "erst", "haben", "hier", "ihre",
    "ihrem", "ihren", "ihrer", "ihres", "immer", "kann", "kein", "keine", "koennen",
    "können", "mehr", "nach", "nicht", "noch", "nur", "oder", "ohne", "sein", "seine",
    "seinem", "seinen", "seiner", "sich", "sind", "sowie", "unter", "viele", "weitere",
    "weiteren", "welche", "wenn", "werden", "wird", "wurde", "wurden", "zwischen",
    "darstellung", "integration", "referenz", "uebersicht", "übersicht", "inhalt",
    # englische Funktions-/Allerweltswörter
    "about", "after", "also", "been", "before", "between", "cannot", "contains",
    "document", "documents", "file", "files", "from", "have", "here", "into", "more",
    "only", "other", "over", "page", "pages", "shall", "should", "some", "such",
    "that", "their", "them", "then", "there", "these", "this", "those", "under",
    "used", "uses", "using", "very", "were", "what", "when", "which", "while",
    "will", "with", "within", "would", "your",
}

# Höchstens so viele Stichwörter fließen pro Korrektur in die Regel-Statistik ein —
# der Titel zuerst (stärkstes Signal), die Funktionsbeschreibung füllt nur auf.
_MAX_TOKENS_PER_CORRECTION = 4


def _tokens(text: str) -> list[str]:
    """Aussagekräftige Stichwörter (>= 4 Zeichen, keine reinen Zahlen/Jahre)."""
    out = []
    for w in re.findall(r"[a-zA-ZäöüÄÖÜß0-9]{4,}", (text or "").lower()):
        if w.isdigit():
            continue
        out.append(w)
    return out


def parse_rules(text: str) -> list[tuple[str, str]]:
    """Regeln (stichwort, kategorie) aus dem Wachstafel-Text lesen (mensch-editierbar)."""
    rules: list[tuple[str, str]] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        m = RULE_RE.search(line)
        if m:
            kw = m.group(1).strip().lower()
            kat = m.group(2).strip().lower()
            if kw and kat:
                rules.append((kw, kat))
    return rules


def derive_rules(corrections: list[dict], categories: list[str], *,
                 limit: int = 15) -> list[tuple[str, str, int, str]]:
    """RISE: aus den Korrekturen eindeutige (stichwort → kategorie)-Regeln ableiten.

    Ein Stichwort wird zur Regel, wenn es in den Korrekturen **eindeutig** auf eine
    Zielkategorie zeigt (dominante Mehrheit). Rückgabe: (stichwort, kategorie, treffer, alt).

    Gefiltert wird streng (BUG-7): Stoppwörter, Einzelwörter bekannter Kategorien
    (sonst würde z. B. „technische" aus „technische dokumentation" umgelenkt) und
    höchstens ``_MAX_TOKENS_PER_CORRECTION`` Stichwörter pro Korrektur (Titel zuerst).
    """
    cats = {c.strip().lower() for c in categories}
    # Auch die EINZELWÖRTER aller Kategorien sperren — inkl. der in den Korrekturen
    # vorkommenden alten/neuen Labels (die Taxonomie kann sich verändert haben).
    cat_words: set[str] = set(cats)
    for label in cats | {
        (c.get("kategorie_alt") or "").strip().lower() for c in corrections
    } | {(c.get("kategorie_neu") or "").strip().lower() for c in corrections}:
        cat_words.update(_tokens(label))

    stats: dict[str, dict[str, Counter]] = defaultdict(
        lambda: {"cats": Counter(), "alt": Counter()})
    for c in corrections:
        neu = (c.get("kategorie_neu") or "").strip().lower()
        if not neu or neu == "_unassigned":
            continue
        alt = (c.get("kategorie_alt") or "").strip().lower()

        def _ok(tok: str) -> bool:
            return tok not in cat_words and tok not in _STOP
        # Titel zuerst (stärkstes Signal), Funktion füllt auf — hart gekappt,
        # damit eine einzelne Korrektur nicht die halbe Tafel vollritzt.
        toks = [t for t in _tokens(c.get("title", "")) if _ok(t)]
        toks += [t for t in _tokens(c.get("funktion", "")) if _ok(t) and t not in toks]
        for tok in toks[:_MAX_TOKENS_PER_CORRECTION]:
            stats[tok]["cats"][neu] += 1
            if alt and alt != "_unassigned":
                stats[tok]["alt"][alt] += 1

    rules: list[tuple[str, str, int, str]] = []
    for tok, s in stats.items():
        neu, n = s["cats"].most_common(1)[0]
        rest = sum(s["cats"].values()) - n
        if rest >= n:                       # mehrdeutig → keine Regel
            continue
        alt = s["alt"].most_common(1)[0][0] if s["alt"] else ""
        rules.append((tok, neu, n, alt))
    rules.sort(key=lambda r: (-r[2], r[0]))
    return rules[:limit]


def render(rules: list[tuple[str, str, int, str]], *, n_corrections: int) -> str:
    """Regeln als menschenlesbare (und wieder parsebare) Wachstafel-Markdown rendern."""
    lines = [
        "# 🐝 Wachstafel — Gelernte Projekt-Regeln",
        "",
        f"> Von der Königin aus {n_corrections} Korrektur(en) in die Wachstafel geritzt.",
        "> Gilt **nur für dieses Projekt** und wird beim Sortieren beachtet.",
        "> Anzeigen: `wachstafel` · Verwerfen: `wachstafel leeren`.",
        "",
    ]
    for kw, kat, n, alt in rules:
        alt_hint = f", statt „{alt}“" if alt else ""
        lines.append(f"- **{kw}** → Wabe **{kat}**  "
                     f"_(gelernt aus {n} Korrektur(en){alt_hint})_")
    lines.append("")
    return "\n".join(lines)


class Wachstafel:
    """Die projektgebundene Regeltafel unter ``<projekt>/.honig/wachstafel.md``."""

    def __init__(self, hive: Path):
        from .config import honig
        self.hive = hive
        self.path = honig(hive) / "wachstafel.md"

    def exists(self) -> bool:
        return self.path.exists()

    def text(self) -> str:
        try:
            return self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        except OSError:
            return ""

    def regeln(self) -> list[tuple[str, str]]:
        return parse_rules(self.text())

    def leeren(self) -> bool:
        if self.path.exists():
            self.path.unlink()
            return True
        return False

    def vorschau(self, feedback, *, categories: list[str] | None = None
                 ) -> tuple[list[tuple[str, str, int, str]], int]:
        """Regeln ABLEITEN, ohne zu schreiben (für die [J/n]-Rückfrage). Gibt (rules, n)."""
        corrections = feedback.all() if hasattr(feedback, "all") else list(feedback)
        return derive_rules(corrections, categories or []), len(corrections)

    def schreiben(self, rules: list[tuple[str, str, int, str]], *, n_corrections: int) -> None:
        """Bereits abgeleitete Regeln in die Wachstafel schreiben (nach Bestätigung)."""
        if rules:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(render(rules, n_corrections=n_corrections), encoding="utf-8")

    def reflektiere(self, feedback, *, categories: list[str] | None = None
                    ) -> list[tuple[str, str, int, str]]:
        """RISE+ACE: Korrekturen lesen, Regeln ableiten und die Wachstafel schreiben."""
        rules, n = self.vorschau(feedback, categories=categories)
        self.schreiben(rules, n_corrections=n)
        return rules

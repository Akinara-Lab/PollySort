"""Baubienen (Project Agents, Stufe 2 / Wabenbau, §v0.3).

Verwandeln eine sortierte Wabe (Kategorie-Ordner) in ein echtes Projekt: erzeugen die
Project Charter ``Bienenstock.md`` direkt im Waben-Ordner, halten Status & Deadlines und
erkennen fehlende Infos, die bei den Stakeholdern (Zuständigkeits-Tabelle ``responsibilities``)
proaktiv erfragt werden.

Charter-Daten liegen menschenlesbar in ``.honig/projekte/<slug>.toml``; die ``Bienenstock.md``
wird daraus gerendert und enthält nur Metadaten (keine Dokumentinhalte, §17).
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ..config import _toml_val, honig, pretty_category
from .kalender import Kalender


@dataclass
class Charter:
    """Die Project Charter einer Wabe (Stufe 2)."""

    kategorie: str
    name: str = ""
    ziel: str = ""
    status: str = "im bau"                      # im bau | aktiv | abgeschlossen
    stakeholder: list[str] = field(default_factory=list)
    deadline: str = ""                          # ISO-Datum oder ""
    erstellt: str = ""

    def luecken(self) -> list[str]:
        """Welche Charter-Felder fehlen noch (für proaktive Rückfragen)?"""
        fehlt = []
        if not self.ziel:
            fehlt.append("ziel")
        if not self.stakeholder:
            fehlt.append("stakeholder")
        if not self.deadline:
            fehlt.append("deadline")
        return fehlt


class Baubiene:
    """Baut aus einer Wabe ein Projekt und pflegt dessen Charter."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.hive = ctx.hive
        self.kalender = Kalender(ctx.hive)

    # -- Pfade & Persistenz -------------------------------------------------
    @staticmethod
    def _slug(kategorie: str) -> str:
        return kategorie.strip().lower().replace(" ", "_").replace("/", "_")

    def _charter_path(self, kategorie: str) -> Path:
        return honig(self.hive) / "projekte" / f"{self._slug(kategorie)}.toml"

    def laden(self, kategorie: str) -> Charter:
        p = self._charter_path(kategorie)
        if not p.exists():
            return Charter(kategorie=kategorie, name=getattr(self.ctx.seed, "name", ""))
        try:
            with p.open("rb") as fh:
                d = tomllib.load(fh).get("projekt", {})
        except (tomllib.TOMLDecodeError, OSError):
            return Charter(kategorie=kategorie)
        return Charter(
            kategorie=kategorie,
            name=d.get("name", ""),
            ziel=d.get("ziel", ""),
            status=d.get("status", "im bau"),
            stakeholder=list(d.get("stakeholder", [])),
            deadline=d.get("deadline", ""),
            erstellt=d.get("erstellt", ""),
        )

    def speichern(self, ch: Charter) -> None:
        p = self._charter_path(ch.kategorie)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "# PollySort — Project Charter (Stufe 2 / Wabenbau, §v0.3)\n\n"
            "[projekt]\n"
            f"kategorie   = {_toml_val(ch.kategorie)}\n"
            f"name        = {_toml_val(ch.name)}\n"
            f"ziel        = {_toml_val(ch.ziel)}\n"
            f"status      = {_toml_val(ch.status)}\n"
            f"stakeholder = {_toml_val(ch.stakeholder)}\n"
            f"deadline    = {_toml_val(ch.deadline)}\n"
            f"erstellt    = {_toml_val(ch.erstellt)}\n",
            encoding="utf-8",
        )

    # -- Inhalte ------------------------------------------------------------
    def dokumente(self, kategorie: str) -> list[dict]:
        return self.ctx.store.query(kategorie=kategorie)

    def offene_aufgaben(self, kategorie: str, ch: Charter) -> list[str]:
        """Was ist im Projekt noch offen? (Dokument-Klärungen + Charter-Lücken)."""
        tasks: list[str] = []
        for d in self.dokumente(kategorie):
            if d.get("status") in ("needs_review", "error"):
                tasks.append(f"Dokument klären: {d['filename']} ({d['status']})")
        luecke_text = {
            "ziel": "Projektziel definieren",
            "stakeholder": "Zuständigkeit klären (kein Stakeholder gesetzt)",
            "deadline": "Deadline festlegen",
        }
        tasks += [luecke_text[k] for k in ch.luecken()]
        return tasks

    # -- Der Wabenbau selbst ------------------------------------------------
    def wabenbau(self, kategorie: str, *, ask: Callable[[str], str] | None = None) -> Charter:
        """Charter erzeugen/aktualisieren; fehlende Infos ggf. bei Stakeholdern erfragen."""
        kategorie = kategorie.strip().lower()
        ch = self.laden(kategorie)
        ch.erstellt = ch.erstellt or datetime.now(UTC).replace(microsecond=0).isoformat()
        # Stakeholder aus der lebenden Zuständigkeits-Tabelle übernehmen, falls leer.
        if not ch.stakeholder:
            ch.stakeholder = self.ctx.taxonomy.persons_for(kategorie)

        if ask is not None:
            self._rueckfragen(kategorie, ch, ask)

        # Deadline → in den Bienen-Kalender eintragen (Wächterbienen erinnern daran).
        if ch.deadline:
            self.kalender.eintragen(
                f"Deadline: {pretty_category(kategorie)}", ch.deadline,
                projekt=self._slug(kategorie), notiz=ch.ziel)

        self.speichern(ch)
        self._render_md(kategorie, ch)
        self.pollen_sync()          # .ics-Kalender mit dem aktuellen Stand überschreiben
        self.ctx.journal.event("wabenbau", kategorie=kategorie, status=ch.status,
                               stakeholder=len(ch.stakeholder), deadline=ch.deadline or "-")
        return ch

    def pollen_sync(self) -> Path:
        """Die Pollen-Uhr (``.honig/kalender.ics``) aus allen Projekt-Deadlines neu schreiben."""
        from .ics import write_ics
        termine = self.kalender.offen()
        path = write_ics(honig(self.hive) / "kalender.ics", termine)
        con = getattr(self.ctx, "console", None)
        if con is not None and termine:
            con.honey("Baubienen haben den Pollen-Kalender synchronisiert "
                      f"({len(termine)} Termin(e) → kalender.ics).", "🐝")
        return path

    def _rueckfragen(self, kategorie: str, ch: Charter, ask: Callable[[str], str]) -> None:
        """Proaktiv fehlende Charter-Infos bei den Beteiligten erfragen."""
        con = self.ctx.console
        wer = ", ".join(ch.stakeholder) or "noch niemand zuständig"
        con.info(f"Baubienen bauen die Wabe '{pretty_category(kategorie)}' — Stakeholder: {wer}",
                 "🛠️")
        if not ch.stakeholder:
            antwort = ask("    🐝 Wer ist zuständig? (Namen, kommagetrennt, leer=offen): ").strip()
            personen = [p.strip() for p in antwort.split(",") if p.strip()]
            if personen:
                ch.stakeholder = personen
                self.ctx.taxonomy.set_persons(kategorie, personen)   # ins Gedächtnis lernen
        if not ch.ziel:
            ch.ziel = ask("    🎯 Projektziel (1 Satz, leer=später): ").strip()
        if not ch.deadline:
            ch.deadline = ask("    📅 Deadline (JJJJ-MM-TT, leer=keine): ").strip()

    def _render_md(self, kategorie: str, ch: Charter) -> None:
        """Die Project Charter als Bienenstock.md in den Waben-Ordner schreiben."""
        wabe = self.hive / pretty_category(kategorie)
        wabe.mkdir(parents=True, exist_ok=True)
        docs = self.dokumente(kategorie)
        tasks = self.offene_aufgaben(kategorie, ch)
        stakeholder = ", ".join(ch.stakeholder) or "—"
        deadline = ch.deadline or "—"
        if ch.deadline:
            tage = self.kalender.eintragen(
                f"Deadline: {pretty_category(kategorie)}", ch.deadline,
                projekt=self._slug(kategorie)).tage_bis()
            wann = f"in {tage} Tagen" if tage >= 0 else f"{-tage} Tage überfällig"
            deadline += f"  ({wann})"

        lines = [
            f"# 🍯 Bienenstock — {pretty_category(kategorie)}",
            "",
            f"> Project Charter (Stufe 2 / Wabenbau) · Projekt: **{ch.name or self.hive.name}**",
            "",
            "## 📋 Steckbrief",
            "",
            f"- **Status:** {ch.status}",
            f"- **Ziel:** {ch.ziel or '_(noch offen — mit `wabenbau` ergänzen)_'}",
            f"- **Stakeholder (Zuständig):** {stakeholder}",
            f"- **Deadline:** {deadline}",
            f"- **Waben-Inhalt:** {len(docs)} Dokument(e)",
            "",
            "## 🐝 Waben-Inhalt",
            "",
        ]
        if docs:
            for d in docs:
                lines.append(f"- `{d['filename']}` — {d.get('title') or '—'}  "
                             f"_(Status: {d.get('status')})_")
        else:
            lines.append("_(noch keine Dokumente in dieser Wabe)_")
        lines += ["", "## ✅ Offene Aufgaben", ""]
        if tasks:
            lines += [f"- [ ] {t}" for t in tasks]
        else:
            lines.append("_Alles erledigt — die Wabe summt zufrieden. 🎉_")
        lines += [
            "",
            "---",
            f"_Erzeugt von den Baubienen am {datetime.now(UTC).date().isoformat()} · "
            "Charter-Daten in `.honig/projekte/`_",
            "",
        ]
        (wabe / "Bienenstock.md").write_text("\n".join(lines), encoding="utf-8")

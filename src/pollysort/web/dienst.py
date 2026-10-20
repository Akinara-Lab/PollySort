"""Der Dienst des Flugbretts — jede Aktion der Konsole als Funktion mit JSON-Ergebnis.

Die Konsole (``repl.py``) fragt mit ``input()`` nach und druckt Tabellen. Der Browser
braucht stattdessen Daten: Zahlen, Listen, eine Antwort pro Klick. Dieser Dienst ruft
dieselben Kern-Funktionen in derselben Reihenfolge wie die Konsole auf und gibt das
Ergebnis als ``dict`` zurück. Was der Kern unterwegs meldet, landet über die
``WebKonsole`` im Ereignisstrom (Protokoll, Fortschritt).

Die Grundsätze bleiben unverhandelbar (CONTRIBUTING.md):

- **Nichts wird gelöscht** außer über ``leeren`` — und das nur mit der getippten Anzahl.
- **Eine Vorschau bleibt eine Vorschau:** ``vorschau`` füllt nur den Analyse-Cache.
- **Zugangsdaten bleiben in der Konsole:** Schlüssel und Flugrouten zeigt das Flugbrett
  nur maskiert an; eingetragen werden sie über ``schluessel setzen`` / ``flugrouten setup``.
- **Eine Aktion nach der anderen:** Schreibende Aktionen laufen nacheinander (``Beschaeftigt``)
  und respektieren das Lock der Königin, falls parallel eine Konsole im Stock arbeitet.
"""

from __future__ import annotations

import functools
import os
import shutil
import threading
import time
from collections import Counter
from datetime import date
from pathlib import Path

from .. import __version__, config, i18n, spiel
from ..config import DEFAULT_CATEGORIES, NEKTAR_SORTEN, HiveSeed, pretty_category
from ..console import resolve_theme
from ..guards import IgnoreMatcher
from ..journal import Journal
from ..llm import build_client
from ..lock import QueenLock, QueenLockError
from ..models import Status
from ..pipeline import Context, run_cycle
from ..scout import walk
from .konsole import Ereignisbus, WebKonsole

ANIMATIONEN = ("voll", "dezent", "aus")
THEMEN = ("dark", "light", "auto")
WACHE = ("off", "notify", "move")
QUELLEN = ("assign", "review", "analysiere")


class Ungueltig(ValueError):
    """Eine Anfrage, die so nicht ausführbar ist — die Meldung geht wörtlich an die Seite."""


class Beschaeftigt(RuntimeError):
    """Die Bienen arbeiten gerade an etwas anderem — eine Aktion nach der anderen."""


class Gesperrt(RuntimeError):
    """Ein anderer PollySort-Prozess (z. B. die Konsole) hält das Lock der Königin."""


def auftrag(name: str, *, sperre: bool = True):
    """Eine Methode als Aktion des Flugbretts markieren.

    Die Antwort ist immer ``{"ergebnis": …, "meldungen": […]}`` — die Meldungen sind, was
    der Kern währenddessen über die Konsole gesagt hat. ``sperre`` = nur eine solche
    Aktion gleichzeitig (alles, was Dateien bewegt, KI fragt oder den Stand schreibt).
    """
    def deko(fn):
        @functools.wraps(fn)
        def huelle(self: Dienst, *args, **kwargs):
            if sperre and not self._arbeit.acquire(blocking=False):
                raise Beschaeftigt(i18n.t("web.err.busy"))
            self.bus.senden({"art": "auftrag", "name": name, "zustand": "start"})
            zustand = "fehler"
            try:
                with self.con.sammeln() as meldungen:
                    ergebnis = fn(self, *args, **kwargs)
                zustand = "ende"
                return {"ergebnis": ergebnis, "meldungen": meldungen}
            finally:
                if sperre:
                    self._arbeit.release()
                self.bus.senden({"art": "auftrag", "name": name, "zustand": zustand})
        huelle.auftrag = name
        return huelle
    return deko


def ansicht(fn):
    """Eine Methode als lesende Ansicht markieren (GET, keine Sperre, keine Meldungen)."""
    fn.ansicht = fn.__name__
    return fn


class Dienst:
    """Der Zustand des Flugbretts: aktives Projekt, Ereignisbus, Vorschau-Cache, Wache."""

    def __init__(self, hive: Path | None = None, *, bus: Ereignisbus | None = None):
        self.bus = bus or Ereignisbus()
        self.con = WebKonsole(self.bus.senden)
        self._arbeit = threading.Lock()
        self._vorschau_cache: dict | None = None
        self._proben: list = []
        self._proben_pfad: Path | None = None
        i18n.set_language(getattr(config.load_config(), "language", "de"))
        self.hive: Path | None = hive.resolve() if hive else None
        self.wache = Wache(self)
        if self.hive and config.is_setup(self.hive):
            self.wache.nach_seed()

    # ------------------------------------------------------------------ #
    #  Helfer
    # ------------------------------------------------------------------ #
    def _projekt(self) -> Path:
        if self.hive is None or not config.is_setup(self.hive):
            raise Ungueltig(i18n.t("web.err.noproject"))
        return self.hive

    def _ctx(self) -> Context:
        """Wie ``BeehiveShell._ctx``: Modus pro Projekt, gelernte Regeln im Prompt."""
        from ..feedback import Feedback
        from ..wachstafel import Wachstafel
        hive = self._projekt()
        seed = config.load_seed(hive)
        cfg = config.load_config()
        cfg.llm_provider = seed.provider
        api_key = config.load_credentials() if seed.provider == "openrouter" else None
        few = Feedback(hive).few_shots()
        client = build_client(cfg, api_key, seed.categories, few,
                              wachstafel=Wachstafel(hive).text())
        return Context.build(hive=hive, cfg=cfg, seed=seed, client=client, console=self.con,
                             journal=Journal(hive))

    def _koenigin(self, hive: Path) -> QueenLock:
        return _Koenigin(hive)

    def _eingang_pfade(self, hive: Path | None = None) -> list[Path]:
        hive = hive or self.hive
        if not hive or not hive.is_dir():
            return []
        try:
            return walk([hive], IgnoreMatcher(hive), recursive=False)
        except Exception:
            return []

    def _taxonomie(self, hive: Path):
        from ..hive_mind import Taxonomy
        return Taxonomy.bootstrap(hive, config.load_seed(hive))

    def _store(self, hive: Path):
        from ..store import Store
        return Store(hive)

    @staticmethod
    def _wabe(kat: str | None) -> dict:
        kat = kat or "_unassigned"
        return {"key": kat, "name": pretty_category(kat)}

    def _eintrag(self, row: dict) -> dict:
        pfad = Path(row.get("path") or "")
        try:
            rel = pfad.relative_to(self.hive).as_posix() if self.hive else pfad.name
        except ValueError:
            rel = pfad.name
        return {
            "id": row["id"], "datei": row.get("filename") or pfad.name, "titel": row.get("title") or "",
            "zusammenfassung": (row.get("summary") or "")[:400],
            "stichworte": [k for k in (row.get("keywords") or "").split(",") if k][:8],
            "funktion": row.get("funktion") or "", "wabe": self._wabe(row.get("kategorie")),
            "status": row.get("status") or "", "konfidenz": round(float(row.get("confidence") or 0), 3),
            "datum": (row.get("scanned_at") or "")[:10], "ort": rel, "vorhanden": pfad.exists(),
        }

    def _einstellungen(self, cfg=None) -> dict:
        cfg = cfg or config.load_config()
        return {
            "thema": cfg.theme, "thema_aktiv": resolve_theme(cfg.theme), "sprache": cfg.language,
            "animationen": cfg.web_animationen if cfg.web_animationen in ANIMATIONEN else "voll",
            "fortschritt": cfg.web_fortschritt, "klartext": cfg.web_klartext,
            "arbeitsmodus": (cfg.web_animationen == "dezent" and not cfg.web_fortschritt
                             and cfg.web_klartext),
        }

    def _spiel(self, hive: Path) -> dict:
        stand = spiel.laden(hive)
        idx, schluessel = spiel.stufe_fuer(stand.dokumente)
        weiter = spiel.naechste_stufe(stand.dokumente)
        von = spiel.STUFEN[idx][0]
        if weiter:
            fehlt, schwelle = weiter
            anteil = (stand.dokumente - von) / max(1, schwelle - von)
        else:
            fehlt, schwelle, anteil = 0, None, 1.0
        return {
            "stufe": schluessel, "stufe_name": i18n.t(f"spiel.stufe.{schluessel}"),
            "nummer": idx + 1, "stufen": len(spiel.STUFEN), "anteil": round(anteil, 3),
            "fehlt": fehlt, "schwelle": schwelle, "dokumente": stand.dokumente,
            "waben": stand.waben, "regeln": stand.regeln, "serie": stand.serie,
            "korrekturen": stand.korrekturen,
            "abzeichen": [{"key": k, "name": i18n.t(f"spiel.abzeichen.{k}"),
                           "grund": i18n.t(f"spiel.grund.{k}"), "verdient": k in stand.abzeichen}
                          for k in spiel.ABZEICHEN],
        }

    def _buchen(self, summary=None, *, korrekturen: int = 0) -> dict | None:
        """Fortschritt buchen wie die Konsole — und die Fakten zum Feiern zurückgeben."""
        try:
            stand, neue, aufgestiegen = spiel.buchen(
                self.hive, summary, korrekturen=korrekturen,
                eingang_leer=not self._eingang_pfade())
        except Exception:
            return None      # Fortschritt ist nett, aber nie wichtiger als der Lauf
        for k in neue:
            self.con.honey(i18n.t("spiel.neu", name=i18n.t(f"spiel.abzeichen.{k}"),
                                  grund=i18n.t(f"spiel.grund.{k}")), "🏅")
        stufe = i18n.t(f"spiel.stufe.{stand.stufe}")
        if aufgestiegen:
            self.con.honey(i18n.t("spiel.aufgestiegen", stufe=stufe), "🏆")
        return {"neue_abzeichen": [{"key": k, "name": i18n.t(f"spiel.abzeichen.{k}"),
                                    "grund": i18n.t(f"spiel.grund.{k}")} for k in neue],
                "aufgestiegen": stufe if aufgestiegen else None}

    def _projektliste(self) -> list[dict]:
        out = []
        for p in config.list_projects():
            try:
                name = config.load_seed(p).name or p.name
            except Exception:
                name = p.name
            out.append({"name": name, "pfad": str(p), "aktiv": bool(self.hive and p == self.hive),
                        "eingerichtet": config.is_setup(p)})
        return out

    def _kann_rueckflug(self, hive: Path) -> bool:
        p = config.honig(hive) / ".moves.jsonl"
        try:
            return p.exists() and bool(p.read_text(encoding="utf-8").strip())
        except OSError:
            return False

    def _beenara(self, *, zeilen: bool = True) -> dict:
        """Der Stand von BeeNara — für Kopfzeile, Assistent und Werkstatt. Rein lokal, kein Netz.
        ``zeilen``: dieselben Statuszeilen wie ``beenara`` in der Konsole (beenara.bericht)."""
        from .. import beenara
        cfg = config.load_config()
        s = beenara.stand()
        grund = beenara.warum_nicht(cfg)
        info = {"bereit": grund is None, "grund": grund, "an": bool(cfg.beenara),
                "vorhanden": s.vollstaendig, "angefangen": s.angefangen, "passend": s.passend,
                "version": s.version, "mb": s.mb, "ungefaehr_mb": beenara.UNGEFAEHR_MB,
                "repo": beenara.REPO}
        if zeilen:
            hive = self.hive if self.hive and config.is_setup(self.hive) else None
            info["zeilen"] = [{"art": art, "emoji": emoji, "text": text}
                              for art, emoji, text in beenara.bericht(cfg, hive)]
        return info

    def _beenara_big(self) -> dict:
        """Der Stand von BeeNara Big und die Modellwahl — für die Werkstatt. Rein lokal, kein Netz
        (``nvidia-smi`` fragt nur die eigene Grafikkarte)."""
        from .. import beenara_big
        cfg = config.load_config()
        s = beenara_big.stand()
        grund = beenara_big.warum_nicht(cfg)
        return {"bereit": grund is None, "grund": grund, "vorhanden": s.vollstaendig,
                "angefangen": s.angefangen, "passend": s.passend, "version": s.version, "mb": s.mb,
                "ungefaehr_mb": beenara_big.UNGEFAEHR_MB, "repo": beenara_big.REPO,
                "gpu_grund": beenara_big.gpu_grund(), "modus": cfg.beenara_modell,
                "zeilen": [{"art": art, "emoji": emoji, "text": text}
                           for art, emoji, text in beenara_big.bericht(cfg)]}

    @staticmethod
    def _provider(name: str) -> str:
        provider = config.provider_aus_wort(name)
        if provider is None:
            raise Ungueltig(i18n.t("web.err.mode"))
        return provider

    # ------------------------------------------------------------------ #
    #  Ansichten (GET)
    # ------------------------------------------------------------------ #
    @ansicht
    def zustand(self) -> dict:
        """Alles für Kopfzeile und Zuhause auf einen Blick."""
        from ..swarm.kalender import Kalender
        from ..wachstafel import Wachstafel
        cfg = config.load_config()
        projekt = None
        stock = None
        if self.hive and config.is_setup(self.hive):
            seed = config.load_seed(self.hive)
            try:
                counts = self._store(self.hive).status_counts()
            except Exception:
                counts = {}
            try:
                faellig = len(Kalender(self.hive).faellig(innerhalb_tage=7))
            except Exception:
                faellig = 0
            projekt = {
                "eingerichtet": True, "name": seed.name or self.hive.name, "pfad": str(self.hive),
                "modus": seed.provider, "modus_name": i18n.modus_name(seed.provider),
                "wache": seed.watch, "nacherfassung": seed.nacherfassung,
                "lose": len(self._eingang_pfade()),
                "sortiert": counts.get("assigned", 0) + counts.get("indexed", 0),
                "rueckfragen": counts.get("needs_review", 0), "fehler": counts.get("error", 0),
                "quarantaene": counts.get("quarantined", 0), "deadlines": faellig,
                "regeln": len(Wachstafel(self.hive).regeln()),
                "waben": len(self._taxonomie(self.hive).categories),
                "kann_rueckflug": self._kann_rueckflug(self.hive),
                "vorschau_offen": self._vorschau_cache is not None,
            }
            stock = self._spiel(self.hive)
        elif self.hive:
            projekt = {"eingerichtet": False, "pfad": str(self.hive), "name": self.hive.name}
        return {
            "version": __version__, "sprache": i18n.get_language(),
            "erststart": not cfg.onboarded, "einstellungen": self._einstellungen(cfg),
            "projekt": projekt, "projekte": self._projektliste(), "stock": stock,
            "wache": self.wache.status(), "beschaeftigt": self._arbeit.locked(),
            "beenara": self._beenara(zeilen=False),
        }

    @ansicht
    def texte(self) -> dict:
        """Alle Texte der aktiven Sprache — die Seite setzt die Platzhalter selbst ein."""
        return {"sprache": i18n.get_language(), "texte": i18n.katalog()}

    @ansicht
    def protokoll(self) -> dict:
        return {"ereignisse": self.bus.letzte()}

    @ansicht
    def eingang(self) -> dict:
        dateien = []
        for p in self._eingang_pfade():
            try:
                st = p.stat()
                dateien.append({"datei": p.name, "groesse": st.st_size,
                                "geaendert": time.strftime("%Y-%m-%d %H:%M",
                                                           time.localtime(st.st_mtime))})
            except OSError:
                continue
        return {"dateien": dateien}

    @ansicht
    def rueckfragen(self) -> dict:
        hive = self._projekt()
        rows = self._store(hive).query(status=Status.NEEDS_REVIEW.value)
        faelle = []
        for r in rows:
            e = self._eintrag(r)
            e["vorschlag"] = e.pop("wabe")
            faelle.append(e)
        return {"faelle": faelle,
                "waben": [self._wabe(k) for k in self._taxonomie(hive).categories]}

    @ansicht
    def waben(self) -> dict:
        hive = self._projekt()
        seed = config.load_seed(hive)
        tax = self._taxonomie(hive)
        zaehler: Counter[str] = Counter()
        for r in self._store(hive).query():
            if r.get("status") in (Status.ASSIGNED.value, Status.INDEXED.value):
                zaehler[r.get("kategorie") or "_unassigned"] += 1
        waben = []
        for k in tax.categories:
            waben.append({**self._wabe(k), "anzahl": zaehler.get(k, 0),
                          "unterordner": seed.subrouting.get(k),
                          "projekt": (hive / pretty_category(k) / "Bienenstock.md").exists(),
                          "personen": tax.persons_for(k)})
        from ..heuristics import datums_muster
        return {"waben": waben, "muster": datums_muster(),
                "gesamt": sum(zaehler.values())}

    @ansicht
    def eintraege(self, kategorie: str = "", status: str = "", suche: str = "",
                  grenze: str = "200") -> dict:
        hive = self._projekt()
        if status and status not in {s.value for s in Status}:
            raise Ungueltig(i18n.t("web.err.params"))
        rows = self._store(hive).query(status=status or None, kategorie=kategorie or None,
                                       keyword=suche.strip() or None)
        n = max(1, min(1000, int(grenze) if str(grenze).isdigit() else 200))
        return {"eintraege": [self._eintrag(r) for r in rows[:n]], "gesamt": len(rows)}

    @ansicht
    def schwarm(self) -> dict:
        from ..flugrouten import load_flugrouten
        from ..swarm import Koenigin, Waechterbiene
        ctx = self._ctx()
        st = Koenigin(ctx).schwarm_status()
        termine = []
        for t in Waechterbiene(ctx).kalender.offen():
            tage = t.tage_bis()
            termine.append({"id": t.id, "titel": t.titel, "faellig": t.faellig, "tage": tage,
                            "projekt": t.projekt})
        termine.sort(key=lambda t: t["tage"])
        fr = load_flugrouten()
        return {**st, "gewohnheiten": [{"wabe": self._wabe(k), "ort": v}
                                       for k, v in (st.get("gewohnheiten") or {}).items()],
                "termine": termine, "flugrouten": fr.any_enabled()}

    @ansicht
    def wachstafel(self) -> dict:
        from ..feedback import Feedback
        from ..wachstafel import Wachstafel
        hive = self._projekt()
        wt = Wachstafel(hive)
        return {"regeln": [{"stichwort": kw, "wabe": self._wabe(kat)} for kw, kat in wt.regeln()],
                "korrekturen": len(Feedback(hive).all()), "vorhanden": wt.exists()}

    @ansicht
    def gedaechtnis(self) -> dict:
        from ..hive_mind.reflection import Reflection
        ctx = self._ctx()
        refl = Reflection(ctx.hive)
        drift = ctx.mind.mismatch(getattr(ctx.client, "embed_model", None))
        vorschlaege = refl.reflect(ctx.store, ctx.mind) or refl.pending()
        return {"waben": [self._wabe(k) for k in ctx.taxonomy.categories],
                "vektoren": ctx.mind.count(), "drift": drift or None,
                "vorschlaege": [{"slug": p.slug, "text": p.describe()} for p in vorschlaege]}

    @ansicht
    def quarantaene(self) -> dict:
        from ..undertaker import buried_candidates
        hive = self._projekt()
        store = self._store(hive)
        dubletten = [{"datei": Path(r["path"]).name, "original": r["filename"],
                      "wabe": self._wabe(r.get("kategorie"))}
                     for r in store.duplicate_rows() if Path(r["path"]).exists()]
        return {"dateien": [p.name for p in buried_candidates(hive)],
                "eintraege": [self._eintrag(r) for r in store.query(status=Status.QUARANTINED.value)],
                "dubletten": dubletten}

    @ansicht
    def werkstatt(self) -> dict:
        """Einstellungen & Zugänge — Schlüssel und Flugrouten nur maskiert."""
        from ..flugrouten import load_flugrouten, mask
        cfg = config.load_config()
        env = os.environ.get("OPENROUTER_API_KEY")
        gespeichert = config.CREDENTIALS_PATH.exists() and config.load_credentials()
        schluessel = ({"quelle": "env", "maskiert": mask(env)} if env else
                      {"quelle": "datei", "maskiert": mask(gespeichert)} if gespeichert else
                      {"quelle": None, "maskiert": ""})
        fr = load_flugrouten()
        projekt = None
        if self.hive and config.is_setup(self.hive):
            seed = config.load_seed(self.hive)
            projekt = {"modus": seed.provider, "wache": seed.watch,
                       "nacherfassung": seed.nacherfassung, "schwelle": seed.threshold_assign}
        return {"einstellungen": self._einstellungen(cfg), "projekt": projekt,
                "schluessel": schluessel,
                "flugrouten": {"discord": fr.discord.enabled, "email": fr.email.enabled,
                               "kalender": fr.calendar.enabled},
                "modell": cfg.llm_model,
                "sorten": [{"kurz": k, "id": v} for k, v in NEKTAR_SORTEN.items()],
                "beenara": self._beenara(), "beenara_big": self._beenara_big()}

    # ------------------------------------------------------------------ #
    #  Sortieren
    # ------------------------------------------------------------------ #
    def _summary(self, s, ctx: Context) -> dict:
        from ..pipeline import quelle_name, quellen_text
        teile = sorted(s.by_category.items(), key=lambda x: -x[1])
        plan = []
        for p in s.plan:
            q = quelle_name(p.get("quelle"), ctx.client)
            plan.append({**p, "wabe": self._wabe(p.get("kategorie")),
                         "quelle_text": i18n.t(f"web.src.{q}") if q else ""})
        provider = getattr(ctx.cfg, "llm_provider", "")
        return {
            "eingelagert": s.stored, "verschoben": s.moved, "dubletten": s.duplicates,
            "rueckfragen": s.needs_review, "fehler": s.errors, "nachgezogen": s.recovered,
            "ki_anfragen": s.llm_calls, "modus": provider,
            "kosten": round(s.est_cost_eur, 4) if provider == "openrouter" else None,
            "waben": [{"name": cat, "anzahl": n} for cat, n in teile],
            "quellen": dict(s.quellen), "quellen_text": quellen_text(s, ctx.client), "plan": plan,
            "sauber": bool(s.stored and not s.needs_review and not s.errors),
        }

    def _nacherfassen(self, ctx: Context) -> None:
        """Wie ``BeehiveShell._nacherfassen`` (automatischer Weg): Titel per KI verfeinern."""
        from .. import entscheidung, nacherfassung
        if not entscheidung.unterstuetzt(ctx.client) or not getattr(ctx.seed, "nacherfassung", True):
            return
        vorher = len(nacherfassung.offen(ctx.hive))
        if not vorher:
            return
        self.con.info(i18n.t("nx.start", n=vorher), "✍️")
        fertig, grund = nacherfassung.nacherfassen(ctx)
        if fertig:
            self.con.honey(i18n.t("nx.done", n=fertig), "✍️")
        if grund:
            self.con.error(i18n.t("nx.stopped", reason=grund))
        rest = len(nacherfassung.offen(ctx.hive))
        if rest:
            self.con.info(i18n.t("nx.left", n=rest), "✍️")

    def _lauf(self, *, dry_run: bool = False, cache: dict | None = None, workers: int = 1,
              roots=None, recursive=None, nacherfassen: bool = True, ansagen: bool = True) -> dict:
        """Ein Sortierlauf wie ``BeehiveShell._cycle`` — mit Ergebnis statt Ausdruck."""
        from ..wachstafel import Wachstafel
        ctx = self._ctx()
        if ansagen and Wachstafel(ctx.hive).exists():
            self.con.bloom(i18n.t("r.cycle.rules"), "🐝")
        with self._koenigin(ctx.hive):
            summary = run_cycle(ctx, mode="move", roots=roots, recursive=recursive,
                                dry_run=dry_run, cache=cache, workers=workers)
            if nacherfassen and not dry_run:
                self._nacherfassen(ctx)
        if summary.errors and ctx.cfg.llm_provider == "openrouter":
            self.con.ask(i18n.t("r.cycle.keyhint"))
        ergebnis = self._summary(summary, ctx)
        ergebnis["vorschau"] = dry_run
        # Eine Vorschau zählt bewusst NICHT auf den Fortschritt — nur echte Arbeit.
        ergebnis["spiel"] = None if dry_run else self._buchen(summary)
        return ergebnis

    @auftrag("vorschau")
    def vorschau(self) -> dict:
        cache: dict = {}
        ergebnis = self._lauf(dry_run=True, cache=cache)
        self._vorschau_cache = cache if ergebnis["eingelagert"] or ergebnis["rueckfragen"] else None
        return ergebnis

    @auftrag("anwenden")
    def anwenden(self) -> dict:
        """Die Vorschau übernehmen — aus dem Cache, ohne zweite KI-Anfragen."""
        cache, self._vorschau_cache = self._vorschau_cache, None
        return self._lauf(cache=cache, ansagen=False)

    @auftrag("verwerfen", sperre=False)
    def verwerfen(self) -> dict:
        self._vorschau_cache = None
        self.con.info(i18n.t("r.preview.none"), "🧪")
        return {}

    @auftrag("sortieren")
    def sortieren(self, turbo: bool = False, bienen: int = 10) -> dict:
        workers = max(2, min(32, int(bienen or 10))) if turbo else 1
        self._vorschau_cache = None
        return self._lauf(workers=workers)

    @auftrag("importieren")
    def importieren(self, ordner: str = "") -> dict:
        src = Path(str(ordner).strip().strip('"')).expanduser()
        if not str(ordner).strip() or not src.is_dir():
            raise Ungueltig(i18n.t("r.import.nofolder", path=src))
        return self._lauf(roots=[src.resolve()], recursive=True)

    @auftrag("scan")
    def scan(self) -> dict:
        from ..sweeper import sweep
        ctx = self._ctx()
        with self._koenigin(ctx.hive):
            report = sweep(ctx, mode="index")
        if report.learned:
            self.con.honey(i18n.t("r.scan.learned", n=report.learned), "🧠")
            self._reflektieren(ctx)
        return {"neu": report.new, "geaendert": report.changed, "verschoben": report.moved,
                "verschwunden": report.missing, "fehler": report.errors, "gelernt": report.learned}

    # ------------------------------------------------------------------ #
    #  Rückfragen & Korrektur
    # ------------------------------------------------------------------ #
    def _reflektieren(self, ctx: Context) -> list:
        from ..swarm import Koenigin
        regeln = Koenigin(ctx).reflektieren()
        if regeln:
            self.con.honey(i18n.t("r.reflect.saved_n", n=len(regeln)), "📜")
        return regeln

    @auftrag("zuordnen")
    def zuordnen(self, id: str = "", kategorie: str = "", quelle: str = "assign") -> dict:
        """Eine Datei einer Wabe zuordnen — trainiert das Gedächtnis wie in der Konsole.

        ``quelle``: ``review`` (Rückfrage beantwortet), ``assign`` (Korrektur, zählt als
        beigebrachte Regel), ``analysiere`` (Umsortieren nach einer Neu-Analyse).
        """
        from ..review import apply_correction
        kategorie = str(kategorie).strip().lower()
        if not id or not kategorie or quelle not in QUELLEN:
            raise Ungueltig(i18n.t("r.assign.usage"))
        ctx = self._ctx()
        row = ctx.store.by_id(str(id)) or {}
        with self._koenigin(ctx.hive):
            alt = apply_correction(ctx, id, kategorie, mode="move", source=quelle)
        if alt is None:
            raise Ungueltig(i18n.t("r.noentry", id=id))
        self.con.honey(i18n.t("r.assign.ok", id=id, old=alt, new=kategorie))
        if quelle == "assign":
            self._reflektieren(ctx)                       # wie 'zuordnen' in der Konsole
        # Eine beantwortete Rückfrage IST eine beigebrachte Korrektur — sie zählt wie 'zuordnen'.
        stand = self._buchen(None, korrekturen=1) if quelle in ("assign", "review") else None
        return {"id": id, "datei": row.get("filename") or id, "alt": self._wabe(alt),
                "neu": self._wabe(kategorie), "spiel": stand}

    @auftrag("oeffnen", sperre=False)
    def oeffnen(self, id: str = "") -> dict:
        """„Das Auge der Biene": das Original mit dem Standardprogramm öffnen."""
        from ..review import open_file
        row = self._store(self._projekt()).by_id(str(id))
        if not row or not Path(row["path"]).exists():
            raise Ungueltig(i18n.t("r.reana.missing", name=(row or {}).get("filename", id)))
        open_file(row["path"])
        return {"datei": row["filename"]}

    @auftrag("analysieren")
    def analysieren(self, id: str = "") -> dict:
        """Wie 'analysiere': neu lesen, Titel aktualisieren — umsortiert wird erst auf Nachfrage."""
        from .. import nacherfassung
        from ..extractor import extract
        from ..heuristics import snap_category
        from ..models import Content
        from ..scout import scout
        from ..store import row_to_entry
        ctx = self._ctx()
        row = ctx.store.by_id(str(id))
        if not row:
            raise Ungueltig(i18n.t("r.noentry", id=id))
        path = Path(row["path"])
        funde = scout([path]) if path.exists() else []
        if not funde:
            raise Ungueltig(i18n.t("r.reana.missing", name=path.name))
        self.con.bloom(i18n.t("r.reana.working", name=path.name), "🔎")
        with self._koenigin(ctx.hive):
            analyse, status, grund = extract(funde[0], ctx.client, max_file_mb=ctx.seed.max_file_mb)
            if status != Status.INDEXED:
                raise Ungueltig(i18n.t("r.reana.failed", reason=grund or "?"))
            entry = row_to_entry(row)
            entry.content = Content(title=analyse.title, summary=analyse.summary,
                                    keywords=list(analyse.keywords))
            entry.funktion.aufgabe = analyse.funktion_aufgabe
            entry.zustaendigkeit = ctx.taxonomy.persons_for(entry.kategorie)
            ctx.store.save(entry)
            nacherfassung.austragen(ctx.hive, entry.id)
        self.con.honey(i18n.t("r.reana.done", title=analyse.title), "🔎")
        alt = row.get("kategorie") or "_unassigned"
        neu = snap_category(analyse.kategorie, ctx.taxonomy.categories) or "_unassigned"
        anders = neu not in (alt, "_unassigned")
        if not anders:
            self.con.info(i18n.t("r.reana.same", cat=pretty_category(alt)), "🔎")
        return {"id": entry.id, "titel": analyse.title, "alt": self._wabe(alt),
                "neu": self._wabe(neu), "umsortieren_moeglich": anders}

    # ------------------------------------------------------------------ #
    #  Rückflug, Quarantäne, Dubletten
    # ------------------------------------------------------------------ #
    @auftrag("rueckflug")
    def rueckflug(self) -> dict:
        """Die letzte Verschiebung rückgängig machen — genau wie 'rueckflug'."""
        from ..movelog import MoveLog
        hive = self._projekt()
        with self._koenigin(hive):
            last = MoveLog(hive).pop_last()
            if not last:
                self.con.info(i18n.t("r.undo.none"), "🐝")
                return {"nichts": True}
            src, dst = Path(last["dst"]), Path(last["src"])
            if src.exists():
                store = self._store(hive)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                store.update_path(last["bee_id"], str(dst))
                store.set_status(last["bee_id"], Status.NEEDS_REVIEW)
        self.con.honey(i18n.t("r.undo.ok", name=src.name, folder=dst.parent.name), "↩️")
        return {"datei": src.name, "ordner": dst.parent.name}

    @auftrag("papierkorb")
    def papierkorb(self, id: str = "") -> dict:
        from ..hive_mind import HiveMind
        from ..undertaker import undertake
        hive = self._projekt()
        with self._koenigin(hive):
            dest = undertake(hive, self._store(hive), str(id))
            if dest:
                HiveMind(hive).forget(str(id))
        if not dest:
            raise Ungueltig(i18n.t("r.noentry", id=id))
        self.con.info(i18n.t("r.trash.moved", name=dest.name), "⚰️")
        return {"datei": dest.name}

    @auftrag("zurueckholen")
    def zurueckholen(self, id: str = "") -> dict:
        from ..undertaker import resurrect
        hive = self._projekt()
        with self._koenigin(hive):
            dest = resurrect(hive, self._store(hive), str(id))
        if not dest:
            raise Ungueltig(i18n.t("r.restore.none"))
        self.con.honey(i18n.t("r.restore.ok", name=dest.name))
        return {"datei": dest.name, "ordner": dest.parent.name}

    @auftrag("dubletten_aufraeumen")
    def dubletten_aufraeumen(self) -> dict:
        """Erkannte Dubletten in die Quarantäne legen (löscht nichts) — wie 'dubletten aufraeumen'."""
        from ..movelog import MoveLog
        from ..mover import collision_safe_name
        hive = self._projekt()
        store = self._store(hive)
        moved = 0
        with self._koenigin(hive):
            rows = [r for r in store.duplicate_rows() if Path(r["path"]).exists()]
            friedhof = config.honig(hive) / "papierkorb"
            friedhof.mkdir(parents=True, exist_ok=True)
            log = MoveLog(hive)
            for r in rows:
                src = Path(r["path"])
                try:
                    dest = collision_safe_name(friedhof, src.name, r["bee_id"])
                    shutil.move(str(src), str(dest))
                    store.remove_duplicate_path(r["path"])
                    log.record(bee_id=r["bee_id"], src=str(src), dst=str(dest), action="dublette")
                    moved += 1
                except OSError as exc:
                    self.con.error(f"{src.name}: {exc}")
        self.con.honey(i18n.t("r.dup.moved", n=moved), "⚰️")
        return {"verschoben": moved}

    @auftrag("leeren")
    def leeren(self, anzahl: int = -1) -> dict:
        """Die Quarantäne ENDGÜLTIG leeren — nur, wenn die getippte Zahl stimmt (§13).

        Das ist der einzige Löschpfad des Flugbretts, und er verlangt dieselbe Bestätigung
        wie die Konsole: die Anzahl der Dateien, ausgeschrieben.
        """
        from ..undertaker import buried_candidates, bury
        hive = self._projekt()
        with self._koenigin(hive):
            kandidaten = buried_candidates(hive)
            if not kandidaten:
                self.con.info(i18n.t("r.trash.empty"), "🐝")
                return {"geloescht": 0}
            try:
                bestaetigt = int(anzahl) == len(kandidaten)
            except (TypeError, ValueError):
                bestaetigt = False
            if not bestaetigt:
                raise Ungueltig(i18n.t("web.err.confirm_count", n=len(kandidaten)))
            entfernt = bury(hive, self._store(hive))
        self.con.honey(i18n.t("r.trash.deleted", n=len(entfernt)), "⚰️")
        return {"geloescht": len(entfernt)}

    # ------------------------------------------------------------------ #
    #  Waben, Wabenbau, Schwarm
    # ------------------------------------------------------------------ #
    @auftrag("unterordner")
    def unterordner(self, kategorie: str = "", muster: str = "") -> dict:
        hive = self._projekt()
        kat = str(kategorie).strip().lower()
        if not kat:
            raise Ungueltig(i18n.t("web.err.params"))
        seed = config.load_seed(hive)
        muster = str(muster or "").strip()
        if not muster or muster.lower() in ("aus", "off", "-"):
            seed.subrouting.pop(kat, None)
            self.con.honey(i18n.t("r.sub.removed", cat=kat), "🗂️")
        else:
            seed.subrouting[kat] = muster
            self.con.honey(i18n.t("r.sub.set", cat=kat, pattern=muster), "🗂️")
        config.write_seed(hive, seed)
        return {"kategorie": kat, "muster": seed.subrouting.get(kat)}

    @auftrag("wabenbau")
    def wabenbau(self, kategorie: str = "", wer: str = "", ziel: str = "",
                 deadline: str = "") -> dict:
        """Stufe 2: aus einer Wabe ein Projekt bauen — die Rückfragen kommen aus dem Formular."""
        from ..swarm import Baubiene
        kat = str(kategorie).strip().lower()
        if not kat:
            raise Ungueltig(i18n.t("r.charter.cancel"))
        deadline = str(deadline or "").strip()
        if deadline:
            try:
                date.fromisoformat(deadline)
            except ValueError:
                raise Ungueltig(i18n.t("web.err.date"))
        ctx = self._ctx()
        if kat not in ctx.taxonomy.categories:
            self.con.ask(i18n.t("r.charter.unknown", cat=pretty_category(kat)))
        antworten = {i18n.t("bb.who"): str(wer or ""), i18n.t("bb.goal"): str(ziel or ""),
                     i18n.t("bb.deadline"): deadline}
        bau = Baubiene(ctx)
        self.con.bloom(i18n.t("r.charter.building", cat=pretty_category(kat)), "🛠️")
        ch = bau.wabenbau(kat, ask=lambda frage: antworten.get(frage, ""))
        datei = ctx.hive / pretty_category(kat) / "Bienenstock.md"
        self.con.honey(i18n.t("r.charter.built", path=datei), "🍯")
        aufgaben = bau.offene_aufgaben(kat, ch)
        if ch.deadline:
            self.con.info(i18n.t("r.charter.deadline", date=ch.deadline), "📅")
        return {"wabe": self._wabe(kat), "datei": str(datei), "aufgaben": aufgaben,
                "deadline": ch.deadline or None, "komplett": not aufgaben}

    @auftrag("kalender_melden")
    def kalender_melden(self) -> dict:
        from ..swarm import Waechterbiene
        w = Waechterbiene(self._ctx())
        faellig = w.deadlines_pruefen(innerhalb_tage=7, senden=True)
        if not faellig:
            self.con.info(i18n.t("r.cal.nothing"), "🐝")
        elif not w.kanaele:
            self.con.info(i18n.t("r.cal.noroutes"), "🧭")
        return {"faellig": len(faellig), "versendet": bool(faellig and w.kanaele)}

    @auftrag("empfehlung", sperre=False)
    def empfehlung(self, strategie: str = "para") -> dict:
        from ..recommender import PRESETS, suggest
        strategie = str(strategie).strip().lower() or "para"
        if strategie not in PRESETS:
            raise Ungueltig(i18n.t("web.err.params"))
        return {"strategie": strategie, "hinweise": suggest(self._ctx(), strategie)}

    # ------------------------------------------------------------------ #
    #  Wachstafel & Gedächtnis
    # ------------------------------------------------------------------ #
    def _regel_vorschau(self, hive: Path):
        from ..feedback import Feedback
        from ..wachstafel import Wachstafel
        wt = Wachstafel(hive)
        regeln, n = wt.vorschau(Feedback(hive), categories=self._taxonomie(hive).categories)
        return wt, regeln, n

    @auftrag("reflexion_vorschau", sperre=False)
    def reflexion_vorschau(self) -> dict:
        _wt, regeln, n = self._regel_vorschau(self._projekt())
        if not regeln:
            self.con.info(i18n.t("r.reflect.few"), "🐝")
        return {"korrekturen": n,
                "regeln": [{"stichwort": kw, "wabe": self._wabe(kat), "anzahl": cnt,
                            "statt": self._wabe(alt) if alt else None}
                           for kw, kat, cnt, alt in regeln]}

    @auftrag("reflexion_ritzen")
    def reflexion_ritzen(self) -> dict:
        """Die Regeln (neu abgeleitet, nicht vom Browser übernommen) in die Wachstafel ritzen."""
        hive = self._projekt()
        wt, regeln, n = self._regel_vorschau(hive)
        if not regeln:
            self.con.info(i18n.t("r.reflect.few"), "🐝")
            return {"geritzt": 0}
        wt.schreiben(regeln, n_corrections=n)
        self.con.honey(i18n.t("r.reflect.saved", n=len(regeln)), "📜")
        return {"geritzt": len(regeln)}

    @auftrag("wachstafel_leeren")
    def wachstafel_leeren(self) -> dict:
        from ..wachstafel import Wachstafel
        wt = Wachstafel(self._projekt())
        if not wt.exists():
            self.con.info(i18n.t("r.rules.nothing"), "🐝")
            return {"abgewischt": False}
        wt.leeren()
        self.con.info(i18n.t("r.rules.cleared"), "🧽")
        return {"abgewischt": True}

    @auftrag("gedaechtnis_uebernehmen")
    def gedaechtnis_uebernehmen(self, slug: str = "") -> dict:
        from ..hive_mind.reflection import Reflection
        from ..migrate import approve
        ctx = self._ctx()
        refl = Reflection(ctx.hive)
        p = refl.get(str(slug))
        if not p:
            raise Ungueltig(i18n.t("r.mem.noprop", slug=slug))
        with self._koenigin(ctx.hive):
            msg = approve(ctx, p)
            refl.resolve(str(slug))
        self.con.honey(msg)
        return {"text": msg}

    @auftrag("gedaechtnis_neu")
    def gedaechtnis_neu(self) -> dict:
        """'gedaechtnis neu' — alle Einträge mit dem aktuellen Modell neu einbetten."""
        from ..pipeline import reindex_memory
        ctx = self._ctx()
        if not ctx.store.query(status=Status.ASSIGNED.value):
            self.con.info(i18n.t("r.mem.empty"), "🧠")
            return {"ok": 0, "fehler": 0}
        with self._koenigin(ctx.hive):
            ok, fail = reindex_memory(ctx)
        msg = i18n.t("r.mem.rebuilt", ok=ok) + (i18n.t("r.mem.skipped", n=fail) if fail else "")
        self.con.honey(msg + ".", "🧠")
        return {"ok": ok, "fehler": fail}

    # ------------------------------------------------------------------ #
    #  Einstellungen, Modus, Werkstatt
    # ------------------------------------------------------------------ #
    @auftrag("einstellungen", sperre=False)
    def einstellungen(self, thema: str | None = None, sprache: str | None = None,
                      animationen: str | None = None, fortschritt: bool | None = None,
                      klartext: bool | None = None, arbeitsmodus: bool | None = None) -> dict:
        cfg = config.load_config()
        if thema is not None:
            if thema not in THEMEN:
                raise Ungueltig(i18n.t("web.err.params"))
            cfg.theme = thema
        if sprache is not None:
            if sprache not in ("de", "en"):
                raise Ungueltig(i18n.t("lang.usage"))
            cfg.language = sprache
            i18n.set_language(sprache)
        if arbeitsmodus is not None:
            # Ein Klick statt drei Schalter: dezent, ohne Fortschritt, Klartext zuerst.
            cfg.web_animationen = "dezent" if arbeitsmodus else "voll"
            cfg.web_fortschritt = not arbeitsmodus
            cfg.web_klartext = bool(arbeitsmodus)
        if animationen is not None:
            if animationen not in ANIMATIONEN:
                raise Ungueltig(i18n.t("web.err.params"))
            cfg.web_animationen = animationen
        if fortschritt is not None:
            cfg.web_fortschritt = bool(fortschritt)
        if klartext is not None:
            cfg.web_klartext = bool(klartext)
        config.save_config(cfg)
        return self._einstellungen(cfg)

    @auftrag("modi_pruefen", sperre=False)
    def modi_pruefen(self) -> dict:
        """Welche Modi sind gerade nutzbar? (Ollama-Probe dauert ggf. einen Timeout lang.)"""
        from ..llm.client import ollama_available
        return {"offline": True, "ollama": bool(ollama_available()),
                "openrouter": config.load_credentials() is not None}

    @auftrag("modus")
    def modus(self, name: str = "") -> dict:
        """Wie 'modus spar | lokal | cloud' — den KI-Modus DIESES Projekts umstellen."""
        from ..llm.client import ollama_available
        hive = self._projekt()
        provider = self._provider(name)
        if provider == "openrouter" and not config.load_credentials():
            raise Ungueltig(i18n.t("web.err.nokey"))
        if provider == "ollama" and not ollama_available():
            raise Ungueltig(i18n.t("mode.noollama"))
        seed = config.load_seed(hive)
        seed.provider = provider
        config.write_seed(hive, seed)
        self.con.honey(i18n.t("mode.set", name=i18n.modus_name(provider)), "🧠")
        return {"modus": provider, "modus_name": i18n.modus_name(provider)}

    @auftrag("projekt_einstellen", sperre=False)
    def projekt_einstellen(self, wache: str | None = None,
                           nacherfassung: bool | None = None) -> dict:
        hive = self._projekt()
        seed = config.load_seed(hive)
        if wache is not None:
            if wache not in WACHE:
                raise Ungueltig(i18n.t("web.err.params"))
            seed.watch = wache
        if nacherfassung is not None:
            seed.nacherfassung = bool(nacherfassung)
        config.write_seed(hive, seed)
        if wache is not None:
            self.wache.nach_seed()
        return {"wache": seed.watch, "nacherfassung": seed.nacherfassung}

    @auftrag("modell", sperre=False)
    def modell(self, name: str = "") -> dict:
        name = str(name).strip()
        if not name:
            raise Ungueltig(i18n.t("r.model.usage"))
        cfg = config.load_config()
        cfg.llm_model = NEKTAR_SORTEN.get(name.lower(), name)
        config.save_config(cfg)
        self.con.honey(i18n.t("r.model.set", model=cfg.llm_model), "🍯")
        return {"modell": cfg.llm_model}

    @auftrag("stock_check", sperre=False)
    def stock_check(self) -> dict:
        from ..doctor import run_checks
        return {"checks": [{"titel": label, "status": status, "detail": detail}
                           for label, status, detail in run_checks(self.hive)]}

    # -- BeeNara (lokales Entscheider-Modell) — wie 'beenara laden|an|aus|entfernen' --------
    @auftrag("beenara_laden")
    def beenara_laden(self) -> dict:
        """Modell von Hugging Face und Laufzeit-Pakete holen. Lang: Fortschritt kommt in Bytes.
        Ein Fehler wird gemeldet, nicht geworfen — der Stand danach sagt, was fehlt."""
        from .. import beenara
        try:
            ok = beenara.einrichten(self.con)
        except Exception as exc:          # wie in der Konsole: nie die Oberfläche abreißen
            self.con.error(i18n.t("bn.err.download", err=exc))
            ok = False
        return {"ok": ok, "beenara": self._beenara()}

    @auftrag("beenara_schalten", sperre=False)
    def beenara_schalten(self, an: bool = True) -> dict:
        cfg = config.load_config()
        cfg.beenara = bool(an)
        config.save_config(cfg)
        self.con.honey(i18n.t("bn.set.on" if an else "bn.set.off"), "🐝")
        return self._beenara()

    @auftrag("beenara_entfernen")
    def beenara_entfernen(self) -> dict:
        """Nur die eigenen Downloads unter ~/.pollysort/modelle/BeeNara — die Seite fragt vorher."""
        from .. import beenara
        s = beenara.stand()
        if not s.vollstaendig and not s.angefangen:
            self.con.info(i18n.t("bn.remove.none"), "🐝")
            return self._beenara()
        try:
            beenara.entfernen()
        except OSError as exc:
            raise Ungueltig(i18n.t("bn.remove.failed", err=exc))
        self.con.honey(i18n.t("bn.remove.done"), "🗑️")
        return self._beenara()

    # -- BeeNara Big — wie 'beenara big laden|entfernen' und 'beenara modell …' -------------
    @auftrag("beenara_big_laden")
    def beenara_big_laden(self) -> dict:
        """Big-Teil, Basismodell (~4,6 GB) und Laufzeit holen — erst nach der GPU-Prüfung."""
        from .. import beenara_big
        try:
            ok = beenara_big.einrichten(self.con)
        except Exception as exc:
            self.con.error(i18n.t("bn.err.download", err=exc))
            ok = False
        return {"ok": ok, "beenara_big": self._beenara_big()}

    @auftrag("beenara_big_entfernen")
    def beenara_big_entfernen(self) -> dict:
        """Nur die eigenen Downloads unter ~/.pollysort/modelle/BeeNara-Big — die Seite fragt vorher."""
        from .. import beenara_big
        s = beenara_big.stand()
        if not s.vollstaendig and not s.angefangen:
            self.con.info(i18n.t("bb.remove.none"), "🐝")
            return self._beenara_big()
        try:
            beenara_big.entfernen()
        except OSError as exc:
            raise Ungueltig(i18n.t("bn.remove.failed", err=exc))
        self.con.honey(i18n.t("bb.remove.done"), "🗑️")
        return self._beenara_big()

    @auftrag("beenara_modell", sperre=False)
    def beenara_modell(self, modell: str = "auto") -> dict:
        from ..entscheidung import MODELLE
        if modell not in MODELLE:
            raise Ungueltig(i18n.t("bb.usage"))
        cfg = config.load_config()
        cfg.beenara_modell = modell
        config.save_config(cfg)
        self.con.honey(i18n.t(f"bb.modus.{modell}"), "🔀")
        return self._beenara_big()

    # -- Gedächtnis-Modell über Ollama — wie 'ollama' und 'ollama laden' -----------------
    def _ollama_modelle(self) -> dict:
        from .. import ollama_laden
        staende = ollama_laden.staende()
        return {"erreichbar": staende[0].erreichbar,
                "modelle": [{"rolle": s.rolle, "modell": s.modell, "vorhanden": s.vorhanden,
                             "gb": ollama_laden.UNGEFAEHR_GB[s.rolle],
                             "zeilen": [{"art": art, "emoji": emoji, "text": text}
                                        for art, emoji, text in ollama_laden.bericht(s)]}
                            for s in staende]}

    @ansicht
    def ollama_modelle(self) -> dict:
        """Hat Ollama das Sprach- und das Gedächtnis-Modell? Fragt den lokalen Server — läuft er
        nicht, bis zu 1,5 s. Darum steht das nicht in 'werkstatt'; die Seite lädt es nach."""
        return self._ollama_modelle()

    @auftrag("ollama_modell_laden")
    def ollama_modell_laden(self, rolle: str = "gedaechtnis") -> dict:
        """Ein Ollama-Modell holen: ``sprache`` oder ``gedaechtnis``. Lang: Fortschritt kommt in
        Bytes. Ein Fehler wird gemeldet, nicht geworfen — der Stand danach sagt, was fehlt."""
        from .. import ollama_laden
        if rolle not in ollama_laden.ROLLEN:
            raise Ungueltig(i18n.t("web.err.params"))
        try:
            ok = ollama_laden.laden(self.con, ollama_laden.ROLLEN[rolle])
        except Exception as exc:          # wie bei BeeNara: nie die Oberfläche abreißen
            self.con.error(i18n.t("om.err.pull", err=exc))
            ok = False
        return {"ok": ok, "ollama": self._ollama_modelle()}

    # ------------------------------------------------------------------ #
    #  Projekte & Einrichtung
    # ------------------------------------------------------------------ #
    def _oeffnen(self, hive: Path) -> None:
        self.wache.stoppen()
        self.hive = hive
        self._vorschau_cache = None
        config.register_project(hive)
        config.remember_last_hive(hive)
        self.wache.nach_seed()

    @auftrag("wechseln", sperre=False)
    def wechseln(self, pfad: str = "") -> dict:
        p = Path(str(pfad).strip().strip('"')).expanduser()
        if not str(pfad).strip() or not p.is_dir():
            raise Ungueltig(i18n.t("r.projects.notfound", name=pfad))
        p = p.resolve()
        if not config.is_setup(p):
            return {"einrichten": True, "pfad": str(p)}
        with self._arbeit_frei():
            self._oeffnen(p)
        seed = config.load_seed(p)
        self.con.info(i18n.t("open.project", name=seed.name or p.name, path=p), "📂")
        return {"einrichten": False, "pfad": str(p), "name": seed.name or p.name}

    def _arbeit_frei(self):
        """Ein Projektwechsel darf keinen laufenden Sortierlauf unter den Füßen wegziehen."""
        if not self._arbeit.acquire(blocking=False):
            raise Beschaeftigt(i18n.t("web.err.busy"))
        return _Freigabe(self._arbeit)

    @auftrag("einrichtung_pruefen", sperre=False)
    def einrichtung_pruefen(self, pfad: str = "") -> dict:
        roh = str(pfad).strip().strip('"')
        if not roh:
            raise Ungueltig(i18n.t("web.err.path"))
        p = Path(roh).expanduser().resolve()
        cfg = config.load_config()
        return {"pfad": str(p), "existiert": p.exists(), "ist_ordner": p.is_dir(),
                "eingerichtet": p.is_dir() and config.is_setup(p),
                "lose": len(self._eingang_pfade(p)), "name": p.name,
                "schluessel": config.load_credentials() is not None,
                "standard": [self._wabe(k) for k in DEFAULT_CATEGORIES],
                "erststart": not cfg.onboarded}

    @auftrag("waben_vorschlagen")
    def waben_vorschlagen(self, pfad: str = "", modus: str = "offline") -> dict:
        """Die Spähbienen ausschicken: Dateien & vorhandene Ordner ansehen, Waben vorschlagen."""
        from ..onboarding import propose_structure
        from ..repl import _AiProbe
        p = Path(str(pfad).strip().strip('"')).expanduser().resolve()
        if not p.is_dir():
            raise Ungueltig(i18n.t("su.path.notdir", path=p))
        provider = self._provider(modus)
        cfg = config.load_config()
        cfg.llm_provider = provider
        api_key = config.load_credentials() if provider == "openrouter" else None
        probe = _AiProbe(build_client(cfg, api_key, None, []))
        self.con.bloom(i18n.t("su.scout.ai") if provider != "offline"
                       else i18n.t("su.scout.offline"), "🐝")
        vorschlag, gesamt, used_ai, vorhanden, _protokoll = propose_structure(p, ai_analyze=probe)
        if probe.errors and provider != "offline":
            if not probe.ok:
                self.con.error(i18n.t("su.scout.failed", n=probe.errors,
                                      reason=probe.last_reason or i18n.t("su.scout.unreachable")))
            else:
                self.con.info(i18n.t("su.scout.partial", bad=probe.errors,
                                     total=probe.errors + probe.ok), "⚠️")
        self._proben = list(probe.proben)
        self._proben_pfad = p
        return {"vorschlag": [{**self._wabe(k), "anzahl": n, "vorhanden": k in vorhanden}
                              for k, n in vorschlag],
                "gesamt": gesamt, "ki": bool(used_ai and provider != "offline"),
                "ki_fehler": probe.errors if provider != "offline" else 0}

    @auftrag("unterordner_vorschlagen", sperre=False)
    def unterordner_vorschlagen(self, kategorien: list | None = None,
                                modus: str = "offline") -> dict:
        kats = _kategorien(kategorien)
        provider = self._provider(modus)
        try:
            cfg = config.load_config()
            cfg.llm_provider = provider
            api_key = config.load_credentials() if provider == "openrouter" else None
            vorschlag = build_client(cfg, api_key, kats, []).suggest_subrouting(kats)
        except Exception:
            from ..heuristics import suggest_subrouting
            vorschlag = suggest_subrouting(kats)
        return {"vorschlag": [{**self._wabe(k), "muster": m} for k, m in (vorschlag or {}).items()]}

    @auftrag("einrichten")
    def einrichten(self, pfad: str = "", name: str = "", modus: str = "offline",
                   kategorien: list | None = None, unterordner: dict | None = None,
                   wache: str = "off", anlegen: bool = False) -> dict:
        """Der Einrichtungs-Assistent in einem Schritt: Name → Modus → Waben → Unterordner → Wache."""
        roh = str(pfad).strip().strip('"')
        if not roh:
            raise Ungueltig(i18n.t("web.err.path"))
        p = Path(roh).expanduser().resolve()
        if not p.exists():
            if not anlegen:
                raise Ungueltig(i18n.t("web.err.path_missing", path=p))
            try:
                p.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise Ungueltig(i18n.t("su.path.mkfail", err=exc))
        if not p.is_dir():
            raise Ungueltig(i18n.t("su.path.notdir", path=p))
        provider = self._provider(modus)
        if provider == "openrouter" and not config.load_credentials():
            raise Ungueltig(i18n.t("web.err.nokey"))
        if wache not in WACHE:
            raise Ungueltig(i18n.t("web.err.params"))
        kats = _kategorien(kategorien) or list(DEFAULT_CATEGORIES)
        sub = {str(k).strip().lower(): str(v) for k, v in (unterordner or {}).items()
               if str(k).strip().lower() in kats and str(v).strip()}
        name = str(name).strip() or p.name
        seed = HiveSeed(categories=kats, responsibility={c: [] for c in kats}, subrouting=sub,
                        name=name, provider=provider, watch=wache)
        config.write_seed(p, seed)
        angelegt = 0
        for k in kats:
            ordner = p / pretty_category(k)
            if not ordner.exists():
                ordner.mkdir(parents=True, exist_ok=True)
                angelegt += 1
        cfg = config.load_config()
        if not cfg.onboarded:
            cfg.onboarded = True
            cfg.tutorial_seen = True
            cfg.llm_provider = provider
            config.save_config(cfg)
        self._oeffnen(p)
        made = f" ({i18n.t('su.done.made', n=angelegt)})" if angelegt else ""
        watch_txt = {"off": "", "notify": " · " + i18n.t("su.done.notify"),
                     "move": " · " + i18n.t("su.done.move")}[wache]
        self.con.honey(i18n.t("su.done", name=name, n=len(kats), made=made,
                              provider=i18n.modus_name(provider), watch=watch_txt), "✅")
        self._vorwaermen(p, kats, provider)
        return {"name": name, "pfad": str(p), "waben": len(kats), "angelegt": angelegt,
                "lose": len(self._eingang_pfade(p))}

    def _vorwaermen(self, hive: Path, kats: list[str], provider: str) -> None:
        """Wie ``BeehiveShell._vorwaermen``: das Gedächtnis mit den Spähbienen-Analysen füllen."""
        if not self._proben or self._proben_pfad != hive:
            return
        from .. import vorwaermen as vw
        from ..extractor import gedaechtnis_text
        from ..hive_mind import HiveMind
        from ..llm.client import embed_model_for
        from ..models import embedding_text_for
        try:
            cfg = config.load_config()
            cfg.llm_provider = provider
            api_key = config.load_credentials() if provider == "openrouter" else None
            client = build_client(cfg, api_key, kats, [])
            gesaet = vw.vorwaermen(
                self._proben, kats, mind=HiveMind(hive), embed=client.embed,
                embed_model=embed_model_for(cfg, api_key),
                text_fuer=lambda f, a: gedaechtnis_text(client, f.path, embedding_text_for(a)))
        except Exception:
            return
        finally:
            self._proben, self._proben_pfad = [], None
        if gesaet:
            self.con.info(i18n.t("vw.done", n=sum(gesaet.values()), k=len(gesaet)), "🧠")

    @auftrag("wache_schalten", sperre=False)
    def wache_schalten(self, an: bool = True) -> dict:
        """Die Wache pausieren oder (im Modus aus der Projekt-Config) wieder aufnehmen."""
        self._projekt()
        if an:
            self.wache.nach_seed(erzwingen=True)
        else:
            self.wache.stoppen()
        return self.wache.status()

    def _wache_sortieren(self, n: int) -> bool:
        """Von der Wache gerufen: neue Dateien sofort einsortieren — nur, wenn niemand arbeitet."""
        if not self._arbeit.acquire(blocking=False):
            return False
        try:
            with self.con.sammeln():
                self.con.honey(i18n.t("r.watch.sorting", ts=time.strftime("%H:%M:%S"), n=n), "📥")
                ergebnis = self._lauf(nacherfassen=False, ansagen=False)
            self.bus.senden({"art": "wache_lauf", "ergebnis": ergebnis})
        except Exception as exc:
            self.con.error(i18n.t("r.failed", err=exc))
        finally:
            self._arbeit.release()
        return True


class _Koenigin:
    """``QueenLock`` mit einer Meldung, die der Browser versteht."""

    def __init__(self, hive: Path):
        self._lock = QueenLock(hive)

    def __enter__(self):
        try:
            self._lock.__enter__()
        except QueenLockError as exc:
            raise Gesperrt(i18n.t("web.err.locked")) from exc
        return self

    def __exit__(self, *exc) -> None:
        self._lock.__exit__(*exc)


class _Freigabe:
    def __init__(self, lock: threading.Lock):
        self._lock = lock

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        self._lock.release()


def _kategorien(roh) -> list[str]:
    """Kategorien aus dem Formular: Liste oder Komma-Text → kleingeschrieben, ohne Dubletten."""
    if isinstance(roh, str):
        roh = roh.split(",")
    out: list[str] = []
    for k in roh or []:
        k = str(k).strip().lower()
        if k and k != "_unassigned" and k not in out:
            out.append(k)
    return out


class Wache:
    """Die Flugloch-Wache des Flugbretts — wie 'wache' in der Konsole, nur im Hintergrund.

    Läuft, solange das Flugbrett offen ist und die Projekt-Config es vorsieht
    (``watch = notify | move``). Neue Dateien im Eingang werden gemeldet oder sofort
    einsortiert; nebenbei behalten die Wächterbienen die Deadlines im Blick. Bereits
    vorhandene lose Dateien fasst die Wache nicht an — wie in der Konsole zählt nur Neues.
    """

    def __init__(self, dienst: Dienst):
        self._d = dienst
        self._stopp = threading.Event()
        self._faden: threading.Thread | None = None
        self.aktion = "off"
        self.echtzeit = False

    def status(self) -> dict:
        aktiv = bool(self._faden and self._faden.is_alive())
        return {"aktiv": aktiv, "aktion": self.aktion if aktiv else "off",
                "echtzeit": self.echtzeit and aktiv}

    def nach_seed(self, *, erzwingen: bool = False) -> None:
        hive = self._d.hive
        if not hive or not config.is_setup(hive):
            return
        seed = config.load_seed(hive)
        aktion = seed.watch
        if aktion == "off" and erzwingen:
            aktion = "notify"
        self.starten(hive, aktion, max(3, seed.watch_seconds))

    def starten(self, hive: Path, aktion: str, poll: int = 10) -> None:
        self.stoppen()
        if aktion not in ("notify", "move"):
            self.aktion = "off"
            self._d.bus.senden({"art": "wache", **self.status()})
            return
        self.aktion = aktion
        self._stopp = threading.Event()
        self._faden = threading.Thread(target=self._lauf, args=(hive, aktion, poll, self._stopp),
                                       name="flugloch-wache", daemon=True)
        self._faden.start()

    def stoppen(self) -> None:
        if self._faden and self._faden.is_alive():
            self._stopp.set()
            self._faden.join(timeout=5)
        self._faden = None
        self._d.bus.senden({"art": "wache", **self.status()})

    def _beobachter(self, hive: Path, wecker: threading.Event):
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
            handler = FileSystemEventHandler()
            handler.on_any_event = lambda _e: wecker.set()
            obs = Observer()
            obs.schedule(handler, str(hive), recursive=False)
            obs.start()
            return obs
        except Exception:
            return None

    def _lauf(self, hive: Path, aktion: str, poll: int, stopp: threading.Event) -> None:
        wecker = threading.Event()
        obs = self._beobachter(hive, wecker)
        self.echtzeit = obs is not None
        self._d.bus.senden({"art": "wache", "aktiv": True, "aktion": aktion,
                            "echtzeit": self.echtzeit})
        gesehen = {str(p) for p in self._d._eingang_pfade(hive)}
        try:
            while not stopp.is_set():
                if wecker.wait(timeout=poll):
                    stopp.wait(1.5)                # Debounce: halbe Downloads ausreifen lassen
                wecker.clear()
                if stopp.is_set():
                    break
                aktuell = self._d._eingang_pfade(hive)
                neu = [p for p in aktuell if str(p) not in gesehen]
                erledigt = True
                if neu:
                    if aktion == "move":
                        erledigt = self._d._wache_sortieren(len(neu))
                    else:
                        self._d.con.ask(i18n.t("r.watch.new", ts=time.strftime("%H:%M:%S"),
                                               n=len(neu)))
                        self._d.bus.senden({"art": "eingang", "neu": len(neu)})
                if erledigt:                       # sonst beim nächsten Takt erneut versuchen
                    gesehen = {str(p) for p in self._d._eingang_pfade(hive)}
                self._deadlines(hive)
        finally:
            if obs is not None:
                try:
                    obs.stop()
                    obs.join(timeout=2)
                except Exception:
                    pass

    def _deadlines(self, hive: Path) -> None:
        try:
            if self._d.hive != hive:
                return
            from ..swarm import Waechterbiene
            Waechterbiene(self._d._ctx()).deadlines_pruefen(innerhalb_tage=7)
        except Exception:
            pass          # der Terminwächter darf die Eingangs-Wache nie stören

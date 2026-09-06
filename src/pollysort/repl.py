"""PollySort — interaktive Bienenstock-Konsole (REPL).

Der eigentliche Konsolen-Code. Nach der Installation startet ihn der Befehl ``pollysort``;
aus dem Repo heraus ``python polly.py``. Beide Wege rufen ``main()`` auf.

Ein Projekt ist ein Ordner, dessen lose Dateien der Posteingang sind — 'sortiere' (oder 's')
räumt sie in Kategorie-Ordner ein. Alles Generierte liegt versteckt in EINEM Ordner '.honig'.
Läuft offline (kostenlos), lokal (Ollama) oder online (OpenRouter, 'modus online').
"""

from __future__ import annotations

import cmd
import shlex
import sys
from pathlib import Path

from pollysort import __version__, config, i18n
from pollysort.config import DEFAULT_CATEGORIES, HiveSeed
from pollysort.console import BeeConsole, resolve_theme
from pollysort.guards import IgnoreMatcher
from pollysort.journal import Journal
from pollysort.llm import build_client
from pollysort.lock import QueenLock, QueenLockError
from pollysort.pipeline import Context, run_cycle
from pollysort.scout import walk

# Pfeiltasten-Historie & Zeilenbearbeitung. Unter Windows via pyreadline3, sonst GNU readline.
try:
    import readline  # noqa: F401
except Exception:
    readline = None  # type: ignore[assignment]

BANNER = r"""
 ___     _ _      ___          _
| _ \___| | |_  _/ __| ___ _ _| |_        🐝  PollySort
|  _/ _ \ | | || \__ \/ _ \ '_|  _|          Your learning document archivist
|_| \___/_|_|\_, |___/\___/_|  \__|          Developed by Akinara
             |__/
"""


# Wörter, mit denen der Nutzer eine laufende interaktive Aktion (Setup, Rückfrage …) verlässt,
# OHNE sie auszuführen. Zusätzlich brechen Strg-C und Strg-D/Z jede Abfrage ab.
ABORT_WORDS = {"abbruch", "abbrechen", "abbrich", "bye", "tschuess", "tschüss",
               "cancel", "abort", "esc", "escape", "exit", "quit", "zurück", "zurueck"}


class AbortAction(Exception):
    """Der Nutzer hat eine laufende interaktive Aktion abgebrochen — nichts ausführen."""


class _AiProbe:
    """Zählende Analyse-Funktion für den Waben-Vorschlag (BUG-6).

    Scheitert die KI-Analyse einer Datei (Provider down, kaputtes JSON …), wird das
    GEZÄHLT und als Fehler weitergereicht, damit ``propose_structure`` heuristisch
    weitermacht — statt „_unassigned" als vermeintliches KI-Ergebnis zu übernehmen
    und dem Nutzer eine „Sonstiges"-Taxonomie als KI-Analyse zu verkaufen.
    """

    def __init__(self, client):
        self._client = client
        self.ok = 0
        self.errors = 0
        self.last_reason: str | None = None
        #: (Finding, Analyse) je erfolgreich untersuchtem Dokument. Diese Analysen waren
        #: bisher nach dem Zählen weg — dabei sind sie genau das Wissen, mit dem sich das
        #: Gedächtnis vorwärmen lässt (siehe `_gedaechtnis_vorwaermen`).
        self.proben: list = []

    def __call__(self, finding) -> tuple[str, list[str]]:
        from pollysort.extractor import extract
        from pollysort.models import Status
        a, status, reason = extract(finding, self._client, max_file_mb=100)
        if status != Status.INDEXED:
            self.errors += 1
            self.last_reason = str(reason or "Analyse fehlgeschlagen")
            raise RuntimeError(self.last_reason)
        self.ok += 1
        self.proben.append((finding, a))
        return a.kategorie, list(a.keywords)


class BeehiveShell(cmd.Cmd):
    """Die interaktive Konsole. Verwaltet mehrere Projekte (jedes ein eigener Ordner)."""

    def __init__(self, hive: Path | None):
        super().__init__()
        _cfg = config.load_config()
        self._theme_pref = _cfg.theme                 # dark | light | auto (Nutzer-Voreinstellung)
        self.con = BeeConsole(theme=resolve_theme(_cfg.theme))
        self._static_view = _cfg.static_view          # statische Ansicht (kein Log-Scrolling)
        from pollysort import i18n
        i18n.set_language(getattr(_cfg, "language", "de"))   # UI-Sprache (de|en)
        self.hive: Path | None = hive
        self.offline = True
        self._ollama: bool | None = None      # lazy - siehe _ollama_ready()
        self._proben: list = []               # Analysen des letzten Struktur-Vorschlags
        self._sync_prompt()

    def _maybe_auto_theme(self) -> None:
        """Im Automatik-Modus das Thema anhand der Tageszeit umschalten (tags dunkel, abends hell)."""
        if self._theme_pref != "auto":
            return
        eff = resolve_theme("auto")
        if eff != self.con.theme_name:
            self.con.set_theme(eff)                   # emittiert die Farb-OSC (nur im Terminal)

    def _use_static_view(self) -> bool:
        """Statische Ansicht nur im echten Terminal (nicht bei Pipe/CI/quiet)."""
        return (self._static_view and not self.con.quiet
                and sys.stdout.isatty() and sys.stdin.isatty())

    def _render_frame(self) -> None:
        """Bildschirm leeren und die persistente Kopfzeile neu zeichnen (statische Ansicht)."""
        if not self._use_static_view():
            return
        self.con.clear()
        self.con.header(self._header_status())

    def _header_status(self) -> str:
        label = self.hive.name if self.hive else "kein Projekt"
        parts = [label]
        if self.hive:
            try:
                seed = config.load_seed(self.hive)
                parts.append(f"Modus {seed.provider}")
                n = self._inbox_count()
                parts.append(f"{n} lose" if n else "aufgeräumt")
            except Exception:
                pass
        if self._theme_pref == "auto":
            parts.append(f"Thema auto·{self.con.theme_name}")
        else:
            parts.append(f"Thema {self.con.theme_name}")
        return "  ·  ".join(parts)

    def _sync_prompt(self) -> None:
        label = self.hive.name if self.hive else "kein Projekt"
        self.prompt = f"🐝 {label} ▸ "

    # ------------------------------------------------------------------ #
    #  REPL-Schleife (Pfeiltasten-Historie, Strg-C bricht nur die Zeile ab)
    # ------------------------------------------------------------------ #
    def cmdloop(self, intro=None) -> None:  # type: ignore[override]
        self.preloop()
        hist = self._load_history()
        stop = False
        while not stop:
            try:
                line = input(self.prompt)
            except EOFError:                 # Strg-D / Strg-Z → sauber beenden
                self.con.raw("")
                line = "exit"
            except KeyboardInterrupt:        # Strg-C → nur die Zeile verwerfen, weiterlaufen
                self.con.raw("^C")
                continue
            # UTF-8-BOM tolerieren (erste Zeile aus Pipes/Skripten, z. B. PowerShell).
            # Je nach stdin-Encoding kommt er als U+FEFF ODER als die rohen Bytes
            # "\xef\xbb\xbf" (dekodiert zu 'ï»¿') an — beide Formen abstreifen.
            for _bom in ("﻿", "ï»¿"):
                if line.startswith(_bom):
                    line = line[len(_bom):]
            line = self.precmd(line)
            self._maybe_auto_theme()      # Automatik: Thema ggf. an die Tageszeit anpassen
            # Statische Ansicht: vor der Ausgabe Bildschirm leeren + Kopfzeile neu zeichnen,
            # damit sich die Konsole selbst aktualisiert statt endlos nach oben zu scrollen.
            if line.strip():
                self._render_frame()
            try:
                stop = self.onecmd(line)
                stop = self.postcmd(stop, line)
            except AbortAction:
                # Nutzer hat die Aktion (z. B. Setup) abgebrochen — sauber verlassen.
                self.con.info("Abgebrochen — nichts ausgeführt.", "🐝")
                stop = False
            except Exception as exc:
                # Ein fehlerhafter Befehl darf nie die ganze Konsole beenden (§16) —
                # melden und weitermachen. (Strg-C ist BaseException und bleibt außen.)
                self.con.error(f"Befehl fehlgeschlagen: {exc}")
                stop = False
        self.postloop()
        self._save_history(hist)

    def _load_history(self) -> Path | None:
        if readline is None:
            return None
        path = config.POLLYSORT_HOME / "history"
        try:
            config.POLLYSORT_HOME.mkdir(parents=True, exist_ok=True)
            if path.exists():
                readline.read_history_file(str(path))
            readline.set_history_length(500)
        except Exception:
            return None
        return path

    def _save_history(self, path: Path | None) -> None:
        if readline is not None and path is not None:
            try:
                readline.write_history_file(str(path))
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    #  Start & Hilfe
    # ------------------------------------------------------------------ #
    def preloop(self) -> None:
        self.con.raw(BANNER, style="honey")
        try:
            self._global_onboarding()          # einmalig: Sprache → Darstellung → KI
            # Erst NACH der Sprachwahl — sonst stünde die erste Zeile in einer Sprache,
            # die der Nutzer soeben abgewählt hat.
            self.con.info(i18n.t("start.hint", version=__version__), "🐝")
            if self.hive is None:
                self._first_run()
            else:
                self._open_project(self.hive, greet=True)
        except AbortAction:
            # Nutzer hat die Ersteinrichtung abgebrochen — Konsole trotzdem starten.
            self.con.info(i18n.t("setup.aborted"), "🐝")

    def _global_onboarding(self) -> None:
        """Einmalige Grundeinrichtung VOR den Projekten: Sprache → Darstellung → KI.

        Der Ablauf selbst liegt in :mod:`pollysort.firstrun` (dort ohne Terminal testbar);
        hier wird nur verdrahtet und das Ergebnis persistiert. Die Flugrouten-Frage ist
        bewusst NICHT mehr Teil des Erststarts: ohne Projekt gibt es noch keine Deadlines,
        über die jemand benachrichtigt werden könnte — der Hinweis steht jetzt im Überblick.
        """
        from pollysort import firstrun
        cfg = config.load_config()
        if cfg.onboarded:
            # Bestandsnutzer: Einrichtung steht schon — nur die ersten Handgriffe nachreichen.
            if not getattr(cfg, "tutorial_seen", False):
                firstrun.show_next_steps(self.con)
                cfg.tutorial_seen = True
                config.save_config(cfg)
            return
        res = firstrun.run(
            self.con, self._ask,
            ollama_probe=self._ollama_ready,
            has_key=lambda: config.load_credentials() is not None,
            save_key=self._save_key,
            apply_theme=self._apply_theme,
        )
        # Erst nach dem vollständigen Durchlauf schreiben — ein Abbruch hinterlässt nichts.
        cfg = config.load_config()
        cfg.language = res.language
        cfg.theme = res.theme
        cfg.llm_provider = res.provider
        cfg.onboarded = True
        cfg.tutorial_seen = True
        config.save_config(cfg)
        self.offline = res.provider == "offline"

    def _first_run(self) -> None:
        """Kein Projekt hinterlegt → Erst-Einrichtung, beginnend mit dem Pfad."""
        self.con.info(i18n.t("firstrun.welcome"), "🐝")
        self.con.raw("   " + i18n.t("firstrun.what"))
        self._new_project()

    # Befehle, die auch OHNE aktives Projekt erlaubt sind.
    _NO_PROJECT_OK = {"neu", "wechsel", "ordner", "projekte", "setup",
                      "home", "start", "zuhause", "doctor",
                      "modell", "modellwechsel", "flugrouten", "api",
                      "schluessel", "key", "apikey",
                      "thema", "theme", "farbe", "ansicht", "view",
                      "sprache", "language", "lang",
                      # englische Aliase
                      "new", "switch", "projects", "mode", "model", "routes",
                      "hilfe", "help", "exit", "quit", "eof", ""}

    def precmd(self, line: str) -> str:
        """Ohne aktives Projekt nur Projekt-Befehle zulassen (statt eines Fehlers)."""
        name = line.strip().split(" ", 1)[0].lower() if line.strip() else ""
        if self.hive is None and name not in self._NO_PROJECT_OK:
            self.con.ask("Kein Projekt aktiv. 'neu' legt eins an, 'wechsel' öffnet ein bestehendes.")
            return ""
        return line

    def _open_project(self, hive: Path, *, greet: bool = False) -> None:
        """Ein Projekt öffnen: bekanntes laden, neues per Assistent einrichten."""
        self.hive = hive
        self._sync_prompt()
        if config.is_setup(hive):
            seed = config.load_seed(hive)
            self.offline = seed.provider == "offline"
            config.register_project(hive)
            config.remember_last_hive(hive)
            self.con.info(f"Projekt: {seed.name or hive.name}  ·  {hive}", "📂")
            self.con.info(f"Modus: {seed.provider} · Kategorien: {', '.join(seed.categories)}",
                          "🧠")
            self._show_inbox()
            # Eingangs-Verhalten beim Öffnen anwenden (§ Überwachung).
            if seed.watch == "move" and self._inbox_count():
                self.con.info("Sortiere neue Dateien …", "⚡")
                self._cycle(mode="move")
            elif seed.watch != "off" and self._inbox_count():
                self.con.info(f"Überwachung aktiv ({seed.watch}). 'wache' für Dauerbetrieb.", "👀")
        else:
            self.con.info(f"Ordner: {hive}", "📂")
            self.con.ask("Dieses Projekt ist noch nicht eingerichtet.")
            ans = self._ask("Jetzt einrichten? [J/n]: ")
            if ans.strip().lower() in ("", "j", "ja", "y"):
                self._run_setup(hive)
            else:
                self.offline = True
                self.con.info("Ok. 'setup' startet die Einrichtung, wann du willst.", "🐝")
                if greet:
                    self._show_inbox()

    def _show_inbox(self) -> None:
        from pollysort import i18n
        n = self._inbox_count()
        if n:
            self.con.honey(i18n.t("inbox.some", n=n), "📥")
        else:
            self.con.info(i18n.t("inbox.empty"), "📭")

    def _inbox_paths(self) -> list[Path]:
        if not self.hive:
            return []
        try:
            return walk([self.hive], IgnoreMatcher(self.hive), recursive=False)
        except Exception:
            return []

    def _inbox_count(self) -> int:
        return len(self._inbox_paths())

    def emptyline(self) -> bool:
        return False

    def default(self, line: str) -> None:
        self.con.error(f"Unbekannt: {line!r}. 'hilfe' zeigt alle Befehle.")

    def do_hilfe(self, _arg: str) -> None:
        """Alle Befehle mit Kurzbeschreibung anzeigen."""
        from rich.table import Table
        from rich.text import Text

        # Die wichtigsten Kürzel gleich oben — der Rest ist gruppiert darunter.
        from pollysort import i18n
        self.con.info(i18n.t("help.shortcuts"), "⌨️")
        groups = {
            "🐝 Täglich benötigt": [
                ("home  (start)", "Zurück zum Start-/Zuhause-Bildschirm (Übersicht)"),
                ("sortiere  (s)", "Lose Dateien in Kategorie-Ordner einräumen"),
                ("vorschau  (v)", "Erst zeigen, dann direkt anwenden [J/n]"),
                ("rueckfragen (r)", "Unsichere Fälle schnell selbst zuordnen"),
                ("status", "Was liegt hier, was ist schon sortiert?"),
                ("liste [kategorie]", "Sortierte Einträge auflisten"),
                ("suche <wort>", "Nach Stichwort suchen"),
            ],
            "🎯 Für bestimmte Anwendungsfälle": [
                ("wache", "Eingang in Echtzeit überwachen (watchdog)"),
                ("sortiere turbo [N]", "Ultra Swarm — viele Dateien parallel"),
                ("scan  (sweep)", "Ganzen Ordner prüfen; aus manuellen Moves lernen"),
                ("importiere <ordner>", "Aus einem anderen Ordner hierher sortieren"),
                ("zuordnen <id> <kat>", "Zuordnung korrigieren (Gedächtnis lernt)"),
                ("unterordner <kat> <muster>", "Dynamische Unterordner, z. B. {jahr}/{monat}"),
                ("dubletten [aufraeumen]", "Erkannte Dubletten zeigen / in die Quarantäne"),
                ("papierkorb <id> / leeren", "In Quarantäne / endgültig löschen"),
                ("zurueckholen <id> · rueckflug", "Aus Quarantäne zurück · letzten Move rückgängig"),
                ("fortschritt", "Wie weit ist dein Bienenstock? Stufe, Abzeichen, Serie"),
                ("wabenbau [kategorie]", "Aus einer Wabe ein Projekt bauen (Bienenstock.md)"),
                ("kalender [melden] · schwarm", "Deadlines / Schwarm-Überblick"),
                ("empfehlung [para|..]", "Ablage-Strategie + Hinweise"),
            ],
            "🛠️ Für Profis": [
                ("neu [pfad] · wechsel [nr]", "Projekt anlegen · zu anderem wechseln"),
                ("projekte · setup", "Alle Projekte · aktuelles neu einrichten"),
                ("modus <offline|ollama|online>", "KI-Backend für dieses Projekt"),
                ("modell [name|liste]", "OpenRouter-Modell wechseln (Nektar-Sorte)"),
                ("schluessel [test|setzen]", "OpenRouter-Schlüssel prüfen / erneuern"),
                ("flugrouten [setup|test]", "Discord/E-Mail der Wächterbienen (opt-in)"),
                ("reflektiere · wachstafel", "Meta-Learning: Regeln ableiten / zeigen"),
                ("gedaechtnis [approve|neu]", "Kategorien/Vorschläge · 'neu' = Reindex n. Modellwechsel"),
                ("person <name> <kat,..>", "Zuständigkeit im Hintergrund setzen"),
                ("doctor", "Health-Check: Python, KI-Provider, Datenbank, Gedächtnis"),
                ("sprache <de|en>", "UI-Sprache umschalten (language / lang)"),
                ("thema [dunkel|hell|auto]", "Dark/Light; 'auto' = tags dunkel, abends hell"),
                ("ansicht [statisch|log]", "Statische Selbst-Ansicht oder klassisches Log"),
                ("hilfe / exit", "Diese Hilfe / Konsole verlassen"),
            ],
        }
        for title, rows in groups.items():
            self.con.rule(title)
            table = Table(show_header=False, box=None, padding=(0, 3, 0, 0))
            table.add_column(no_wrap=True)
            table.add_column(overflow="fold")
            for name, desc in rows:
                table.add_row(Text(name, style="honey"), Text(desc))
            self.con.raw(table)
        self.con.info("Tipp: In Abfragen (z. B. Setup) bricht 'abbruch' oder 'bye' die Aktion ab.",
                      "🐝")

    do_help = do_hilfe

    def do_exit(self, _arg: str) -> bool:
        """Konsole verlassen."""
        self.con.info(i18n.t("bye"), "🐝")
        return True

    do_quit = do_exit

    def do_EOF(self, _arg: str) -> bool:
        self.con.raw("")
        return self.do_exit(_arg)

    # ------------------------------------------------------------------ #
    #  Kern-Aktionen
    # ------------------------------------------------------------------ #
    def do_sortiere(self, arg: str) -> None:
        """sortiere [turbo [N]] — lose Dateien in Kategorie-Ordner einräumen.

        'sortiere turbo' aktiviert den Ultra Swarm: die KI-Analysen laufen parallel
        (Standard 10 Bienen, 'turbo N' setzt die Anzahl) — für viele Dateien deutlich
        schneller, gleiches Ergebnis.
        """
        workers = 1
        parts = arg.split()
        if parts and parts[0].lower() in ("turbo", "swarm", "ultra"):
            workers = 10
            if len(parts) > 1 and parts[1].isdigit():
                workers = max(2, int(parts[1]))
        self._cycle(mode="move", workers=workers)

    do_s = do_sortiere

    def do_vorschau(self, _arg: str) -> None:
        """vorschau — zeigen, wohin sortiert würde, und direkt anwenden können.

        Die Analyse wird zwischengespeichert: Wer nach der Vorschau „Anwenden" wählt,
        zahlt KEINE zweiten KI-Anfragen — es wird nur noch verschoben & gespeichert.
        """
        cache: dict = {}
        summary = self._cycle(mode="move", dry_run=True, cache=cache)
        if not summary or not getattr(summary, "stored", 0):
            return          # nichts würde einsortiert → nichts anzuwenden
        if self._ja("Änderungen jetzt anwenden? [J/n]: "):
            self._cycle(mode="move", dry_run=False, cache=cache, announce=False)
        else:
            self.con.info("Nichts verändert — die Vorschau bleibt eine Vorschau.", "🧪")

    do_v = do_vorschau

    def do_erfasse(self, _arg: str) -> None:
        """erfasse — nur katalogisieren (Kategorie-Vorschlag), nichts verschieben."""
        self._cycle(mode="index")

    def do_importiere(self, arg: str) -> None:
        """importiere <ordner> — Dateien aus einem anderen Ordner hierher sortieren."""
        folder = arg.strip().strip('"')
        if not folder:
            self.con.ask("Nutzung: importiere <ordner>")
            return
        src = Path(folder).expanduser().resolve()
        if not src.is_dir():
            self.con.error(f"Kein Ordner: {src}")
            return
        self._cycle(mode="move", roots=[src], recursive=True)

    def do_scan(self, _arg: str) -> None:
        """scan — den ganzen Ordner auf manuelle Änderungen prüfen (verschoben/geändert/neu)
        und aus manuellen Verschiebungen ZWISCHEN Waben lernen (Selbstlern-Schleife)."""
        ctx = self._ctx()
        from pollysort.sweeper import sweep
        try:
            with QueenLock(ctx.hive):
                report = sweep(ctx, mode="index")
        except QueenLockError as exc:
            self.con.error(str(exc))
            return
        # Hast du Dateien von Hand umsortiert, leitet die Königin daraus Regeln ab.
        if report.learned:
            self.con.honey(f"{report.learned} manuelle Verschiebung(en) als Korrektur "
                           "verstanden — die Königin lernt daraus.", "🧠")
            self._reflektieren(ctx, laut=False)

    do_sweep = do_scan

    def do_unterordner(self, arg: str) -> None:
        """unterordner [<kategorie> <muster|aus>] — dynamische Unterordner je Kategorie.

        Platzhalter: {jahr}/{monat}/{tag}. Beispiel: 'unterordner rechnung {jahr}/{monat}'
        legt Rechnungen künftig nach Jahr/Monat ab. Ohne Argumente: aktuelle Regeln zeigen.
        """
        seed = config.load_seed(self.hive)
        parts = arg.split()
        if not parts:
            if not seed.subrouting:
                self.con.info("Keine dynamischen Unterordner gesetzt. Beispiel: "
                              "unterordner rechnung {jahr}/{monat}", "🗂️")
                return
            self.con.rule("Dynamische Unterordner")
            for k, v in seed.subrouting.items():
                self.con.raw(f"    {k:<22} → {v}")
            return
        if len(parts) < 2:
            self.con.ask("Nutzung: unterordner <kategorie> <muster|aus>  "
                         "(z. B. rechnung {jahr}/{monat})")
            return
        kat = parts[0].strip().lower()
        muster = " ".join(parts[1:]).strip()
        if muster.lower() in ("aus", "off", "-"):
            seed.subrouting.pop(kat, None)
            self.con.honey(f"Unterordner für '{kat}' entfernt.", "🗂️")
        else:
            seed.subrouting[kat] = muster
            self.con.honey(f"'{kat}' → {muster}  (greift beim nächsten Sortieren)", "🗂️")
        config.write_seed(self.hive, seed)

    def _cycle(self, *, mode: str, roots=None, recursive=None, dry_run: bool = False,
               cache: dict | None = None, announce: bool = True, workers: int = 1):
        """Einen Sortier-Lauf ausführen und die Summary zurückgeben (oder None bei Lock-Fehler)."""
        ctx = self._ctx()
        from pollysort.wachstafel import Wachstafel
        if announce and Wachstafel(self.hive).exists():
            self.con.bloom("Spurbienen fliegen aus (unter Beachtung der gelernten "
                           "Wachstafel-Regeln) …", "🐝")
        try:
            with QueenLock(ctx.hive):
                summary = run_cycle(ctx, mode=mode, roots=roots, recursive=recursive,
                                    dry_run=dry_run, cache=cache, workers=workers)
        except QueenLockError as exc:
            self.con.error(str(exc))
            return None
        # Häufen sich Fehler im OpenRouter-Modus, ist meist der Schlüssel abgelaufen —
        # klaren Weg zum Erneuern zeigen, statt es als „nicht erreichbar" stehen zu lassen.
        if getattr(summary, "errors", 0) and ctx.cfg.llm_provider == "openrouter":
            self.con.ask("Falls der OpenRouter-Schlüssel abgelaufen ist: 'schluessel test' "
                         "prüft ihn, 'schluessel setzen' erneuert ihn.")
        if not dry_run:
            # Eine Vorschau ist nebenwirkungsfrei — sie zählt bewusst NICHT auf den
            # Fortschritt ein. Gezählt wird nur, was wirklich einsortiert wurde.
            self._fortschritt_buchen(summary)
        return summary

    def _fortschritt_buchen(self, summary, *, korrekturen: int = 0) -> None:
        """Den Bienenstock wachsen lassen und neue Abzeichen feiern.

        Läuft strikt nebenwirkungsarm: Wenn hier etwas schiefgeht, darf das den
        Sortierlauf nicht nachträglich beschädigen — der ist längst fertig.
        """
        from pollysort import spiel
        from pollysort.wachstafel import Wachstafel
        try:
            sortiert = int(getattr(summary, "stored", 0) or 0) if summary else 0
            waben = len(getattr(summary, "by_category", {}) or {}) if summary else 0
            try:
                regeln = len(Wachstafel(self.hive).rules())
            except Exception:
                regeln = None
            stand, neue, aufgestiegen = spiel.nach_lauf(
                self.hive, sortiert=sortiert, korrekturen=korrekturen,
                regeln=regeln, waben=waben or None,
                eingang_leer=self._inbox_count() == 0)
            for schluessel in neue:
                self.con.honey(i18n.t("spiel.neu",
                                      name=i18n.t(f"spiel.abzeichen.{schluessel}"),
                                      grund=i18n.t(f"spiel.grund.{schluessel}")), "🏅")
            if aufgestiegen:
                self.con.celebrate(i18n.t("spiel.aufgestiegen",
                                          stufe=i18n.t(f"spiel.stufe.{stand.stufe}")))
        except Exception:
            pass

    def _start_inbox_observer(self, wake):
        """watchdog-Observer auf dem Eingangsordner (nur Root). None, wenn nicht verfügbar."""
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except Exception:
            return None
        try:
            handler = FileSystemEventHandler()
            handler.on_any_event = lambda _e: wake.set()   # jede Änderung weckt die Wache
            obs = Observer()
            obs.schedule(handler, str(self.hive), recursive=False)   # nur der Eingang
            obs.start()
            return obs
        except Exception:
            return None

    def do_wache(self, arg: str) -> None:
        """wache [notify|move] — Eingang in Echtzeit überwachen (watchdog, Poll-Fallback).

        Neue Dateien im Eingang werden sofort erkannt (watchdog) und gemeldet bzw. sortiert.
        Ist watchdog nicht verfügbar, greift ein Poll-Rhythmus. Strg-C beendet.
        """
        import threading
        import time
        seed = config.load_seed(self.hive)
        action = arg.strip().lower() or (seed.watch if seed.watch != "off" else "notify")
        if action not in ("notify", "move"):
            action = "notify"
        poll = max(3, seed.watch_seconds)
        verb = "sortiere sofort" if action == "move" else "melde"

        wake = threading.Event()
        observer = self._start_inbox_observer(wake)
        modus = "Echtzeit (watchdog)" if observer is not None else f"Poll alle {poll}s"
        self.con.honey(f"Wache aktiv — {modus}, {verb}. Strg-C beendet.", "🟢")
        self._deadlines_wachen()          # beim Start einmal die Deadlines prüfen
        seen = {str(p) for p in self._inbox_paths()}
        try:
            while True:
                # Sofort bei FS-Event weiter; sonst spätestens nach 'poll' (Fallback + Deadlines).
                fired = wake.wait(timeout=poll)
                wake.clear()
                if fired:
                    time.sleep(1.5)        # Debounce: halbfertige Downloads/Kopien ausreifen
                    wake.clear()
                new = [p for p in self._inbox_paths() if str(p) not in seen]
                if new:
                    ts = time.strftime("%H:%M:%S")
                    if action == "move":
                        self.con.honey(f"[{ts}] {len(new)} neue Datei(en) → sortiere …", "📥")
                        self._cycle(mode="move")
                    else:
                        self.con.ask(f"[{ts}] {len(new)} neue Datei(en) im Eingang "
                                     f"— 'sortiere' zum Einräumen")
                seen = {str(p) for p in self._inbox_paths()}
                self._deadlines_wachen()   # Wächterbienen behalten auch Deadlines im Blick
        except KeyboardInterrupt:
            self.con.raw("")
            self.con.info("Wache beendet.", "🐝")
        finally:
            if observer is not None:
                try:
                    observer.stop()
                    observer.join(timeout=2)
                except Exception:
                    pass

    def _deadlines_wachen(self) -> None:
        """Fällige Deadlines prüfen; bei aktiven Flugrouten echt versenden (Anti-Spam via Flag)."""
        try:
            from pollysort.swarm import Waechterbiene
            Waechterbiene(self._ctx()).deadlines_pruefen(innerhalb_tage=7)
        except Exception:
            pass          # der Terminwächter darf die Eingangs-Wache nie stören

    # ------------------------------------------------------------------ #
    #  Anzeigen
    # ------------------------------------------------------------------ #
    def do_home(self, _arg: str) -> None:
        """home — zurück zum Start-/Zuhause-Bildschirm: Banner (Name) + aktuelles Projekt
        auf einen Blick + alle Projekte. Wie direkt nach dem Öffnen des Tools.

        Funktioniert aus jeder Ebene und bricht keinen Teil ab, wenn einer scheitert.
        """
        from pollysort import i18n
        # Wie am Anfang: Banner (Name) zeigen, damit 'home' sich wie der Startbildschirm anfühlt.
        self.con.raw(BANNER, style="honey")
        self.con.info(f"v{__version__} · 'hilfe' zeigt alle Befehle", "🐝")
        self.con.rule(i18n.t("home.title"))
        if self.hive is None:
            self.con.info(i18n.t("home.noproject"), "🐝")
        else:
            seed = config.load_seed(self.hive)
            self.con.info(f"Projekt: {seed.name or self.hive.name}  ·  {self.hive}", "📂")
            self.con.info(f"Modus: {seed.provider} · Überwachung: {seed.watch}", "🧠")
            try:
                from pollysort.store import Store
                counts = Store(self.hive).status_counts()
            except Exception:
                counts = {}
            inbox = self._inbox_count()
            if inbox:
                self.con.honey(f"{inbox} lose Datei(en) → 'sortiere'", "📥")
            sorted_n = counts.get("assigned", 0) + counts.get("indexed", 0)
            if sorted_n:
                self.con.honey(f"{sorted_n} Datei(en) sortiert/erfasst", "🍯")
            if counts.get("needs_review"):
                self.con.ask(f"{counts['needs_review']} unsicher → 'rueckfragen'")
            if counts.get("error"):
                self.con.error(f"{counts['error']} mit Fehler → 'liste error'")
            # Anstehende Deadlines des Schwarms (nie den Home-Überblick abbrechen lassen).
            try:
                from pollysort.swarm import Koenigin
                faellig = Koenigin(self._ctx()).schwarm_status().get("deadlines_faellig", 0)
                if faellig:
                    self.con.ask(f"{faellig} Deadline(s) in ≤ 7 Tagen → 'kalender'")
            except Exception:
                pass
        # Projektliste (nummeriert, aktives markiert) — der Sprungbrett-Teil.
        try:
            projects = config.list_projects()
            if projects:
                self._print_projects(projects)          # zieht die 'Projekte'-Überschrift selbst
                self.con.info("Wechseln:  wechsel <nr>   ·   Neu:  neu <pfad>   ·   Hilfe:  hilfe",
                              "🐝")
        except Exception:
            pass

    do_start = do_home
    do_zuhause = do_home

    def do_status(self, _arg: str) -> None:
        """status — Überblick: lose Dateien, sortierte Einträge, offene Fälle."""
        from pollysort.store import Store
        counts = Store(self.hive).status_counts()
        seed = config.load_seed(self.hive)
        self.con.info(f"Ordner: {self.hive}", "📂")
        self.con.info(f"Modus: {seed.provider} · Überwachung: {seed.watch}", "🧠")
        inbox = self._inbox_count()
        if inbox:
            self.con.honey(f"{inbox} lose Datei(en) → 'sortiere'", "📥")
        sorted_n = counts.get("assigned", 0) + counts.get("indexed", 0)
        if sorted_n:
            self.con.honey(f"{sorted_n} Datei(en) sortiert/erfasst", "🍯")
        if counts.get("needs_review"):
            self.con.ask(f"{counts['needs_review']} unsicher → 'rueckfragen'")
        if counts.get("error"):
            self.con.error(f"{counts['error']} mit Fehler → 'liste error'")
        if not (inbox or sorted_n or counts):
            self.con.info("Noch nichts passiert. Leg Dateien hier ab und tippe 'sortiere'.", "🐝")

    def do_liste(self, arg: str) -> None:
        """liste [kategorie|status] — sortierte Einträge auflisten."""
        from pollysort.models import Status
        from pollysort.store import Store
        arg = arg.strip().lower()
        store = Store(self.hive)
        if arg in {s.value for s in Status}:
            self._table(store.query(status=arg))
        else:
            self._table(store.query(kategorie=arg or None))

    do_l = do_liste

    def do_suche(self, arg: str) -> None:
        """suche <wort> — in Titel/Keywords/Zusammenfassung suchen."""
        if not arg.strip():
            self.con.ask("Nutzung: suche <wort>")
            return
        from pollysort.store import Store
        self._table(Store(self.hive).query(keyword=arg.strip()))

    # ------------------------------------------------------------------ #
    #  Rückfragen & Korrektur
    # ------------------------------------------------------------------ #
    def do_rueckfragen(self, _arg: str) -> None:
        """rueckfragen — unsichere Dateien gebündelt & interaktiv zuordnen."""
        ctx = self._ctx()
        from pollysort.review import review
        try:
            with QueenLock(ctx.hive):
                review(ctx, mode="move")
        except QueenLockError as exc:
            self.con.error(str(exc))

    do_r = do_rueckfragen

    def do_zuordnen(self, arg: str) -> None:
        """zuordnen <id> <kategorie> — Zuordnung korrigieren (trainiert das Gedächtnis)."""
        parts = shlex.split(arg)
        if len(parts) != 2:
            self.con.ask("Nutzung: zuordnen <id> <kategorie>")
            return
        ctx = self._ctx()
        from pollysort.review import apply_correction
        old = apply_correction(ctx, parts[0], parts[1], mode="move", source="assign")
        if old is None:
            self.con.error(f"Kein Eintrag '{parts[0]}'.")
        else:
            self.con.honey(f"{parts[0]}: {old} → {parts[1].lower()} ✓ (Gedächtnis lernt)")
            self._reflektieren(ctx, laut=False)   # Wachstafel gleich mit-aktualisieren
            # Dem Werkzeug etwas beizubringen ist echte Arbeit und zählt entsprechend.
            self._fortschritt_buchen(None, korrekturen=1)

    def _reflektieren(self, ctx, *, laut: bool = True) -> list:
        """Königin liest die Korrekturen und ritzt Regeln in die Wachstafel (RISE + ACE)."""
        from pollysort.swarm import Koenigin
        if laut:
            self.con.bloom("Die Königin studiert die Korrekturen und ritzt neue Regeln "
                           "in die Wachstafel …", "🐝")
        regeln = Koenigin(ctx).reflektieren()
        if regeln:
            self.con.honey(f"Wachstafel aktualisiert — {len(regeln)} gelernte Regel(n). "
                           f"Ansehen: 'wachstafel'.", "📜")
        elif laut:
            self.con.info("Noch zu wenig Nektar-Feedback für neue Regeln — korrigiere weiter "
                          "mit 'zuordnen'.", "🐝")
        return regeln

    def do_reflektiere(self, _arg: str) -> None:
        """reflektiere — Regeln aus deinen Korrekturen zeigen und nach Rückfrage ritzen."""
        ctx = self._ctx()
        from pollysort.feedback import Feedback
        from pollysort.wachstafel import Wachstafel
        wt = Wachstafel(ctx.hive)
        rules, n = wt.vorschau(Feedback(ctx.hive), categories=ctx.taxonomy.categories)
        if not rules:
            self.con.info("Noch zu wenig Nektar-Feedback für neue Regeln — korrigiere weiter "
                          "mit 'zuordnen'.", "🐝")
            return
        self.con.rule("Vorgeschlagene Regeln")
        for kw, kat, cnt, alt in rules:
            alt_hint = f"  (statt „{alt}“)" if alt else ""
            self.con.raw(f"    • [honey]{kw}[/honey] → Wabe [honey]{kat}[/honey]"
                         f"  _(aus {cnt} Korrektur(en){alt_hint})_")
        if self._ja("Diese Regeln in die Wachstafel ritzen? [J/n]: "):
            wt.schreiben(rules, n_corrections=n)
            self.con.honey(f"Wachstafel aktualisiert — {len(rules)} Regel(n). "
                           "Ansehen: 'wachstafel'.", "📜")
        else:
            self.con.info("Verworfen — die Wachstafel bleibt unverändert.", "🐝")

    do_reflektieren = do_reflektiere

    def do_wachstafel(self, arg: str) -> None:
        """wachstafel [leeren] — gelernte Projekt-Regeln zeigen (oder verwerfen)."""
        from pollysort.wachstafel import Wachstafel
        wt = Wachstafel(self.hive)
        if arg.strip().lower() in ("leeren", "loeschen", "löschen", "clear"):
            if not wt.exists():
                self.con.info("Es gibt noch keine Wachstafel zum Abwischen.", "🐝")
                return
            if not self._ja("Alle gelernten Regeln wirklich verwerfen? [j/N]: "):
                self.con.info("Abgebrochen — die Wachstafel bleibt.", "🐝")
                return
            wt.leeren()
            self.con.info("Wachstafel abgewischt — die gelernten Regeln sind verworfen.", "🧽")
            return
        if not wt.exists():
            self.con.info("Noch keine Wachstafel. 'reflektiere' ritzt Regeln aus deinen "
                          "Korrekturen ('zuordnen').", "📜")
            return
        self.con.rule("Wachstafel — gelernte Projekt-Regeln")
        for line in wt.text().splitlines():
            self.con.raw(line)

    do_regeln = do_wachstafel

    def do_doctor(self, _arg: str) -> None:
        """doctor — Health-Check: Interpreter, KI-Provider, Datenbank, Extras, Gedächtnis."""
        from pollysort.doctor import run_checks
        icon = {"ok": "✅", "warn": "⚠️", "fail": "❌"}
        self.con.rule("🩺 Doctor")
        for label, status, detail in run_checks(self.hive):
            self.con.raw(f"  {icon.get(status, '•')}  {label:<12} {detail}")

    def do_sprache(self, arg: str) -> None:
        """sprache <de|en> — UI-Sprache umschalten (auch: language, lang)."""
        from pollysort import i18n
        choice = arg.strip().lower()
        if choice not in ("de", "en", "deutsch", "english", "englisch"):
            self.con.ask(i18n.t("lang.usage"))
            return
        lang = "en" if choice.startswith("en") else "de"
        i18n.set_language(lang)
        cfg = config.load_config()
        cfg.language = lang
        config.save_config(cfg)
        self.con.honey(i18n.t("lang.set"), "🌍")

    do_language = do_sprache
    do_lang = do_sprache

    def do_person(self, arg: str) -> None:
        """person <name> <kat,kat> — Zuständigkeit im Hintergrund setzen."""
        parts = shlex.split(arg)
        if len(parts) < 2:
            self.con.ask("Nutzung: person <name> <kategorie,kategorie>")
            return
        ctx = self._ctx()
        cats = [c.strip().lower() for c in parts[1].split(",") if c.strip()]
        for cat in cats:
            persons = set(ctx.taxonomy.persons_for(cat)) | {parts[0]}
            ctx.taxonomy.set_persons(cat, sorted(persons))
        self.con.honey(f"{parts[0]} → {', '.join(cats)}")

    # ------------------------------------------------------------------ #
    #  Gedächtnis / Empfehlungen
    # ------------------------------------------------------------------ #
    def do_gedaechtnis(self, arg: str) -> None:
        """gedaechtnis [approve <slug> | neu] — Kategorien/Vorschläge zeigen; 'neu' baut das
        Gedächtnis mit dem aktuellen Embedding-Modell neu auf (nach einem Modellwechsel)."""
        ctx = self._ctx()
        from pollysort.hive_mind.reflection import Reflection
        refl = Reflection(ctx.hive)
        parts = shlex.split(arg)
        if len(parts) == 2 and parts[0] == "approve":
            from pollysort.migrate import approve
            p = refl.get(parts[1])
            if not p:
                self.con.error(f"Kein Vorschlag '{parts[1]}'.")
                return
            with QueenLock(ctx.hive):
                msg = approve(ctx, p)
                refl.resolve(parts[1])
            self.con.honey(msg)
            return
        if parts and parts[0] in ("neu", "rebuild", "reindex"):
            self._reindex_gedaechtnis(ctx)
            return
        self.con.info(f"Kategorien: {', '.join(ctx.taxonomy.categories)}", "🧠")
        drift = ctx.mind.mismatch(getattr(ctx.client, "embed_model", None))
        if drift:
            self.con.info(f"Embedding-Modell hat sich geändert (Gedächtnis: {drift}). Alte "
                          "Vektoren matchen nicht mehr — 'gedaechtnis neu' baut es neu auf.", "⚠️")
        for p in (refl.reflect(ctx.store, ctx.mind) or refl.pending()):
            self.con.raw(f"    🐣 [{p.slug}] {p.describe()}")
            self.con.info("Übernehmen mit:  gedaechtnis approve <slug>", "🐣")

    def _reindex_gedaechtnis(self, ctx) -> None:
        """'gedaechtnis neu' — alle einsortierten Einträge mit dem aktuellen Embedding-Modell
        neu einbetten (F1-Remedy). Fragt vorher nach; online kostet es je Eintrag einen Call."""
        from pollysort.models import Status
        from pollysort.pipeline import reindex_memory
        total = len(ctx.store.query(status=Status.ASSIGNED.value))
        if total == 0:
            self.con.info("Kein einsortierter Bestand — nichts neu einzubetten.", "🧠")
            return
        model = getattr(ctx.client, "embed_model", None)
        self.con.info(f"Baut das Gedächtnis für {total} Eintrag/Einträge mit dem aktuellen "
                      f"Modell ({model}) neu auf.", "🧠")
        if ctx.cfg.llm_provider == "openrouter":
            self.con.info("Das erzeugt pro Eintrag einen (günstigen) Embedding-Call.", "💸")
        if not self._ja("Jetzt neu aufbauen? [J/n]: "):
            return
        with QueenLock(ctx.hive):
            ok, fail = reindex_memory(ctx)
        msg = f"Gedächtnis neu aufgebaut: {ok} eingebettet"
        if fail:
            msg += f", {fail} übersprungen"
        self.con.honey(msg + ".", "🧠")

    def do_empfehlung(self, arg: str) -> None:
        """empfehlung [para|johnny|dewey] — Ablage-Strategie + dynamische Hinweise."""
        ctx = self._ctx()
        from pollysort.recommender import suggest
        suggest(ctx, arg.strip() or "para")

    # ------------------------------------------------------------------ #
    #  Schwarm & Projekte (Stufe 2 / Wabenbau) — §v0.3
    # ------------------------------------------------------------------ #
    def do_modell(self, arg: str) -> None:
        """modell [name|id|liste] — OpenRouter-Modell (Nektar-Sorte) im Betrieb wechseln."""
        from pollysort.config import NEKTAR_SORTEN
        cfg = config.load_config()
        arg = arg.strip()
        if arg.lower() in ("liste", "list", "ls"):
            self.con.rule("Nektar-Sorten (OpenRouter-Modelle)")
            for kurz, mid in NEKTAR_SORTEN.items():
                aktiv = "  ◀ aktiv" if mid == cfg.llm_model else ""
                self.con.raw(f"   🍯 {kurz:12} {mid}{aktiv}")
            self.con.info("Auch beliebige IDs möglich:  modell <provider/modell-id>", "🐝")
            return
        if not arg:
            self.con.honey(f"Aktuelle Nektar-Sorte: {cfg.llm_model}", "🍯")
            self.con.info("Wechseln:  modell <name|id>   ·   Sorten:  modell liste", "🐝")
            return
        model = NEKTAR_SORTEN.get(arg.lower(), arg)
        cfg.llm_model = model
        config.save_config(cfg)
        self.con.honey(f"Nektar gewechselt — die Königin sammelt jetzt von: {model}", "🍯")
        if self.hive and config.load_seed(self.hive).provider != "openrouter":
            prov = config.load_seed(self.hive).provider
            self.con.ask(f"Dieses Projekt fliegt im Modus '{prov}'. "
                         f"'modus online' aktiviert OpenRouter für den Nektar.")

    do_modellwechsel = do_modell

    # ------------------------------------------------------------------ #
    #  OpenRouter-Schlüssel (Nektar-Quelle) — prüfen / erneuern / entfernen
    # ------------------------------------------------------------------ #
    def do_schluessel(self, arg: str) -> None:
        """schluessel [test|setzen|entfernen] — OpenRouter-Zugang (Nektar-Quelle) verwalten."""
        sub = arg.strip().lower()
        if sub in ("setzen", "neu", "erneuern", "aendern", "ändern", "set"):
            self._schluessel_setzen()
        elif sub in ("test", "pruefen", "prüfen", "check"):
            self._schluessel_test()
        elif sub in ("entfernen", "raus", "loeschen", "löschen", "remove"):
            self._schluessel_entfernen()
        else:
            self._schluessel_status()

    do_key = do_schluessel
    do_apikey = do_schluessel

    def _schluessel_status(self) -> None:
        import os

        from pollysort.flugrouten import mask
        self.con.rule("Nektar-Quelle (OpenRouter-Schlüssel)")
        env = os.environ.get("OPENROUTER_API_KEY")
        stored = config.load_credentials()
        if env:
            self.con.info(f"Aus Umgebungsvariable OPENROUTER_API_KEY ({mask(env)}) — hat Vorrang.",
                          "🔑")
        elif stored:
            self.con.info(f"Hinterlegt: {mask(stored)}   ({config.CREDENTIALS_PATH})", "🔑")
        else:
            self.con.info("Kein Schlüssel hinterlegt — Offline/Ollama gehen, OpenRouter nicht.",
                          "🔑")
        self.con.info("Prüfen: 'schluessel test' · Erneuern: 'schluessel setzen' · "
                      "Entfernen: 'schluessel entfernen'", "🐝")

    def _schluessel_test(self) -> None:
        from pollysort.llm.client import verify_openrouter_key
        key = config.load_credentials()
        if not key:
            self.con.info("Kein Schlüssel hinterlegt. 'schluessel setzen' weist einen aus.", "🔑")
            return
        self.con.bloom("Spähbiene prüft die Nektar-Quelle bei OpenRouter …", "🐝")
        ok, grund = verify_openrouter_key(key)
        if ok:
            self.con.honey("Nektar-Quelle offen — der Schlüssel ist gültig. 🍯", "✅")
        else:
            self.con.error(f"Schlüssel {grund} — erneuern mit 'schluessel setzen'.")

    def _schluessel_setzen(self) -> None:
        import os

        from pollysort.llm.client import verify_openrouter_key
        if os.environ.get("OPENROUTER_API_KEY"):
            self.con.ask("Hinweis: OPENROUTER_API_KEY (Umgebungsvariable) hat Vorrang vor dem "
                         "gespeicherten Schlüssel und wird nicht überschrieben.")
        self.con.info("Neue Nektar-Quelle ausweisen (ersetzt den bisherigen Schlüssel).", "🔑")
        key = self._ask("     🔑 Neuer OpenRouter-API-Key (leer = abbrechen): ").strip()
        if not key:
            self.con.info("Abgebrochen — Schlüssel unverändert.", "🐝")
            return
        self.con.bloom("Spähbiene prüft die neue Nektar-Quelle …", "🐝")
        ok, grund = verify_openrouter_key(key)
        if ok:
            config.save_credentials(key)
            self.con.honey(f"Schlüssel gültig & gespeichert ({config.CREDENTIALS_PATH}, chmod 600).",
                           "✅")
        else:
            self.con.error(f"Der neue Schlüssel {grund}.")
            if self._ja("     Trotzdem speichern (ungeprüft)? [j/N]: "):
                config.save_credentials(key)
                self.con.info("Gespeichert — bei Bedarf 'schluessel test'.", "🔑")
            else:
                self.con.info("Nicht gespeichert — bisheriger Schlüssel bleibt.", "🐝")

    def _schluessel_entfernen(self) -> None:
        import os
        if not config.load_credentials():
            self.con.info("Kein Schlüssel hinterlegt.", "🔑")
            return
        if not self._ja("     Schlüssel wirklich entfernen? (OpenRouter-Projekte fallen auf "
                        "Offline zurück) [j/N]: "):
            self.con.info("Abgebrochen.", "🐝")
            return
        try:
            config.CREDENTIALS_PATH.unlink()
        except OSError:
            pass
        if os.environ.get("OPENROUTER_API_KEY"):
            self.con.ask("Achtung: OPENROUTER_API_KEY (Umgebungsvariable) ist weiter gesetzt "
                         "und aktiv — im Terminal/Profil entfernen, falls gewünscht.")
        else:
            self.con.info("Schlüssel entfernt — OpenRouter-Projekte nutzen jetzt die "
                          "Offline-Heuristik.", "🔑")

    # ------------------------------------------------------------------ #
    #  Ansicht & Thema (Dark/Light, statische Ansicht ohne Scrolling)
    # ------------------------------------------------------------------ #
    def do_thema(self, arg: str) -> None:
        """thema [dunkel|hell|auto] — Dark/Light umschalten; 'auto' = tags dunkel, abends hell."""
        mapping = {"dunkel": "dark", "dark": "dark", "hell": "light", "light": "light",
                   "auto": "auto", "automatisch": "auto", "automatik": "auto"}
        key = arg.strip().lower()
        if key not in mapping:
            if self._theme_pref == "auto":
                aktiv = "Dunkel" if self.con.theme_name == "dark" else "Hell"
                self.con.info(f"Thema: Automatik (tags dunkel, abends hell) — gerade {aktiv}. "
                              "Wechseln: 'thema dunkel | hell | auto'.", "🎨")
            else:
                akt = "Dunkel" if self._theme_pref == "dark" else "Hell"
                self.con.info(f"Thema: {akt}-Modus. Wechseln: 'thema dunkel | hell | auto'.", "🎨")
            return
        cfg = config.load_config()
        cfg.theme = mapping[key]
        config.save_config(cfg)
        eff = self._apply_theme(mapping[key])
        self._render_frame()
        if self._theme_pref == "auto":
            self.con.honey(f"Thema: Automatik — tagsüber Dunkel, abends Hell. Jetzt aktiv: "
                           f"{'Dunkel' if eff == 'dark' else 'Hell'}. 🎨", "🎨")
        else:
            self.con.honey(f"Thema gewechselt — {'Dunkel' if eff == 'dark' else 'Hell'}-Modus. 🎨",
                           "🎨")

    do_theme = do_thema
    do_farbe = do_thema

    def do_ansicht(self, arg: str) -> None:
        """ansicht [statisch|log] — statische Ansicht (kein Scrolling) oder klassisches Log."""
        key = arg.strip().lower()
        if key in ("statisch", "static", "an", "on"):
            self._static_view = True
        elif key in ("log", "scroll", "aus", "off"):
            self._static_view = False
        else:
            akt = "statisch (kein Scrolling)" if self._static_view else "Log (scrollend)"
            self.con.info(f"Aktuelle Ansicht: {akt}. Wechseln: 'ansicht statisch' | 'ansicht log'.",
                          "🖥️")
            return
        cfg = config.load_config()
        cfg.static_view = self._static_view
        config.save_config(cfg)
        if self._static_view and not (sys.stdout.isatty() and sys.stdin.isatty()):
            self.con.ask("Hinweis: die statische Ansicht wirkt nur im echten Terminal "
                         "(bei Pipe/CI bleibt es beim Log).")
        self._render_frame()
        self.con.honey("Ansicht: statisch — die Konsole zeichnet sich selbst neu."
                       if self._static_view else "Ansicht: klassisches Log (scrollend).", "🖥️")

    do_view = do_ansicht

    def do_wabenbau(self, arg: str) -> None:
        """wabenbau [kategorie] — Stufe 2: aus einer Wabe ein Projekt bauen (Bienenstock.md)."""
        from pollysort.config import pretty_category
        from pollysort.swarm import Baubiene
        ctx = self._ctx()
        cats = ctx.taxonomy.categories
        kat = arg.strip().lower()
        if not kat:
            if not cats:
                self.con.info("Noch keine Waben da — erst 'sortiere'.", "🐝")
                return
            self.con.info("Welche Wabe zum Projekt ausbauen?", "🛠️")
            for i, c in enumerate(cats, 1):
                self.con.raw(f"       [{i}] {pretty_category(c)}")
            choice = self._ask("     Nummer oder Name: ").strip()
            kat = cats[int(choice) - 1] if choice.isdigit() and 1 <= int(choice) <= len(cats) \
                else choice.lower()
        if not kat:
            self.con.info("Abgebrochen — keine Wabe gewählt.", "🐝")
            return
        if kat not in cats:
            self.con.ask(f"'{pretty_category(kat)}' ist (noch) keine bekannte Wabe — baue trotzdem.")
        bau = Baubiene(ctx)
        self.con.bloom(f"Baubienen schwärmen aus für die Wabe '{pretty_category(kat)}' …", "🛠️")
        ch = bau.wabenbau(kat, ask=self._ask)
        wabe = self.hive / pretty_category(kat)
        self.con.honey(f"Bienenstock.md gebaut → {wabe / 'Bienenstock.md'}", "🍯")
        tasks = bau.offene_aufgaben(kat, ch)
        if tasks:
            self.con.ask(f"{len(tasks)} offene Aufgabe(n) in der Wabe:")
            for t in tasks:
                self.con.raw(f"       ☐ {t}")
        else:
            self.con.celebrate("Wabe komplett — nichts bleibt offen!")
        if ch.deadline:
            self.con.info(f"Deadline im Bienen-Kalender vermerkt: {ch.deadline}", "📅")

    def do_kalender(self, arg: str) -> None:
        """kalender [melden] — Deadlines zeigen; 'kalender melden' schickt fällige Erinnerungen."""
        from pollysort.swarm import Waechterbiene
        w = Waechterbiene(self._ctx())
        offen = w.kalender.offen()
        if not offen:
            self.con.info("Der Bienen-Kalender ist leer. Deadlines setzt 'wabenbau'.", "📅")
            return
        self.con.rule("Bienen-Kalender")
        for t in offen:
            tage = t.tage_bis()
            wann = f"in {tage} T" if tage >= 0 else f"{-tage} T überfällig"
            mark = "🔴" if tage < 0 else ("🟠" if tage <= 7 else "🟢")
            self.con.raw(f"   {mark} {t.faellig}  {t.titel}  ({wann})")
        # Ansicht sendet NICHT; nur die Wächterbienen 'summen' (Konsole). Echt-Versand:
        # 'kalender melden' oder automatisch beim 'wache'-Dienst.
        senden = arg.strip().lower() in ("melden", "send", "ausfliegen")
        due = w.deadlines_pruefen(innerhalb_tage=7, senden=senden)
        if not due:
            self.con.info("Nichts Dringendes in den nächsten 7 Tagen. 🍯", "🐝")
        elif senden and not w.kanaele:
            self.con.info("Keine Flugrouten aktiv — 'flugrouten setup' schaltet den Versand frei.",
                          "🧭")

    def do_fortschritt(self, _arg: str) -> None:
        """fortschritt — wie weit ist dein Bienenstock? (auch: progress, stufe)"""
        from pollysort import spiel
        stand = spiel.laden(self.hive)
        self.con.rule("🍯 " + i18n.t("spiel.titel"))
        if stand.dokumente == 0 and not stand.abzeichen:
            self.con.info(i18n.t("spiel.leer"), "🐝")
            return
        for zeile in spiel.uebersicht(stand):
            self.con.raw("  " + zeile)

    do_progress = do_fortschritt
    do_stufe = do_fortschritt
    do_level = do_fortschritt

    def do_schwarm(self, _arg: str) -> None:
        """schwarm — Überblick über Königin & Bienen (Waben, offene Fälle, Projekte, Deadlines)."""
        from pollysort.swarm import Koenigin
        st = Koenigin(self._ctx()).schwarm_status()
        self.con.rule("Der Schwarm")
        self.con.info(f"👑 Königin orchestriert {st['waben']} Wabe(n) · "
                      f"{st['dokumente']} Dokument(e)", "🐝")
        self.con.raw(f"   🐝 Spurbienen:   {st['assigned']} einsortiert · "
                     f"{st['needs_review']} Rückfrage(n) · {st['error']} Fehler")
        self.con.raw(f"   🛠️ Baubienen:    {st['projekte']} Projekt-Charter (Stufe 2)")
        self.con.raw(f"   🔔 Wächterbienen: {st['deadlines_faellig']} Deadline(s) in ≤ 7 Tagen")
        if st["gewohnheiten"]:
            self.con.raw("   🍯 Sammelbienen (gelernte Ablage-Orte):")
            for kat, ort in st["gewohnheiten"].items():
                self.con.raw(f"        {kat} → {ort}")

    # ------------------------------------------------------------------ #
    #  Flugrouten — Kommunikationskanäle der Wächterbienen (opt-in) §v0.3
    # ------------------------------------------------------------------ #
    def do_flugrouten(self, arg: str) -> None:
        """flugrouten [setup|test|aus] — Discord/E-Mail-Benachrichtigungen der Wächterbienen."""
        sub = arg.strip().lower()
        if sub in ("setup", "config", "einrichten"):
            self._flugrouten_setup()
        elif sub in ("test", "testflug"):
            self._flugrouten_test()
        elif sub in ("aus", "off", "deaktivieren", "stopp"):
            from pollysort.flugrouten import Flugrouten, save_flugrouten
            save_flugrouten(Flugrouten())
            self.con.info("Alle Flugrouten stillgelegt — die Wächterbienen bleiben im Stock.",
                          "🧭")
        else:
            self._flugrouten_status()

    do_api = do_flugrouten

    def _flugrouten_status(self) -> None:
        from pollysort.flugrouten import load_flugrouten, mask
        fr = load_flugrouten()
        self.con.rule("Flugrouten der Wächterbienen")
        if not fr.any_enabled() and not fr.calendar.enabled:
            self.con.info("Noch keine Flugrouten ausgewiesen. 'flugrouten setup' richtet welche ein.",
                          "🧭")
            return
        if fr.discord.enabled:
            self.con.raw(f"   🎮 Discord: aktiv · Channel {fr.discord.channel_id} · "
                         f"Token {mask(fr.discord.bot_token)}")
        if fr.email.enabled:
            self.con.raw(f"   📧 E-Mail: aktiv · {fr.email.address} · {fr.email.provider} "
                         f"({fr.email.smtp_host}:{fr.email.smtp_port}) · Pass {mask(fr.email.password)}")
        if fr.calendar.enabled:
            self.con.raw(f"   📅 Kalender: vorgemerkt ({fr.calendar.kind})")
        self.con.info("🔒 Zugangsdaten bleiben lokal — kein LLM sieht sie je. 'flugrouten test' prüft.",
                      "🐝")

    def _flugrouten_test(self) -> None:
        from pollysort.flugrouten import load_flugrouten
        from pollysort.swarm.kanaele import build_kanaele
        kanaele = build_kanaele(load_flugrouten())
        if not kanaele:
            self.con.info("Keine aktiven Flugrouten. 'flugrouten setup' weist welche aus.", "🧭")
            return
        self.con.bloom("Wächterbienen fliegen zum Testflug aus …", "🐝")
        for k in kanaele:
            try:
                k.senden("Bienentanz-Testflug",
                         "🐝 Hallo vom Bienenstock! Diese Flugroute steht bereit.")
                stock = getattr(k, "STOCK", f"{k.name}-Wabe")
                self.con.honey(f"Wächterbienen haben die {stock} erfolgreich informiert!", "🐝")
            except Exception as exc:
                self.con.error(f"Flugroute {k.name} blockiert: {exc}")

    def _flugrouten_setup(self) -> None:
        """Assistent: neue Flugrouten für die Wächterbienen ausweisen (Discord/E-Mail/Kalender)."""
        from pollysort.flugrouten import (
            EMAIL_PRESETS,
            CalendarConfig,
            DiscordConfig,
            EmailConfig,
            load_flugrouten,
            save_flugrouten,
        )
        fr = load_flugrouten()
        self.con.rule("Flugrouten ausweisen")
        self.con.info("Wohin sollen die Wächterbienen bei fälligen Deadlines fliegen?", "🧭")
        self.con.info("🔒 Alle Zugangsdaten bleiben strikt lokal — kein LLM bekommt sie je zu sehen.",
                      "🐝")

        # -- Discord --------------------------------------------------------
        if self._ja("  🎮 Discord-Flugroute einrichten? [j/N]: "):
            token = self._ask("      🔑 Discord-Bot-Token: ").strip()
            channel = self._ask("      #  Channel-ID des Main-Channels: ").strip()
            if token and channel:
                fr.discord = DiscordConfig(enabled=True, bot_token=token, channel_id=channel)
                self.con.honey("Discord-Flugroute ausgewiesen.", "🐝")
            else:
                self.con.info("Unvollständig — Discord übersprungen.", "🧭")

        # -- E-Mail (mit Presets) ------------------------------------------
        if self._ja("  📧 E-Mail-Flugroute einrichten? [j/N]: "):
            self.con.raw("      Provider:  [1] Gmail   [2] Outlook/Hotmail   [3] Benutzerdefiniert")
            wahl = self._ask("      Wahl [1]: ").strip() or "1"
            if wahl == "2":
                provider = "outlook"
                host, port, tls = EMAIL_PRESETS["outlook"]
            elif wahl == "3":
                provider = "custom"
                host = self._ask("      SMTP-Server: ").strip()
                port = int(self._ask("      Port [587]: ").strip() or "587")
                tls = True
            else:
                provider = "gmail"
                host, port, tls = EMAIL_PRESETS["gmail"]
            address = self._ask("      ✉️  E-Mail-Adresse: ").strip()
            password = self._ask("      🔒 Passwort / App-Passwort: ").strip()
            recipient = self._ask("      📮 Empfänger [leer = an dich selbst]: ").strip()
            if address and password and host:
                fr.email = EmailConfig(enabled=True, provider=provider, address=address,
                                       password=password, smtp_host=host, smtp_port=port,
                                       use_tls=tls, recipient=recipient)
                self.con.honey(f"E-Mail-Flugroute ausgewiesen ({provider}, {host}:{port}).", "🐝")
            else:
                self.con.info("Unvollständig — E-Mail übersprungen.", "🧭")

        # -- Kalender (nur Struktur) ---------------------------------------
        if self._ja("  📅 Kalender-Flugroute anlegen? (Struktur, Sync folgt) [j/N]: "):
            fr.calendar = CalendarConfig(enabled=True)
            self.con.honey("Kalender-Flugroute vorgemerkt.", "🐝")

        save_flugrouten(fr)
        self.con.honey("Flugrouten gesichert (nur lokal, chmod 600). Testflug: 'flugrouten test'.",
                       "🍯")

    #: Zustimmung in beiden Sprachen — sonst versteht der EN-Modus sein eigenes "yes" nicht.
    _YES = ("j", "ja", "y", "yes")

    def _ja(self, prompt: str) -> bool:
        """Ja/Nein-Frage mit Default **nein**."""
        return self._ask(prompt).strip().lower() in self._YES

    def _ja_default(self, prompt: str) -> bool:
        """Ja/Nein-Frage mit Default **ja** (leere Eingabe = ja)."""
        return self._ask(prompt).strip().lower() in ("", *self._YES)

    # ------------------------------------------------------------------ #
    #  Löschung (separat, nie automatisch)
    # ------------------------------------------------------------------ #
    def do_papierkorb(self, arg: str) -> None:
        """papierkorb <id> — Eintrag in die Quarantäne verschieben (löscht nichts)."""
        ctx = self._ctx()
        from pollysort.undertaker import undertake
        dest = undertake(ctx.hive, ctx.store, arg.strip())
        if dest:
            ctx.mind.forget(arg.strip())
            self.con.info(f"→ Quarantäne (nicht gelöscht): {dest.name}", "⚰️")
        else:
            self.con.error(f"Kein Eintrag '{arg.strip()}'.")

    def do_zurueckholen(self, arg: str) -> None:
        """zurueckholen <id> — Datei aus der Quarantäne zurückholen."""
        ctx = self._ctx()
        from pollysort.undertaker import resurrect
        dest = resurrect(ctx.hive, ctx.store, arg.strip())
        if dest:
            self.con.honey(f"Zurück im Ordner: {dest.name}")
        else:
            self.con.error("Nichts zurückzuholen.")

    def do_dubletten(self, arg: str) -> None:
        """dubletten [aufraeumen] — erkannte Dubletten zeigen; 'aufraeumen' legt sie in die
        Quarantäne (löscht nichts). So wird der Posteingang endlich sauber (BUG-9)."""
        import shutil

        from pollysort.mover import collision_safe_name
        ctx = self._ctx()
        rows = [r for r in ctx.store.duplicate_rows() if Path(r["path"]).exists()]
        if not rows:
            self.con.info("Keine Dubletten im Eingang. ✨", "🛡️")
            return
        self.con.rule(f"{len(rows)} Dublette(n)")
        for r in rows:
            self.con.raw(f"    🛡️ {Path(r['path']).name}  — Original: "
                         f"{r['filename']} ({r['kategorie'] or 'unsortiert'})")
        if arg.strip().lower() not in ("aufraeumen", "aufräumen", "cleanup", "clean", "tidy"):
            self.con.ask("'dubletten aufraeumen' verschiebt sie in die Quarantäne "
                         "(papierkorb — nichts wird gelöscht).")
            return
        if not self._ja(f"{len(rows)} Dublette(n) in die Quarantäne verschieben? [j/N]: "):
            self.con.info("Abgebrochen.", "🐝")
            return
        from pollysort.config import honig
        friedhof = honig(ctx.hive) / "papierkorb"
        friedhof.mkdir(parents=True, exist_ok=True)
        moved = 0
        for r in rows:
            src = Path(r["path"])
            try:
                dest = collision_safe_name(friedhof, src.name, r["bee_id"])
                shutil.move(str(src), str(dest))
                ctx.store.remove_duplicate_path(r["path"])
                ctx.movelog.record(bee_id=r["bee_id"], src=str(src), dst=str(dest),
                                   action="dublette")
                moved += 1
            except OSError as exc:
                self.con.error(f"{src.name}: {exc}")
        self.con.honey(f"{moved} Dublette(n) in der Quarantäne — endgültig löschen "
                       f"erst mit 'leeren'.", "⚰️")

    def do_leeren(self, _arg: str) -> None:
        """leeren — Quarantäne endgültig löschen (mit Rückbestätigung)."""
        from pollysort.store import Store
        from pollysort.undertaker import buried_candidates, bury
        candidates = buried_candidates(self.hive)
        if not candidates:
            self.con.info("Quarantäne ist leer.", "🐝")
            return
        for p in candidates:
            self.con.raw(f"    🗑️ {p.name}")
        answer = input(f'Wirklich {len(candidates)} Datei(en) endgültig löschen? '
                       f'Tippe "{len(candidates)}": ').strip()
        if answer != str(len(candidates)):
            self.con.info("Abgebrochen.", "🐝")
            return
        # Store übergeben → verwaiste Katalog-Einträge werden mit entfernt (kein Waisen-Rest).
        removed = bury(self.hive, Store(self.hive))
        self.con.honey(f"{len(removed)} Datei(en) endgültig gelöscht.", "⚰️")

    def do_rueckflug(self, _arg: str) -> None:
        """rueckflug — die letzte automatische Verschiebung rückgängig machen (undo)."""
        import shutil

        from pollysort.movelog import MoveLog
        ctx = self._ctx()
        last = MoveLog(ctx.hive).pop_last()
        if not last:
            self.con.info("Nichts rückgängig zu machen.", "🐝")
            return
        src, dst = Path(last["dst"]), Path(last["src"])
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            ctx.store.update_path(last["bee_id"], str(dst))
            # Zurückgeholte Datei ist wieder eine offene Frage: als needs_review markieren,
            # damit sie in 'status'/'rueckfragen' auftaucht und nicht still im Root verharrt.
            from pollysort.models import Status
            ctx.store.set_status(last["bee_id"], Status.NEEDS_REVIEW)
        self.con.honey(f"Rückgängig: {src.name} → {dst.parent.name} (wieder offen)", "↩️")

    # ------------------------------------------------------------------ #
    #  Projekte anlegen / wechseln / anzeigen
    # ------------------------------------------------------------------ #
    def do_neu(self, arg: str) -> None:
        """neu [pfad] — ein neues Projekt anlegen (fragt nach dem Ordner-Pfad)."""
        self._new_project(arg)

    def do_wechsel(self, arg: str) -> None:
        """wechsel [nr|name|pfad] — zu einem anderen Projekt wechseln."""
        projects = config.list_projects()
        arg = arg.strip().strip('"')
        if not arg:
            if not projects:
                self.con.info("Noch keine Projekte. 'neu' legt eins an.", "🐝")
                return
            self._print_projects(projects)
            arg = self._ask("  Nummer, Name oder Pfad: ").strip().strip('"')
        target = self._resolve_project(arg, projects)
        if target is None:
            self.con.error(f"Projekt '{arg}' nicht gefunden. 'projekte' zeigt die Liste.")
            return
        self._open_project(target)

    do_ordner = do_wechsel   # Alias

    def do_projekte(self, _arg: str) -> None:
        """projekte — alle Projekte anzeigen (Wechsel mit 'wechsel <nr>')."""
        projects = config.list_projects()
        if not projects:
            self.con.info("Noch keine Projekte. 'neu' legt eins an.", "🐝")
            return
        self._print_projects(projects)
        self.con.info("Wechseln mit:  wechsel <nr>   ·   Neu:  neu <pfad>", "🐝")

    def do_setup(self, _arg: str) -> None:
        """setup — das AKTUELLE Projekt neu einrichten (Name, Kategorien, Modus …)."""
        if self.hive is None:
            self._new_project()
        else:
            self._run_setup(self.hive)

    # -- Helfer für Projekte -----------------------------------------------
    def _new_project(self, path_arg: str = "") -> None:
        path = self._acquire_path(path_arg)
        if path is None:
            self.con.info(i18n.t("su.cancelled"), "🐝")
            return
        if config.is_setup(path):
            # Ordner hat schon eine Konfiguration (z. B. eine KOPIE eines Projekts). Den
            # Setup-Assistenten NICHT still überspringen — sonst landen neue Dateien in der
            # alten, evtl. unpassenden Taxonomie. Stattdessen die Wahl lassen.
            self.con.ask(i18n.t("su.exists", name=path.name))
            if self._ja(i18n.t("su.exists.redo")):
                if self._ja(i18n.t("su.exists.reset")):
                    self._reset_honig(path)
                self._run_setup(path)
            else:
                self.con.info(i18n.t("su.exists.open"), "🐝")
                self._open_project(path)
            return
        self._run_setup(path)

    def _reset_honig(self, path: Path) -> None:
        """Das bestehende `.honig` sichern (umbenennen), damit ein Setup frisch startet.

        Es wird NICHTS gelöscht: der alte Stand landet in `.honig.bak-<zeit>` daneben.
        """
        import time
        honig = config.honig(path)
        if honig.exists():
            backup = honig.with_name(f".honig.bak-{time.strftime('%Y%m%d-%H%M%S')}")
            try:
                honig.rename(backup)
                self.con.info(i18n.t("su.backup.ok", name=backup.name), "🗄️")
            except OSError as exc:
                self.con.error(i18n.t("su.backup.fail", name=honig.name, err=exc))

    def _acquire_path(self, path_arg: str = "") -> Path | None:
        """Nach dem Projekt-Pfad fragen (erste Setup-Frage); legt den Ordner bei Bedarf an."""
        raw = path_arg.strip().strip('"')
        while True:
            if not raw:
                raw = self._ask("  📂 " + i18n.t("su.path.ask")).strip().strip('"')
            if not raw:
                return None
            p = Path(raw).expanduser().resolve()
            if p.is_dir():
                return p
            if not p.exists():
                if self._ja_default("     " + i18n.t("su.path.create", path=p)):
                    try:
                        p.mkdir(parents=True, exist_ok=True)
                        return p
                    except OSError as exc:
                        self.con.error("     " + i18n.t("su.path.mkfail", err=exc))
            else:
                self.con.error("     " + i18n.t("su.path.notdir", path=p))
            raw = ""

    def _resolve_project(self, arg: str, projects: list[Path]) -> Path | None:
        if arg.isdigit():
            i = int(arg) - 1
            return projects[i] if 0 <= i < len(projects) else None
        p = Path(arg).expanduser()
        if p.is_dir():
            return p.resolve()
        for cand in projects:                       # nach Projektname suchen
            try:
                if config.load_seed(cand).name.lower() == arg.lower():
                    return cand
            except Exception:
                continue
        return None

    def _print_projects(self, projects: list[Path]) -> None:
        self.con.rule("Projekte")
        for i, p in enumerate(projects, 1):
            try:
                name = config.load_seed(p).name or p.name
            except Exception:
                name = p.name
            mark = "◉" if self.hive and p == self.hive else " "
            self.con.raw(f"  {mark} [{i}] {name:<18} {p}")

    def do_modus(self, arg: str) -> None:
        """modus <offline|ollama|online> — KI-Backend für DIESES Projekt umstellen."""
        mapping = {"offline": "offline", "ollama": "ollama",
                   "online": "openrouter", "openrouter": "openrouter"}
        provider = mapping.get(arg.strip().lower())
        if provider is None:
            self.con.info(f"Modus: {config.load_seed(self.hive).provider}", "🐝")
            return
        if provider == "openrouter" and not self._ensure_key():
            self.con.info("Kein Key → Modus unverändert.", "🐝")
            return
        if provider == "ollama" and not self._ollama_ready(refresh=True):
            self.con.ask("Kein lokales Ollama erkannt — bitte Ollama starten.")
            return
        self.offline = provider == "offline"
        self._update_seed(provider=provider)
        self.con.honey(f"Modus für dieses Projekt: {provider}", "🧠")

    # ------------------------------------------------------------------ #
    #  Einrichtungs-Assistent
    # ------------------------------------------------------------------ #
    def _run_setup(self, hive: Path) -> None:
        """Assistent — Reihenfolge: Name → KI-Modus → Kategorien (KI-Vorschlag) → Überwachung."""
        self.hive = hive
        # Proben eines frueheren Setups verwerfen: Sonst wuerde beim zweiten Projekt das
        # Gedaechtnis mit den Dokumenten des ERSTEN vorgewaermt, sobald hier nicht der
        # Vorschlags-Modus gewaehlt wird.
        self._proben = []
        self.con.rule(i18n.t("su.title"))
        self.con.info(i18n.t("su.folder", path=hive), "📂")

        name = self._ask("  1) " + i18n.t("su.name", default=hive.name)).strip() or hive.name
        provider = self._choose_mode()                       # 2) KI-Modus zuerst
        self.offline = provider == "offline"
        categories = self._choose_categories(hive, provider)  # 3) Kategorien (KI-Vorschlag)
        subrouting = self._choose_subrouting(categories, provider)  # 3b) Unterordner-Vorschlag
        watch = self._choose_watch()                          # 4) Überwachung

        seed = HiveSeed(categories=categories,
                        responsibility={c: [] for c in categories},
                        subrouting=subrouting,
                        name=name, provider=provider, watch=watch)
        config.write_seed(hive, seed)
        config.register_project(hive)
        config.remember_last_hive(hive)
        made = self._scaffold_categories(hive, categories)   # Kategorie-Ordner anlegen
        self._sync_prompt()

        self.con.rule(i18n.t("su.done.title"))
        watch_txt = {"off": "", "notify": " · " + i18n.t("su.done.notify"),
                     "move": " · " + i18n.t("su.done.move")}
        made_txt = f" ({i18n.t('su.done.made', n=made)})" if made else ""
        self.con.honey(i18n.t("su.done", name=name, n=len(categories), made=made_txt,
                              provider=provider, watch=watch_txt.get(watch, "")), "✅")
        self._vorwaermen(hive, categories, provider)
        # Die schon vorhandenen losen Dateien direkt in die Waben einlagern.
        if self._inbox_count():
            self.con.info(i18n.t("su.filing"), "🐝")
            self._cycle(mode="move")
        else:
            self._show_inbox()

    def _vorwaermen(self, hive: Path, categories: list[str], provider: str) -> None:
        """Das Gedächtnis mit den Analysen des Struktur-Vorschlags vorwärmen.

        Ohne das startet der erste Sortierlauf mit leerem Gedächtnis — und sobald die
        ersten Dokumente einer Sorte drin sind, widerspricht der kNN dem Label jeder
        NEUEN Sorte. Die Datei landet dann in der Rückfrage, obwohl ihre Kategorie
        stimmt und der Nutzer sie eben selbst bestätigt hat. Details: `vorwaermen.py`.

        Läuft nur, wenn der Vorschlag tatsächlich mit KI lief (offline gibt es keine
        vergleichbaren Analysen). Ein Fehler hier darf die Einrichtung nie abbrechen.
        """
        if not self._proben:
            return
        from pollysort import vorwaermen as vw
        from pollysort.hive_mind import HiveMind
        from pollysort.llm.client import embed_model_for
        try:
            cfg = config.load_config()
            cfg.llm_provider = provider
            api_key = config.load_credentials() if provider == "openrouter" else None
            client = build_client(cfg, api_key, categories, [])
            gesaet = vw.vorwaermen(self._proben, categories, mind=HiveMind(hive),
                                   embed=client.embed,
                                   embed_model=embed_model_for(cfg, api_key))
        except Exception:
            return
        if gesaet:
            self.con.info(i18n.t("vw.done", n=sum(gesaet.values()), k=len(gesaet)), "🧠")

    def _scaffold_categories(self, hive: Path, categories: list[str]) -> int:
        """Die gewählten/vorgeschlagenen Kategorie-Ordner sichtbar im Projekt anlegen."""
        from pollysort.config import pretty_category
        made = 0
        for cat in categories:
            folder = hive / pretty_category(cat)
            if not folder.exists():
                folder.mkdir(parents=True, exist_ok=True)
                made += 1
        return made

    def _choose_mode(self) -> str:
        """Schritt 2: KI-Backend wählen (offline / lokale Ollama / OpenRouter)."""
        ollama = self._ollama_ready(refresh=True)   # nur ERREICHBARES Ollama anbieten
        has_key = config.load_credentials() is not None
        opts: list[tuple[str, str]] = [("offline", i18n.t("fr.ai.offline"))]
        if ollama:
            opts.append(("ollama", i18n.t("fr.ai.ollama")))
        if has_key:
            opts.append(("openrouter", i18n.t("su.mode.or_key")))
        elif not ollama:
            opts.append(("openrouter", i18n.t("su.mode.or_nokey")))

        self.con.raw("  2) " + i18n.t("su.mode.q"))
        for i, (_, desc) in enumerate(opts, 1):
            self.con.raw(f"       [{i}] {desc}")
        default = str(len(opts))          # bevorzugt die beste verfügbare KI
        choice = self._ask("     " + i18n.t("su.choice", default=default)).strip() or default
        idx = int(choice) - 1 if choice.isdigit() and 0 < int(choice) <= len(opts) else len(opts) - 1
        provider = opts[idx][0]
        if provider == "openrouter" and not has_key and not self._ensure_key():
            self.con.info(i18n.t("su.mode.nokey"), "🐝")
            return "offline"
        return provider

    def _choose_categories(self, hive: Path, provider: str) -> list[str]:
        """Schritt 3: Vorschlag (KI, wenn online) / Standard / Eigene."""
        n = self._inbox_count()
        ki = provider != "offline"
        how = i18n.t("su.cat.byai") if ki else i18n.t("su.cat.byheur")
        self.con.raw("  3) " + i18n.t("su.cat.q"))
        self.con.raw("       [1] " + i18n.t("su.cat.propose", n=n, how=how)
                     + (f"  {i18n.t('su.cat.recommended')}" if n else ""))
        self.con.raw("       [2] " + i18n.t("su.cat.standard", cats=", ".join(DEFAULT_CATEGORIES)))
        self.con.raw("       [3] " + i18n.t("su.cat.own"))
        default = "1" if n else "2"
        choice = self._ask("     " + i18n.t("su.choice", default=default)).strip() or default
        if choice == "1":
            return self._propose_categories(hive, provider)
        if choice == "3":
            return self._parse_cats(self._ask("     " + i18n.t("su.cat.enter"))) \
                or list(DEFAULT_CATEGORIES)
        return list(DEFAULT_CATEGORIES)

    def _propose_categories(self, hive: Path, provider: str) -> list[str]:
        """Vorschlags-Modus: Dokumente scannen (KI wenn online) und Struktur vorschlagen."""
        from pollysort.config import pretty_category
        from pollysort.onboarding import propose_structure

        ai_analyze = self._ai_analyzer(provider)
        self._proben = []
        # Offline laeuft zwar derselbe Client-Pfad, aber eben keine KI.
        self.con.bloom(i18n.t("su.scout.ai") if provider != "offline"
                       else i18n.t("su.scout.offline"), "🐝")
        proposals, total, used_ai, existing, protokoll = propose_structure(
            hive, ai_analyze=ai_analyze)
        # Ehrlich bleiben (BUG-6): Wenn die KI (teilweise) ausgefallen ist, das laut sagen,
        # statt einen Heuristik-Notvorschlag als „KI-Analyse" zu verkaufen.
        if ai_analyze is not None and ai_analyze.errors and provider != "offline":
            if not ai_analyze.ok:
                self.con.error(i18n.t(
                    "su.scout.failed", n=ai_analyze.errors,
                    reason=ai_analyze.last_reason or i18n.t("su.scout.unreachable")))
                self.con.ask(i18n.t("su.scout.failed_hint"))
            else:
                self.con.info(i18n.t("su.scout.partial", bad=ai_analyze.errors,
                                     total=ai_analyze.errors + ai_analyze.ok), "⚠️")
        if not proposals:
            self.con.info(i18n.t("su.scout.nothing"), "🐝")
            return list(DEFAULT_CATEGORIES)
        # Der Weg ist derselbe, die Sache nicht: Offline rechnet keine KI.
        ki_genutzt = used_ai and provider != "offline"
        tag = i18n.t("su.scout.tag_ai") if ki_genutzt else i18n.t("su.scout.tag_heur")
        note = i18n.t("su.scout.note", n=len(existing)) if existing else ""
        self.con.honey(i18n.t("su.scout.header", total=total, tag=tag, note=note), "🍯")
        maxn = max(n for _, n in proposals) or 1
        for label, n in proposals:
            bar = "█" * max(1, round(10 * n / maxn))
            mark = " · " + i18n.t("su.scout.exists") if label in existing else ""
            self.con.raw(f"       {pretty_category(label):<18} [honey]{bar}[/honey] {n}{mark}")
        # Die Analysen aufheben: Sie sind das Wissen, mit dem sich gleich das
        # Gedächtnis vorwärmen lässt (siehe `_vorwaermen`).
        self._proben = list(getattr(ai_analyze, "proben", []) or [])
        ans = self._ask("     " + i18n.t("su.scout.apply")).strip()
        chosen = [label for label, _ in proposals]
        if ans.lower() in ("", *self._YES):
            return chosen
        if ans.lower() in ("n", "nein", "no"):
            return self._parse_cats(self._ask("     " + i18n.t("su.cat.enter"))) or chosen
        return self._parse_cats(ans) or chosen

    def _ai_analyzer(self, provider: str) -> _AiProbe:
        """Analyse-Funktion (Datei → (kategorie, keywords)) für den Struktur-Vorschlag.

        Läuft für **jeden** Provider, auch offline: Nur so entstehen vollwertige Analysen
        (Titel, Aufgabe, Summary, Keywords), aus denen sich anschließend das Gedächtnis
        vorwärmen lässt. Der frühere Sonderweg über die reine Heuristik lieferte nur
        Label und Stichworte — daraus gebaute Vektoren lägen in einem anderen Textraum
        als die späteren echten Einträge und wären als Nachbarn wertlos.

        ``categories=None`` heißt „alle Regeln erlaubt" — beim Vorschlag gibt es die
        Projekt-Kategorien ja noch nicht. Fehlgeschlagene Analysen werden gezählt statt
        verschluckt (BUG-6); ``propose_structure`` weicht dann auf die Heuristik aus.
        """
        cfg = config.load_config()
        cfg.llm_provider = provider
        api_key = config.load_credentials() if provider == "openrouter" else None
        client = build_client(cfg, api_key, None, [])
        return _AiProbe(client)

    def _choose_subrouting(self, categories: list[str], provider: str) -> dict[str, str]:
        """Schritt 3b: dynamische Unterordner (Jahr/Monat) — KI/Heuristik schlägt vor.

        Fragt das Backend (online: LLM, offline: Heuristik), welche Kategorien von einer
        Datums-Gliederung profitieren, zeigt den Vorschlag und lässt ihn übernehmen.
        """
        try:
            cfg = config.load_config()
            cfg.llm_provider = provider
            api_key = config.load_credentials() if provider == "openrouter" else None
            client = build_client(cfg, api_key, categories, [])
            suggestions = client.suggest_subrouting(categories)
        except Exception:
            from pollysort.heuristics import suggest_subrouting
            suggestions = suggest_subrouting(categories)
        if not suggestions:
            return {}
        from pollysort.config import pretty_category
        self.con.raw("  ↳ " + i18n.t("su.sub.q"))
        for cat, pattern in suggestions.items():
            self.con.raw(f"       {pretty_category(cat)} → {pattern}")
        return suggestions if self._ja_default("     " + i18n.t("su.sub.apply")) else {}

    def _choose_watch(self) -> str:
        """Schritt 4: Verhalten bei neuen Dateien im Eingang (alle ~10 s)."""
        self.con.raw("  4) " + i18n.t("su.watch.q"))
        self.con.raw("       [1] " + i18n.t("su.watch.off"))
        self.con.raw("       [2] " + i18n.t("su.watch.notify"))
        self.con.raw("       [3] " + i18n.t("su.watch.move"))
        choice = self._ask("     " + i18n.t("su.choice", default="1")).strip() or "1"
        return {"1": "off", "2": "notify", "3": "move"}.get(choice, "off")

    @staticmethod
    def _parse_cats(raw: str) -> list[str]:
        return [c.strip().lower() for c in raw.split(",") if c.strip()]

    def _ollama_ready(self, *, refresh: bool = False) -> bool:
        """Antwortet ein lokaler Ollama-Server? Das Ergebnis wird für die Sitzung gemerkt.

        Früher lief diese Prüfung bei **jedem** Start — ohne laufenden Ollama kostete das
        jedes Mal den vollen Verbindungs-Timeout, bevor überhaupt das Banner erschien.
        Jetzt wird nur dort geprüft, wo die Antwort gebraucht wird; ``refresh=True``
        erzwingt eine frische Prüfung (wenn der Nutzer den Modus bewusst umstellt).
        """
        if refresh or self._ollama is None:
            from pollysort.llm.client import ollama_available
            self._ollama = ollama_available()
        return bool(self._ollama)

    def _apply_theme(self, pref: str) -> str:
        """Themen-Voreinstellung setzen und sofort aufs Terminal anwenden.

        Gibt das effektive Thema zurück (``auto`` löst sich nach Tageszeit auf).
        """
        self._theme_pref = pref
        return self.con.set_theme(resolve_theme(pref))

    def _save_key(self, key: str) -> bool:
        """Den OpenRouter-Key lokal ablegen. Gibt zurück, ob es geklappt hat.

        🔒 Wachssiegel: Der Key wird nur an ``config.save_credentials`` weitergereicht
        (chmod 600) — er wird nie ausgegeben, geloggt oder in einen Prompt geschrieben.
        """
        try:
            config.save_credentials(key.strip())
        except OSError as exc:
            self.con.error(f"Key konnte nicht gespeichert werden: {exc}")
            return False
        return True

    def _ensure_key(self) -> bool:
        """Sicherstellen, dass ein OpenRouter-Key da ist (fragt bei Bedarf). True = vorhanden."""
        if config.load_credentials():
            return True
        key = self._ask("     🔑 OpenRouter API-Key (leer = abbrechen): ").strip()
        if not key or not self._save_key(key):
            return False
        self.con.honey("     Key gespeichert (chmod 600).", "✅")
        return True

    def _update_seed(self, **changes) -> None:
        """Ein paar Felder der Projekt-Config ändern und speichern."""
        seed = config.load_seed(self.hive)
        for k, v in changes.items():
            setattr(seed, k, v)
        config.write_seed(self.hive, seed)

    def _ask(self, prompt: str, *, abortable: bool = True) -> str:
        """Eine Frage stellen. Tippt der Nutzer ein Abbruch-Wort (oder Strg-C/Strg-D),
        wird die ganze Aktion sauber abgebrochen (``AbortAction``) — nichts wird ausgeführt.
        """
        try:
            raw = input(prompt)
        except EOFError:
            raise AbortAction from None
        except KeyboardInterrupt:
            self.con.raw("^C")
            raise AbortAction from None
        if abortable and raw.strip().lower() in ABORT_WORDS:
            raise AbortAction
        return raw

    # ------------------------------------------------------------------ #
    #  Interne Helfer
    # ------------------------------------------------------------------ #
    def _ctx(self) -> Context:
        seed = config.load_seed(self.hive)
        cfg = config.load_config()
        cfg.llm_provider = seed.provider            # KI-Backend pro Projekt
        api_key = config.load_credentials() if seed.provider == "openrouter" else None
        from pollysort.feedback import Feedback
        from pollysort.wachstafel import Wachstafel
        few = Feedback(self.hive).few_shots()
        # Gelernte Projekt-Regeln (ACE) beim Sortieren beachten — strikt projektgebunden.
        wachstafel = Wachstafel(self.hive).text()
        client = build_client(cfg, api_key, seed.categories, few, wachstafel=wachstafel)
        return Context.build(hive=self.hive, cfg=cfg, seed=seed, client=client,
                             console=self.con, journal=Journal(self.hive))

    def _table(self, rows: list[dict]) -> None:
        if not rows:
            self.con.info("Keine Treffer.", "🕸️")
            return
        from rich.table import Table
        from rich.text import Text
        table = Table(show_header=True, header_style="bold gold1", box=None)
        for col in ("id", "kategorie", "status", "titel", "datei"):
            table.add_column(col)
        for r in rows[:60]:
            table.add_row(Text(r["id"]), Text(r.get("kategorie") or ""),
                          Text(r.get("status") or ""), Text((r.get("title") or "")[:34]),
                          Text((r.get("filename") or "")[:30]))
        self.con.raw(table)

    # ------------------------------------------------------------------ #
    #  Englische Befehls-Aliase (ENG Mode) — dieselben Handler, engl. Namen.
    #  So können englischsprachige Nutzer das Tool in ihrer Sprache bedienen.
    # ------------------------------------------------------------------ #
    do_sort = do_sortiere
    do_preview = do_vorschau
    do_capture = do_erfasse
    do_import = do_importiere
    do_watch = do_wache
    do_review = do_rueckfragen
    do_assign = do_zuordnen
    do_list = do_liste
    do_search = do_suche
    do_new = do_neu
    do_switch = do_wechsel
    do_projects = do_projekte
    do_mode = do_modus
    do_model = do_modell
    do_trash = do_papierkorb
    do_restore = do_zurueckholen
    do_duplicates = do_dubletten
    do_empty = do_leeren
    do_undo = do_rueckflug
    do_subfolder = do_unterordner
    do_memory = do_gedaechtnis
    do_recommend = do_empfehlung
    do_swarm_status = do_schwarm
    do_calendar = do_kalender
    do_routes = do_flugrouten
    do_reflect = do_reflektiere
    do_rules = do_wachstafel


def _startup_target() -> Path | None:
    """Welches Projekt beim Start? Argument > zuletzt genutztes > erstes bekanntes > keins.

    Es gibt KEIN stilles Default-Verzeichnis mehr: ist nichts hinterlegt, wird ``None``
    zurückgegeben → die Konsole startet die Erst-Einrichtung (fragt nach dem Pfad).
    """
    for a in sys.argv[1:]:
        if not a.startswith("-"):
            return Path(a).expanduser().resolve()
    cfg = config.load_config()
    if cfg.hive:
        p = Path(cfg.hive)
        if p.exists() and config.is_setup(p):
            return p.resolve()
    for p in config.list_projects():
        if config.is_setup(p):
            return p.resolve()
    return None


def _configure_console() -> None:
    """Windows-Konsolen laufen oft mit cp1252 → Emojis würden crashen. UTF-8 erzwingen."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


def main() -> int:
    """Einstiegspunkt der Konsole — vom Befehl ``pollysort`` und von ``polly.py`` gerufen."""
    _configure_console()
    shell = BeehiveShell(_startup_target())
    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        shell.con.raw("")
        shell.con.info("Abgebrochen. 🐝", "🐝")
    finally:
        shell.con.reset_terminal_colors()   # Terminal-Standardfarben wiederherstellen
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Changelog

Alle nennenswerten Änderungen an **PollySort** (Developed by Akinara).
Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

Interne Metaphern (Bienen/Waben/Honig) und der Paketname `bumble` bleiben bewusst bestehen —
sichtbar ist der Produktname PollySort.

## [Unveröffentlicht]

_Noch nichts._

## [0.4.0b1] — 2026-07-15 — erste öffentliche Beta

Erste öffentlich getestete Version. Bündelt die gesamte bisherige Entwicklung (Kern, Schwarm,
Stufe 2, Rebranding auf PollySort) und macht das Paket beta-tauglich.

### Hinzugefügt
- **Ultra Swarm** (`sortiere turbo [N]`): teure KI-Analysen laufen parallel und wärmen den
  Analyse-Cache vor; das Einlagern bleibt einthreadig → keine Races, gleiches Ergebnis. Lizenzpflichtig.
- **Live-Preview & Apply** (`vorschau`): zeigt den Plan und wendet ihn direkt an — der Analyse-Cache
  spart die zweiten KI-Calls; nebenwirkungsfrei bis zum „Ja".
- **Echtzeit-Wache** (`wache`): watchdog-Observer auf dem Eingang, reagiert sofort auf neue Dateien;
  Polling als Rückfallebene.
- **Scan/Sweep** (`scan`): Drift-Bericht über den ganzen Ordner und **Lernen aus manuellen Moves**
  zwischen Waben (kostenfrei, kein KI-Call).
- **Sub-Routing** (`unterordner <kat> {jahr}/{monat}`): dynamische Unterordner pro Kategorie; der
  Setup-Assistent schlägt datums-laufende Kategorien selbst vor.
- **Gedächtnis-Reindex** (`gedaechtnis neu`): erkennt einen Wechsel des Embedding-Modells (nur per
  Config-Datei möglich) an gespeichertem Modellnamen bzw. gemischten Vektor-Dimensionen, warnt bei
  `sortiere`/`doctor`/`gedaechtnis` und bettet das Gedächtnis mit dem aktuellen Modell neu ein. [F1]
- **ENG-Mode** (`sprache de|en`): umschaltbare UI-Sprache (`i18n`) und englische Befehls-Aliase
  (`sort`, `preview`, `list`, `watch`, `scan`, `new` …).
- **Start-/Zuhause-Bildschirm** (`home`), **3-Ebenen-Hilfe** (Täglich · Anwendungsfälle · Profis),
  **Erststart-Tutorial** und **Abbruch** aus jeder Abfrage (`abbruch`/`bye`/`exit`/Strg-C).
- **Fair-Code-Lizenzmodul** (`lizenz`): bis 5 Projekte gratis, Ultra-Swarm-Gate, Key nur maskiert
  gespeichert; **`doctor`** Health-Check (Interpreter, Provider, DB, Extras, Lizenz, Gedächtnis).
- **Offline-Heuristik** ausgebaut: 254 Begriffe über 12 Kategorien; nahtloser Mid-Run-Fallback
  (≥ 3 KI-Fehler in Folge → Rest des Laufs offline).
- **CI-Matrix** (`.github/workflows/ci.yml`: ruff + pytest auf {Windows, macOS, Ubuntu} × {3.12, 3.13}).
- **Installationsanleitung** in der README (clone → `pipx install ".[extract]"` → `bumble`).

### Geändert
- **Rebranding** des sichtbaren Namens: *Bumble Beebliothek* → *BumbleNara* → **PollySort**
  (neues ASCII-Banner, „Developed by Akinara", alle sichtbaren Titel, README). Paketname `bumble`,
  Befehle (`bumble`/`bumble-cli`), `~/.beehive` und `.honig` bleiben bewusst unverändert.
- **Paket-Metadaten** für die Beta: Distributionsname `pollysort`, Version `0.4.0b1`, Autor „Akinara".
- **Hilfe** zeigt jetzt die Optionen von `thema [dunkel|hell|auto]` und `ansicht [statisch|log]`
  (vorher verschluckt), plus `gedaechtnis [approve|neu]`.
- **`neu`** überspringt bei einem bereits konfigurierten (kopierten) Ordner das Setup nicht mehr
  still, sondern fragt „neu einrichten?" (altes `.honig` wird gesichert, nichts gelöscht).

### Behoben
- **Rogue-Ordner**: das LLM rastet gelieferte Labels auf die bekannten Kategorien ein
  (`snap_category`) — kein Ordner außerhalb der Projekt-Menge mehr.
- **F1**: stille Gedächtnis-Degradation nach einem Embedding-Modellwechsel (Alt-Vektoren fremder
  Dimension wurden totes Gewicht) — jetzt erkannt und per Reindex behebbar.
- Zahlreiche QA-Fixes (BUG-1…12): centroid-Absturz bei gemischten Dimensionen, fehlende REPL-Fehler-
  Isolation, Dry-run-Nebenwirkung, Retry von `error`-Einträgen, Wachstafel-Stoppwortfilter,
  `rueckflug`/`zurueckholen`-Zielpfade, Dubletten-Aufräumen, Font-Lizenz-Filter (DOCX), Repair-Retry
  + Fallback-Modell bei kaputtem LLM-JSON, BOM-Toleranz auf Pipes, zentrale Timeouts.
- **Ollama** robust: 4xx nicht mehr endlos wiederholt, klare Fehlermeldung, lokale PDF-Extraktion,
  automatischer **CPU-Fallback** bei GPU-Backend-Crash, Embedding-Task-Prefix.

### Sicherheit
- 🔒 **Kein Master-/Dev-Schlüssel mehr im Code**: die Dev-Freischaltung läuft nur noch über die
  Umgebung (`POLLYSORT_DEV_LICENSE=1` bzw. optional `POLLYSORT_MASTER_KEY`) — kein auslieferbares
  Backdoor-Geheimnis im Repo/Wheel.
- 🔒 **Wachssiegel**: API-Keys, SMTP-/Bot-Zugänge und der Lizenzschlüssel liegen nur lokal und
  maskiert, nie im Klartext, nie in Logs oder LLM-Prompts.

### Bekannte Einschränkungen
- Lizenz-Validierung ist noch offline/lokal (jeder wohlgeformte Key aktiviert eine bezahlte Stufe);
  die echte License-API + Signatur folgt nach der Beta. Für die Gratis-Beta bewusst so.
- Ollamas GPU-Backend crasht auf manchen Maschinen (Treiber); das Tool weicht sauber auf CPU aus.
- `LICENSE.md` ist ein Proprietary-Beta-Platzhalter; der finale Fair-Code-Text (siehe
  `LICENSE-KONZEPT.md`) wird nach der Beta juristisch geprüft eingesetzt.

---

## Entwicklungshistorie (vor der Beta, nicht öffentlich veröffentlicht)

### [0.3.0] — 2026-07-14 — Schwarm, Stufe 2 & Außenwelt
- Schwarm-Architektur (`swarm/`: Königin, Spur-/Bau-/Sammel-/Wächterbienen; `schwarm`).
- **Stufe 2 Wabenbau**: `Bienenstock.md`-Charter mit Stakeholdern und Deadlines.
- **Pollen-Uhr**: abonnierbarer Kalender-Export `.honig/kalender.ics` (RFC 5545).
- **Flugrouten**: Discord-Bot + SMTP-E-Mail (opt-in, Anti-Spam, gemockt getestet).
- **Wachstafel-Meta-Learning** (ACE+RISE): Korrekturen → Regeln in `wachstafel.md` → Prompt-Injection
  bzw. Offline-Anwendung; projekt-isoliert, kein Code-Gen.
- Migration eines v0.1-Stocks auf den aktuellen Stand ohne Datenverlust verifiziert (QA-Runde 3+4).

### [0.2.0] — 2026-07-08 — Deployment & lokale KI
- Paketierung für `pipx` / `uv tool install` (Entry-Points `bumble`, `bumble-cli`).
- Kern-Dependencies entschlackt (Extraktion via Extra `[extract]`).
- Lokale KI über Ollama (`/v1`-API). QA-Runden 1+2: BUG-1…4 + OPT-1…6 behoben.

### [0.1.0] — Kern
- Interaktive REPL, Mehrprojekt-Verwaltung, Einrichtungs-Assistent.
- `sortiere`/`vorschau`/`importiere`, SHA-256-Dedupe, **nie löschen/überschreiben** (Kollisions-Suffixe).
- SQL-Index + Markdown/JSON-Einträge (PKM-ready), Hive-Mind-Vektorgedächtnis mit Confidence-Logik.
- Rückfragen, Zuordnen, Gedächtnis, Empfehlungen, Überwachung (`wache`), Quarantäne (`papierkorb`),
  Undo (`rueckflug`).

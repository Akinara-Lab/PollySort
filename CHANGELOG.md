# Changelog

Alle nennenswerten Änderungen an **PollySort** (Developed by Akinara).
Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

Interne Metaphern (Bienen/Waben/Honig) und der Paketname `bumble` bleiben bewusst bestehen —
sichtbar ist der Produktname PollySort.

## [Unveröffentlicht]

### Geändert — Open Core (Apache-2.0)
- **Lizenz von Fair-Code auf [Apache-2.0](LICENSE) umgestellt.** PollySort ist damit echtes,
  OSI-anerkanntes Open Source. Grund: Der Wert des Projekts für Akinara liegt in Sichtbarkeit
  und Vertrauen, nicht in Lizenzumsatz — den trägt später das kommerzielle Web-Cockpit.
- **Lizenz-Gate vollständig aus dem Kern entfernt** (`licensing.py`, `lizenz`,
  `bumble-cli activate`, Doctor-Lizenzzeile, Projektzähler). Es gibt keine Freigrenze mehr.
- **Ultra Swarm (`sortiere turbo`) ist jetzt frei** — vorher lizenzpflichtig.
- `NOTICE`, `TRADEMARK.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`,
  Issue-/PR-Vorlagen ergänzt. `LICENSE-KONZEPT.md` entfällt (Fair-Code-Modell hinfällig).
- `pyproject.toml`: `License-Expression: Apache-2.0`, Projekt-URLs, Klassifizierer.

### Geändert — Erststart
- **Erststart-Assistent neu gebaut** (`firstrun.py`): vier Schritte in fester Reihenfolge —
  **Sprache → Darstellung → KI-Backend → Überblick**. Die Sprache kommt zuerst, damit jede
  weitere Frage schon in der gewählten Sprache steht; das Thema wird sofort angewandt.
- **Sprache und Thema werden überhaupt erst gefragt** — vorher startete jeder Nutzer
  unwiderruflich auf Deutsch im Dunkel-Modus, ohne je gefragt worden zu sein.
- **Englisch ist die Vorauswahl** (Enter = English); Deutsch bleibt voll gleichwertig.
- **KI-Auswahl zeigt die Verfügbarkeit ehrlich an** (Ollama erkannt / nicht erreichbar, Key
  hinterlegt / nötig) und schlägt nur eine Option vor, die auch funktioniert. Wer trotzdem
  ein nicht erreichbares Ollama wählt, landet in Offline statt im ersten Sortierlauf zu scheitern.
- **Der komplette Projekt-Assistent ist übersetzt** (Pfad, Name, KI-Modus, Kategorien,
  Unterordner, Überwachung) — ein englischer Nutzer fällt nicht mehr nach dem zweiten Schritt
  zurück ins Deutsche. `yes` wird jetzt als Zustimmung verstanden.
- **Flugrouten-Frage aus dem Erststart entfernt**: ohne Projekt gibt es noch keine Deadlines,
  über die jemand benachrichtigt werden könnte. Der Hinweis steht jetzt im Abschluss-Überblick.
- Das getrennte 3-Schritt-Tutorial entfällt; es ist Schritt 4 des Assistenten geworden.

### Behoben
- **Ollama wurde bei jedem Start geprüft**, auch wenn die Einrichtung längst stand — ohne
  laufenden Ollama kostete das jeden Start den vollen Verbindungs-Timeout, bevor auch nur das
  Banner erschien. Die Prüfung läuft jetzt erst, wenn die Antwort gebraucht wird, und wird
  für die Sitzung gemerkt.

### Qualität
- **144 Tests grün** (vorher 124), `ruff` clean. Neu: `test_firstrun.py` (20) und
  `test_doctor.py` (5, inkl. Wächter gegen ein zurückkehrendes Lizenz-Gate).
- i18n-Wächter: jeder Katalog-Eintrag muss DE **und** EN haben, mit identischen Platzhaltern.
- **Wheel-Build erstmals real verifiziert** (`uv build` → Installation in frischem venv →
  `bumble` und `bumble-cli doctor` laufen). Damit ist der letzte offene Beta-SOLL-Punkt erledigt.

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

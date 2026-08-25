# 🐝 PollySort

> _Developed by Akinara_

Ein lernender Dokumenten-Archivar für die Konsole. Du zeigst auf einen Ordner voller loser
Dateien, tippst **`sortiere`** — und das Tool räumt sie in saubere Kategorie-Ordner ein.
Es lernt mit jeder Korrektur dazu.

**Aufgeräumt by design:** Alles, was das Tool generiert (Datenbank, Logs, Gedächtnis,
Einträge, Quarantäne), liegt in **einem einzigen versteckten Ordner `.honig`**. Dein
Verzeichnis bleibt sauber — sichtbar entstehen nur die Kategorie-Ordner.

---

## Installation

Voraussetzung: **Python 3.12+**. PollySort ist ein reines Konsolen-Tool. Empfohlen wird eine
isolierte Installation mit [`pipx`](https://pipx.pypa.io) oder
[`uv`](https://docs.astral.sh/uv/) — das legt den Befehl **`bumble`** in deinen PATH, ohne dass
du dich um virtuelle Umgebungen kümmern musst (Windows, macOS und Linux gleichermaßen).

### Am einfachsten: das Installer-Skript

Das Projekt bringt ein Installer-Skript mit, das **die Voraussetzungen prüft** (Projektdateien
vorhanden, Python 3.12+), automatisch das beste verfügbare Werkzeug wählt (`uv` → `pipx` → `pip`)
und PollySort inklusive Text-Extraktion (`[extract]`) installiert:

- **Windows:** Doppelklick auf **`install.bat`** — oder im Terminal `install.bat`.
- **Linux / macOS / Git-Bash:** **`bash install.sh`**  (ggf. vorher `chmod +x install.sh`).

Am Ende meldet das Skript, ob der Befehl `bumble` bereit ist. Kommt der Hinweis, dass `bumble`
noch nicht im PATH liegt, hilft ein Neustart des Terminals bzw. `pipx ensurepath`.

### Manuell (oder wenn das Skript nicht passt)

**Schnellstart (während der Beta wird aus dem Repo installiert):**

```bash
# 1) Code holen
git clone <repo-url> pollysort      # alternativ: ZIP herunterladen und entpacken
cd pollysort

# 2) Installieren (empfohlen: mit besserer Text-Extraktion)
pipx install ".[extract]"           # oder:  uv tool install ".[extract]"

# 3) Prüfen & starten
bumble doctor                       # Health-Check: Python, KI-Provider, DB, Lizenz
bumble                              # öffnet die interaktive Konsole
```

Das Extra `[extract]` (DOCX/CSV/HTML → Markdown, MIME-Erkennung via libmagic) ist **optional** —
bewusst nicht im Kern, damit die Installation überall problemlos durchläuft. Nur der Kern genügt:

```bash
pipx install .                      # oder:  uv tool install .
```

> Ohne `[extract]` fällt das Tool auf `mimetypes` + rohes Textlesen zurück — es funktioniert,
> erkennt Dateitypen/Office-Formate aber etwas gröber. PDFs liest der Kern immer selbst
> (`pypdf`) — wichtig für die **lokale KI (Ollama)**, die keine Datei-Anhänge kennt.

> **🦙 Robuste lokale KI:** Stürzt Ollamas GPU-Backend ab (Treiberprobleme), wechselt PollySort
> automatisch auf CPU-Inferenz (`num_gpu: 0`) — langsamer, aber es läuft weiter.

**Aktualisieren** (nach `git pull`): `pipx install --force ".[extract]"` bzw.
`uv tool install --force ".[extract]"`. **Deinstallieren:** `pipx uninstall pollysort`.

**Entwicklung (aus dem geklonten Repo, editierbar + Test-/Lint-Tools):**

```bash
uv pip install -e ".[extract,dev]"   # oder: python -m venv .venv && pip install -e ".[extract,dev]"
```

> **Ohne Installation** geht aus dem Repo weiterhin `python Beehive.py [pfad]` — läuft das
> versehentlich unter einem alten Python, wechselt es automatisch in die projekteigene `.venv`.

---

## Starten

Nach der Installation:

```bash
bumble                    # öffnet das zuletzt genutzte Projekt (interaktive Konsole)
bumble "C:\Pfad"          # öffnet/erstellt ein Projekt an diesem Pfad
```

Aus dem Repo ohne Installation geht weiterhin `python Beehive.py [pfad]` — läuft das
versehentlich unter altem Python, wechselt es automatisch in die projekteigene `.venv`.
Für Skripting/Automatisierung gibt es zusätzlich das Zweit-Kommando **`bumble-cli`**
(z. B. `bumble-cli scan --mode move`).

Das öffnet eine interaktive Konsole. Ein **Projekt** ist ein Ordner, dessen Dokumente sortiert
werden; die losen Dateien darin sind dein Posteingang. Das Tool geht **nicht** vom aktuellen
Verzeichnis aus — es merkt sich deine Projekte.

**Beim allerersten Start** klärt eine einmalige Grundeinrichtung das KI-Backend: Es erkennt ein
lokales **Ollama** und fragt, ob ein **OpenRouter-Key** hinterlegt werden soll. Danach fragt der
Assistent **zuerst nach dem Ordner-Pfad** und führt durch die Projekt-Einrichtung. Zum Warmwerden
zeigt das Tool ein kurzes **3-Schritt-Tutorial** — **Ordner wählen → `vorschau` → `sortiere`** —
damit du den ersten Schwung Dateien sofort einräumen kannst.

Reihenfolge: **Name → KI-Modus → Kategorien → Überwachung.** Bei den Kategorien gibt es einen
**Vorschlags-Modus** — er schaut sich sowohl die losen Dateien **als auch die bereits bestehende
Ordnerstruktur** an (vorhandene Unterordner = schon gelebte Kategorien, adaptiv statt starr) und
schlägt daraus eine Struktur vor. Im Online-Modus analysiert die **KI** die Dokumente inhaltlich,
offline heuristisch. Jedes Projekt speichert seine Config in `.honig/hive.toml`; so laufen
**mehrere Projekte unabhängig nebeneinander** (`neu`, `wechsel <nr>`).

```text
🐝  PollySort
──────── Erste Einrichtung ────────
🦙  Lokales Ollama erkannt — KI kann kostenlos & privat lokal laufen.
🔑  OpenRouter-API-Key hinterlegen? [j/N]: n

🐝  Willkommen! Noch kein Projekt vorhanden.
  📂 Pfad zum Projekt-Ordner: C:\Users\ich\Documents\test hive
──────── Projekt einrichten ────────
  1) Projektname [test hive]: Kanzlei
  2) KI-Modus — womit sollen Dokumente eingeordnet werden?
       [1] Offline — Heuristik, kostenlos, ohne Internet
       [2] Lokale KI (Ollama) — gratis & privat
     Wahl [2]: 2
  3) Kategorien — wie soll einsortiert werden?
       [1] Vorschlag — Dateien & bestehende Ordner anschauen (die KI schaut sie an)  (empfohlen)
       [2] Standard  ·  [3] Eigene
     Wahl [1]: 1
  📁  14 Datei(en) angeschaut (KI-Analyse, davon 2 vorhandene Ordner) — Vorschlag:
       Steuer 2023  ██████████ 4 · vorhanden
       Rechnungen   ███████ 3
       Fotos        █████ 2 · vorhanden
       Vertraege    █████ 2
       …
     Übernehmen? [J/n]: j
  4) Neue Dateien im Eingang (alle ~10 s prüfen)?
       [1] aus  ·  [2] nur melden  ·  [3] sofort sortieren
     Wahl [1]: 3
✅  'Kanzlei' · 6 Kategorien · Modus ollama · Eingang: auto-sortieren

🐝 test hive ▸ sortiere
🍯  10 Datei(en) sortiert: 3 → Rechnungen, 2 → Vertraege, 2 → Bilder, …
🎉  Sauber sortiert — nichts bleibt liegen!
```

Beim nächsten Öffnen desselben Ordners wird die Config geladen (kein Assistent mehr).
`setup` richtet neu ein, `projekte` zeigt alle Projekte, `ordner <pfad>` wechselt.

---

## Befehle

**Loslegen**

| Befehl | Wirkung |
|---|---|
| `home` · `start` | Zurück zum **Start-/Zuhause-Bildschirm** (Banner + Name), dann aktuelles Projekt (Modus, Eingang, offene Rückfragen, fällige Deadlines) + Liste aller Projekte — funktioniert aus jeder Ebene, wie direkt nach dem Öffnen |
| `sortiere` · `s` | Lose Dateien hier in Kategorie-Ordner einräumen |
| `sortiere turbo [N]` | „Ultra Swarm": KI-Analysen laufen parallel (Standard 10 Bienen, `turbo N` setzt die Anzahl) — deutlich schneller bei vielen Dateien, gleiches Ergebnis (lizenzpflichtig) |
| `scan` · `sweep` | Ganzen Ordner auf manuelle Änderungen prüfen (verschoben/geändert/neu/verschwunden) und aus Hand-Verschiebungen lernen — kostenfrei (kein KI-Call) |
| `wache` | Eingang in **Echtzeit** überwachen (watchdog) — neue Dateien sofort erkennen und melden bzw. sortieren; Strg-C beendet |
| `rueckfragen` · `r` | Unsichere Fälle schnell selbst zuordnen |
| `status` | Was liegt hier, was ist schon sortiert? |

**⚡ Ultra Swarm (`sortiere turbo`).** Bei vielen Dateien lässt du die Königin die KI-Analysen
**parallel** durch mehrere Bienen fliegen (Standard 10, `turbo N` setzt die Anzahl) — das Einlagern
selbst bleibt sicher **einthreadig**, das Ergebnis ist identisch, nur schneller. Ultra Swarm ist ein
**lizenzpflichtiges** Feature: ohne Lizenz sortiert das Tool ganz normal weiter (mit kurzem Hinweis).

**🧹 Nachträglich aufräumen & lernen (`scan` / `sweep`).** `scan` schaut den ganzen Ordner durch und
erkennt, was du **von Hand** geändert hast (verschoben/geändert/neu/verschwunden). Ziehst du eine
Datei selbst von **Wabe A nach Wabe B**, zieht Bumble das als Korrektur an und lässt die Königin
daraus **Wachstafel-Regeln** ableiten — kostenfrei, ganz ohne KI-Anfrage.

**👁️ Echtzeit-Wache (`wache`).** Der Wachdienst überwacht den Eingang jetzt live per **watchdog**
statt nur zu pollen — neue Dateien werden sofort erkannt. Fällt watchdog aus, greift automatisch das
Polling als Rückfallebene; **Strg-C** beendet den Dienst.

**Finden**

| Befehl | Wirkung |
|---|---|
| `liste [kategorie]` | Sortierte Einträge auflisten |
| `suche <wort>` | Nach Stichwort suchen |

**Projekt**

| Befehl | Wirkung |
|---|---|
| `neu [pfad]` | Neues Projekt anlegen (fragt nach dem Ordner) |
| `wechsel [nr]` | Zu einem anderen Projekt wechseln |
| `projekte` | Alle Projekte anzeigen (nummeriert) |
| `setup` | Aktuelles Projekt neu einrichten |
| `modus <offline\|ollama\|online>` | KI-Backend für dieses Projekt wählen |
| `modell [name\|liste]` | OpenRouter-Modell im Betrieb wechseln (Nektar-Sorte) |
| `schluessel [test\|setzen\|entfernen]` | OpenRouter-Schlüssel prüfen / erneuern / entfernen |
| `lizenz [aktivieren <KEY>\|entfernen]` | Fair-Code-Lizenzstatus zeigen / verwalten (Aktivierung auch als `bumble-cli activate <KEY>`) |
| `doctor` | Health-Check: Interpreter, KI-Provider-Erreichbarkeit, Datenbank, Extraktions-Extras, Lizenzstatus (auch als `bumble-cli doctor`) |

> **🔒 Wachssiegel:** Dein Lizenzschlüssel wird **nur maskiert lokal** gespeichert — nie im Klartext,
> nie in Logs oder KI-Prompts. Mehr zum Modell im Abschnitt [Lizenz (Fair-Code)](#lizenz-fair-code).

**Schwarm & Projektmanagement (Stufe 2)**

Der Schwarm besteht aus der **Königin** (Orchestrator) und spezialisierten Bienen:
**Spurbienen** (sortieren), **Baubienen** (Projekte/Charter), **Sammelbienen** (lernen
Ablage-Gewohnheiten) und **Wächterbienen** (Eingang & Deadlines).

| Befehl | Wirkung |
|---|---|
| `wabenbau [kategorie]` | Aus einer sortierten Wabe ein Projekt bauen — erzeugt `Bienenstock.md` (Charter), fragt fehlende Infos bei den Stakeholdern ab, setzt Deadlines |
| `schwarm` | Überblick: Königin & Bienen (Waben, offene Fälle, Projekte, Deadlines) |
| `kalender [melden]` | Deadlines zeigen · `melden` schickt fällige Erinnerungen über die Flugrouten |
| `flugrouten [setup\|test\|aus]` | Discord/E-Mail-Benachrichtigungen der Wächterbienen (opt-in) |
| `reflektiere` | Königin leitet aus deinen Korrekturen Regeln ab (Wachstafel) |
| `wachstafel [leeren]` | Gelernte Projekt-Regeln zeigen (oder verwerfen) |

**Die lernende Wachstafel (Meta-Learning).** Korrigierst du eine Zuordnung (`zuordnen <id> <kat>`),
studiert die Königin die Korrekturen und **ritzt Regeln in natürlicher Sprache** in
`.honig/wachstafel.md` (z. B. „**telekom** → Wabe **internet_2026**"). Beim nächsten `sortiere`
beachten die Spurbienen diese Regeln — online als „Gelernte Projekt-Regeln" im LLM-Prompt, offline
direkt. So passt sich jeder Bienenstock hochspezifisch an dich an.

> **🔒 Sicher & projektgebunden:** Es wird **niemals Code** generiert — gelernt wird ausschließlich
> über die Textdatei `wachstafel.md`. Die Regeln gelten **nur für ihr Projekt** und sprechen nie
> in ein anderes über. `wachstafel` zeigt sie, `wachstafel leeren` verwirft sie.

> **Stufe 1 → Stufe 2:** `sortiere` bringt lose Dateien in Waben (Kategorie-Ordner);
> `wabenbau` macht aus einer Wabe ein Projekt mit Charter, Aufgaben und Terminen.

**Flugrouten (Benachrichtigungen, opt-in).** Über `flugrouten setup` (auch im Erststart-Onboarding)
weist du den Wächterbienen **Discord** (Bot-Token + Channel, echter API-Post) und/oder **E-Mail**
(SMTP-Presets für Gmail/Outlook oder benutzerdefiniert) als Flugrouten aus. Bei fälligen Deadlines
fliegen sie dann echt aus (`kalender melden` bzw. automatisch im `wache`-Dienst; Anti-Spam inklusive).

**Pollen-Uhr (Kalender-Sync via `.ics`).** Bei `wabenbau` schreiben die Baubienen die Projekt-Deadlines
zusätzlich als echte iCalendar-Datei nach `<projekt>/.honig/kalender.ics` (RFC 5545). Diese Datei
kannst du in **Apple Kalender, Outlook oder Google** abonnieren — bei jedem Wabenbau wird sie mit dem
aktuellen Stand überschrieben.

> **🔒 Wachssiegel (harte Regel):** Zugangsdaten liegen **nur lokal** in `~/.beehive/flugrouten.toml`
> (chmod 600, Env-Override möglich), **nie** im Projekt und **niemals** in einem LLM-Prompt.
> API-Calls (Discord/SMTP) laufen völlig unabhängig von der KI; in `log.jsonl` werden sensible
> Felder maskiert. Kein Auto-Versand ohne deine Konfiguration.

**Mehr**

| Befehl | Wirkung |
|---|---|
| `vorschau` · `v` | Sortier-Plan zeigen und direkt fragen „Änderungen jetzt anwenden? [J/n]" — beim Anwenden fallen dank Zwischenspeicher **keine zweiten KI-Anfragen** an |
| `unterordner <kategorie> <muster\|aus>` | Dynamische Unterordner je Kategorie mit Platzhaltern `{jahr}/{monat}/{tag}` (z. B. `unterordner rechnung {jahr}/{monat}`) — `aus` schaltet sie wieder ab |
| `importiere <ordner>` | Dateien aus einem anderen Ordner hierher sortieren |
| `zuordnen <id> <kat>` | Zuordnung korrigieren (Gedächtnis lernt dazu) |
| `person <name> <kat,..>` | Zuständigkeit im Hintergrund setzen |
| `gedaechtnis` | Gelernte Kategorien + Vorschläge (`gedaechtnis approve <slug>`) |
| `empfehlung [para\|johnny\|dewey]` | Ablage-Strategie + dynamische Hinweise |
| `papierkorb <id>` / `leeren` | In Quarantäne / endgültig löschen (mit Rückfrage) |
| `zurueckholen <id>` | Aus der Quarantäne zurückholen (zurück in ihre Wabe) |
| `dubletten [aufraeumen]` | Erkannte Dubletten zeigen · `aufraeumen` legt sie in die Quarantäne |
| `rueckflug` | Letzte Verschiebung rückgängig machen |
| `thema [dunkel\|hell\|auto]` | Dark-/Light-Mode; `auto` = tagsüber dunkel, abends hell |
| `ansicht [statisch\|log]` | Statische, sich selbst neu zeichnende Ansicht (kein Scrolling) oder klassisches Log |
| `sprache <de\|en>` · `language` · `lang` | UI-Sprache umschalten (Deutsch/Englisch) |
| `hilfe` / `exit` | Hilfe / Konsole verlassen |

**📁 Dynamische Unterordner (`unterordner`).** Je Kategorie legst du ein Ablage-Muster mit den
Platzhaltern `{jahr}`, `{monat}` und `{tag}` fest — `unterordner rechnung {jahr}/{monat}` legt
Rechnungen z. B. nach Jahr und Monat ab. Das Datum kommt aus **Titel/Dateiname**, sonst aus dem
**Katalog-Zeitpunkt**. `unterordner <kategorie> aus` schaltet das Muster wieder ab.

**🌍 Sprache & englische Aliase.** Mit `sprache en` schaltest du die Oberfläche auf Englisch (zurück
mit `sprache de`). Alle Befehle verstehen zusätzlich **englische Aliase** — z. B. `sort`, `preview`,
`list`, `review`, `watch`, `scan`, `new`, `switch`, `trash`, `restore`, `duplicates`, `subfolder`.

**🛟 Abbrechen.** Jede interaktive Abfrage (Setup, Rückfragen …) verlässt du sauber, indem du
`abbruch` (auch `bye`, `exit`, `zurück`) tippst oder **Strg-C** drückst — die Aktion wird dann
**nicht** ausgeführt, nichts geht verloren.

**❓ Hilfe in drei Ebenen.** `hilfe` gliedert die Befehle in **🐝 Täglich benötigt**,
**🎯 Für bestimmte Anwendungsfälle** und **🛠️ Für Profis** — so findest du dich schnell zurecht.

**Ansicht & Thema.** Standardmäßig läuft die Konsole in einer **statischen Ansicht**: Statt endlos
nach oben zu scrollen, leert sie vor jeder Ausgabe Bildschirm **und Scrollback** und zeichnet eine
feste Kopfzeile (Projekt · Modus · Eingang · Thema) neu — die Konsole aktualisiert sich also selbst.
Mit `ansicht log` schaltest du auf klassisches Scrolling zurück (bei Pipes/CI automatisch aktiv).

Über `thema dunkel`/`thema hell` wechselst du den **Dark-/Light-Mode**: Dabei wird der **gesamte
Terminal-Hintergrund** schwarz bzw. weiß eingefärbt (per OSC-Sequenz, nicht nur die Fläche hinter
dem Text), während **der Text gelb bleibt** und die Emojis unverändert sind. Beim Verlassen werden
die Standardfarben des Terminals wiederhergestellt. Beides wird global gemerkt.

Mit `thema auto` läuft die Konsole **automatisch nach Tageszeit**: tagsüber (07–19 Uhr) im
Dunkel-Modus, abends/nachts im Hell-Modus. Der Wechsel greift beim nächsten Befehl, sobald die
Uhrzeit die Grenze überschreitet.

> In modernen Terminals (Windows Terminal, iTerm2, GNOME Terminal, kitty …) färbt sich das ganze
> Fenster. Terminals ohne OSC-10/11-Unterstützung ignorieren die Sequenz — dann bleibt der Text
> gelb, nur der Hintergrund richtet sich nach der Terminal-Einstellung.

**Grundprinzip:** Es wird **nie** automatisch gelöscht oder überschrieben — nur verschoben.
Namenskollisionen bekommen ein eindeutiges Suffix. Löschen läuft ausschließlich über
`papierkorb` → `leeren` (mit Rückbestätigung).

---

## Was liegt wo?

```
<dein Ordner>/
├── Rechnungen/        ← sichtbare Kategorie-Ordner (das Ergebnis)
├── Vertraege/
├── Protokolle/
├── notiz.txt          ← lose Dateien, die noch deine Freigabe brauchen ('rueckfragen')
└── .honig/            ← EIN versteckter Ordner mit allem Generierten:
    ├── katalog.db         · durchsuchbarer Index
    ├── eintraege/         · pro Datei ein Markdown- + JSON-Eintrag (PKM-ready)
    ├── gedaechtnis.db     · das lernende Kategorie-Gedächtnis
    ├── taxonomie.toml     · gelernte Kategorien + Zuständigkeiten
    ├── korrekturen.jsonl  · Feedback aus deinen Zuordnungen
    ├── papierkorb/        · Quarantäne (nie automatisch geleert)
    ├── journal.md         · was wann passiert ist
    └── log.jsonl          · strukturiertes Log (nur Metadaten, nie Inhalte)
```

Die Markdown-Einträge beginnen mit YAML-Frontmatter und lassen sich direkt in
Obsidian, Logseq oder Notion öffnen.

---

## Tests & Lint

```bash
pip install pytest ruff
pytest -q
ruff check src Beehive.py
```

---

## Datenschutz

Offline verlässt kein Inhalt deinen Rechner. Online (OpenRouter) werden Dokumentinhalte zur
Analyse übertragen — vertrauliche Dateien vorher aussortieren oder Offline-Modus nutzen.

---

## Lizenz (Fair-Code)

PollySort ist **Fair-Code**: Der Quellcode ist öffentlich einsehbar, und für dich als
Privatperson bleibt der Schwarm großzügig kostenlos.

- 🐝 **Privat & intern kostenlos** — für deine eigenen Daten, bis zu **5 Projekte**.
- 🍯 **Ab dem 6. Projekt** oder für **zahlende Kundenprojekte** braucht es eine **Jahreslizenz**.
- ⚡ **Ultra Swarm** (`sortiere turbo`) ist ein **lizenzpflichtiges** Leistungs-Feature.

Läuft eine Lizenz aus, bleiben bereits sortierte Bestände und die Kernfunktionen nutzbar —
Fair-Code sperrt keine Daten weg. Den Status zeigst und verwaltest du mit `lizenz`; alle Details
zum Modell stehen in **[`LICENSE-KONZEPT.md`](LICENSE-KONZEPT.md)** (Preise findest du auf der
Produktseite, nicht hier im Repo).

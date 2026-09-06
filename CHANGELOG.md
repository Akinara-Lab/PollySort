# Changelog

Alle nennenswerten Änderungen an **PollySort** (Developed by Akinara).
Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

Interne Metaphern (Bienen/Waben/Honig) und der Paketname `pollysort` bleiben bewusst bestehen —
sichtbar ist der Produktname PollySort.

## [Unveröffentlicht]

### Hinzugefügt — Release-Workflow und CLA
- **`.github/workflows/release.yml`**: Tag → bauen → auf allen drei Betriebssystemen aus dem
  **Wheel** installieren und starten → GitHub-Release. Bewusst dreistufig: Ein Wheel, das
  sich nicht installieren lässt, darf nie auf PyPI landen — dort ist eine Version nicht
  ersetzbar, nur zurückziehbar. Eine Sperre bricht ab, wenn Tag und `pyproject`-Version
  auseinanderlaufen. Der PyPI-Schritt bleibt **inaktiv**, bis dort ein Trusted Publisher
  eingerichtet und `PUBLISH_TO_PYPI=true` gesetzt ist.
- **`CLA.md` + `.github/workflows/cla.yml`** (Entwurf, juristisch noch ungeprüft, Workflow
  inaktiv bis `REQUIRE_CLA=true`). Ohne CLA bleiben die Rechte an einem Beitrag bei der
  beitragenden Person — Akinara dürfte ihn dann nicht ins kommerzielle Cockpit übernehmen,
  und rückwirkend einholen lässt sich das praktisch nie.

### Geändert — der Sortierlauf spricht jetzt die gewählte Sprache
- Damit ist der Weg **durchgängig** zweisprachig: Erststart, Projekt-Einrichtung,
  Struktur-Vorschlag, Sortierlauf, Abschluss, Abzeichen, Verabschiedung. Vorher wählte man
  Englisch, richtete auf Englisch ein — und der erste Sortierlauf antwortete auf Deutsch.
- Auch der Unterordner-Vorschlag: `{year}/{month}` statt `{jahr}/{monat}`. Beide
  Schreibweisen löst `resolve_subpath` identisch auf, gespeicherte Muster funktionieren
  also unverändert weiter.
- `dubletten` versteht jetzt auch `cleanup`/`clean`/`tidy` — sonst hätte die englische
  Meldung auf ein Wort verwiesen, das der Befehl gar nicht kennt.
- Der Projekt-Journaleintrag (`journal.md`) bleibt bewusst deutsch: Eine über die Zeit
  gemischtsprachige Logdatei wäre schlechter lesbar als eine durchgängig deutsche.

### Behoben — das erste Dokument einer neuen Sorte landete in der Rückfrage
- **`vorwaermen.py`** (neu): Der Einrichtungs-Assistent schaut sich die Dokumente an und
  leitet daraus die Kategorien ab — dieses Wissen wurde danach **weggeworfen**. Jetzt legt
  er von **jeder** akzeptierten Kategorie bis zu zwei Vertreter ins Gedächtnis, bevor der
  erste Sortierlauf startet.
- **Die Ursache war nicht das leere Gedächtnis, sondern das einseitig gefüllte.** Ist das
  Gedächtnis leer, greift in `assigner.py` der Zweig „kein aussagekräftiges Gedächtnis →
  dem klaren Label vertrauen" (`BASE_KNOWN` = 0,80) und die Datei wird einsortiert. Sind
  aber erst zwei Rechnungen gespeichert, ist „rechnungen" für **jedes** weitere Dokument
  der kNN-Gewinner — und die erste Reisekostenabrechnung bekommt Widerspruch statt
  Bestätigung. Widerspruch wertet der Assigner als Mehrdeutigkeit (`CONFLICT` = 0,55), also
  Rückfrage, obwohl die Kategorie stimmt und der Nutzer sie Sekunden vorher bestätigt hat.
- Zwei Eigenschaften, auf die es dabei ankommt: Die Saat liegt unter **derselben ID**, die
  der echte Eintrag später bekommt (aus dem Inhalts-Hash) — der reale Lauf überschreibt sie,
  statt Dubletten anzulegen. Und gesät wird nur, was per `snap_category` auf eine
  **tatsächlich gewählte** Kategorie passt: Wer den Vorschlag verwirft und eigene Kategorien
  eingibt, bekommt kein Gedächtnis voller Labels, die es gar nicht mehr gibt.
- Der Embedding-Text hat jetzt **eine** Definition (`models._embedding_text`), die Saat und
  Echteintrag teilen — sonst lägen sie in verschiedenen Räumen und die Saat wäre wirkungslos.
- Scheitert eine Einbettung (Provider weg, Embedding-Modell nicht gezogen), wird sie
  übersprungen: Vorwärmen ist eine Verbesserung, kein Muss, und darf die Einrichtung nie
  abbrechen.
- **Gilt auch offline.** Dafür läuft der Struktur-Vorschlag jetzt für **jeden** Provider
  über den Client statt über eine abgekürzte Heuristik. Nur so entstehen vollwertige
  Analysen (Titel, Aufgabe, Summary, Keywords) — aus Label und Stichworten allein gebaute
  Vektoren lägen in einem anderen Textraum als die späteren echten Einträge und wären als
  Nachbarn wertlos. Der `OfflineClient` versteht dafür jetzt `categories=None` als „alle
  Regeln"; eine **leere Liste** bedeutet weiterhin „keine Kategorie erlaubt" und hätte für
  jedes Dokument `_unassigned` geliefert — genau daran scheiterte der erste Anlauf.
- **Gemessen mit `qwen3.5:9b`**, 6 Dokumente in 3 Kategorien: vorher 3 von 6 in der
  Rückfrage (zwei mit 0,55, eines als `_unassigned` mit 0,26), nachher **keine einzige** —
  alle zwischen 0,80 und 0,88. **Offline** dieselben Dokumente: alle 6 einsortiert mit
  0,90–0,93. Im Gedächtnis liegen danach jeweils 6 Vektoren, nicht 11: die Saat wurde von
  den echten Einträgen überschrieben.
- Zwei irreführende Meldungen dabei behoben: Der Vorschlag meldete offline „die KI
  begutachtet Dokumente" und hätte das Ergebnis als „KI-Analyse" ausgewiesen, obwohl offline
  keine KI rechnet.

### Hinzugefügt — Deinstallation
- **`uninstall.sh`, `uninstall.ps1`, `uninstall.bat`** (neu). Standardmäßig wird nur die
  **Anwendung** entfernt: die Befehle `pollysort`/`pollysort-cli` und der PATH-Eintrag des
  Installers — letzterer nur, wenn in dem Ordner nichts anderes mehr liegt (`~/.local/bin`
  gehört uv und pipx gemeinsam, nicht PollySort allein).
- **`--alles`** (PowerShell: `-Alles`) entfernt zusätzlich die globale Ablage
  `~/.pollysort` samt Einstellungen, OpenRouter-Schlüssel, Projektliste, Flugrouten und
  Historie — mit Rückfrage, und die alte `~/.beehive` gleich mit.
- **Nutzerdaten werden unter KEINER Option angefasst**: weder die Projektordner noch die
  versteckten `.honig`-Ordner darin. In `.honig/papierkorb/` liegt die Quarantäne, die noch
  echte Dateien enthalten kann, die aussortiert, aber nie endgültig gelöscht wurden. Der
  Deinstaller listet diese Ordner stattdessen auf. Ein Deinstaller, der ungefragt
  Nutzerdaten mitnimmt, ist Datenverlust mit gutem Gewissen.
- Beide kennen `--dry-run`.

### Behoben — stderr fremder Programme brach die PowerShell-Skripte ab
- Mit `$ErrorActionPreference = 'Stop'` macht PowerShell aus jeder stderr-Zeile eines
  aufgerufenen Programms einen Abbruch. Ein `pip show` für ein nicht installiertes Paket
  schreibt eine Warnung dorthin — und beendete die Deinstallation mitten im Lauf. Alle
  Aufrufe fremder Programme laufen jetzt durch einen Helfer, der stderr einsammelt und nur
  den Exit-Code weiterreicht. Dieselbe Falle steckte auch in `install.ps1`.

### Behoben — Mindestgröße einer Kategorie war absolut statt relativ
- Aufgefallen in einem echten Ollama-Lauf: sechs Dokumente in drei sauber getrennten
  Gruppen zu je zwei wurden zu **einer** Wabe zusammengefaltet, weil eine Kategorie starr
  drei Dokumente brauchte. Bei sechs Dokumenten sind drei Ordner aber genau richtig. Die
  Untergrenze skaliert jetzt mit dem Bestand: nie mehr als ein Viertel, nie weniger als zwei.

### Behoben — erfundene Kosten im lokalen Betrieb
- Der Sortierlauf meldete auch offline und mit Ollama „N KI-Anfragen · ~0.0006 €". Offline
  gibt es gar keine KI-Anfrage, und lokale Inferenz kostet nichts. Jetzt sagt die Zeile, was
  wirklich passiert ist — Vertrauen ist bei einem Werkzeug, das die eigenen Dokumente liest,
  die ganze Währung.

### Hinzugefügt — Klare Regeln gegen Doppelordner
- **`taxonomie.py`** (neu): Bisher wurde jedes Dokument **einzeln** analysiert und die
  Labels nur gezählt — niemand schaute je auf die Gesamtmenge. Dasselbe Bündel Rechnungen
  bekam so mal „rechnungen", mal „finanzen", mal „belege": drei Ordner für einen Stapel.
  Jetzt gibt es eine Konsolidierung mit sieben verbindlichen Regeln, die in **zwei** Ebenen
  wirken: als System-Message für das Modell **und** als deterministische Nachkontrolle im
  Code. Ein Sprachmodell hält sich nicht zuverlässig an Vorgaben; die Ordnerstruktur des
  Nutzers ist kein Ort für „meistens".
- Die Leitregel: **Zwei Ordner dürfen nie dieselbe Frage beantworten.** Ein Oberbegriff
  („Finanzen") verschwindet neben seinem Unterbegriff („Rechnungen"); umgekehrt bleiben
  echte Gruppen (Rechnungen · Reisekosten · Kontoauszüge) getrennt. Jede Zusammenlegung
  wird im Klartext protokolliert — der Nutzer soll sehen, *warum* aus fünf Vorschlägen
  drei Ordner wurden.
- **Deutsche Komposita** werden erkannt: „eingangsrechnungen" ist dasselbe wie
  „rechnungen", „reisekostenabrechnung" aber ausdrücklich **nicht** — entschieden über den
  Fugenlaut vor dem Kopf-Nomen, nicht über einen naiven Teilstring-Vergleich.

### Behoben — `classify` nahm die erstbeste statt der besten Kategorie
- Die Offline-Klassifikation lief `RULES` in Dict-Reihenfolge durch und nahm den **ersten**
  Treffer. Weil `rechnungen` der erste Schlüssel ist und dort Allerweltswörter wie „betrag",
  „beleg" oder „gutschrift" stehen, landete praktisch jedes Geschäftsdokument dort: ein
  Kontoauszug wegen „Gutschriften", eine Reisekostenabrechnung wegen „laut Beleg". Jetzt
  wird bewertet — längere (spezifischere) Begriffe wiegen mehr, der Kategoriename im Text
  am schwersten.
- Neue Kategorien **`kontoauszuege`**, **`steuer`** und **`spesen`**; `finanzen` behält die
  Begriffe bewusst mit, damit ein Projekt mit nur einer „Finanzen"-Wabe weiterhin alles
  dorthin einsortiert bekommt.

### Hinzugefügt — Testprojekte und automatische Prüfung
- **`tools/testprojekte.py`** erzeugt vier reproduzierbare Szenarien (70 Dokumente, ohne
  verräterische Dateinamen — die Zuordnung muss allein über den Inhalt gelingen).
- **`tools/taxonomie_check.py`** prüft sie gegen hinterlegte Erwartungen und misst beide
  Richtungen: keine Doppelordner, aber echte Gruppen bleiben getrennt.
  Offline **von 2/4 auf 4/4**.

### Hinzugefügt — Der wachsende Bienenstock (Gamification)
- **`spiel.py`**: Stufen, acht Abzeichen, Tagesserie und ein Fortschrittsbalken; neuer
  Befehl **`fortschritt`** (`progress`, `level`).
- Bewusst **ohne dunkle Muster**: keine Punkte fürs Starten des Programms, keine täglichen
  Anmelde-Belohnungen, keine Erinnerungen mit schlechtem Gewissen. Jeder Punkt steht für
  ein Dokument, das wirklich einsortiert wurde. Eine Vorschau zählt nicht mit.

### Behoben — Lokale KI war 4× langsamer als nötig
- `qwen3.5:9b` ist ein Reasoning-Modell und grübelt vor jeder Antwort mehrere tausend
  Zeichen — für ein kurzes Klassifikations-JSON reine Wartezeit. Der native CPU-Fallback
  schaltete das schon ab (`think: False`), der normale `/v1`-Pfad aber nicht; dort wird
  `think` ignoriert und nur `reasoning_effort` wirkt.
- Gemessen mit warmem Modell, vier Dokumente je Variante: **12,2 s je Dokument mit Denken,
  2,8 s ohne — bei identischen Antworten.**

### Hinzugefügt — Installer, die den PATH wirklich setzen
- **`install.ps1`** (neu, Windows/PowerShell): trägt den Programm-Ordner dauerhaft in den
  **Benutzer-PATH** ein — nie systemweit, keine Administratorrechte nötig. Idempotent: ein
  zweiter Lauf legt keinen Doppeleintrag an. `install.bat` ist jetzt ein dünner Starter dafür
  (Doppelklick funktioniert weiter), weil sich der PATH nur in PowerShell sauber setzen lässt.
- **`install.sh`** (überarbeitet, Linux/macOS/Git-Bash): schreibt den PATH-Eintrag in die
  Startdatei, die die Shell des Nutzers **tatsächlich liest** — `~/.zshrc`, `~/.bashrc`, unter
  macOS `~/.bash_profile`, für fish `~/.config/fish/config.fish` (mit fish-eigener Syntax).
  Der Block ist markiert, ein zweiter Lauf ergänzt nichts doppelt. Vorher meldete das Skript
  nur, dass der PATH fehlt, und überließ es dem Nutzer.
- Beide kennen **`--dry-run`** (zeigt nur, was passieren würde) und **`--no-path`**.
- **Robuste Python-Erkennung:** Unter Windows sind `python3`/`python` oft nur
  Microsoft-Store-Platzhalter, die beim Aufruf lediglich eine Werbemeldung ausgeben. Die
  Installer erkennen das und nehmen den nächsten Kandidaten, statt daran zu scheitern.

### Geändert — Paket-Rebranding auf `pollysort`
- **Paket `bumble` → `pollysort`.** Der Produktname und der Code-Name sind endlich dieselben.
  Bewusst **jetzt**, vor dem ersten PyPI-Release: danach wäre der Wechsel ein Bruch für jede
  bestehende Installation.
- **Befehle:** `bumble` → **`pollysort`**, `bumble-cli` → **`pollysort-cli`**.
- **Repo-Starter:** `Beehive.py` → **`polly.py`** (nicht `pollysort.py` — eine gleichnamige
  Datei neben dem Paket würde beim Start aus dem Repo den Import überschatten).
- **Globale Ablage:** `~/.beehive` → **`~/.pollysort`**. Eine vorhandene alte Ablage wird beim
  ersten Start **einmalig übernommen** — sie wird **kopiert, nie verschoben und nie gelöscht**;
  eine Notiz `UEBERNOMMEN.txt` erklärt, was passiert ist. Neue Env-Variable `POLLYSORT_HOME`;
  der Altname `BEEHIVE_HOME` wird weiterhin akzeptiert, damit bestehende Skripte nicht brechen.
- **Der versteckte Projektordner `.honig/` bleibt unverändert** — er liegt in den Ordnern der
  Nutzer, und ein Rename dort hieße, in fremden Daten aufzuräumen.
- Alle verbliebenen „Bumble Beebliothek"-Strings gezogen: ICS-`PRODID` und Kalendername,
  OpenRouter-`X-Title` und `HTTP-Referer`, Charter-, Export- und Config-Header, Docstrings.

### Geändert — Open Core (Apache-2.0)
- **Lizenz von Fair-Code auf [Apache-2.0](LICENSE) umgestellt.** PollySort ist damit echtes,
  OSI-anerkanntes Open Source. Grund: Der Wert des Projekts für Akinara liegt in Sichtbarkeit
  und Vertrauen, nicht in Lizenzumsatz — den trägt später das kommerzielle Web-Cockpit.
- **Lizenz-Gate vollständig aus dem Kern entfernt** (`licensing.py`, `lizenz`,
  `pollysort-cli activate`, Doctor-Lizenzzeile, Projektzähler). Es gibt keine Freigrenze mehr.
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
- **201 Tests grün** (vorher 124), `ruff` clean. Neu: `test_vorwaermen.py` (18), `test_taxonomie.py` (15),
  `test_spiel.py` (15), `test_firstrun.py` (20),
  `test_doctor.py` (5, inkl. Wächter gegen ein zurückkehrendes Lizenz-Gate) und
  `test_rename_migration.py` (9 — vor allem: die alte Ablage wird kopiert, nicht verschoben).
- i18n-Wächter: jeder Katalog-Eintrag muss DE **und** EN haben, mit identischen Platzhaltern.
- **Wheel-Build erstmals real verifiziert** (`uv build` → Installation in frischem venv →
  `pollysort` und `pollysort-cli doctor` laufen). Damit ist der letzte offene Beta-SOLL-Punkt erledigt.

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
- **Installationsanleitung** in der README (clone → `pipx install ".[extract]"` → `pollysort`).

### Geändert
- **Rebranding** des sichtbaren Namens: *PollySort* → *BumbleNara* → **PollySort**
  (neues ASCII-Banner, „Developed by Akinara", alle sichtbaren Titel, README). Paketname `pollysort`,
  Befehle (`pollysort`/`pollysort-cli`), `~/.beehive` und `.honig` bleiben bewusst unverändert.
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
- Paketierung für `pipx` / `uv tool install` (Entry-Points `pollysort`, `pollysort-cli`).
- Kern-Dependencies entschlackt (Extraktion via Extra `[extract]`).
- Lokale KI über Ollama (`/v1`-API). QA-Runden 1+2: BUG-1…4 + OPT-1…6 behoben.

### [0.1.0] — Kern
- Interaktive REPL, Mehrprojekt-Verwaltung, Einrichtungs-Assistent.
- `sortiere`/`vorschau`/`importiere`, SHA-256-Dedupe, **nie löschen/überschreiben** (Kollisions-Suffixe).
- SQL-Index + Markdown/JSON-Einträge (PKM-ready), Hive-Mind-Vektorgedächtnis mit Confidence-Logik.
- Rückfragen, Zuordnen, Gedächtnis, Empfehlungen, Überwachung (`wache`), Quarantäne (`papierkorb`),
  Undo (`rueckflug`).

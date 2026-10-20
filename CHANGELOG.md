# Changelog

Alle nennenswerten Änderungen an **PollySort** (Developed by Akinara).
Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

Interne Metaphern (Bienen/Waben/Honig) und der Paketname `pollysort` bleiben bewusst bestehen —
sichtbar ist der Produktname PollySort.

## [Unveröffentlicht]

### Gedächtnis-Modell per Knopfdruck (Ollama)
- **Werkstatt → Gedächtnis-Modell (Ollama) → Herunterladen.** Im Modus Lokal braucht das
  Gedächtnis das Embedding-Modell `nomic-embed-text-v2-moe`. Fehlte es, sortierte PollySort zwar,
  lernte aber still nichts dazu; der Rat war `ollama pull …` im Terminal. Jetzt holt PollySort
  das Modell selbst über Ollama, mit demselben Ablauf wie der BeeNara-Download: Fortschritt in
  MB, Meldungen im Protokoll, Fehler werden gemeldet statt geworfen. Die Karte zeigt, ob Ollama
  läuft und das Modell schon hat; den Stand lädt die Seite nach, damit die Werkstatt ohne
  laufendes Ollama nicht hängt.
- **Konsole:** `ollama` zeigt den Stand, `ollama laden` (`ollama pull`) lädt das Modell. Mit
  Modellnamen lädt es ein anderes, z. B. `ollama pull qwen3.5:9b` — so klappt der Rat von
  `doctor` auch direkt in der PollySort-Konsole. Skript-CLI: `pollysort-cli ollama [status|pull]`
  (Exit 0 = Modell da).
- `doctor` nennt beim fehlenden Embedding-Modell zusätzlich die Werkstatt.

### Gedächtnis — Herkunft je Eintrag
- **Zwei Vermutungen sortieren kein drittes Dokument mehr ein.** Das Gedächtnis merkt sich jedes
  analysierte Dokument mit Label, auch Rückfragen und jeden Vorschlag von BeeNara Big. Bisher
  zählten diese Einträge wie bestätigte: Bekamen zwei ähnliche Dokumente denselben falschen,
  unsicheren Vorschlag, sortierte das Gedächtnis ein drittes ohne Rückfrage ein (Test:
  `tests/test_gedaechtnis_herkunft.py`). Im vollen Analyse-Weg reichte schon eine Rückfrage, um
  die Konfidenz des nächsten Dokuments über die Schwelle zu heben.
- Jeder Eintrag trägt jetzt seine **Herkunft**: `bestaetigt` (Rückfrage beantwortet,
  `zuordnen`, Umsortieren nach `analysiere`, Saat aus dem Vorwärmen), `sicher` (automatisch über
  der Schwelle) oder `unsicher` (Rückfrage). Selbst entscheiden (Stufe A), als Beispiel für die
  Mindestzahl zählen und im Assigner die Konfidenz heben oder ein fehlendes Label ersetzen dürfen
  nur bestätigte und sichere Einträge. Unsichere wirken weiter als **Gegenstimme**: Liegt ein
  unsicherer Eintrag einer anderen Kategorie näher, fragt PollySort nach wie bisher.
- Wird ein unsicherer Eintrag später bestätigt oder automatisch sicher einsortiert, steigt seine
  Herkunft; herabgestuft wird sie nie, solange die Kategorie bleibt. `gedaechtnis neu` behält sie.
- **Bestehende Gedächtnisse** werden beim ersten Start einmal eingestuft, aus Katalog und
  Korrekturen: einsortiert → sicher, Rückfrage → unsicher, korrigiert → bestätigt, im Index-Modus
  nach Konfidenz und Schwelle. Nennt der Katalog inzwischen eine andere Kategorie (von Hand
  verschoben), gilt das alte Label als unsicher; Saat ohne Katalog-Eintrag als bestätigt.

### Feldmessung — welche Stufe lag daneben?
- **Jede Korrektur hält fest, wer vorher entschieden hatte** und wie sicher: `quelle_vorher`
  (`gedaechtnis`, `beenara`, `beenara-big`, `nummer`, `label`, `zweitmeinung`, `keine`, oder eine
  frühere Korrektur), `konfidenz_vorher` und `status_vorher` in `korrekturen.jsonl`.
  `status_vorher: assigned` heißt: Die Datei war schon automatisch einsortiert, ein echter Fehler
  dieser Stufe. So zeigt die Beta, ob BeeNaras „höchstens 1 % falsch" auch draußen hält. Es wird
  nur gemessen; nichts regelt sich danach von selbst nach.
- Dafür steht im Katalog jetzt bei jeder Datei, wer ihre Kategorie gesetzt hat (Spalte `quelle`,
  wird beim ersten Start nachgerüstet; ältere Einträge bleiben ohne). In der Lauf-Zusammenfassung
  zählen BeeNara und BeeNara Big weiter gemeinsam als „BeeNara".
- Ältere Zeilen in `korrekturen.jsonl` bleiben gültig; Wachstafel und Few-Shots lesen sie wie
  bisher.

## [0.4.0b2] — 2026-10-18 — öffentlicher Start

### Dokumentation — README für den öffentlichen Start
- **Neue Kopfzeile:** Logo in der Pixel-Schrift des Flugbretts, Badges (CI, Lizenz, Python, Beta,
  BeeNara-Modelle). Feature- und Extras-Tabellen tragen jetzt die Pixel-Icons der App statt
  Emojis; Hinweise sind GitHub-Hinweisboxen.
- **BeeNara-Abschnitt neu:** v0.3 mit Risiko-Regel und den Zahlen aus der Modellkarte, dazu
  BeeNara Big (Vorschau), die Modellwahl und was Big braucht. Befehle, Extras, Fehlerhilfe, Ablage
  und FAQ ergänzt.
- **Bilder neu:** Screenshots mit Pixel-Icons und mit BeeNara Big in der Werkstatt;
  `tools/readme_bilder.py` bindet ein geladenes Big per Hardlink ein und fotografiert hohe Karten
  vollständig. Neu: `tools/readme_grafiken.py` zeichnet Logo und Icons aus `pixel.js` als SVG.
- **Finanzierung:** Die README beschreibt jetzt PollySort Server (Arbeitstitel, eigenes Repo,
  source-available, intern frei) statt des früheren Web-Cockpits.
- **Realistischere Demo-Dokumente** für die Screenshots: Rechnungen, Verträge, Policen, Bescheid,
  Gehaltsabrechnungen und Kontoauszüge mit Briefkopf, Positionen und Fußzeile wie im Alltag
  (alles erfunden). BeeNara v0.3 sortiert davon 9 von 14 richtig ein und fragt bei 5 nach, zwei
  davon passen bewusst in keinen Ordner.

### BeeNara v0.3
- **Neues Modell:** PollySort lädt jetzt BeeNara v0.3 (Hub-Commit `8597874`, Tag `v0.3`). Auf
  einem neuen Testsatz mit unbekannten Ordnerbäumen und Namen trifft es 84–85 % statt 69 %, auf
  dem alten v0.2-Benchmark 95,9 % statt 94,1 %. Wer v0.2 schon geladen hat, bekommt mit
  `beenara laden` nur die geänderten Dateien.
- **Selbst einsortiert wird nur noch über der Risiko-Schwelle:** höchstens 1 % der automatischen
  Entscheidungen falsch (Learn-then-Test, δ = 0,1, kalibriert für 3–9 Ordner). Im unabhängigen
  Test mit 70 Dokumenten: Fehlt der richtige Ordner, wurden 0 statt 4 Dokumente falsch
  einsortiert; dafür fragt PollySort 7–15 Punkte öfter nach.
- **Anfang und Ende des Dokuments:** BeeNara bekommt bei langen Dokumenten jetzt Anfang und
  Ende statt nur den Anfang, wie im Training von v0.3 (Summe, Unterschrift, Grußformel).
- **Zu alte Laufzeit wird erkannt:** `beenara laden` prüft jetzt auch die Versionen, nicht nur ob
  die Pakete da sind. Unter Windows zog `markitdown` magika 0.6.3 und hielt damit onnxruntime auf
  1.20.1; BeeNara v0.3 ließ sich so nicht öffnen und galt trotzdem als bereit. Das Extra `extract`
  begrenzt magika unter Windows deshalb auf < 0.6.3.
- **BeeNara Big (Vorschau):** das große Modell für ganze Ordnerbäume (3 bis etwa 300 Ordner,
  [Kwokou/BeeNara-Big](https://huggingface.co/Kwokou/BeeNara-Big)). `beenara big laden` bzw. der
  Knopf in der Werkstatt prüft zuerst die Grafikkarte (NVIDIA ab 8 GB; `POLLYSORT_BEENARA_BIG_CPU=1`
  erzwingt die CPU), lädt dann LoRA und Kopf (~164 MB) und das Basismodell Qwen3.5-2B-Base
  (~4,6 GB), je aus einem festen Commit mit Prüfsumme, und installiert torch passend zum
  Grafiktreiber — eine schon installierte CPU-Fassung von torch wird dabei gegen die CUDA-Fassung
  getauscht. Big macht in v0.3 nur Vorschläge: Sein Favorit wird immer eine Rückfrage.
- **Modellwahl, wenn beide da sind** (`beenara modell auto|klein|big`, Schalter in der Werkstatt):
  Automatisch nimmt BeeNara bei 3–9 Ordnern und Big bei mehr. Ohne Big ändert sich nichts.
  Der Schalter steht schon vor dem Download in der Werkstatt; Konsole und `pollysort-cli`
  zeigen, ob Big auf der Grafikkarte oder der CPU rechnet.

### Dokumentation — README für die Beta
- **Screenshots:** Vorschau als Titelbild, dazu Zuhause, Rückfragen, Waben und die BeeNara-Karte —
  jeweils hell und dunkel; GitHub zeigt das passende Bild zum eigenen Thema (`docs/bilder/`).
- **`tools/readme_bilder.py`** erzeugt sie neu: Demo-Projekt mit erfundenen englischen Dokumenten
  in einem temporären `POLLYSORT_HOME`, Aufnahme mit Edge/Chrome über Playwright. Echte Pfade
  werden vor jedem Bild durch Demo-Pfade ersetzt; steht der eigene Benutzername noch auf der
  Seite, bricht das Skript ab, statt ein Bild zu speichern.
- **Installationsanleitung neu:** Schnellstart in vier Schritten (Python → ZIP oder `git clone` →
  Installer → Desktop-Symbol), Python je Betriebssystem, was der Installer genau tut, welche
  Befehle es danach gibt, optionale Zusätze (BeeNara, Ollama, OpenRouter), Aktualisieren,
  Extras-Tabelle, Fehlerbehebung (Befehl nicht gefunden, Store-Platzhalter, Ausführungsrichtlinie,
  gesperrte ZIP-Dateien, App im Browser-Tab, abgebrochener Download).
- Richtiggestellt: Verweise auf `TODO.md` und den Projektbrief entfernt (beide liegen nicht im
  Repository); der Sprachhinweis nennt jetzt genau, was noch deutsch ist (Installer,
  Teile von `pollysort-cli`); die Roadmap führt das inzwischen veröffentlichte BeeNara nicht
  mehr als Forschungsvorhaben. BeeNara-Abschnitt: Tempo und der Hinweis, dass Sammelordner wie
  „Letters" oder „Correspondence" nicht erkannt werden (gemessen: „keiner passt" bei beiden
  Briefen der Demo, mit 0,97–0,98).

### Schneller — Sortieren mit BeeNara etwa doppelt so schnell
- Gemessen über den Dienst des Flugbretts, 70 Testdokumente, Laptop auf Akku, abwechselnd in
  vier Runden: **vorher 734–860 ms je Datei (Median 752), jetzt 350–476 ms (Median 353)**.
  Die Entscheidungen bleiben gleich: Stufe-0 mit 6 Threads 420/420 wie die PyTorch-Referenz.
- **BeeNara rechnet mit 6 statt 4 Threads** (Core Ultra 7 255H: 4 → 481 ms, 6 → 368 ms,
  8 → 380 ms mit mehr Streuung, 16 → 861 ms). Höchstens 6, nie mehr als Kerne da sind;
  `POLLYSORT_BEENARA_THREADS` überschreibt.
- **Das Gedächtnis wird einmal je Lauf geladen** statt für jede Datei aus SQLite und JSON; was
  der Lauf lernt, wird nachgetragen. Jede andere Änderung (Korrektur, Papierkorb, Umbenennen,
  Neuaufbau) erhöht `HiveMind.version` und lädt neu. Mit numpy rechnet der Vergleich als
  Matrix-Produkt. Das hilft auch dem Modus Lokal.
- **Jede Datei wird je Analyse nur einmal gelesen** (`extractor.einmal_lesen`) — vorher lasen
  Heuristik und BeeNara sie im Sparmodus nacheinander.
- Flugbrett: Während einer langen Aktion sind die Knöpfe ihrer Karte gesperrt — „Herunterladen"
  lässt sich während des Downloads nicht noch einmal anklicken.

### Hinzugefügt — BeeNara im Flugbrett
- **Werkstatt:** BeeNara-Karte mit demselben Stand wie `beenara` in der Konsole; herunterladen
  (mit Fortschritt in MB, Laufzeit wird mitinstalliert), an/aus, entfernen mit Bestätigung.
- **Assistent:** Im Schritt „Modus" ein Haken „BeeNara mit herunterladen" (Vorauswahl: aus).
  Bisher sah, wer über die App einstieg, die BeeNara-Frage nie.
- **Flugloch:** „Entschieden: 5 von BeeNara" statt „{teile}"; im Plan steht je Datei, wer
  entschieden hat. Die Modus-Auswahl sagt „mit BeeNara", wenn es mitsortiert.
- Kern: `beenara.bericht()` und `pipeline.quellen_text()` — je eine Quelle für Konsole, CLI und
  Flugbrett. `WebKonsole.progress(transfer=True)`, gedrosselt auf ein Ereignis je Prozent.
  Beim ersten Lauf meldet PollySort „BeeNara wird geladen …".
- Wächter-Tests: Jeder Aufruf der Seite hat einen Endpunkt (und umgekehrt), jeder Text bekommt
  alle seine Platzhalter.

### Hinzugefügt — das Flugbrett: PollySort im Browser
- **`pollysort-web`** (oder `oberflaeche` / `web` in der Konsole) startet eine lokale
  Browser-Oberfläche auf demselben Kern: Zuhause, Flugloch (Vorschau → Anwenden mit Live-
  Fortschritt), Rückfragen (Tasten 1–9 · ⏎ · s · v wie in der Konsole), Waben (Umsortieren per
  Auswahl oder Ziehen), Schwarm & Kalender, Wachstafel & Gedächtnis, Quarantäne, Werkstatt und
  ein Einrichtungs-Assistent, der auch den Erststart übernimmt.
- **Retro-Pixel, aber ruhig:** eigene 5×7-Pixel-Schrift und Pixel-Sprites (selbst gezeichnet,
  ohne Fremd-Schrift oder Downloads), Farb-Semantik aus der Konsole, Kontraste nach WCAG AA,
  Hell/Dunkel/Automatik. Stil-Tafel unter `/musterbuch.html`.
- **Gamification in Maßen:** Stufen und Abzeichen ausschließlich aus `spiel.py`; Animationen
  nur dort, wo auch die Konsole reagiert, und abschaltbar (Voll · Dezent · Aus). Der
  **Arbeitsmodus** stellt mit einem Klick auf dezent, blendet Fortschritt aus und setzt den
  Klartext vor die Bienen-Begriffe.
- **Keine neue Abhängigkeit:** Server aus der Standardbibliothek, nur `127.0.0.1`, Sitzungs-
  Token, Host- und Origin-Prüfung, strenge Content-Security-Policy. Schlüssel und Flugrouten
  zeigt der Browser nur maskiert — eingetragen werden sie weiter in der Konsole.
- Dokumentation für das Team: `docs/flugbrett.md` (Begriffe, Gestaltung, Technik, Testplan).

### Hinzugefügt — PollySort als eigene Anwendung
- **`pollysort-app`** (oder `anwendung` / `app` in der Konsole): das Flugbrett im eigenen
  Programmfenster statt im Browser-Tab. Natives Fenster über das optionale Extra **`[app]`**
  (pywebview), sonst ein randloses Edge-/Chrome-App-Fenster, notfalls der Browser.
  **Fenster zu = PollySort beendet** (Server und Wache fahren herunter).
- Unter Windows ein **GUI-Programm ohne Konsolenfenster** mit eigenem Symbol und eigener
  App-Kennung in der Taskleiste; Diagnose in `~/.pollysort/app.log`, Startfehler als
  Meldungsfenster.
- **Installer legen Starter an:** Startmenü + Desktop (Windows, auch aus Git-Bash), Eintrag im
  Anwendungsmenü (Linux), `~/Applications/PollySort.app` (macOS) — abschaltbar mit
  `--no-shortcut` / `-NoShortcut`. Die Deinstaller entfernen nur, was erkennbar von PollySort
  stammt (Verknüpfung, Symbol, Fensterprofil).
- **App-Symbol** aus der Pixel-Biene (`.ico`, `.png`, `.icns`), reproduzierbar mit
  `python tools/app_icon.py`.
- Der Ereignisstrom bemerkt geschlossene Fenster jetzt binnen Sekunden statt erst beim nächsten
  Lebenszeichen.

### Geändert
- `CycleSummary.plan` hält je Datei fest, was ein Lauf getan hat bzw. tun würde (nur
  Metadaten) — Grundlage der Liste „Datei → Wabe" im Browser.
- Fortschritt buchen ist jetzt eine gemeinsame Funktion (`spiel.buchen`) für Konsole und Browser.
- Beantwortete **Rückfragen zählen als beigebrachte Korrektur** (Abzeichen „Lehrmeister"),
  genau wie `zuordnen` — jede Antwort trainiert das Gedächtnis.

### Behoben
- **„Weise Königin" war unerreichbar:** Die Konsole fragte `Wachstafel.rules()` ab, die
  Methode heißt `regeln()`; der Fehler wurde still geschluckt und die Zahl der gelernten Regeln
  kam nie im Fortschritt an.
### Neu — BeeNara von Hugging Face laden
- **`beenara laden` / `beenara pull`** holt das lokale Entscheider-Modell
  [Kwokou/BeeNara](https://huggingface.co/Kwokou/BeeNara) (ONNX + Tokenizer, ca. 370 MB) nach
  `~/.pollysort/modelle/BeeNara/`. Alle Dateien stammen aus einem Commit; jede wird gegen die
  Prüfsumme des Hubs geprüft, bevor sie ihren Namen bekommt. Ein abgebrochener Download setzt
  an derselben Stelle fort, ein Update lädt nur geänderte Dateien. `beenara.py` aus dem Repo
  wird bewusst nicht geladen. Ohne neue Abhängigkeit (httpx statt `huggingface_hub`).
- **Erststart fragt nach** (neuer Schritt 4/5). Enter heißt „später" — 370 MB laufen nie
  durch bloßes Durchklicken.
- `beenara` zeigt den Stand, `beenara entfernen` löscht das Modell nach Rückfrage;
  `pollysort-cli beenara [status|pull]` für Skripte; `doctor` meldet Version und Größe.

### Neu — BeeNara entscheidet beim Sortieren mit
- **Sparmodus:** BeeNara wählt den Ordner statt der Heuristik (Titel und Zusammenfassung
  bleiben heuristisch). **Lokal:** nach dem Gedächtnis, statt des KI-Kurzentscheids — das 9B
  wird für die Wahl nicht mehr gebraucht. **Cloud:** unverändert.
- Sortiert wird nur, wenn BeeNaras konforme Vorhersagemenge genau einen Ordner enthält
  (kalibriert ≥ 0,97). „Keiner passt" und Unsicherheit werden Rückfragen, mit BeeNaras
  Favorit als Vorschlag; kein zweites Modell rät nach. Eine gelernte Wachstafel-Regel und ein
  widersprechendes Gedächtnis haben Vorrang. Gilt bei 3–9 Ordnern (so trainiert und
  kalibriert), sonst der bisherige Weg.
- Gemessen auf den 70 Testdokumenten (57 verschiedene): Sparmodus 57 von 57 richtig statt 55;
  fehlen die Ordner Versicherung und Steuer, sortiert BeeNara 4 Dokumente falsch statt 8 und
  fragt bei den Steuerbescheiden nach. Die 4 sind Versicherungspolicen unter „Verträge" — die
  bekannte Schwäche bei Ordnern ohne Beschreibung.
- **Laufzeit:** neues Extra `[beenara]` (`onnxruntime`, `tokenizers`, `numpy`); `beenara laden`
  installiert es in die Umgebung, in der PollySort läuft (pip, sonst `uv pip`). Die
  Laufzeit liegt als Kopie im Paket (`beenara_laufzeit.py`), Code vom Hub wird nie geladen.
- **Fester Modell-Commit** (`beenara.REVISION`, v0.2): Ein neues BeeNara kommt mit einem
  PollySort-Update, nie still über `main`. Liegt eine andere Version da, sortiert BeeNara
  nicht mit, bis `beenara laden` die passende geholt hat.
- `beenara an` / `beenara aus` schaltet es ab, ohne es zu löschen. `beenara` sagt, ob es
  mitsortiert und warum nicht (aus, nicht geladen, Version, Laufzeit, Cloud, Ordnerzahl).
- Ein Ausfall beim Rechnen wird einmal gemeldet; der Rest des Laufs entscheidet ohne BeeNara.
- Lauf-Zusammenfassung nennt nur die Quellen, die vorkamen („2 aus dem Gedächtnis · 5 von
  BeeNara"), im Sparmodus „per Heuristik" statt „per Vollanalyse".
- Tests: Kein Test sieht mehr ein echtes BeeNara auf dem Rechner (eigene `POLLYSORT_HOME` je
  Test). Live-Test mit dem echten Modell über `BEENARA_MODELL=<ordner>`.

### Geändert — alle offenen Punkte aus TEIL 3 der TODO
- **Vollständig zweisprachig:** alle 155 Befehlsmeldungen der Konsole und die Ausgaben von
  Rückfragen, Daemon, Wächter-/Baubienen, Scan und Empfehlungen laufen über `i18n.t()`. Ein
  Test verhindert, dass neue feste Texte dazukommen. Offen bleiben nur die Hilfetexte der
  Skript-CLI.
- **Unterordner nach dem echten Dokumentdatum:** beschriftetes Datum („Rechnungsdatum:",
  „Kontoauszug vom 3. März 2026") schlägt Dateiname und erstes Datum; Fristen und Zeiträume
  („zahlbar bis", „Leistungszeitraum") zählen nicht mehr. Vorher landete eine Rechnung im Monat
  ihrer Zahlungsfrist.
- **`doctor` meldet die GPU-Belegung** (warnt, wenn das Modell teilweise auf der CPU läuft) und
  die Ollama-Version.
- **Neu: `analysiere <id>` / `reanalyze <id>`** — einen Altfall neu analysieren; fragt, bevor
  umsortiert wird, und lernt dann daraus.
- **`kalender` schreibt die abonnierbare `.ics` jedes Mal neu** — auch wenn alles erledigt ist.

### Behoben
- **Konsolidierung wählte den engeren Namen:** 4× „arbeitsvertraege" + 3× „vertraege" wurden
  ein Ordner „Arbeitsvertraege" — samt Mietverträgen. Jetzt gewinnt der Name, der alle deckt.
- Wächterbienen: „ist 3 Tag(e) überfällig fällig" → zwei saubere Sätze.
- Empfehlungen verwiesen auf nicht existierende Befehle und trugen noch „Beebliothek".
- Der Sweep-Bericht nannte „LLM-Calls · ~0,0000 €" auch im Sparmodus.

### Geändert — die Modi heißen jetzt Sparmodus · Lokal · Cloud
- **Sparmodus** (bisher „offline"): reine Heuristik — sofort, kostenlos, läuft auf jedem
  Rechner. **Lokal** (bisher „ollama"): KI auf dem eigenen Rechner. **Cloud** (bisher
  „online"/„openrouter"): KI über eine API. Der alte Name „offline" war irreführend — ein
  lokales Sprachmodell arbeitet genauso offline.
- Nur die sichtbaren Namen ändern sich: In `hive.toml` und der Config stehen weiter
  `offline`/`ollama`/`openrouter`, bestehende Projekte laufen ohne Umbau. `modus`/`mode`
  versteht die neuen Wörter (`spar`, `lokal`, `cloud`, auch `low`, `local`, `api`) **und** die
  alten; die CLI kennt `--spar` neben `--offline`.
- Angepasst: Erststart, Projekt-Einrichtung, `modus`, Kopfzeile, `home`/`status`, `doctor`,
  Sortierlauf-Meldungen, README. Die Meldungen des `modus`-Befehls sind jetzt zweisprachig.
- README bereinigt: eine sinnlose FAQ aus der automatischen Umbenennung („Why is the command
  `pollysort` and not `pollysort`?") und zwei überholte Roadmap-Punkte (Lizenz-Aktivierung —
  widerspricht Open Core; Release-Workflow — erledigt) entfernt.

### Geändert — der Ollama-Modus entscheidet dreistufig (Plan §8.3, gemessen §8.13)
- **Gedächtnis → Nummer → Rückfrage** (`entscheidung.py`). Das Gedächtnis entscheidet allein,
  wenn das ähnlichste bekannte Dokument ≥ 0,75 ähnlich ist, 0,05 vor der nächsten Kategorie
  liegt und die Kategorie schon zwei Beispiele hat — die Schwellen sind gemessen: Fehlte eine
  Kategorie ganz, kam kein fremdes Dokument über 0,67. Sonst wählt das Modell die Kategorie
  mit **einem** Token; die Konfidenz kommt aus den Logprobs (nicht aus dem gezogenen Token —
  `presence_penalty` bestraft Ziffern, die im Prompt stehen).
- **Gemessen, echter Sortierlauf, 70 Testdokumente, `qwen3.5:9b`:** GPU 0,21 s statt 22,2 s
  je Dokument, **nur CPU 4,0 s statt 48,7 s**; 56 von 57 eindeutigen Dokumenten richtig, keine
  Rückfrage. 30 davon entschied das Gedächtnis ohne KI-Aufruf.
- **Nacherfassung** (`nacherfassung.py`, Befehl `nacherfassen [an|aus|jetzt]` / `enrich`):
  Titel und Zusammenfassung entstehen erst heuristisch und werden nach dem Sortieren von der
  KI verfeinert — die Kategorie bleibt dabei unangetastet. Strg-C überspringt, der nächste Lauf
  macht weiter. Beim automatischen Sortieren (Projekt öffnen, `wache`) läuft sie nicht.
- **Das Gedächtnis bettet im Ollama-Modus den Dokument-Anfang ein** statt der
  KI-Zusammenfassung — nur so kann es vor der KI entscheiden. Saat, Einträge, Korrekturen und
  `gedaechtnis neu` nutzen dieselbe Textbasis (`extractor.gedaechtnis_text`). Bestehende
  Gedächtnisse werden erkannt und bleiben aus den Entscheidungen heraus, bis `gedaechtnis neu`
  sie einmal umbaut (lokal, kostenlos).
- Geprüft und **verworfen**: ein Hinweis „nach Dokumenttyp, nicht Absender" im Prompt. Er
  behob einen Fehlgriff, senkte aber die Erkennung von „passt nichts" beim 9B von 44 auf 26 %.

### Behoben — der lokale Modus war unnötig langsam
- **Jede Anfrage an Ollama kostete unter Windows ~2,4 s Verbindungsaufbau:** `localhost` löst
  zuerst auf `::1` auf, Ollama lauscht nur auf IPv4, und für jede Anfrage wurde eine neue
  Verbindung geöffnet. Jetzt hält jeder Client **eine** Verbindung, Standard-Endpunkt ist
  `127.0.0.1`.
- **Ollama 0.34 lädt Modelle mit 65 536 Tokens Kontext** — das 9B passte nicht mehr in 8 GB
  VRAM und lief zu 42 % auf der CPU (22 s statt 12–16 s je Dokument). Der Ollama-Client nutzt
  jetzt die native API mit `num_ctx 4096` (100 % GPU, 6,0 s je voller Analyse) und
  `temperature 0`; der Dokumenttext wird passend gekappt, damit Ollama nicht die Anweisungen
  am Prompt-Anfang abschneidet.
- **Das Gedächtnis führt das Modell je Vektor.** Vorher gab es nur einen Wert für alle — der
  erste neue Vektor überschrieb ihn, und ab da galt ein Altbestand aus einem anderen Modell
  als passend. Alte Datenbanken werden beim Öffnen nachgerüstet.
- **Kein Test geht mehr ins Netz** (`tests/conftest.py`). Beim Umstellen auf die gehaltene
  Verbindung zeigte sich, dass drei Tests noch `httpx.post` patchten und ihre
  Platzhalter-Schlüssel tatsächlich an OpenRouter schickten.

### Hinzugefügt — Zweitmeinung, Modell-Prüfung, Tippfehler-Vorschläge (2026-09-10)
- **Zweitmeinung der Heuristik** (`assigner.py`): Rastet das Modell-Label auf keine
  Projekt-Kategorie ein (das Modell antwortet etwa „gehaltsabrechnung" für eine
  Reisekostenabrechnung), schaut die Offline-Heuristik auf die Zusammenfassung, die das
  Modell selbst geschrieben hat. Steht dort ein spezifischer Fachbegriff, wird einsortiert
  statt nachgefragt. Greift **nur** bei einem unbrauchbaren Label, nie gegen eine
  Entscheidung des Modells — und wird in Konsole und Journal als Quelle ausgewiesen.
- **`doctor` prüft im Ollama-Modus, ob Analyse- und Embedding-Modell gezogen sind.** Fehlt
  das Embedding-Modell, sortiert PollySort zwar, aber das Gedächtnis lernt still nichts
  dazu — jeder Lauf bleibt ein Kaltstart. Jetzt steht der passende `ollama pull`-Befehl
  in der Ausgabe; fehlt das Analyse-Modell, ist es ein `fail`.
- **Tippfehler-Vorschläge:** „sortire" → „Meintest du 'sortiere' / 'sort'?" — deutsche wie
  englische Namen zählen.
- Aliase, die das README schon versprach, die es aber nicht gab: `swarm`, `charter` (für
  `wabenbau`), `find`, `calendar notify`.

### Geändert — der Alltagspfad spricht die gewählte Sprache
- `hilfe`/`help` ist datengetrieben und zeigt in Englisch die englischen Befehlsnamen
  (`sort  (s)` statt `sortiere  (s)`), inklusive `{year}/{month}`. Ein Test stellt sicher,
  dass jeder in der Hilfe genannte Name auch ein echter Befehl ist.
- Projekt öffnen, Kopfzeile/Prompt, `home`, `status`, `doctor` (REPL **und** CLI) sind
  zweisprachig.
- README: `~/.beehive/` → `~/.pollysort/`, `BEEHIVE_HOME` → `POLLYSORT_HOME` — der Text war
  seit dem Paket-Rename veraltet.

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

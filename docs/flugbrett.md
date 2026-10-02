# Das Flugbrett — PollySort im Browser

Das Flugbrett ist das Brett vor dem Flugloch, auf dem Bienen landen und starten. In PollySort
ist es die lokale Browser-Oberfläche: derselbe Kern wie die Konsole, nur mit Knöpfen statt
Befehlen. Dieses Dokument richtet sich an das Team. Es hält fest, **welche Begriffe** die
Oberfläche benutzt, **wie** sie gestaltet ist, **wie** sie technisch funktioniert und **wie**
sie mit echten Menschen getestet werden soll.

> Kurz: **PollySort** im Startmenü oder auf dem Desktop anklicken. Es öffnet sich ein eigenes
> Programmfenster; schließt man es, beendet sich PollySort. Wer lieber den Browser nimmt:
> `pollysort-web`.

---

## 1. Starten & bedienen

| Weg | Befehl |
|---|---|
| **Eigene Anwendung** | Verknüpfung „PollySort" (Startmenü/Desktop, Linux-Menü, `~/Applications`) · `pollysort-app` · `pollysort-app --fenster app` |
| Aus der Konsole | `anwendung` (Alias `app`) — die Konsole wartet, bis das Fenster zu ist |
| Im Browser | `pollysort-web` · `pollysort-web "C:\Pfad\zum\Ordner"` · `--port 9000` · `--kein-browser` |
| Browser aus der Konsole | `oberflaeche` (Alias `web`) — läuft im Vordergrund wie `wache`, `Strg-C` führt zurück |
| Aus dem Repo | `python -m pollysort.web.app` · `python -m pollysort.web.server` |

**Die eigene Anwendung (`pollysort-app`)** startet den Server im selben Prozess auf einem freien
Port und zeigt die Oberfläche in einem eigenen Fenster. Der erste Weg, der klappt, gewinnt:

1. **natives Fenster** über pywebview (Extra `[app]`), unter Windows mit Edge WebView2 und
   eigenem Symbol in Titel- und Taskleiste;
2. **randloses App-Fenster** von Edge, Chrome, Chromium oder Brave (`--app` mit eigenem Profil
   unter `~/.pollysort/fenster`, damit das Fenster ein eigener Prozess bleibt);
3. **Browser-Tab** als letzter Ausweg.

Schließt man das Fenster, fahren Server und Wache herunter. Ist das Fenster ein fremder
Browser-Prozess, merkt der Server das am Ereignisstrom (binnen Sekunden) und beendet sich nach
12 Sekunden Gnadenfrist — ein Neuladen der Seite fällt nicht darunter. Unter Windows ist
`pollysort-app` ein GUI-Programm ohne Konsolenfenster; Diagnose (Port, Fenster-Art — nie das
Token) steht in `~/.pollysort/app.log`, ein Startfehler erscheint als Meldungsfenster.

Die Installer legen die Starter an (`--no-shortcut` / `-NoShortcut` verhindert das), die
Deinstaller entfernen sie wieder — nur, was erkennbar von PollySort stammt. Das App-Symbol
(`static/pollysort.ico/.png/.icns`) erzeugt `python tools/app_icon.py` aus der Pixel-Biene.

Der Server hört nur auf `127.0.0.1` (Standard-Port 8737, sonst ein freier). Die geöffnete Adresse
enthält das Sitzungs-Token im Fragment (`#t=…`); die Seite merkt es sich für den Tab und entfernt
es aus der Adresszeile.

**Tastenkürzel** — dieselben wie in der Konsole, wo es sie dort gibt:

| Wo | Taste | Wirkung |
|---|---|---|
| überall | `h` · `f` · `r` · `w` | Zuhause · Flugloch · Rückfragen · Waben |
| Flugloch | `v` · `s` | Vorschau · Jetzt sortieren |
| Rückfragen | `1`–`9` · `⏎` · `s` / `→` · `v` | Wabe wählen · Vorschlag übernehmen · überspringen · Datei ansehen |
| Protokoll | `Esc` | schließen |

---

## 2. Die Begriffe

Die Bienen-Begriffe stammen ausnahmslos aus dem Code und den Texten der Konsole (`i18n.py`).
**Regel:** Der Bienen-Begriff steht groß, der Klartext klein darunter. Im **Arbeitsmodus**
(oder mit „Klartext zuerst") dreht sich das um. Niemand muss raten, und die Welt bleibt erhalten.

| Bienen-Begriff | Klartext | Bedeutung im Programm | Im Flugbrett |
|---|---|---|---|
| **Zuhause** | Übersicht | `home` — Projekt, Eingang, offene Fälle, Deadlines | Startseite |
| **Flugloch** | Eingang sortieren | lose Dateien im Projekt-Ordner; Flugloch-Wache, Flugloch-Validierung | Sortieren mit Vorschau |
| **Rückfragen** | Unsichere Fälle | Dateien unter der Schwelle (75 %), bleiben liegen | Karten-Stapel |
| **Waben** | Kategorien | Kategorie-Ordner, die lebende Taxonomie | Waben-Raster + Einträge |
| **Schwarm** | Überblick & Termine | Königin + Bienen-Rollen (`schwarm`) | Rollen, Kalender, Empfehlungen |
| **Wachstafel** | Gelernte Regeln | `.honig/wachstafel.md`, Regeln werden „geritzt" / „abgewischt" | Regeln + Gedächtnis |
| **Quarantäne** | Aussortiertes | `papierkorb/` — nichts ist gelöscht, bis man leert | Zurückholen, Dubletten, Leeren |
| **Werkstatt** *(neu)* | Einstellungen | Profi-Befehle (Modus, Thema, Sprache, `doctor` …) | Einstellungen |
| Königin | — | Orchestrierung, leitet Regeln aus Korrekturen ab | Rolle im Schwarm |
| Spähbienen („beschnuppern") | — | Struktur-Vorschlag beim Einrichten | Assistent, Schritt „Waben" |
| Spurbienen | — | der Sortierlauf | fliegende Bienen im Flugloch |
| Baubienen · Wabenbau · Bienenstock.md | Projekt-Steckbrief | Stufe 2: aus einer Wabe ein Projekt machen | Formular in der Wabe |
| Wächterbienen · Flugrouten · Testflug | Benachrichtigungen | Deadlines, Discord/E-Mail | Schwarm, Werkstatt (nur Status) |
| Sammelbienen | gelernte Ablageorte | dominanter Ordner je Kategorie | Rolle im Schwarm |
| Bienen-Kalender · Pollen-Uhr | Termine · `.ics` | Deadlines, abonnierbare Kalenderdatei | Schwarm |
| Gedächtnis („vorwärmen") | lernender Speicher | kNN-Vektoren je Wabe | Wachstafel-Seite |
| Rückflug | Rückgängig | letzte Verschiebung zurück | Knopf in der Kopfzeile |
| Nektar-Quelle · Nektar-Sorte | API-Schlüssel · KI-Modell | OpenRouter | Werkstatt |
| Ultra Swarm | Turbo | parallele KI-Analysen | Option im Flugloch |
| Sparmodus · Lokal · Cloud | KI-Modus | Heuristik · Ollama · OpenRouter | Kopfzeile, Werkstatt |
| BeeNara | lokales Entscheider-Modell | wählt im Sparmodus und im Modus Lokal den Ordner (`beenara`) | Werkstatt (laden · an/aus · entfernen), Assistent (Schritt „Modus") |
| Dein Bienenstock · Stufen · Abzeichen | Fortschritt | `spiel.py` | Zuhause (abschaltbar) |
| Flugbrett *(neu)* | Browser-Oberfläche | dieses Paket `pollysort.web` | Name im Code & in der Konsole |

*(neu)* = Begriff, den es vorher im Programm nicht gab. Beide sind bewusst Bienen-nah, aber
nicht erklärungsbedürftig.

---

## 3. Gestaltung

Die **Stil-Tafel** liegt als Seite im Flugbrett: `http://127.0.0.1:<port>/musterbuch.html`
(statisch, ohne Token). Dort sind alle Farben, die Schrift, alle Sprites, Bausteine und
Animationen zu sehen, umschaltbar zwischen Hell/Dunkel und Voll/Dezent/Aus.

### Leitsätze

1. **Klartext gewinnt.** Bienen-Begriffe geben Charakter, der Klartext steht immer dabei.
2. **Pixel nur zum Ansehen.** Pixel-Schrift für Logo, Überschriften, Zahlen und Abzeichen.
   Alles, was gelesen werden muss, steht in der Systemschrift (Segoe UI / system-ui),
   Dateinamen und Pfade in Festbreitenschrift.
3. **Farbe hat eine Bedeutung** — dieselbe wie in der Konsole (§12): Honiggelb = Erfolg,
   Blütenrosa = in Arbeit, Orange = Rückfrage, Rot = Fehler (dazu Grün = Wache/Lernen).
   Status nie nur über Farbe: immer mit Icon und Wort.
4. **Feiern nur echte Arbeit** (siehe 4.).
5. **Ernstes bleibt ernst.** Löschen, Fehler und Zugangsdaten bekommen keine Animation.
6. **Bewegung ist abschaltbar** — und „Bewegung reduzieren" des Systems gilt immer.

### Farben

Alle Textfarben erreichen auf Hintergrund und Flächen **mindestens 4,5 : 1 (WCAG AA)**, in
beiden Themen nachgerechnet. Honiggelb (`#FFD700` der Konsole) hat auf Weiß nur 1,4 : 1 und ist
deshalb **nur Fläche**. Als Text dient im hellen Thema ein dunkles Bernstein.

| Token | Hell („Tag im Stock") | Dunkel („Nacht im Stock") | Zweck |
|---|---|---|---|
| `--bg` | `#FBF4E2` Wachs-Creme | `#17110A` | Hintergrund (mit leisem Wabenmuster) |
| `--flaeche` | `#FFFDF6` | `#221A10` | Karten, Kopf, Fuß |
| `--text` | `#2B1D0E` | `#F7EBD0` | Fließtext, Pixel-Rahmen |
| `--honig` / `--honig-flaeche` | `#8A5A00` / `#FFC83D` | `#FFD24A` / `#FFC83D` | Erfolg · Hauptknopf |
| `--bluete` | `#B0306E` | `#FF85C2` | in Arbeit, Vorschau |
| `--frage` | `#A84B00` | `#FFA24D` | Rückfrage, Deadline bald |
| `--fehler` | `#B3261E` | `#FF7A6E` | Fehler, endgültig löschen |
| `--wache` | `#2F6B3A` | `#7FD08B` | Wache aktiv, Gedächtnis lernt |

„Automatik" folgt der Regel der Konsole: tagsüber (7–19 Uhr) dunkel, abends hell.

### Schrift & Sprites

- **Wabenschrift:** eigene 5×7-Pixel-Schrift (Großbuchstaben, Ziffern, Umlaute mit Punkten über
  der Versalhöhe, gängige Zeichen). Ein SVG je Wort, damit Überschriften umbrechen. Der echte
  Text steht unsichtbar daneben (Screenreader). Selbst gezeichnet, daher ohne Lizenzfragen und
  ohne Download.
- **Sprites:** Textraster in `static/pixel.js` (Farbbuchstaben → CSS-Variablen), gerendert als
  SVG mit `crispEdges`. Rollen-Icons passend zu den Emojis der Konsole: 👑 Königin, 🐝 Spurbiene,
  🛠️ Baubiene, 🔔 Wächterbiene, 🍯 Sammelbiene, dazu Haus, Flugloch (Bienenkorb), Rückfrage,
  Wabe, Wachstafel, Kiste (Quarantäne), Rückflug, Kalender, Auge, Blitz, Stift, Funkeln, Sonne,
  Blume.
- **Rahmen:** 2-px-Linien und harte Versatzschatten statt runder Ecken; Knöpfe „drücken sich"
  in zwei Schritten ein.

---

## 4. Gamification in Maßen

Die Haltung steht schon in `spiel.py` und gilt im Flugbrett unverändert:

> „Eine Fortschrittsanzeige, die lügt, ist schlimmer als gar keine."

- **Es gibt nur, was `spiel.py` kennt:** 6 Stufen (Junger Schwarm → Legendärer Stock),
  8 Abzeichen, die Tagesserie. Keine Punkte, keine Ranglisten, keine Belohnung fürs Öffnen.
- **Gezählt wird echte Arbeit:** einsortierte Dokumente, Korrekturen (Umsortieren *und*
  beantwortete Rückfragen), gelernte Regeln. Eine Vorschau zählt nie.
- **Gefeiert wird leise:** neue Abzeichen und Aufstiege erscheinen als kleiner Hinweis unten
  rechts, der von selbst verschwindet und nichts blockiert.
- **Arbeitsmodus** (Werkstatt oder erster Schritt des Assistenten): Animationen „Dezent",
  Stufen & Abzeichen ausgeblendet, Klartext vor den Bienen-Begriffen. Gezählt wird trotzdem,
  nur angezeigt wird es nicht. Wer den Arbeitsmodus wieder ausschaltet, findet den Stand
  unverändert vor.

## 5. Animationen

Animationen gibt es nur an den Stellen, an denen auch die Konsole reagiert. Kurze Rückmeldungen
dauern höchstens etwa 0,3 s, Feiern höchstens etwa 1 s, alles läuft in Pixel-Schritten
(`steps()`) und blockiert nie die Bedienung. Ton gibt es nicht.

| Moment | Animation | Dezent | Aus |
|---|---|---|---|
| Sortierlauf | Spurbienen fliegen vom Flugloch zu den Waben, Wabenbalken füllt sich | nur Balken | Balken ohne Bewegung |
| Vorschau | dieselben Bienen halbtransparent („noch passiert nichts") | nur Balken | — |
| Sauber sortiert | Honig-Funkeln am Ergebnis | — | — |
| Neues Abzeichen / Aufstieg | Hinweis gleitet ein | ohne Gleiten | ohne Gleiten |
| Einrichtung | Spähbienen „schnuppern" | still | still |
| Neue Regel | Regel wird in die Wachstafel geritzt | Einblenden | — |
| Fällige Deadline | Glocke wackelt einmal | — | — |
| Rückflug | Biene fliegt zurück | — | — |
| Eingang leer | schlafende Biene, „z" steigt auf | still | still |
| Wache aktiv | Biene schwebt im Wache-Chip | still | still |

**Bewusst ohne Animation:** Quarantäne leeren (Bestätigung durch Eintippen der Anzahl),
Fehlermeldungen, Zugangsdaten.

---

## 6. Technik

```
Browser (static/: index.html · app.css · pixel.js · app.js)
   │  fetch /api/<ansicht>   (GET, Token im Header)
   │  fetch /api/<aktion>    (POST, JSON)
   │  fetch /api/ereignisse  (Server-Sent Events, Token im Header)
   ▼
server.py  ── Flugbrett (ThreadingHTTPServer, nur 127.0.0.1)
   │   Token · Host · Origin · JSON · CSP · nur markierte Methoden
   ▼
dienst.py  ── Dienst: jede Konsolen-Aktion als Funktion mit JSON-Ergebnis
   │   eine Aktion nach der anderen (Beschaeftigt) + QueenLock (Gesperrt)
   ▼
Kern (pipeline, review, swarm, wachstafel, spiel …)  ──►  WebKonsole  ──►  Ereignisbus
```

- **`konsole.py` / `WebKonsole`:** Unterklasse von `BeeConsole`. Sie druckt nichts, sondern macht
  aus jeder Meldung ein Ereignis (`honey`, `bloom`, `ask`, `error`, `info`, `feier`,
  `fortschritt`). Dadurch brauchte der Kern **keine Sonderzeile** für den Browser.
- **`dienst.py` / `Dienst`:** ruft dieselben Kern-Funktionen in derselben Reihenfolge wie
  `repl.py` auf. Methoden mit `@ansicht` sind lesend (GET), Methoden mit `@auftrag` sind
  Aktionen (POST). Der Server erlaubt nur diese.
- **`Wache`:** die Flugloch-Wache als Hintergrund-Thread, solange das Flugbrett offen ist und
  `watch` in der Projekt-Config es vorsieht. Sie meldet neue Dateien oder sortiert sie sofort,
  schon vorhandene lose Dateien fasst sie nicht an.
- **Keine neue Pflicht-Abhängigkeit**, kein Build-Schritt, kein Fremd-Code im Browser. Nur das
  optionale Extra `[app]` (pywebview) bringt das native Fenster; ohne läuft alles weiter.
- **`app.py`:** die eigene Anwendung — Fenster-Wahl (nativ → App-Fenster → Browser), Warten bis
  das Fenster zu ist (`Ereignisbus.abonnenten()`), Aufräumen, Windows-App-Kennung für die
  Taskleiste.

**Sicherheit**

| Maßnahme | Wogegen |
|---|---|
| Bindung an `127.0.0.1` | Zugriff aus dem Netz |
| Sitzungs-Token im Header (`hmac.compare_digest`) | andere Programme/Seiten auf demselben Rechner |
| `Host`-Prüfung | DNS-Rebinding |
| `Origin`-Prüfung, nur `POST` + `application/json`, max. 1 MB | Cross-Site-Anfragen |
| CSP `default-src 'self'`, keine Inline-Skripte/-Styles, `frame-ancestors 'none'` | eingeschleuster Code, Clickjacking |
| `esc()` für alles aus Dateien/Dokumenten | XSS über Dateinamen oder Titel |
| Statische Dateien nur aus `static/`, nur bekannte Endungen | Pfad-Traversal |
| Schlüssel & Flugrouten nur maskiert, Eintragen nur in der Konsole | Geheimnisse im Browser, im Protokoll, in Screenshots |
| Kein Zugriffsprotokoll auf der Konsole | Token oder Pfade im Terminal-Verlauf |

**Kleine Änderungen im Kern** (alle getestet):

- `CycleSummary.plan` — je Datei: Name, Wabe, Konfidenz, Status, Ziel (nur Metadaten).
- `spiel.buchen()` — gemeinsames Fortschritt-Buchen. Behebt nebenbei `Wachstafel.rules()` →
  `regeln()`; dadurch war „Weise Königin" vorher unerreichbar.
- Rückfragen zählen als Korrektur, in Konsole und Browser gleich.
- `AppConfig`: `web_animationen`, `web_fortschritt`, `web_klartext`, `web_port`.
- `i18n.katalog()` und rund 290 neue Texte (`web.*`) in Deutsch und Englisch.

**Tests:** `tests/test_web.py` (Vorschau bewegt nichts und zählt nicht, Leeren nur mit Anzahl,
Schlüssel verlassen den Rechner nicht, Token/Host/Origin/JSON, keine Dateien außerhalb von
`static/`, alle Texte zweisprachig, kein Inline-Code).

**BeeNara im Flugbrett** (kam nach dem ersten Stand dazu, `tests/test_web_beenara.py`):

- **Werkstatt:** Karte mit demselben Stand wie `beenara` in der Konsole (`beenara.bericht()` —
  eine Quelle für Konsole, CLI und Flugbrett), Herunterladen bzw. Vervollständigen, an/aus,
  Entfernen mit Bestätigung. Aktionen `beenara_laden` · `beenara_schalten` · `beenara_entfernen`.
- **Assistent:** Im Schritt „Modus" ein Haken „BeeNara mit herunterladen" — wie im Erststart der
  Konsole nur auf Zusage, Vorauswahl aus. Geladen wird erst nach „Projekt einrichten", damit die
  Einrichtung nie am Download hängt. Wer über die App einsteigt, sieht den Konsolen-Erststart
  sonst nie.
- **Fortschritt in Bytes:** `WebKonsole.progress(transfer=True)`; die Seite zeigt MB. Gedrosselt
  auf ein Ereignis je Prozent, sonst verdrängen ein paar hundert 1-MB-Stücke das Protokoll.
- **Wer hat entschieden:** `pipeline.quellen_text()` liefert „Entschieden: … von BeeNara" für
  Konsole und Seite; der Plan trägt je Datei die Quelle (Gedächtnis · BeeNara · KI-Kurzentscheid
  · Vollanalyse · Heuristik).
- **Wächter** gegen den Bruch, der beim Zusammenführen unbemerkt blieb („Entschieden: {teile}"):
  Jeder Aufruf der Seite hat einen Endpunkt und umgekehrt, und jeder Text bekommt alle seine
  Platzhalter.

---

## 7. Phase 4: Testplan für Nutzertests

**Ziel:** prüfen, ob das Flugbrett ohne Erklärung bedienbar ist und ob die Bienenwelt hilft oder
stört, getrennt für Privatpersonen und Unternehmen.

**Teilnehmende:** je 2–3 aus beiden Gruppen. Business-Teilnehmende testen einmal mit und einmal
ohne Arbeitsmodus (Reihenfolge wechseln).

**Vorbereitung:** ein Test-Ordner mit ~15 gemischten Dateien (Rechnungen, Verträge, Protokolle,
1 Dublette, 2 nichtssagende Notizen). `pollysort-web` mit eigenem `POLLYSORT_HOME`, damit
nichts Echtes berührt wird.

**Aufgaben** (laut denken lassen, nicht helfen):

1. Richte den Ordner als Projekt ein.
2. Finde heraus, wohin PollySort die Dateien sortieren würde, *ohne dass sich etwas bewegt*.
3. Sortiere die Dateien ein.
4. Kümmere dich um die Dateien, bei denen PollySort unsicher war.
5. Eine Rechnung liegt in der falschen Kategorie: Korrigiere das.
6. Mach die letzte Verschiebung rückgängig.
7. Schalte alles „Verspielte" für den Büroalltag ab.
8. Finde heraus, ob eine Datei doppelt vorhanden ist, und räume sie weg.

**Beobachten & fragen:**

- Welche Begriffe waren unklar (Flugloch? Wachstafel? Rückflug?)? Wurde der Klartext gelesen?
- Wurde die Vorschau als „sicher, es passiert nichts" verstanden?
- Haben Animationen oder Abzeichen gestört, motiviert oder waren sie egal?
- Business: Würden Sie das im Team einsetzen? Was müsste dafür anders sein?
- Einschätzung 1–5: „wirkt seriös" · „macht Spaß" · „ich wusste immer, was passiert".

**Auswertung:** Probleme nach Häufigkeit × Schwere sortieren. Begriffe, die mehr als die Hälfte
nicht versteht, bekommen einen stärkeren Klartext oder werden im Arbeitsmodus standardmäßig
umgedreht.

---

## 8. Offen & nächste Schritte

- **Konsolen-Hinweise im Browser:** Ein paar Meldungen aus dem Kern nennen Konsolenbefehle oder
  Tasten („'beenara laden' setzt fort", „Strg-C unterbricht"). Im Flugbrett wären „Werkstatt"
  bzw. der Knopf die bessere Wortwahl — dafür bräuchte die WebKonsole eigene Varianten dieser Texte.
- **Zugangsdaten im Browser** (OpenRouter-Schlüssel, Flugrouten): bewusst noch nicht. Falls
  gewünscht, als eigenes Formular mit eigener Prüfung, nie im Protokoll.
- **Logo & Markenfarben:** Die Pixel-Biene ist ein Vorschlag. Sobald es ein offizielles Logo
  gibt, ersetzt es `Pixel.biene()` im Kopf und `favicon.svg`.
- **Web-Cockpit für Teams:** Der `Dienst` ist so geschnitten, dass er später hinter einer
  Mehrbenutzer-Schicht laufen kann (Rechte, Server-Betrieb). Das gehört in das kommerzielle
  Cockpit-Paket, nicht hierher.
- **Wabenbau-Kontakte & Meilensteine** (Roadmap): passen als Erweiterung des Formulars in der Wabe.
- **Datei-Auswahl statt Pfad tippen:** Browser geben keine Ordnerpfade heraus. In der eigenen
  Anwendung ginge das jetzt nativ (pywebview hat einen Ordner-Dialog) — ein naheliegender
  nächster Schritt für den Einrichtungs-Assistenten.
- **Nur eine Instanz:** Wer PollySort zweimal startet, bekommt zwei Fenster mit je eigenem
  Server. Das Lock der Königin verhindert gleichzeitiges Schreiben; schöner wäre, das
  vorhandene Fenster nach vorn zu holen.
- **Installierbares Paket ohne Python** (z. B. per PyInstaller als `.exe`/`.app`): bisher setzen
  die Installer ein vorhandenes Python 3.12+ voraus.

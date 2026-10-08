"""Leichtgewichtige i18n für die Konsole (DE/EN).

``t(key, **kw)`` liefert den Text in der aktiven Sprache. Fehlt ein Schlüssel in der
Zielsprache, fällt es auf Deutsch zurück (dann auf den Schlüssel selbst) — nie ein Crash.
Die Bienen-Metaphern werden bewusst sinngemäß übersetzt, nicht Wort für Wort.

Die aktive Sprache wird beim Start aus der Config gesetzt (`set_language`).
"""

from __future__ import annotations

_LANG = "de"

_CATALOG: dict[str, dict[str, str]] = {
    # Sprache
    "lang.set": {"de": "Sprache: Deutsch 🇩🇪", "en": "Language: English 🇬🇧"},
    "lang.usage": {"de": "Nutzung: sprache <de|en>", "en": "Usage: language <de|en>"},
    # Inbox / Status
    "inbox.some": {
        "de": "{n} lose Datei(en) warten aufs Sortieren — tippe 'sortiere' (s)",
        "en": "{n} loose file(s) waiting — type 'sort' (s)",
    },
    "inbox.empty": {"de": "Keine losen Dateien. Alles aufgeräumt. ✨",
                    "en": "No loose files. All tidy. ✨"},
    "help.shortcuts": {
        "de": "Kürzel:  [honey]s[/honey] sortiere · [honey]v[/honey] vorschau · "
              "[honey]r[/honey] rueckfragen · [honey]l[/honey] liste · "
              "[honey]home[/honey] Übersicht · [honey]hilfe[/honey]/[honey]exit[/honey]",
        "en": "Shortcuts:  [honey]s[/honey] sort · [honey]v[/honey] preview · "
              "[honey]r[/honey] review · [honey]l[/honey] list · "
              "[honey]home[/honey] overview · [honey]help[/honey]/[honey]exit[/honey]",
    },
    "home.title": {"de": "🏠 Zuhause", "en": "🏠 Home"},
    "home.noproject": {
        "de": "Kein Projekt aktiv. 'neu' legt eins an, 'wechsel <nr>' öffnet eins.",
        "en": "No active project. 'new' creates one, 'switch <n>' opens one.",
    },

    # ------------------------------------------------------------------ #
    #  Der wachsende Bienenstock (spiel.py) — Fortschritt sichtbar machen
    # ------------------------------------------------------------------ #
    "spiel.titel": {"de": "Dein Bienenstock", "en": "Your hive"},
    "spiel.stufe": {"de": "Stufe", "en": "Level"},
    "spiel.stufe.schwarm": {"de": "Junger Schwarm", "en": "Fresh swarm"},
    "spiel.stufe.jung": {"de": "Junger Stock", "en": "Young hive"},
    "spiel.stufe.summend": {"de": "Summender Stock", "en": "Humming hive"},
    "spiel.stufe.stark": {"de": "Starker Stock", "en": "Strong hive"},
    "spiel.stufe.golden": {"de": "Goldener Stock", "en": "Golden hive"},
    "spiel.stufe.legendaer": {"de": "Legendärer Stock", "en": "Legendary hive"},
    "spiel.bis_naechste": {"de": "noch {n} bis zur nächsten Stufe",
                           "en": "{n} more to the next level"},
    "spiel.maximum": {"de": "höchste Stufe erreicht 🏆", "en": "top level reached 🏆"},
    "spiel.zahlen": {
        "de": "{dokumente} einsortiert · {waben} Waben · {regeln} gelernte Regeln · "
              "{serie} Tage in Folge",
        "en": "{dokumente} filed · {waben} combs · {regeln} learned rules · "
              "{serie}-day streak",
    },
    "spiel.abzeichen_titel": {"de": "Abzeichen {n}/{gesamt}:", "en": "Badges {n}/{gesamt}:"},
    "spiel.abzeichen.erste_wabe": {"de": "Erste Wabe", "en": "First comb"},
    "spiel.abzeichen.zehn": {"de": "Zehnerpack", "en": "Ten in the tin"},
    "spiel.abzeichen.hundert": {"de": "Hundertschaft", "en": "Century"},
    "spiel.abzeichen.lehrmeister": {"de": "Lehrmeister", "en": "Mentor"},
    "spiel.abzeichen.weise": {"de": "Weise Königin", "en": "Wise queen"},
    "spiel.abzeichen.blitzblank": {"de": "Blitzblank", "en": "Spotless"},
    "spiel.abzeichen.serie": {"de": "Sieben Tage Sonne", "en": "Seven sunny days"},
    "spiel.abzeichen.vielfalt": {"de": "Bunter Stock", "en": "Colourful hive"},
    "spiel.neu": {"de": "Neues Abzeichen: {name} — {grund}",
                  "en": "New badge: {name} — {grund}"},
    "spiel.aufgestiegen": {"de": "Aufgestiegen: {stufe}!", "en": "Level up: {stufe}!"},
    "spiel.leer": {
        "de": "Noch nichts einsortiert — 'sortiere' legt los, dann wächst hier etwas.",
        "en": "Nothing filed yet — run 'sort' and this will start to grow.",
    },
    "spiel.grund.erste_wabe": {"de": "erstes Dokument einsortiert",
                               "en": "filed your first document"},
    "spiel.grund.zehn": {"de": "10 Dokumente einsortiert", "en": "filed 10 documents"},
    "spiel.grund.hundert": {"de": "100 Dokumente einsortiert", "en": "filed 100 documents"},
    "spiel.grund.lehrmeister": {"de": "erste Korrektur beigebracht",
                                "en": "taught your first correction"},
    "spiel.grund.weise": {"de": "5 gelernte Regeln auf der Wachstafel",
                          "en": "5 learned rules on the wax tablet"},
    "spiel.grund.blitzblank": {"de": "Posteingang komplett leer geräumt",
                               "en": "cleared the inbox completely"},
    "spiel.grund.serie": {"de": "7 Tage in Folge aufgeräumt",
                          "en": "tidied 7 days in a row"},
    "spiel.grund.vielfalt": {"de": "6 verschiedene Waben gefüllt",
                             "en": "filled 6 different combs"},

    # ------------------------------------------------------------------ #
    #  Erststart-Assistent (firstrun.py) — Sprache → Darstellung → KI → Überblick
    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    #  Projekt-Einrichtungs-Assistent (repl.py) — Fortsetzung des Erststarts
    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    #  Sortierlauf (pipeline.py) — was der Nutzer bei jedem Lauf liest
    # ------------------------------------------------------------------ #
    "pl.nothing": {"de": "Keine neuen Dateien zu sortieren. Alles aufgeräumt. ✨",
                   "en": "No new files to sort. All tidy. ✨"},
    "pl.found": {"de": "{n} Datei(en) gefunden — verarbeite …",
                 "en": "{n} file(s) found — working …"},
    "pl.progress.sort": {"de": "sortiere", "en": "sorting"},
    "pl.progress.reindex": {"de": "Gedächtnis neu", "en": "rebuilding memory"},
    "pl.drift": {
        "de": "Das Embedding-Modell hat sich geändert (Gedächtnis: {drift}). Alte Vektoren "
              "matchen nicht mehr zuverlässig — 'gedaechtnis neu' baut das Gedächtnis mit "
              "dem aktuellen Modell neu auf.",
        "en": "The embedding model has changed (memory: {drift}). Old vectors no longer "
              "match reliably — 'memory rebuild' rebuilds the memory with the current model.",
    },
    "pl.turbo": {
        "de": "Ultra Swarm: {n} Dokument(e) parallel mit {workers} Bienen vorbereitet — "
              "lagere jetzt ein …",
        "en": "Ultra Swarm: {n} document(s) prepared in parallel by {workers} bees — "
              "filing them now …",
    },
    "pl.unexpected": {"de": "{name}: unerwarteter Fehler — {err}",
                      "en": "{name}: unexpected error — {err}"},
    "pl.reindex_skip": {"de": "Reindex übersprungen ({id}): {err}",
                        "en": "Reindex skipped ({id}): {err}"},
    "pl.retry": {"de": "Neuer Anlauf (war Fehler): {name}",
                 "en": "Retrying (previously failed): {name}"},
    "pl.path_fixed": {"de": "Pfad repariert: {name} (kein LLM-Call)",
                      "en": "Path repaired: {name} (no LLM call)"},
    "pl.duplicate": {"de": "Dublette: {name} (kein neuer Eintrag, kein LLM-Call)",
                     "en": "Duplicate: {name} (no new entry, no LLM call)"},
    "pl.too_big": {"de": "{name} > {mb} MB → Metadaten-Eintrag",
                   "en": "{name} > {mb} MB → metadata-only entry"},
    "pl.dry_move": {"de": "[Vorschau] {name} → {dest}", "en": "[preview] {name} → {dest}"},
    "pl.entry_error": {"de": "{name}: {reason}", "en": "{name}: {reason}"},
    "pl.rule.preview": {"de": "Vorschau", "en": "Preview"},
    "pl.rule.done": {"de": "Fertig", "en": "Done"},
    "pl.preview_sorted": {"de": "[Vorschau] {n} Datei(en) würden einsortiert: {parts}",
                          "en": "[preview] {n} file(s) would be filed: {parts}"},
    "pl.sorted": {"de": "{n} Datei(en) sortiert: {parts}", "en": "{n} file(s) sorted: {parts}"},
    "pl.duplicates": {
        "de": "{n} Dublette(n) erkannt (nicht doppelt abgelegt) — 'dubletten aufraeumen' "
              "legt sie in die Quarantäne",
        "en": "{n} duplicate(s) found (not filed twice) — 'duplicates cleanup' moves them "
              "to quarantine",
    },
    "pl.recovered": {"de": "{n} Pfad(e) nachgezogen", "en": "{n} path(s) updated"},
    "pl.errors": {"de": "{n} Datei(en) mit Fehler — 'liste error' zeigt sie",
                  "en": "{n} file(s) with errors — 'list error' shows them"},
    "pl.review": {
        "de": "{n} Datei(en) unsicher — liegen noch hier. Mit 'rueckfragen' schnell zuordnen.",
        "en": "{n} file(s) uncertain — still lying here. Sort them out with 'review'.",
    },
    "pl.calls_offline": {
        "de": "{n} Analyse(n) — Sparmodus, ohne KI-Anfrage und ohne Kosten",
        "en": "{n} analysis/analyses — low-power mode, no AI request and no cost",
    },
    "pl.calls_local": {"de": "{n} KI-Anfragen — lokal gerechnet, ohne Kosten",
                       "en": "{n} AI requests — computed locally, no cost"},
    "pl.calls_online": {"de": "{n} KI-Anfragen · ~{cost} €", "en": "{n} AI requests · ~{cost} €"},
    "pl.preview_note": {"de": "Vorschau — es wurde nichts verschoben oder gespeichert.",
                        "en": "Preview — nothing was moved or saved."},
    "pl.celebrate": {"de": "Sauber sortiert — nichts bleibt liegen!",
                     "en": "All sorted — nothing left lying around!"},

    "vw.done": {
        "de": "Gedächtnis vorgewärmt: {n} Beispiel(e) aus {k} Kategorie(n) — so landet "
              "auch das erste Dokument jeder Sorte gleich richtig.",
        "en": "Memory warmed up: {n} example(s) from {k} categor(ies) — so the first "
              "document of each kind lands correctly too.",
    },
    "su.choice": {"de": "Wahl [{default}]: ", "en": "Choice [{default}]: "},
    "su.cancelled": {"de": "Abgebrochen — kein Projekt angelegt.",
                     "en": "Cancelled — no project created."},
    "su.exists": {"de": "'{name}' ist schon ein Projekt (Konfiguration vorhanden).",
                  "en": "'{name}' is already a project (configuration found)."},
    "su.exists.redo": {
        "de": "Neu einrichten — Assistent starten (überschreibt die Config)? [j/N]: ",
        "en": "Set up again — run the wizard (overwrites the config)? [y/N]: ",
    },
    "su.exists.reset": {
        "de": "Katalog frisch starten? (Dateien bleiben, altes .honig wird gesichert) [j/N]: ",
        "en": "Start the catalogue fresh? (files stay, old .honig is backed up) [y/N]: ",
    },
    "su.exists.open": {"de": "Ok — öffne das bestehende Projekt.",
                       "en": "OK — opening the existing project."},
    "su.backup.ok": {"de": "Alter Katalog gesichert → {name}",
                     "en": "Old catalogue backed up → {name}"},
    "su.backup.fail": {"de": "Konnte {name} nicht sichern: {err}",
                       "en": "Could not back up {name}: {err}"},

    "su.path.ask": {"de": "Pfad zum Projekt-Ordner (leer = abbrechen): ",
                    "en": "Path to the project folder (empty = cancel): "},
    "su.path.create": {"de": "Ordner gibt es noch nicht. '{path}' anlegen? [J/n]: ",
                       "en": "Folder does not exist yet. Create '{path}'? [Y/n]: "},
    "su.path.mkfail": {"de": "Konnte nicht anlegen: {err}", "en": "Could not create it: {err}"},
    "su.path.notdir": {"de": "'{path}' ist kein Ordner.", "en": "'{path}' is not a folder."},

    "su.title": {"de": "Projekt einrichten", "en": "Set up project"},
    "su.folder": {"de": "Ordner: {path}", "en": "Folder: {path}"},
    "su.name": {"de": "Projektname [{default}]: ", "en": "Project name [{default}]: "},
    "su.done.title": {"de": "Fertig eingerichtet", "en": "All set"},
    "su.done": {
        "de": "'{name}' · {n} Waben{made} · Modus {provider}{watch}",
        "en": "'{name}' · {n} combs{made} · mode {provider}{watch}",
    },
    "su.done.made": {"de": "{n} Ordner angelegt", "en": "{n} folders created"},
    "su.done.notify": {"de": "Eingang: melden", "en": "inbox: notify"},
    "su.done.move": {"de": "Eingang: auto-sortieren", "en": "inbox: auto-sort"},
    "su.filing": {
        "de": "Königin lässt einlagern — sortiere die vorhandenen Dokumente …",
        "en": "The queen files what is already here — sorting the existing documents …",
    },

    "su.mode.q": {
        "de": "Modus — womit sollen Dokumente eingeordnet werden?",
        "en": "Mode — how should documents be classified?",
    },
    "su.mode.or_key": {
        "de": "Cloud — KI über OpenRouter, beste Qualität (Key hinterlegt)",
        "en": "Cloud — AI via OpenRouter, best quality (key on file)",
    },
    "su.mode.or_nokey": {
        "de": "Cloud — KI über OpenRouter, beste Qualität (Key jetzt hinterlegen)",
        "en": "Cloud — AI via OpenRouter, best quality (add a key now)",
    },
    "su.mode.nokey": {
        "de": "Kein Key → Sparmodus.",
        "en": "No key → low-power mode.",
    },

    "su.cat.q": {"de": "Kategorien — wie soll einsortiert werden?",
                 "en": "Categories — how should things be filed?"},
    "su.cat.byai": {"de": "die KI schaut sie an", "en": "the AI looks at them"},
    "su.cat.byheur": {"de": "heuristisch", "en": "heuristically"},
    "su.cat.propose": {"de": "Vorschlag — {n} Datei(en) anschauen ({how})",
                       "en": "Suggestion — look at {n} file(s) ({how})"},
    "su.cat.recommended": {"de": "(empfohlen)", "en": "(recommended)"},
    "su.cat.standard": {"de": "Standard  — {cats}", "en": "Standard  — {cats}"},
    "su.cat.own": {"de": "Eigene    — selbst eingeben", "en": "Custom    — type your own"},
    "su.cat.enter": {"de": "Kategorien (kommagetrennt): ",
                     "en": "Categories (comma-separated): "},

    "su.scout.ai": {
        "de": "Spähbienen fliegen aus — die KI begutachtet Dokumente & bestehende Waben …",
        "en": "Scout bees are out — the AI inspects documents & existing combs …",
    },
    "su.scout.offline": {
        "de": "Spähbienen fliegen aus über Dokumente & bestehende Waben …",
        "en": "Scout bees are out over documents & existing combs …",
    },
    "su.scout.unreachable": {"de": "Provider nicht erreichbar", "en": "provider unreachable"},
    "su.scout.failed": {"de": "KI-Analyse fehlgeschlagen ({n} Datei(en)) — {reason}.",
                        "en": "AI analysis failed ({n} file(s)) — {reason}."},
    "su.scout.failed_hint": {
        "de": "Der Vorschlag unten basiert nur auf der Heuristik des Sparmodus. Tipp: KI prüfen "
              "('modus', 'schluessel test') und 'setup' später erneut ausführen.",
        "en": "The suggestion below is heuristics only (low-power mode). Tip: check the AI ('mode', "
              "'key test') and run 'setup' again later.",
    },
    "su.scout.partial": {
        "de": "{bad} von {total} KI-Analysen fehlgeschlagen — Rest heuristisch ergänzt.",
        "en": "{bad} of {total} AI analyses failed — the rest filled in heuristically.",
    },
    "su.scout.nothing": {"de": "Nichts zu beschnuppern — nehme die Standard-Waben.",
                         "en": "Nothing to sniff at — using the standard combs."},
    "su.scout.tag_ai": {"de": "KI-Analyse", "en": "AI analysis"},
    "su.scout.tag_heur": {"de": "heuristisch", "en": "heuristic"},
    "su.scout.note": {"de": ", davon {n} bestehende", "en": ", {n} of them existing"},
    "su.scout.header": {"de": "{total} Dokument(e) beschnuppert ({tag}{note}) — Waben-Vorschlag:",
                        "en": "Sniffed {total} document(s) ({tag}{note}) — suggested combs:"},
    "su.scout.exists": {"de": "Wabe existiert", "en": "comb exists"},
    "su.scout.apply": {"de": "Übernehmen? [J/n] oder eigene Kategorien eingeben: ",
                       "en": "Use these? [Y/n] or type your own categories: "},

    "su.sub.q": {"de": "Unterordner — diese Kategorien nach Jahr/Monat ablegen? (Vorschlag)",
                 "en": "Subfolders — file these categories by year/month? (suggestion)"},
    "su.sub.apply": {"de": "Übernehmen? [J/n] (n = keine Unterordner): ",
                     "en": "Use these? [Y/n] (n = no subfolders): "},

    "su.watch.q": {"de": "Neue Dateien im Eingang (alle ~10 s prüfen)?",
                   "en": "New files in the inbox (checked every ~10 s)?"},
    "su.watch.off": {"de": "aus", "en": "off"},
    "su.watch.notify": {"de": "nur melden — 'es gibt X neue Dateien'",
                        "en": "notify only — 'there are X new files'"},
    "su.watch.move": {"de": "sofort sortieren", "en": "sort immediately"},

    "bye": {"de": "Bis bald! 🍯", "en": "See you! 🍯"},
    "start.hint": {
        "de": "v{version} · 'hilfe' zeigt alle Befehle",
        "en": "v{version} · type 'help' for all commands",
    },
    "setup.aborted": {
        "de": "Einrichtung abgebrochen — 'neu' oder 'setup' startet sie später.",
        "en": "Setup cancelled — 'new' or 'setup' starts it again later.",
    },
    "firstrun.welcome": {"de": "Willkommen! Noch kein Projekt vorhanden.",
                         "en": "Welcome! No project yet."},
    "firstrun.what": {
        "de": "Ein Projekt ist ein Ordner, dessen Dokumente sortiert werden sollen.",
        "en": "A project is a folder whose documents should be sorted.",
    },

    "fr.choice": {"de": "Wahl [{default}]: ", "en": "Choice [{default}]: "},

    "fr.theme.title": {"de": "Darstellung — wie soll die Konsole aussehen?",
                       "en": "Appearance — how should the console look?"},
    "fr.theme.dark": {"de": "Dunkel — schwarzer Hintergrund, honiggelbe Schrift",
                      "en": "Dark — black background, honey-yellow text"},
    "fr.theme.light": {"de": "Hell — weißer Hintergrund, honiggelbe Schrift",
                       "en": "Light — white background, honey-yellow text"},
    "fr.theme.auto": {"de": "Automatik — tagsüber dunkel, abends hell",
                      "en": "Auto — dark during the day, light in the evening"},

    "fr.ai.title": {"de": "KI — womit sollen Dokumente verstanden werden?",
                    "en": "AI — how should documents be understood?"},
    "fr.ai.offline": {
        "de": "Sparmodus — reine Heuristik: sofort, kostenlos, läuft auf jedem Rechner",
        "en": "Low-power — heuristics only: instant, free, runs on any PC",
    },
    "fr.ai.ollama": {
        "de": "Lokal — KI auf deinem Rechner (Ollama), gratis & privat",
        "en": "Local — AI on your machine (Ollama), free & private",
    },
    "fr.ai.openrouter": {
        "de": "Cloud — KI über eine API (OpenRouter), beste Qualität, kostenpflichtig",
        "en": "Cloud — AI via an API (OpenRouter), best quality, paid",
    },
    "fr.ai.found": {"de": "✅ erkannt", "en": "✅ detected"},
    "fr.ai.notfound": {"de": "— nicht erreichbar", "en": "— not reachable"},
    "fr.ai.keyset": {"de": "✅ Key hinterlegt", "en": "✅ key on file"},
    "fr.ai.keyneeded": {"de": "🔑 Key nötig", "en": "🔑 key needed"},

    # Kurzformen fuer die Zusammenfassung (kein Zerschneiden der Langtexte).
    "fr.short.dark": {"de": "Dunkel", "en": "Dark"},
    "fr.short.light": {"de": "Hell", "en": "Light"},
    "fr.short.auto": {"de": "Automatik", "en": "Auto"},
    "fr.short.offline": {
        "de": "Sparmodus",
        "en": "Low-power",
    },
    "fr.short.ollama": {
        "de": "Lokal (Ollama)",
        "en": "Local (Ollama)",
    },
    "fr.short.openrouter": {
        "de": "Cloud (OpenRouter)",
        "en": "Cloud (OpenRouter)",
    },
    "fr.ai.ollama_missing": {
        "de": "Es antwortet kein lokaler Ollama-Server — vorerst Sparmodus.",
        "en": "No local Ollama server is responding — using low-power mode for now.",
    },
    "fr.ai.ollama_hint": {
        "de": "Starte Ollama ('ollama serve') und wechsle dann mit 'modus lokal'.",
        "en": "Start Ollama ('ollama serve'), then switch with 'mode local'.",
    },
    "fr.ai.key_where": {
        "de": "Key holen: openrouter.ai/keys — er bleibt lokal (chmod 600).",
        "en": "Get a key at openrouter.ai/keys — it stays local (chmod 600).",
    },
    "fr.ai.key_prompt": {"de": "OpenRouter-API-Key (leer = überspringen): ",
                         "en": "OpenRouter API key (empty = skip): "},
    "fr.ai.key_skipped": {
        "de": "Kein Key — Sparmodus. Später jederzeit: 'schluessel setzen'.",
        "en": "No key — low-power mode. Any time later: 'key set'.",
    },
    "fr.ai.key_failed": {
        "de": "Key konnte nicht gespeichert werden — Sparmodus.",
        "en": "Could not save the key — low-power mode.",
    },
    "fr.ai.key_saved": {"de": "Key gespeichert (nur lokal, chmod 600).",
                        "en": "Key saved (local only, chmod 600)."},

    "fr.bn.title": {"de": "BeeNara — lokales Modell für die Ordnerwahl",
                    "en": "BeeNara — local model for picking folders"},
    "fr.bn.what": {
        "de": "Wählt beim Sortieren den passenden Ordner oder sagt, dass keiner passt. "
              "Läuft offline auf der CPU.",
        "en": "Picks the right folder while sorting, or says that none fits. "
              "Runs offline on the CPU.",
    },
    "fr.bn.size": {
        "de": "Einmaliger Download von Hugging Face ({repo}), ca. {mb} MB, dazu die Laufzeit "
              "(onnxruntime).",
        "en": "One-time download from Hugging Face ({repo}), about {mb} MB, plus its runtime "
              "(onnxruntime).",
    },
    "fr.bn.now": {"de": "Jetzt herunterladen", "en": "Download now"},
    "fr.bn.later": {"de": "Später — jederzeit mit 'beenara laden'",
                    "en": "Later — any time with 'beenara pull'"},
    "fr.bn.present": {"de": "✅ schon geladen", "en": "✅ already downloaded"},
    "fr.bn.skipped": {"de": "Kein Download. Später jederzeit: 'beenara laden'.",
                      "en": "No download. Any time later: 'beenara pull'."},
    "fr.done.bn_yes": {"de": "BeeNara: geladen ✅", "en": "BeeNara: downloaded ✅"},
    "fr.done.bn_no": {"de": "BeeNara: nicht geladen — 'beenara laden' holt es.",
                      "en": "BeeNara: not downloaded — 'beenara pull' fetches it."},

    "fr.done.title": {"de": "Fertig eingerichtet", "en": "All set"},
    "fr.done.summary": {
        "de": "Sprache {language} · Darstellung {theme} · KI {ai}",
        "en": "Language {language} · Appearance {theme} · AI {ai}",
    },
    "fr.done.change": {
        "de": "Änderbar jederzeit: 'sprache', 'thema', 'modus', 'schluessel'.",
        "en": "Change any time: 'language', 'theme', 'mode', 'key'.",
    },

    "fr.next.title": {"de": "So geht es los", "en": "How to get going"},
    "fr.next.step1": {
        "de": "1) 📂  Ordner wählen — seine losen Dateien sind dein Eingang.",
        "en": "1) 📂  Pick a folder — its loose files are your inbox.",
    },
    "fr.next.step2": {
        "de": "2) 👀  [honey]vorschau[/honey] (v) — zeigt, wohin sortiert würde, "
              "und fragt: anwenden? [J/n]",
        "en": "2) 👀  [honey]preview[/honey] (v) — shows where things would go, "
              "then asks: apply? [Y/n]",
    },
    "fr.next.step3": {
        "de": "3) 🍯  [honey]sortiere[/honey] (s) — räumt die Dateien in Kategorie-Ordner ein.",
        "en": "3) 🍯  [honey]sort[/honey] (s) — files the documents into category folders.",
    },
    "fr.next.hint": {
        "de": "Später: [honey]home[/honey] Übersicht · [honey]hilfe[/honey] alle Befehle · "
              "[honey]flugrouten setup[/honey] für Erinnerungen.",
        "en": "Later: [honey]home[/honey] overview · [honey]help[/honey] all commands · "
              "[honey]routes setup[/honey] for reminders.",
    },
    # Sortierlauf — Zweitmeinung der Heuristik
    "pl.second_opinion": {
        "de": "{name}: Modell-Label '{label}' passt zu keiner Kategorie — Heuristik sagt {cat}",
        "en": "{name}: model label '{label}' matches no category — heuristic says {cat}",
    },
    # Kopfzeile / Prompt
    "header.noproject": {"de": "kein Projekt", "en": "no project"},
    "header.mode": {"de": "Modus {provider}", "en": "mode {provider}"},
    "header.loose": {"de": "{n} lose", "en": "{n} loose"},
    "header.tidy": {"de": "aufgeräumt", "en": "tidy"},
    "header.theme": {"de": "Thema {theme}", "en": "theme {theme}"},
    # Projekt öffnen
    "open.project": {"de": "Projekt: {name}  ·  {path}", "en": "Project: {name}  ·  {path}"},
    "open.mode": {"de": "Modus: {provider} · Kategorien: {cats}",
                  "en": "Mode: {provider} · categories: {cats}"},
    "open.sorting_new": {"de": "Sortiere neue Dateien …", "en": "Sorting new files …"},
    "open.watch_active": {"de": "Überwachung aktiv ({watch}). 'wache' für Dauerbetrieb.",
                          "en": "Watch active ({watch}). 'watch' runs it continuously."},
    "open.folder": {"de": "Ordner: {path}", "en": "Folder: {path}"},
    "open.not_setup": {"de": "Dieses Projekt ist noch nicht eingerichtet.",
                       "en": "This project isn't set up yet."},
    "open.setup_now": {"de": "Jetzt einrichten? [J/n]: ", "en": "Set it up now? [Y/n]: "},
    "open.setup_later": {"de": "Ok. 'setup' startet die Einrichtung, wann du willst.",
                         "en": "Ok. 'setup' starts the wizard whenever you like."},
    "noproject.hint": {
        "de": "Kein Projekt aktiv. 'neu' legt eins an, 'wechsel' öffnet ein bestehendes.",
        "en": "No project active. 'new' creates one, 'switch' opens an existing one.",
    },
    "unknown.cmd": {"de": "Unbekannt: {line}. 'hilfe' zeigt alle Befehle.",
                    "en": "Unknown: {line}. 'help' lists all commands."},
    "unknown.suggest": {"de": "Unbekannt: {line}. Meintest du {options}?",
                        "en": "Unknown: {line}. Did you mean {options}?"},
    "main.aborted": {"de": "Abgebrochen. 🐝", "en": "Cancelled. 🐝"},
    # Home / Status / Projekte
    "home.version": {"de": "v{version} · 'hilfe' zeigt alle Befehle",
                     "en": "v{version} · 'help' lists all commands"},
    "home.mode": {"de": "Modus: {provider} · Überwachung: {watch}",
                  "en": "Mode: {provider} · watch: {watch}"},
    "home.inbox": {"de": "{n} lose Datei(en) → 'sortiere'", "en": "{n} loose file(s) → 'sort'"},
    "home.sorted": {"de": "{n} Datei(en) sortiert/erfasst", "en": "{n} file(s) sorted/indexed"},
    "home.review": {"de": "{n} unsicher → 'rueckfragen'", "en": "{n} unsure → 'review'"},
    "home.error": {"de": "{n} mit Fehler → 'liste error'", "en": "{n} with errors → 'list error'"},
    "home.deadlines": {"de": "{n} Deadline(s) in ≤ 7 Tagen → 'kalender'",
                       "en": "{n} deadline(s) within 7 days → 'calendar'"},
    "home.nav": {"de": "Wechseln:  wechsel <nr>   ·   Neu:  neu <pfad>   ·   Hilfe:  hilfe",
                 "en": "Switch:  switch <n>   ·   New:  new <path>   ·   Help:  help"},
    "status.nothing": {"de": "Noch nichts passiert. Leg Dateien hier ab und tippe 'sortiere'.",
                       "en": "Nothing yet. Drop files here and type 'sort'."},
    "projects.title": {"de": "Projekte", "en": "Projects"},
    # Hilfe
    "help.group.daily": {"de": "🐝 Täglich benötigt", "en": "🐝 Daily"},
    "help.group.situational": {"de": "🎯 Für bestimmte Anwendungsfälle", "en": "🎯 Situational"},
    "help.group.pro": {"de": "🛠️ Für Profis", "en": "🛠️ Pro"},
    "help.tip": {"de": "Tipp: In Abfragen (z. B. Setup) bricht 'abbruch' oder 'bye' die Aktion ab.",
                 "en": "Tip: inside a prompt (e.g. setup), 'cancel' or 'bye' aborts the action."},
    "help.names": {"de": "Die englischen Befehlsnamen funktionieren ebenfalls.",
                   "en": "The German command names work as well."},
    "help.d.home": {"de": "Zurück zum Start-/Zuhause-Bildschirm (Übersicht)",
                    "en": "Back to the home screen (overview)"},
    "help.d.sort": {"de": "Lose Dateien in Kategorie-Ordner einräumen",
                    "en": "File loose documents into category folders"},
    "help.d.preview": {"de": "Erst zeigen, dann direkt anwenden [J/n]",
                       "en": "Show the plan first, then apply [Y/n]"},
    "help.d.review": {"de": "Unsichere Fälle schnell selbst zuordnen",
                      "en": "Assign the unsure cases yourself"},
    "help.d.status": {"de": "Was liegt hier, was ist schon sortiert?",
                      "en": "What's here, what's already sorted?"},
    "help.d.list": {"de": "Sortierte Einträge auflisten", "en": "List sorted entries"},
    "help.d.search": {"de": "Nach Stichwort suchen", "en": "Search by keyword"},
    "help.d.watch": {"de": "Eingang in Echtzeit überwachen (watchdog)",
                     "en": "Monitor the inbox in real time (watchdog)"},
    "help.d.turbo": {"de": "Ultra Swarm — viele Dateien parallel",
                     "en": "Ultra Swarm — many files in parallel"},
    "help.d.scan": {"de": "Ganzen Ordner prüfen; aus manuellen Moves lernen",
                    "en": "Check the whole folder; learn from hand-moves"},
    "help.d.import": {"de": "Aus einem anderen Ordner hierher sortieren",
                      "en": "Sort files from another folder into here"},
    "help.d.assign": {"de": "Zuordnung korrigieren (Gedächtnis lernt)",
                      "en": "Correct an assignment (memory learns)"},
    "help.d.subfolder": {"de": "Dynamische Unterordner, z. B. {pattern}",
                         "en": "Dynamic subfolders, e.g. {pattern}"},
    "help.d.duplicates": {"de": "Erkannte Dubletten zeigen / in die Quarantäne",
                          "en": "Show detected duplicates / move to quarantine"},
    "help.d.trash": {"de": "In Quarantäne / endgültig löschen (fragt nach)",
                     "en": "Quarantine / delete for good (asks first)"},
    "help.d.restore": {"de": "Aus Quarantäne zurück · letzten Move rückgängig",
                       "en": "Back from quarantine · undo the last move"},
    "help.d.progress": {"de": "Wie weit ist dein Bienenstock? Stufe, Abzeichen, Serie",
                        "en": "How far along is your hive? Level, badges, streak"},
    "help.d.charter": {"de": "Aus einer Wabe ein Projekt bauen (Bienenstock.md)",
                       "en": "Turn a category into a project (Bienenstock.md)"},
    "help.d.calendar": {"de": "Deadlines / Schwarm-Überblick", "en": "Deadlines / swarm overview"},
    "help.d.recommend": {"de": "Ablage-Strategie + Hinweise", "en": "Filing strategy + hints"},
    "help.d.new": {"de": "Projekt anlegen · zu anderem wechseln",
                   "en": "Create a project · switch to another"},
    "help.d.projects": {"de": "Alle Projekte · aktuelles neu einrichten",
                        "en": "All projects · reconfigure the current one"},
    "help.d.mode": {
        "de": "Sparmodus (Heuristik) · Lokal (Ollama) · Cloud (API)",
        "en": "Low-power (heuristics) · local (Ollama) · cloud (API)",
    },
    "help.d.model": {"de": "OpenRouter-Modell wechseln (Nektar-Sorte)",
                     "en": "Switch the OpenRouter model"},
    "help.d.key": {"de": "OpenRouter-Schlüssel prüfen / erneuern / entfernen",
                   "en": "Check / renew / remove the OpenRouter key"},
    "help.d.routes": {"de": "Discord/E-Mail der Wächterbienen (opt-in)",
                      "en": "Discord / e-mail notifications (opt-in)"},
    "help.d.reflect": {"de": "Meta-Learning: Regeln ableiten / zeigen / leeren",
                       "en": "Meta-learning: derive / show / clear rules"},
    "help.d.memory": {"de": "Kategorien/Vorschläge · 'neu' = Reindex nach Modellwechsel",
                      "en": "Categories/proposals · 'rebuild' = reindex after a model change"},
    "help.d.person": {"de": "Zuständigkeit im Hintergrund setzen",
                      "en": "Set responsibility in the background"},
    "help.d.doctor": {"de": "Health-Check: Python, KI-Provider, Modelle, Datenbank, Gedächtnis",
                      "en": "Health check: Python, AI provider, models, database, memory"},
    "help.d.beenara": {"de": "Lokale Entscheider-Modelle: laden · an/aus · entfernen · Big · Modellwahl",
                       "en": "Local decider models: download · on/off · remove · Big · model choice"},
    "help.d.language": {"de": "UI-Sprache umschalten (language / lang)",
                        "en": "Switch the UI language (sprache)"},
    "help.d.theme": {"de": "Dark/Light; 'auto' = tags dunkel, abends hell",
                     "en": "Dark/light; 'auto' = dark by day, light in the evening"},
    "help.d.view": {"de": "Statische Selbst-Ansicht oder klassisches Log",
                    "en": "Static self-redrawing view or classic log"},
    "help.d.help": {"de": "Diese Hilfe / Konsole verlassen", "en": "This help / leave the console"},
    # Doctor
    "doctor.cli_title": {"de": "PollySort — Health-Check", "en": "PollySort — health check"},
    "doctor.python": {"de": "Python", "en": "Python"},
    "doctor.provider": {
        "de": "Modus",
        "en": "Mode",
    },
    "doctor.models": {"de": "Modelle", "en": "Models"},
    "doctor.db": {"de": "Datenbank", "en": "Database"},
    "doctor.extract": {"de": "Extraktion", "en": "Extraction"},
    "doctor.memory": {"de": "Gedächtnis", "en": "Memory"},
    "doctor.noproject": {"de": "kein Projekt aktiv", "en": "no project active"},
    "doctor.py.need": {"de": " (benötigt 3.12+)", "en": " (needs 3.12+)"},
    "doctor.prov.offline": {
        "de": "Sparmodus (Heuristik, kostenlos)",
        "en": "low-power (heuristics, free)",
    },
    "doctor.prov.ollama_ok": {
        "de": "Lokal · Ollama {version} erreichbar",
        "en": "local · Ollama {version} reachable",
    },
    "doctor.prov.ollama_down": {
        "de": "Lokal · Ollama NICHT erreichbar (Server starten)",
        "en": "local · Ollama NOT reachable (start the server)",
    },
    "doctor.prov.or_nokey": {
        "de": "Cloud ohne Schlüssel → Sparmodus",
        "en": "cloud without key → low-power mode",
    },
    "doctor.models.ok": {"de": "{chat} · {embed} gezogen", "en": "{chat} · {embed} pulled"},
    "doctor.models.missing": {"de": "fehlt: {names} → {hint}", "en": "missing: {names} → {hint}"},
    "doctor.models.embed_note": {
        "de": " (ohne Embedding-Modell lernt das Gedächtnis nichts dazu)",
        "en": " (without the embedding model the memory learns nothing)",
    },
    "doctor.db.exists": {"de": "vorhanden", "en": "present"},
    "doctor.db.new": {"de": "wird angelegt", "en": "will be created"},
    "doctor.db.fail": {"de": "nicht schreibbar: {exc}", "en": "not writable: {exc}"},
    "doctor.extract.none": {"de": "keine (Kern-Fallback aktiv)", "en": "none (core fallback active)"},
    "doctor.mem.empty": {"de": "leer", "en": "empty"},
    "doctor.mem.drift": {"de": "{n} Vektoren · Modellwechsel ({drift}) → 'gedaechtnis neu'",
                         "en": "{n} vectors · model changed ({drift}) → 'memory rebuild'"},
    "doctor.mem.ok": {"de": "{n} Vektoren · {model}", "en": "{n} vectors · {model}"},
    "doctor.check_failed": {"de": "Check fehlgeschlagen: {exc}", "en": "check failed: {exc}"},
    "doctor.beenara": {"de": "BeeNara", "en": "BeeNara"},
    "doctor.bn.ok": {"de": "Version {version} · {mb} MB · sortiert mit",
                     "en": "version {version} · {mb} MB · sorting with it"},
    "doctor.bn.none": {"de": "nicht geladen (optional) → 'beenara laden'",
                       "en": "not downloaded (optional) → 'beenara pull'"},
    "doctor.bn.partial": {"de": "unvollständig → 'beenara laden' setzt fort",
                          "en": "incomplete → 'beenara pull' resumes"},
    "doctor.bn.aus": {"de": "Version {version} · ausgeschaltet ('beenara an')",
                      "en": "version {version} · switched off ('beenara on')"},
    "doctor.bn.version": {"de": "Version {version}, erwartet {need} → 'beenara laden'",
                          "en": "version {version}, expected {need} → 'beenara pull'"},
    "doctor.bn.laufzeit": {"de": "Version {version} · Laufzeit fehlt → 'beenara laden'",
                           "en": "version {version} · runtime missing → 'beenara pull'"},
    "doctor.beenara_big": {"de": "BeeNara Big", "en": "BeeNara Big"},
    "doctor.bb.partial": {"de": "unvollständig → 'beenara big laden' setzt fort",
                          "en": "incomplete → 'beenara big pull' resumes"},
    "doctor.bb.version": {"de": "Version {version}, erwartet {need} → 'beenara big laden'",
                          "en": "version {version}, expected {need} → 'beenara big pull'"},
    "doctor.bb.laufzeit": {"de": "Version {version} · Laufzeit fehlt → 'beenara big laden'",
                           "en": "version {version} · runtime missing → 'beenara big pull'"},
    # BeeNara — lokales Entscheider-Modell von Hugging Face (beenara.py)
    "bn.title": {"de": "🐝 BeeNara", "en": "🐝 BeeNara"},
    "bn.what": {
        "de": "Lokales Entscheider-Modell: wählt den passenden Ordner oder sagt, dass keiner "
              "passt. Läuft offline auf der CPU.",
        "en": "Local decider model: picks the right folder or says that none fits. "
              "Runs offline on the CPU.",
    },
    "bn.status.ok": {"de": "Geladen: Version {version} · {mb} MB · {path}",
                     "en": "Downloaded: version {version} · {mb} MB · {path}"},
    "bn.status.none": {
        "de": "Nicht geladen. 'beenara laden' holt es von Hugging Face ({repo}, ca. {mb} MB).",
        "en": "Not downloaded. 'beenara pull' fetches it from Hugging Face ({repo}, about {mb} MB).",
    },
    "bn.status.partial": {"de": "Unvollständig — 'beenara laden' setzt den Download fort.",
                          "en": "Incomplete — 'beenara pull' resumes the download."},
    # Sortiert BeeNara mit? Ein Grund je Zustand (beenara.warum_nicht).
    "bn.active.ja": {
        "de": "Sortiert mit: im Sparmodus statt der Heuristik, im Modus Lokal nach dem Gedächtnis "
              "— bei 3 bis 9 Ordnern. Unsichere Fälle und „keiner passt“ werden Rückfragen.",
        "en": "Sorting with it: instead of the heuristics in low-power mode, after the memory in "
              "local mode — with 3 to 9 folders. Unsure cases and \"none fits\" become reviews.",
    },
    "bn.active.aus": {"de": "Ausgeschaltet — 'beenara an' schaltet es wieder ein.",
                      "en": "Switched off — 'beenara on' switches it back on."},
    "bn.active.modell": {"de": "Sortiert noch nicht mit: Das Modell ist nicht (vollständig) geladen.",
                         "en": "Not sorting yet: the model is not (fully) downloaded."},
    "bn.active.version": {
        "de": "Sortiert nicht mit: Geladen ist Version {have}, dieses PollySort braucht {need} — "
              "'beenara laden' holt sie.",
        "en": "Not sorting: version {have} is downloaded, this PollySort needs {need} — "
              "'beenara pull' fetches it.",
    },
    "bn.active.laufzeit": {
        "de": "Sortiert noch nicht mit: Die Laufzeit fehlt ({pakete}) — 'beenara laden' "
              "installiert sie.",
        "en": "Not sorting yet: the runtime is missing ({pakete}) — 'beenara pull' installs it.",
    },
    "bn.project.ok": {"de": "Projekt {name}: BeeNara entscheidet mit.",
                      "en": "Project {name}: BeeNara takes part."},
    "bn.project.cloud": {"de": "Projekt {name} läuft im Modus Cloud — dort entscheidet BeeNara "
                               "nicht mit.",
                         "en": "Project {name} runs in cloud mode — BeeNara does not take part "
                               "there."},
    "bn.project.count": {
        "de": "Projekt {name} hat {n} Ordner — BeeNara entscheidet bei 3 bis 9 mit, sonst der "
              "bisherige Weg.",
        "en": "Project {name} has {n} folders — BeeNara takes part with 3 to 9, otherwise the "
              "usual path decides.",
    },
    "bn.set.on": {"de": "BeeNara an — es sortiert mit, sobald Modell und Laufzeit da sind.",
                  "en": "BeeNara on — it sorts along as soon as model and runtime are there."},
    "bn.set.off": {"de": "BeeNara aus — es bleibt geladen, sortiert aber nicht mit.",
                   "en": "BeeNara off — it stays downloaded but does not sort."},
    # Keine eckigen Klammern: rich läse „[laden | entfernen]" als Markup und verschluckte es.
    "bn.usage": {"de": "Nutzung: beenara (Stand) · beenara laden · beenara an · beenara aus · "
                       "beenara entfernen",
                 "en": "Usage: beenara (status) · beenara pull · beenara on · beenara off · "
                       "beenara remove"},
    # Laufzeit (onnxruntime, tokenizers, numpy)
    "bn.rt.installing": {"de": "Installiere die Laufzeit ({pakete}) …",
                         "en": "Installing the runtime ({pakete}) …"},
    "bn.rt.done": {"de": "Laufzeit installiert — BeeNara sortiert ab dem nächsten Lauf mit.",
                   "en": "Runtime installed — BeeNara sorts along from the next run."},
    "bn.rt.failed": {"de": "Laufzeit nicht installiert: {err} — von Hand: {cmd}",
                     "en": "Runtime not installed: {err} — by hand: {cmd}"},
    "bn.rt.manual": {
        "de": "Weder pip noch uv gefunden. Bitte die Laufzeit von Hand installieren: {pakete}",
        "en": "Neither pip nor uv found. Please install the runtime by hand: {pakete}",
    },
    "bn.rt.restart": {"de": "Laufzeit installiert — bitte PollySort neu starten.",
                      "en": "Runtime installed — please restart PollySort."},
    # Im Sortierlauf
    "bn.run.load_failed": {"de": "BeeNara ließ sich nicht öffnen ({err}) — dieser Lauf "
                                 "entscheidet ohne BeeNara.",
                           "en": "Could not open BeeNara ({err}) — this run decides without it."},
    "bn.run.loading": {"de": "BeeNara wird geladen …", "en": "Loading BeeNara …"},
    "bn.run.failed": {"de": "BeeNara ist ausgefallen ({err}) — der Rest des Laufs entscheidet "
                            "ohne BeeNara.",
                      "en": "BeeNara failed ({err}) — the rest of this run decides without it."},
    "bn.checking": {"de": "Frage Hugging Face nach der aktuellen Version von {repo} …",
                    "en": "Asking Hugging Face for the current version of {repo} …"},
    "bn.current": {"de": "BeeNara ist aktuell (Version {version}) · {path}",
                   "en": "BeeNara is up to date (version {version}) · {path}"},
    "bn.start": {
        "de": "Lade {n} Datei(en), {mb} MB — Version {version} → {path}. "
              "Strg-C unterbricht, 'beenara laden' setzt später fort.",
        "en": "Downloading {n} file(s), {mb} MB — version {version} → {path}. "
              "Ctrl-C pauses, 'beenara pull' resumes later.",
    },
    "bn.progress": {"de": "BeeNara laden", "en": "Downloading BeeNara"},
    "bn.done": {"de": "BeeNara geladen und geprüft (Version {version}, {mb} MB) · {path}",
                "en": "BeeNara downloaded and verified (version {version}, {mb} MB) · {path}"},
    "bn.interrupted": {
        "de": "Download unterbrochen — 'beenara laden' setzt an derselben Stelle fort.",
        "en": "Download paused — 'beenara pull' resumes where it stopped.",
    },
    "bn.err.hub": {"de": "Hugging Face nicht erreichbar: {err}",
                   "en": "Could not reach Hugging Face: {err}"},
    "bn.err.layout": {"de": "Im Repo {repo} fehlen erwartete Dateien: {names}",
                      "en": "The repo {repo} is missing expected files: {names}"},
    "bn.err.download": {
        "de": "Download fehlgeschlagen: {err} — 'beenara laden' versucht es erneut und setzt fort.",
        "en": "Download failed: {err} — 'beenara pull' tries again and resumes.",
    },
    "bn.err.hash": {
        "de": "Prüfsumme von {name} stimmt nicht — die Datei wurde verworfen. "
              "Bitte 'beenara laden' noch einmal.",
        "en": "Checksum of {name} does not match — the file was discarded. "
              "Please run 'beenara pull' again.",
    },
    "bn.err.space": {"de": "Zu wenig Speicherplatz: {need} MB nötig, {free} MB frei ({path}).",
                     "en": "Not enough disk space: {need} MB needed, {free} MB free ({path})."},
    "bn.remove.confirm": {"de": "BeeNara ({mb} MB) von diesem Rechner entfernen? [j/N]: ",
                          "en": "Remove BeeNara ({mb} MB) from this computer? [y/N]: "},
    "bn.remove.done": {"de": "BeeNara entfernt.", "en": "BeeNara removed."},
    "bn.remove.none": {"de": "BeeNara ist nicht geladen — nichts zu entfernen.",
                       "en": "BeeNara is not downloaded — nothing to remove."},
    "bn.remove.failed": {"de": "Entfernen fehlgeschlagen: {err}", "en": "Removing failed: {err}"},
    # BeeNara Big — das große Modell für ganze Ordnerbäume (beenara_big.py). Fehlt hier ein
    # Text, gilt der bn.…-Text (beenara._t).
    "bb.title": {"de": "🐝 BeeNara Big", "en": "🐝 BeeNara Big"},
    "bb.what": {
        "de": "Das große Modell für ganze Ordnerbäume (3 bis etwa 300 Ordner). Es schlägt den "
              "passenden Ordner vor — in dieser Version immer als Rückfrage, nie automatisch. "
              "Braucht eine NVIDIA-Grafikkarte mit mindestens 8 GB; ca. 4,7 GB Download.",
        "en": "The large model for whole folder trees (3 to about 300 folders). It suggests the "
              "right folder — in this version always as a review, never automatically. Needs an "
              "NVIDIA graphics card with at least 8 GB; about 4.7 GB download.",
    },
    "bb.status.ok": {"de": "Geladen: Version {version} · {mb} MB · {path}",
                     "en": "Downloaded: version {version} · {mb} MB · {path}"},
    "bb.status.none": {
        "de": "Nicht geladen. 'beenara big laden' holt es von Hugging Face ({repo} und das "
              "Basismodell, ca. {mb} MB).",
        "en": "Not downloaded. 'beenara big pull' fetches it from Hugging Face ({repo} and the "
              "base model, about {mb} MB).",
    },
    "bb.status.partial": {"de": "Unvollständig — 'beenara big laden' setzt den Download fort.",
                          "en": "Incomplete — 'beenara big pull' resumes the download."},
    "bb.active.ja": {
        "de": "Bereit: schlägt Ordner vor, wo es laut Modellwahl dran ist. Jeder Vorschlag wird "
              "eine Rückfrage.",
        "en": "Ready: suggests folders where the model choice puts it in charge. Every suggestion "
              "becomes a review.",
    },
    "bb.active.version": {
        "de": "Schlägt nicht vor: Geladen ist Version {have}, dieses PollySort braucht {need} — "
              "'beenara big laden' holt sie.",
        "en": "Not suggesting: version {have} is downloaded, this PollySort needs {need} — "
              "'beenara big pull' fetches it.",
    },
    "bb.active.laufzeit": {
        "de": "Schlägt noch nicht vor: Die Laufzeit fehlt ({pakete}) — 'beenara big laden' "
              "installiert sie.",
        "en": "Not suggesting yet: the runtime is missing ({pakete}) — 'beenara big pull' "
              "installs it.",
    },
    "bb.gpu.ok": {"de": "Grafikkarte: {name} · {mb} MB", "en": "Graphics card: {name} · {mb} MB"},
    "bb.gpu.keine": {
        "de": "Keine NVIDIA-Grafikkarte gefunden — BeeNara Big braucht eine mit mindestens "
              "{need} MB. Auf der CPU rechnet es Sekunden bis Minuten je Dokument; wer das will, "
              "setzt {env}=1 und lädt dann.",
        "en": "No NVIDIA graphics card found — BeeNara Big needs one with at least {need} MB. "
              "On the CPU it takes seconds to minutes per document; to do that anyway, set "
              "{env}=1 and pull again.",
    },
    "bb.gpu.klein": {
        "de": "Die Grafikkarte hat {mb} MB — BeeNara Big braucht mindestens {need} MB. Wer es "
              "trotzdem versuchen will, setzt {env}=1 und lädt dann.",
        "en": "The graphics card has {mb} MB — BeeNara Big needs at least {need} MB. To try "
              "anyway, set {env}=1 and pull again.",
    },
    "bb.modus.auto": {
        "de": "Modellwahl: automatisch — BeeNara bei 3 bis 9 Ordnern, BeeNara Big bei mehr.",
        "en": "Model choice: automatic — BeeNara with 3 to 9 folders, BeeNara Big with more.",
    },
    "bb.modus.klein": {"de": "Modellwahl: nur BeeNara — BeeNara Big bleibt geladen, sortiert aber nicht.",
                       "en": "Model choice: BeeNara only — BeeNara Big stays downloaded but does not sort."},
    "bb.modus.big": {
        "de": "Modellwahl: nur BeeNara Big — auch bei 3 bis 9 Ordnern, dann nur Vorschläge.",
        "en": "Model choice: BeeNara Big only — also with 3 to 9 folders, then suggestions only.",
    },
    "bb.usage": {"de": "Nutzung: beenara big (Stand) · beenara big laden · beenara big entfernen · "
                       "beenara modell auto|klein|big",
                 "en": "Usage: beenara big (status) · beenara big pull · beenara big remove · "
                       "beenara model auto|small|big"},
    "bb.rt.installing": {"de": "Installiere die Laufzeit für BeeNara Big ({pakete}) — torch ist "
                               "groß, das dauert einige Minuten …",
                         "en": "Installing the runtime for BeeNara Big ({pakete}) — torch is large, "
                               "this takes a few minutes …"},
    "bb.rt.done": {"de": "Laufzeit installiert — BeeNara Big ist ab dem nächsten Lauf bereit.",
                   "en": "Runtime installed — BeeNara Big is ready from the next run."},
    "bb.run.loading": {"de": "BeeNara Big wird geladen (beim ersten Mal bis zu einer Minute) …",
                       "en": "Loading BeeNara Big (up to a minute the first time) …"},
    "bb.checking": {"de": "Frage Hugging Face nach {repo} …", "en": "Asking Hugging Face for {repo} …"},
    "bb.current": {"de": "Aktuell (Version {version}) · {path}",
                   "en": "Up to date (version {version}) · {path}"},
    "bb.start": {
        "de": "Lade {n} Datei(en), {mb} MB — Version {version} → {path}. "
              "Strg-C unterbricht, 'beenara big laden' setzt später fort.",
        "en": "Downloading {n} file(s), {mb} MB — version {version} → {path}. "
              "Ctrl-C pauses, 'beenara big pull' resumes later.",
    },
    "bb.progress": {"de": "BeeNara Big laden", "en": "Downloading BeeNara Big"},
    "bb.done": {"de": "Geladen und geprüft (Version {version}, {mb} MB) · {path}",
                "en": "Downloaded and verified (version {version}, {mb} MB) · {path}"},
    "bb.interrupted": {
        "de": "Unterbrochen — 'beenara big laden' setzt an derselben Stelle fort.",
        "en": "Paused — 'beenara big pull' resumes where it stopped.",
    },
    "bb.err.download": {
        "de": "Download fehlgeschlagen: {err} — 'beenara big laden' versucht es erneut und setzt fort.",
        "en": "Download failed: {err} — 'beenara big pull' tries again and resumes.",
    },
    "bb.remove.confirm": {
        "de": "BeeNara Big ({mb} MB, mit Basismodell) von diesem Rechner entfernen? [j/N]: ",
        "en": "Remove BeeNara Big ({mb} MB, with base model) from this computer? [y/N]: ",
    },
    "bb.remove.done": {"de": "BeeNara Big entfernt.", "en": "BeeNara Big removed."},
    "bb.remove.none": {"de": "BeeNara Big ist nicht geladen — nichts zu entfernen.",
                       "en": "BeeNara Big is not downloaded — nothing to remove."},
    # Dreistufige Entscheidung & Nacherfassung (Plan §8.3)
    "pl.quellen": {"de": "Entschieden: {teile}", "en": "Decided: {teile}"},
    "pl.quelle.gedaechtnis": {"de": "{n} aus dem Gedächtnis", "en": "{n} from memory"},
    "pl.quelle.beenara": {"de": "{n} von BeeNara", "en": "{n} by BeeNara"},
    "pl.quelle.nummer": {"de": "{n} per KI-Kurzentscheid", "en": "{n} by quick AI decision"},
    "pl.quelle.analyse": {"de": "{n} per Vollanalyse", "en": "{n} by full analysis"},
    "pl.quelle.heuristik": {"de": "{n} per Heuristik", "en": "{n} by heuristics"},
    "pl.drift_basis": {
        "de": "Das Gedächtnis nutzt seit diesem Update den Dokument-Anfang statt der "
              "KI-Zusammenfassung — so kann es schon vor der KI entscheiden. 'gedaechtnis neu' "
              "baut es einmal um (lokal, kostenlos); bis dahin entscheidet es nicht mit.",
        "en": "Since this update the memory uses the start of each document instead of the AI "
              "summary — that lets it decide before the AI does. 'memory rebuild' converts it "
              "once (local, free); until then it stays out of decisions.",
    },
    "nx.progress": {"de": "✍️ verfeinere …", "en": "✍️ refining …"},
    "nx.start": {
        "de": "Verfeinere Titel & Zusammenfassungen für {n} Datei(en) — sie liegen schon "
              "richtig. Strg-C überspringt.",
        "en": "Refining titles & summaries for {n} file(s) — they're already filed. "
              "Ctrl-C skips.",
    },
    "nx.done": {"de": "{n} Eintrag/Einträge verfeinert.", "en": "{n} entr(y/ies) refined."},
    "nx.left": {
        "de": "{n} bleiben vorgemerkt — der nächste Lauf macht weiter "
              "('nacherfassen aus' schaltet das ab).",
        "en": "{n} stay queued — the next run continues ('enrich off' turns this off).",
    },
    "nx.stopped": {"de": "Nacherfassung unterbrochen: {reason}",
                   "en": "Refining stopped: {reason}"},
    "nx.status": {"de": "Nacherfassung: {state} · {n} Eintrag/Einträge vorgemerkt",
                  "en": "Refining: {state} · {n} entr(y/ies) queued"},
    "nx.on": {"de": "an", "en": "on"},
    "nx.off": {"de": "aus", "en": "off"},
    "nx.set_on": {
        "de": "Nacherfassung an: Nach dem Sortieren verfeinert die KI Titel & Zusammenfassungen.",
        "en": "Refining on: after sorting, the AI refines titles & summaries.",
    },
    "nx.set_off": {
        "de": "Nacherfassung aus: Einträge behalten die schnelle Kurz-Erfassung. "
              "'nacherfassen jetzt' holt es jederzeit nach.",
        "en": "Refining off: entries keep the quick short capture. "
              "'enrich now' catches up any time.",
    },
    "nx.none": {"de": "Nichts vorgemerkt.", "en": "Nothing queued."},
    "nx.nollm": {
        "de": "Die Nacherfassung gibt es im Modus Lokal.",
        "en": "Refining is available in local mode.",
    },
    "help.d.enrich": {"de": "Titel/Zusammenfassung nach dem Sortieren per KI verfeinern",
                      "en": "Refine titles/summaries with AI after sorting"},
    # Modi (seit 2026-09-24 mit neuen Namen; intern offline/ollama/openrouter)
    "mode.offline": {"de": "Sparmodus", "en": "Low-power"},
    "mode.ollama": {"de": "Lokal", "en": "Local"},
    "mode.openrouter": {"de": "Cloud", "en": "Cloud"},
    "mode.current": {
        "de": "Modus: {name}. Wechseln: 'modus spar | lokal | cloud'.",
        "en": "Mode: {name}. Switch: 'mode low | local | cloud'.",
    },
    "mode.set": {"de": "Modus für dieses Projekt: {name}", "en": "Mode for this project: {name}"},
    "mode.nokey": {"de": "Kein Key → Modus unverändert.", "en": "No key → mode unchanged."},
    "mode.noollama": {"de": "Kein lokales Ollama erkannt — bitte Ollama starten.",
                      "en": "No local Ollama found — please start Ollama."},
    "mode.model_hint": {
        "de": "Dieses Projekt läuft im Modus {name}. 'modus cloud' aktiviert OpenRouter.",
        "en": "This project runs in {name} mode. 'mode cloud' enables OpenRouter.",
    },
    "pl.fallback": {
        "de": "KI wiederholt nicht erreichbar — der Rest des Laufs läuft im Sparmodus "
              "(Heuristik, kostenlos, kein Absturz).",
        "en": "AI repeatedly unreachable — the rest of this run uses low-power mode "
              "(heuristics, free, no crash).",
    },
    "doctor.prov.cloud": {"de": "Cloud · OpenRouter: {reason}", "en": "cloud · OpenRouter: {reason}"},
    # Doctor — liegt das Modell auf der Grafikkarte? (2026-09-24)
    "doctor.gpu": {
        "de": "GPU",
        "en": "GPU",
    },
    "doctor.gpu.full": {
        "de": "{model}: ganz auf der Grafikkarte · Kontext {ctx}",
        "en": "{model}: fully on the GPU · context {ctx}",
    },
    "doctor.gpu.cpu": {
        "de": "{model}: läuft auf der CPU (Kontext {ctx}) — normal ohne Grafikkarte; sonst 'ollama "
              "stop {model}', dann lädt es beim nächsten Lauf neu",
        "en": "{model}: running on the CPU (context {ctx}) — normal without a GPU; otherwise 'ollama "
              "stop {model}' and it reloads on the next run",
    },
    "doctor.gpu.partial": {
        "de": "{model}: {cpu} % auf der CPU (Kontext {ctx}) → deutlich langsamer. 'ollama stop "
              "{model}' — beim nächsten Lauf lädt PollySort es passend neu",
        "en": "{model}: {cpu} % on the CPU (context {ctx}) → much slower. 'ollama stop {model}' — "
              "PollySort reloads it properly on the next run",
    },
    "doctor.gpu.idle": {
        "de": "{model} ist gerade nicht geladen (lädt beim ersten Lauf)",
        "en": "{model} is not loaded right now (loads on the first run)",
    },
    # REPL — alle Befehlsmeldungen (2026-09-24)
    "r.preview.apply": {
        "de": "Änderungen jetzt anwenden? [J/n]: ",
        "en": "Apply the changes now? [Y/n]: ",
    },
    "r.watch.on": {
        "de": "Wache aktiv — {mode}, {action}. Strg-C beendet.",
        "en": "Watch active — {mode}, {action}. Ctrl-C stops.",
    },
    "r.reflect.title": {
        "de": "Vorgeschlagene Regeln",
        "en": "Proposed rules",
    },
    "r.reflect.confirm": {
        "de": "Diese Regeln in die Wachstafel ritzen? [J/n]: ",
        "en": "Save these rules? [Y/n]: ",
    },
    "r.rules.title": {
        "de": "Wachstafel — gelernte Projekt-Regeln",
        "en": "Rules — learned project rules",
    },
    "r.mem.cats": {
        "de": "Kategorien: {cats}",
        "en": "Categories: {cats}",
    },
    "r.mem.rebuild": {
        "de": "Baut das Gedächtnis für {n} Eintrag/Einträge mit dem aktuellen Modell ({model}) neu auf.",
        "en": "Rebuilds the memory for {n} entr(y/ies) with the current model ({model}).",
    },
    "r.model.set": {
        "de": "Nektar gewechselt — die Königin sammelt jetzt von: {model}",
        "en": "Model switched — now using: {model}",
    },
    "r.key.title": {
        "de": "Nektar-Quelle (OpenRouter-Schlüssel)",
        "en": "API key (OpenRouter)",
    },
    "r.key.usage": {
        "de": "Prüfen: 'schluessel test' · Erneuern: 'schluessel setzen' · Entfernen: 'schluessel "
              "entfernen'",
        "en": "Check: 'key test' · Renew: 'key set' · Remove: 'key remove'",
    },
    "r.key.testing": {
        "de": "Spähbiene prüft die Nektar-Quelle bei OpenRouter …",
        "en": "Checking the key with OpenRouter …",
    },
    "r.key.new": {
        "de": "Neue Nektar-Quelle ausweisen (ersetzt den bisherigen Schlüssel).",
        "en": "Enter a new key (replaces the current one).",
    },
    "r.key.testing_new": {
        "de": "Spähbiene prüft die neue Nektar-Quelle …",
        "en": "Checking the new key …",
    },
    "r.charter.building": {
        "de": "Baubienen schwärmen aus für die Wabe '{cat}' …",
        "en": "Builder bees set out for '{cat}' …",
    },
    "r.charter.built": {
        "de": "Bienenstock.md gebaut → {path}",
        "en": "Bienenstock.md built → {path}",
    },
    "r.cal.title": {
        "de": "Bienen-Kalender",
        "en": "Calendar",
    },
    "r.swarm.title": {
        "de": "Der Schwarm",
        "en": "The swarm",
    },
    "r.swarm.queen": {
        "de": "👑 Königin orchestriert {waben} Wabe(n) · {docs} Dokument(e)",
        "en": "👑 The queen coordinates {waben} categor(y/ies) · {docs} document(s)",
    },
    "r.swarm.scouts": {
        "de": "   🐝 Spurbienen:   {assigned} einsortiert · {review} Rückfrage(n) · {errors} Fehler",
        "en": "   🐝 Scout bees:   {assigned} filed · {review} to review · {errors} error(s)",
    },
    "r.swarm.builders": {
        "de": "   🛠️ Baubienen:    {n} Projekt-Charter (Stufe 2)",
        "en": "   🛠️ Builder bees: {n} project charter(s) (stage 2)",
    },
    "r.swarm.guards": {
        "de": "   🔔 Wächterbienen: {n} Deadline(s) in ≤ 7 Tagen",
        "en": "   🔔 Guard bees:   {n} deadline(s) within 7 days",
    },
    "r.routes.title": {
        "de": "Flugrouten der Wächterbienen",
        "en": "Notification routes",
    },
    "r.routes.local": {
        "de": "🔒 Zugangsdaten bleiben lokal — kein LLM sieht sie je. 'flugrouten test' prüft.",
        "en": "🔒 Credentials stay local — no LLM ever sees them. 'routes test' checks.",
    },
    "r.routes.testing": {
        "de": "Wächterbienen fliegen zum Testflug aus …",
        "en": "Guard bees are out on a test flight …",
    },
    "r.routes.setup_title": {
        "de": "Flugrouten ausweisen",
        "en": "Set up notification routes",
    },
    "r.routes.where": {
        "de": "Wohin sollen die Wächterbienen bei fälligen Deadlines fliegen?",
        "en": "Where should reminders go when deadlines are due?",
    },
    "r.routes.local2": {
        "de": "🔒 Alle Zugangsdaten bleiben strikt lokal — kein LLM bekommt sie je zu sehen.",
        "en": "🔒 All credentials stay strictly local — no LLM ever sees them.",
    },
    "r.routes.ask_discord": {
        "de": "  🎮 Discord-Flugroute einrichten? [j/N]: ",
        "en": "  🎮 Set up Discord? [y/N]: ",
    },
    "r.routes.ask_email": {
        "de": "  📧 E-Mail-Flugroute einrichten? [j/N]: ",
        "en": "  📧 Set up e-mail? [y/N]: ",
    },
    "r.routes.ask_cal": {
        "de": "  📅 Kalender-Flugroute anlegen? (Struktur, Sync folgt) [j/N]: ",
        "en": "  📅 Add a calendar route? (structure only, sync comes later) [y/N]: ",
    },
    "r.routes.saved": {
        "de": "Flugrouten gesichert (nur lokal, chmod 600). Testflug: 'flugrouten test'.",
        "en": "Routes saved (local only, chmod 600). Test: 'routes test'.",
    },
    "r.dup.title": {
        "de": "{n} Dublette(n)",
        "en": "{n} duplicate(s)",
    },
    "r.dup.moved": {
        "de": "{n} Dublette(n) in der Quarantäne — endgültig löschen erst mit 'leeren'.",
        "en": "{n} duplicate(s) in quarantine — delete for good only with 'empty'.",
    },
    "r.trash.deleted": {
        "de": "{n} Datei(en) endgültig gelöscht.",
        "en": "{n} file(s) deleted for good.",
    },
    "r.undo.ok": {
        "de": "Rückgängig: {name} → {folder} (wieder offen)",
        "en": "Undone: {name} → {folder} (open again)",
    },
    "r.projects.nav": {
        "de": "Wechseln mit:  wechsel <nr>   ·   Neu:  neu <pfad>",
        "en": "Switch with:  switch <n>   ·   New:  new <path>",
    },
    "r.key.saved_short": {
        "de": "     Key gespeichert (chmod 600).",
        "en": "     Key saved (chmod 600).",
    },
    "r.preview.none": {
        "de": "Nichts verändert — die Vorschau bleibt eine Vorschau.",
        "en": "Nothing changed — the preview stays a preview.",
    },
    "r.import.usage": {
        "de": "Nutzung: importiere <ordner>",
        "en": "Usage: import <folder>",
    },
    "r.import.nofolder": {
        "de": "Kein Ordner: {path}",
        "en": "Not a folder: {path}",
    },
    "r.scan.learned": {
        "de": "{n} manuelle Verschiebung(en) als Korrektur verstanden — die Königin lernt daraus.",
        "en": "{n} manual move(s) understood as corrections — the queen learns from them.",
    },
    "r.sub.title": {
        "de": "Dynamische Unterordner",
        "en": "Dynamic subfolders",
    },
    "r.sub.removed": {
        "de": "Unterordner für '{cat}' entfernt.",
        "en": "Subfolders for '{cat}' removed.",
    },
    "r.sub.set": {
        "de": "'{cat}' → {pattern}  (greift beim nächsten Sortieren)",
        "en": "'{cat}' → {pattern}  (applies from the next sort)",
    },
    "r.cycle.rules": {
        "de": "Spurbienen fliegen aus (unter Beachtung der gelernten Wachstafel-Regeln) …",
        "en": "Scout bees are out (following the learned rules) …",
    },
    "r.cycle.keyhint": {
        "de": "Falls der OpenRouter-Schlüssel abgelaufen ist: 'schluessel test' prüft ihn, "
              "'schluessel setzen' erneuert ihn.",
        "en": "If the OpenRouter key has expired: 'key test' checks it, 'key set' renews it.",
    },
    "r.search.usage": {
        "de": "Nutzung: suche <wort>",
        "en": "Usage: search <word>",
    },
    "r.assign.usage": {
        "de": "Nutzung: zuordnen <id> <kategorie>",
        "en": "Usage: assign <id> <category>",
    },
    "r.noentry": {
        "de": "Kein Eintrag '{id}'.",
        "en": "No entry '{id}'.",
    },
    "r.assign.ok": {
        "de": "{id}: {old} → {new} ✓ (Gedächtnis lernt)",
        "en": "{id}: {old} → {new} ✓ (memory learns)",
    },
    "r.reflect.working": {
        "de": "Die Königin studiert die Korrekturen und ritzt neue Regeln in die Wachstafel …",
        "en": "The queen studies your corrections and derives new rules …",
    },
    "r.reflect.saved_n": {
        "de": "Wachstafel aktualisiert — {n} gelernte Regel(n). Ansehen: 'wachstafel'.",
        "en": "Rules updated — {n} learned rule(s). View: 'rules'.",
    },
    "r.reflect.few": {
        "de": "Noch zu wenig Nektar-Feedback für neue Regeln — korrigiere weiter mit 'zuordnen'.",
        "en": "Not enough feedback for new rules yet — keep correcting with 'assign'.",
    },
    "r.reflect.rule": {
        "de": "    • [honey]{kw}[/honey] → Wabe [honey]{kat}[/honey]  _(aus {cnt} Korrektur(en){alt})_",
        "en": "• [honey]{kw}[/honey] → category [honey]{kat}[/honey]  _(from {cnt} "
              "correction(s){alt})_",
    },
    "r.reflect.saved": {
        "de": "Wachstafel aktualisiert — {n} Regel(n). Ansehen: 'wachstafel'.",
        "en": "Rules updated — {n} rule(s). View: 'rules'.",
    },
    "r.reflect.discarded": {
        "de": "Verworfen — die Wachstafel bleibt unverändert.",
        "en": "Discarded — the rules stay unchanged.",
    },
    "r.rules.cleared": {
        "de": "Wachstafel abgewischt — die gelernten Regeln sind verworfen.",
        "en": "Rules cleared — the learned rules are discarded.",
    },
    "r.rules.none": {
        "de": "Noch keine Wachstafel. 'reflektiere' ritzt Regeln aus deinen Korrekturen ('zuordnen').",
        "en": "No rules yet. 'reflect' derives rules from your corrections ('assign').",
    },
    "r.person.usage": {
        "de": "Nutzung: person <name> <kategorie,kategorie>",
        "en": "Usage: person <name> <category,category>",
    },
    "r.mem.drift": {
        "de": "Embedding-Modell hat sich geändert (Gedächtnis: {drift}). Alte Vektoren matchen nicht "
              "mehr — 'gedaechtnis neu' baut es neu auf.",
        "en": "The embedding model has changed (memory: {drift}). Old vectors no longer match — "
              "'memory rebuild' rebuilds it.",
    },
    "r.mem.approve": {
        "de": "Übernehmen mit:  gedaechtnis approve <slug>",
        "en": "Accept with:  memory approve <slug>",
    },
    "r.mem.empty": {
        "de": "Kein einsortierter Bestand — nichts neu einzubetten.",
        "en": "Nothing filed yet — nothing to re-embed.",
    },
    "r.mem.cost": {
        "de": "Das erzeugt pro Eintrag einen (günstigen) Embedding-Call.",
        "en": "This makes one (cheap) embedding call per entry.",
    },
    "r.mem.confirm": {
        "de": "Jetzt neu aufbauen? [J/n]: ",
        "en": "Rebuild now? [Y/n]: ",
    },
    "r.model.title": {
        "de": "Nektar-Sorten (OpenRouter-Modelle)",
        "en": "Models (OpenRouter)",
    },
    "r.model.any": {
        "de": "Auch beliebige IDs möglich:  modell <provider/modell-id>",
        "en": "Any ID works too:  model <provider/model-id>",
    },
    "r.model.current": {
        "de": "Aktuelle Nektar-Sorte: {model}",
        "en": "Current model: {model}",
    },
    "r.model.usage": {
        "de": "Wechseln:  modell <name|id>   ·   Sorten:  modell liste",
        "en": "Switch:  model <name|id>   ·   List:  model list",
    },
    "r.key.env": {
        "de": "Aus Umgebungsvariable OPENROUTER_API_KEY ({masked}) — hat Vorrang.",
        "en": "From environment variable OPENROUTER_API_KEY ({masked}) — takes precedence.",
    },
    "r.key.none_test": {
        "de": "Kein Schlüssel hinterlegt. 'schluessel setzen' weist einen aus.",
        "en": "No key stored. 'key set' adds one.",
    },
    "r.key.valid": {
        "de": "Nektar-Quelle offen — der Schlüssel ist gültig. 🍯",
        "en": "Key accepted — it's valid. 🍯",
    },
    "r.key.invalid": {
        "de": "Schlüssel {reason} — erneuern mit 'schluessel setzen'.",
        "en": "Key {reason} — renew with 'key set'.",
    },
    "r.key.env_note": {
        "de": "Hinweis: OPENROUTER_API_KEY (Umgebungsvariable) hat Vorrang vor dem gespeicherten "
              "Schlüssel und wird nicht überschrieben.",
        "en": "Note: OPENROUTER_API_KEY (environment variable) takes precedence over the stored key "
              "and is not overwritten.",
    },
    "r.key.unchanged": {
        "de": "Abgebrochen — Schlüssel unverändert.",
        "en": "Cancelled — key unchanged.",
    },
    "r.key.saved": {
        "de": "Schlüssel gültig & gespeichert ({path}, chmod 600).",
        "en": "Key valid & saved ({path}, chmod 600).",
    },
    "r.key.new_invalid": {
        "de": "Der neue Schlüssel {reason}.",
        "en": "The new key {reason}.",
    },
    "r.key.save_anyway": {
        "de": "     Trotzdem speichern (ungeprüft)? [j/N]: ",
        "en": "     Save anyway (unchecked)? [y/N]: ",
    },
    "r.key.none": {
        "de": "Kein Schlüssel hinterlegt.",
        "en": "No key stored.",
    },
    "r.key.remove_confirm": {
        "de": "Schlüssel wirklich entfernen? (Cloud-Projekte fallen in den Sparmodus zurück) [j/N]: ",
        "en": "     Really remove the key? (cloud projects fall back to low-power mode) [y/N]: ",
    },
    "r.cancelled": {
        "de": "Abgebrochen.",
        "en": "Cancelled.",
    },
    "r.key.env_still": {
        "de": "Achtung: OPENROUTER_API_KEY (Umgebungsvariable) ist weiter gesetzt und aktiv — im "
              "Terminal/Profil entfernen, falls gewünscht.",
        "en": "Heads-up: OPENROUTER_API_KEY (environment variable) is still set and active — remove "
              "it from your terminal/profile if you want.",
    },
    "r.key.removed": {
        "de": "Schlüssel entfernt — Cloud-Projekte laufen jetzt im Sparmodus (Heuristik).",
        "en": "Key removed — cloud projects now run in low-power mode (heuristics).",
    },
    "r.theme.auto_set": {
        "de": "Thema: Automatik — tagsüber Dunkel, abends Hell. Jetzt aktiv: {name}. 🎨",
        "en": "Theme: automatic — dark by day, light in the evening. Active now: {name}. 🎨",
    },
    "r.theme.set": {
        "de": "Thema gewechselt — {name}-Modus. 🎨",
        "en": "Theme switched — {name} mode. 🎨",
    },
    "r.view.tty": {
        "de": "Hinweis: die statische Ansicht wirkt nur im echten Terminal (bei Pipe/CI bleibt es "
              "beim Log).",
        "en": "Note: the static view only works in a real terminal (piped/CI output stays a log).",
    },
    "r.charter.which": {
        "de": "Welche Wabe zum Projekt ausbauen?",
        "en": "Which category should become a project?",
    },
    "r.charter.cancel": {
        "de": "Abgebrochen — keine Wabe gewählt.",
        "en": "Cancelled — no category chosen.",
    },
    "r.charter.unknown": {
        "de": "'{cat}' ist (noch) keine bekannte Wabe — baue trotzdem.",
        "en": "'{cat}' isn't a known category (yet) — building anyway.",
    },
    "r.charter.tasks": {
        "de": "{n} offene Aufgabe(n) in der Wabe:",
        "en": "{n} open task(s) in this category:",
    },
    "r.charter.done": {
        "de": "Wabe komplett — nichts bleibt offen!",
        "en": "Category complete — nothing left open!",
    },
    "r.charter.deadline": {
        "de": "Deadline im Bienen-Kalender vermerkt: {date}",
        "en": "Deadline noted in the calendar: {date}",
    },
    "r.cal.empty": {
        "de": "Der Bienen-Kalender ist leer. Deadlines setzt 'wabenbau'.",
        "en": "The calendar is empty. 'charter' sets deadlines.",
    },
    "r.cal.nothing": {
        "de": "Nichts Dringendes in den nächsten 7 Tagen. 🍯",
        "en": "Nothing urgent in the next 7 days. 🍯",
    },
    "r.swarm.foragers": {
        "de": "   🍯 Sammelbienen (gelernte Ablage-Orte):",
        "en": "   🍯 Forager bees (learned filing places):",
    },
    "r.routes.none": {
        "de": "Noch keine Flugrouten ausgewiesen. 'flugrouten setup' richtet welche ein.",
        "en": "No notification routes yet. 'routes setup' sets some up.",
    },
    "r.routes.discord": {
        "de": "   🎮 Discord: aktiv · Channel {channel} · Token {token}",
        "en": "   🎮 Discord: active · channel {channel} · token {token}",
    },
    "r.routes.email": {
        "de": "   📧 E-Mail: aktiv · {addr} · {provider} ({host}:{port}) · Pass {pw}",
        "en": "   📧 E-mail: active · {addr} · {provider} ({host}:{port}) · pass {pw}",
    },
    "r.routes.calendar": {
        "de": "   📅 Kalender: vorgemerkt ({kind})",
        "en": "   📅 Calendar: planned ({kind})",
    },
    "r.routes.none_active": {
        "de": "Keine aktiven Flugrouten. 'flugrouten setup' weist welche aus.",
        "en": "No active notification routes. 'routes setup' adds some.",
    },
    "r.routes.providers": {
        "de": "      Provider:  [1] Gmail   [2] Outlook/Hotmail   [3] Benutzerdefiniert",
        "en": "      Provider:  [1] Gmail   [2] Outlook/Hotmail   [3] Custom",
    },
    "r.routes.cal_ok": {
        "de": "Kalender-Flugroute vorgemerkt.",
        "en": "Calendar route noted.",
    },
    "r.trash.moved": {
        "de": "→ Quarantäne (nicht gelöscht): {name}",
        "en": "→ quarantine (not deleted): {name}",
    },
    "r.restore.ok": {
        "de": "Zurück im Ordner: {name}",
        "en": "Back in its folder: {name}",
    },
    "r.restore.none": {
        "de": "Nichts zurückzuholen.",
        "en": "Nothing to restore.",
    },
    "r.dup.none": {
        "de": "Keine Dubletten im Eingang. ✨",
        "en": "No duplicates in the inbox. ✨",
    },
    "r.dup.row": {
        "de": "    🛡️ {name}  — Original: {orig} ({cat})",
        "en": "    🛡️ {name}  — original: {orig} ({cat})",
    },
    "r.dup.hint": {
        "de": "'dubletten aufraeumen' verschiebt sie in die Quarantäne (papierkorb — nichts wird "
              "gelöscht).",
        "en": "'duplicates cleanup' moves them to quarantine (trash — nothing is deleted).",
    },
    "r.dup.confirm": {
        "de": "{n} Dublette(n) in die Quarantäne verschieben? [j/N]: ",
        "en": "Move {n} duplicate(s) to quarantine? [y/N]: ",
    },
    "r.trash.empty": {
        "de": "Quarantäne ist leer.",
        "en": "Quarantine is empty.",
    },
    "r.undo.none": {
        "de": "Nichts rückgängig zu machen.",
        "en": "Nothing to undo.",
    },
    "r.projects.notfound": {
        "de": "Projekt '{name}' nicht gefunden. 'projekte' zeigt die Liste.",
        "en": "Project '{name}' not found. 'projects' shows the list.",
    },
    "r.projects.none": {
        "de": "Noch keine Projekte. 'neu' legt eins an.",
        "en": "No projects yet. 'new' creates one.",
    },
    "r.nohits": {
        "de": "Keine Treffer.",
        "en": "No matches.",
    },
    "r.watch.stop": {
        "de": "Wache beendet.",
        "en": "Watch stopped.",
    },
    "r.rules.nothing": {
        "de": "Es gibt noch keine Wachstafel zum Abwischen.",
        "en": "There are no rules to clear yet.",
    },
    "r.rules.confirm": {
        "de": "Alle gelernten Regeln wirklich verwerfen? [j/N]: ",
        "en": "Really discard all learned rules? [y/N]: ",
    },
    "r.rules.kept": {
        "de": "Abgebrochen — die Wachstafel bleibt.",
        "en": "Cancelled — the rules stay.",
    },
    "r.mem.noprop": {
        "de": "Kein Vorschlag '{slug}'.",
        "en": "No proposal '{slug}'.",
    },
    "r.key.stored": {
        "de": "Hinterlegt: {masked}   ({path})",
        "en": "Stored: {masked}   ({path})",
    },
    "r.key.none_status": {
        "de": "Kein Schlüssel hinterlegt — Sparmodus und Lokal gehen, Cloud nicht.",
        "en": "No key stored — low-power and local mode work, cloud mode doesn't.",
    },
    "r.key.prompt_new": {
        "de": "     🔑 Neuer OpenRouter-API-Key (leer = abbrechen): ",
        "en": "     🔑 New OpenRouter API key (empty = cancel): ",
    },
    "r.key.saved_unchecked": {
        "de": "Gespeichert — bei Bedarf 'schluessel test'.",
        "en": "Saved — run 'key test' if needed.",
    },
    "r.key.not_saved": {
        "de": "Nicht gespeichert — bisheriger Schlüssel bleibt.",
        "en": "Not saved — the current key stays.",
    },
    "r.theme.auto_now": {
        "de": "Thema: Automatik (tags dunkel, abends hell) — gerade {name}. Wechseln: 'thema dunkel | "
              "hell | auto'.",
        "en": "Theme: automatic (dark by day, light in the evening) — currently {name}. Switch: "
              "'theme dark | light | auto'.",
    },
    "r.theme.now": {
        "de": "Thema: {name}-Modus. Wechseln: 'thema dunkel | hell | auto'.",
        "en": "Theme: {name} mode. Switch: 'theme dark | light | auto'.",
    },
    "r.view.now": {
        "de": "Aktuelle Ansicht: {name}. Wechseln: 'ansicht statisch' | 'ansicht log'.",
        "en": "Current view: {name}. Switch: 'view static' | 'view log'.",
    },
    "r.charter.none": {
        "de": "Noch keine Waben da — erst 'sortiere'.",
        "en": "No categories yet — run 'sort' first.",
    },
    "r.cal.noroutes": {
        "de": "Keine Flugrouten aktiv — 'flugrouten setup' schaltet den Versand frei.",
        "en": "No notification routes active — 'routes setup' enables sending.",
    },
    "r.routes.test_ok": {
        "de": "Wächterbienen haben die {target} erfolgreich informiert!",
        "en": "The guard bees reached {target}!",
    },
    "r.routes.discord_ok": {
        "de": "Discord-Flugroute ausgewiesen.",
        "en": "Discord route set up.",
    },
    "r.routes.discord_skip": {
        "de": "Unvollständig — Discord übersprungen.",
        "en": "Incomplete — Discord skipped.",
    },
    "r.routes.email_ok": {
        "de": "E-Mail-Flugroute ausgewiesen ({provider}, {host}:{port}).",
        "en": "E-mail route set up ({provider}, {host}:{port}).",
    },
    "r.routes.email_skip": {
        "de": "Unvollständig — E-Mail übersprungen.",
        "en": "Incomplete — e-mail skipped.",
    },
    "r.key.save_failed": {
        "de": "Key konnte nicht gespeichert werden: {err}",
        "en": "Could not save the key: {err}",
    },
    "r.key.prompt": {
        "de": "     🔑 OpenRouter API-Key (leer = abbrechen): ",
        "en": "     🔑 OpenRouter API key (empty = cancel): ",
    },
    "r.aborted": {
        "de": "Abgebrochen — nichts ausgeführt.",
        "en": "Cancelled — nothing was done.",
    },
    "r.failed": {
        "de": "Befehl fehlgeschlagen: {err}",
        "en": "Command failed: {err}",
    },
    "r.number_or_name": {
        "de": "     Nummer oder Name: ",
        "en": "     Number or name: ",
    },
    "r.routes.off": {
        "de": "Alle Flugrouten stillgelegt — die Wächterbienen bleiben im Stock.",
        "en": "All notification routes switched off — the guard bees stay home.",
    },
    "r.routes.blocked": {
        "de": "Flugroute {name} blockiert: {err}",
        "en": "Route {name} blocked: {err}",
    },
    "r.routes.token": {
        "de": "      🔑 Discord-Bot-Token: ",
        "en": "      🔑 Discord bot token: ",
    },
    "r.routes.channel": {
        "de": "      #  Channel-ID des Main-Channels: ",
        "en": "      #  Channel ID of the main channel: ",
    },
    "r.routes.address": {
        "de": "      ✉️  E-Mail-Adresse: ",
        "en": "      ✉️  E-mail address: ",
    },
    "r.routes.password": {
        "de": "      🔒 Passwort / App-Passwort: ",
        "en": "      🔒 Password / app password: ",
    },
    "r.routes.recipient": {
        "de": "      📮 Empfänger [leer = an dich selbst]: ",
        "en": "      📮 Recipient [empty = yourself]: ",
    },
    "r.watch.sorting": {
        "de": "[{ts}] {n} neue Datei(en) → sortiere …",
        "en": "[{ts}] {n} new file(s) → sorting …",
    },
    "r.watch.new": {
        "de": "[{ts}] {n} neue Datei(en) im Eingang — 'sortiere' zum Einräumen",
        "en": "[{ts}] {n} new file(s) in the inbox — 'sort' files them",
    },
    "r.routes.choice": {
        "de": "      Wahl [1]: ",
        "en": "      Choice [1]: ",
    },
    "r.routes.smtp": {
        "de": "      SMTP-Server: ",
        "en": "      SMTP server: ",
    },
    "r.projects.pick": {
        "de": "  Nummer, Name oder Pfad: ",
        "en": "  Number, name or path: ",
    },
    "r.watch.move": {
        "de": "sortiere sofort",
        "en": "sorting right away",
    },
    "r.watch.notify": {
        "de": "melde",
        "en": "announcing",
    },
    "r.watch.realtime": {
        "de": "Echtzeit (watchdog)",
        "en": "real time (watchdog)",
    },
    "r.watch.poll": {
        "de": "Poll alle {s}s",
        "en": "polling every {s}s",
    },
    "r.reflect.instead": {
        "de": "  (statt „{alt}“)",
        "en": "  (instead of “{alt}”)",
    },
    "r.mem.rebuilt": {
        "de": "Gedächtnis neu aufgebaut: {ok} eingebettet",
        "en": "Memory rebuilt: {ok} embedded",
    },
    "r.mem.skipped": {
        "de": ", {n} übersprungen",
        "en": ", {n} skipped",
    },
    "theme.dark": {
        "de": "Dunkel",
        "en": "Dark",
    },
    "theme.light": {
        "de": "Hell",
        "en": "Light",
    },
    "r.view.static": {
        "de": "statisch (kein Scrolling)",
        "en": "static (no scrolling)",
    },
    "r.view.log": {
        "de": "Log (scrollend)",
        "en": "log (scrolling)",
    },
    "r.view.set_static": {
        "de": "Ansicht: statisch — die Konsole zeichnet sich selbst neu.",
        "en": "View: static — the console redraws itself.",
    },
    "r.view.set_log": {
        "de": "Ansicht: klassisches Log (scrollend).",
        "en": "View: classic log (scrolling).",
    },
    "r.cal.in": {
        "de": "in {n} T",
        "en": "in {n} d",
    },
    "r.cal.overdue": {
        "de": "{n} T überfällig",
        "en": "{n} d overdue",
    },
    "r.trash.confirm": {
        "de": "Wirklich {n} Datei(en) endgültig löschen? Tippe \"{n}\": ",
        "en": "Really delete {n} file(s) for good? Type \"{n}\": ",
    },
    "r.col.cat": {
        "de": "kategorie",
        "en": "category",
    },
    "r.col.title": {
        "de": "titel",
        "en": "title",
    },
    "r.col.file": {
        "de": "datei",
        "en": "file",
    },
    "r.unsorted": {
        "de": "unsortiert",
        "en": "unsorted",
    },
    "r.sub.none": {
        "de": "Keine dynamischen Unterordner gesetzt. Beispiel: unterordner rechnungen {pattern}",
        "en": "No dynamic subfolders set. Example: subfolder invoices {pattern}",
    },
    "r.sub.usage": {
        "de": "Nutzung: unterordner <kategorie> <muster|aus>  (z. B. rechnungen {pattern})",
        "en": "Usage: subfolder <category> <pattern|off>  (e.g. invoices {pattern})",
    },
    # Modell-Liste & Gedächtnis-Vorschläge
    "r.model.active": {
        "de": "  ◀ aktiv",
        "en": "  ◀ active",
    },
    "refl.new": {
        "de": "🐣 Neue Kategorie '{name}' aus {n} ähnlichen Dokumenten (Stichworte: {kw})",
        "en": "🐣 New category '{name}' from {n} similar documents (keywords: {kw})",
    },
    "refl.merge": {
        "de": "🔗 Zusammenführen: '{src}' → '{dst}' (Ähnlichkeit {sim})",
        "en": "🔗 Merge '{src}' → '{dst}' (similarity {sim})",
    },
    # Rückfragen, Daemon, Wächter-, Bau-, Sammelbienen, Empfehlungen
    "rv.none": {
        "de": "Keine offenen Rückfragen. 🎉",
        "en": "No open reviews. 🎉",
    },
    "rv.title": {
        "de": "{n} offene Rückfrage(n)",
        "en": "{n} open review(s)",
    },
    "rv.titel": {
        "de": "    Titel: {title}",
        "en": "    Title: {title}",
    },
    "rv.funktion": {
        "de": "    Funktion: {f}",
        "en": "    Purpose: {f}",
    },
    "rv.vorschlag": {
        "de": "    Vorschlag: {cat}   |   bekannt: {known}",
        "en": "    Suggestion: {cat}   |   known: {known}",
    },
    "rv.prompt": {
        "de": "    Kategorie eingeben ([s]kip, [v]iew, [q]uit): ",
        "en": "    Enter a category ([s]kip, [v]iew, [q]uit): ",
    },
    "rv.prompt2": {
        "de": "    Kategorie eingeben ([s]kip): ",
        "en": "    Enter a category ([s]kip): ",
    },
    "rv.done": {
        "de": "{n} Rückfrage(n) beantwortet.",
        "en": "{n} review(s) answered.",
    },
    "dm.start": {
        "de": "Königin erwacht – Daemon läuft. (Strg-C beendet)",
        "en": "The queen is awake — daemon running. (Ctrl-C stops)",
    },
    "dm.watchdog": {
        "de": "Flugloch-Wache aktiv (watchdog + Fallback-Poll).",
        "en": "Entrance watch active (watchdog + fallback poll).",
    },
    "dm.poll": {
        "de": "watchdog nicht verfügbar → reiner Poll-Modus.",
        "en": "watchdog unavailable → polling only.",
    },
    "dm.next": {
        "de": "Nächster Auto-Sweep in {m} min",
        "en": "Next auto-sweep in {m} min",
    },
    "dm.stop": {
        "de": "Daemon beendet.",
        "en": "Daemon stopped.",
    },
    "dm.failed": {
        "de": "Daemon-Schritt fehlgeschlagen: {err}",
        "en": "Daemon step failed: {err}",
    },
    "wb.due": {
        "de": "Wächterbienen summen: '{title}' ist in {n} Tag(en) fällig ({date}).",
        "en": "Guard bees buzzing: '{title}' is due in {n} day(s) ({date}).",
    },
    "wb.overdue": {
        "de": "Wächterbienen summen: '{title}' ist seit {n} Tag(en) überfällig ({date}).",
        "en": "Guard bees buzzing: '{title}' is {n} day(s) overdue ({date}).",
    },
    "wb.when_overdue": {
        "de": "überfällig",
        "en": "overdue",
    },
    "wb.when_in": {
        "de": "in {n} Tagen",
        "en": "in {n} days",
    },
    "wb.mail": {
        "de": "Fällig am {date} ({when}).",
        "en": "Due on {date} ({when}).",
    },
    "wb.back": {
        "de": "Wächterbiene kehrt vom {name}-Flug zurück: {err}",
        "en": "Guard bee back from the {name} flight: {err}",
    },
    "wb.test_title": {
        "de": "Bienentanz-Testflug",
        "en": "Bee-dance test flight",
    },
    "wb.test_text": {
        "de": "🐝 Hallo vom Bienenstock! Diese Flugroute steht bereit.",
        "en": "🐝 Hello from the hive! This route is ready.",
    },
    "sw.checking": {
        "de": "Prüfe den ganzen Ordner auf manuelle Änderungen …",
        "en": "Checking the whole folder for manual changes …",
    },
    "sw.title": {
        "de": "Sweep-Bericht",
        "en": "Sweep report",
    },
    "sw.line": {
        "de": "📋  🆕 {new} neu · ✏️ {changed} geändert · 🔀 {moved} verschoben · 🗑️ {missing} "
              "verschwunden · ⚠️ {errors} Fehler",
        "en": "📋  🆕 {new} new · ✏️ {changed} changed · 🔀 {moved} moved · 🗑️ {missing} gone · ⚠️ "
              "{errors} error(s)",
    },
    "sw.learned": {
        "de": " · 🧠 {n} gelernt",
        "en": " · 🧠 {n} learned",
    },
    "sw.learned_one": {
        "de": "🧠 gelernt: {name}  {old} → {new}",
        "en": "🧠 learned: {name}  {old} → {new}",
    },
    "sw.safe": {
        "de": "Nichts wurde von uns gelöscht.",
        "en": "Nothing was deleted by us.",
    },
    "sw.calls": {
        "de": " {n} Analyse(n) für neue Dateien.",
        "en": " {n} analysis/analyses for new files.",
    },
    "sw.calls_cost": {
        "de": " {n} KI-Anfrage(n) · ~{cost} €.",
        "en": " {n} AI request(s) · ~{cost} €.",
    },
    "bb.synced": {
        "de": "Baubienen haben den Pollen-Kalender synchronisiert ({n} Termin(e) → kalender.ics).",
        "en": "Builder bees synced the calendar ({n} date(s) → kalender.ics).",
    },
    "bb.nobody": {
        "de": "noch niemand zuständig",
        "en": "nobody responsible yet",
    },
    "bb.building": {
        "de": "Baubienen bauen die Wabe '{cat}' — Stakeholder: {who}",
        "en": "Builder bees are building '{cat}' — stakeholders: {who}",
    },
    "bb.who": {
        "de": "    🐝 Wer ist zuständig? (Namen, kommagetrennt, leer=offen): ",
        "en": "    🐝 Who is responsible? (names, comma-separated, empty = open): ",
    },
    "bb.goal": {
        "de": "    🎯 Projektziel (1 Satz, leer=später): ",
        "en": "    🎯 Project goal (1 sentence, empty = later): ",
    },
    "bb.deadline": {
        "de": "    📅 Deadline (JJJJ-MM-TT, leer=keine): ",
        "en": "    📅 Deadline (YYYY-MM-DD, empty = none): ",
    },
    "rec.para": {
        "de": "Nach Lebenszyklus gruppieren: Abgeschlossenes → Archiv, Laufendes → Projekte.",
        "en": "Group by life cycle: finished → Archive, ongoing → Projects.",
    },
    "rec.johnny": {
        "de": "Nummerierte Bereiche AC.ID (max. 10×10) — flache, eindeutige Ordner-IDs.",
        "en": "Numbered areas AC.ID (max. 10×10) — flat, unique folder IDs.",
    },
    "rec.dewey": {
        "de": "Themenbasierte Dezimalklassen — wie in einer Bibliothek.",
        "en": "Topic-based decimal classes — like in a library.",
    },
    "rec.title": {
        "de": "🍯 Empfehlungen (Strategie: {name})",
        "en": "🍯 Recommendations (strategy: {name})",
    },
    "rec.preset": {
        "de": "▸ Vorlage: {idea}",
        "en": "▸ Preset: {idea}",
    },
    "rec.review": {
        "de": "▸ Hinweis: {n} Einträge unter der Schwelle → 'rueckfragen'",
        "en": "▸ Hint: {n} entries below the threshold → 'review'",
    },
    "rec.errors": {
        "de": "▸ Hinweis: {n} Fehler-Einträge → 'liste error'",
        "en": "▸ Hint: {n} error entries → 'list error'",
    },
    "rec.unassigned": {
        "de": "▸ Hinweis: {n} Dokumente ohne passende Kategorie → neue Kategorie prüfen ('gedaechtnis')",
        "en": "▸ Hint: {n} documents without a fitting category → check for a new category ('memory')",
    },
    "rec.dups": {
        "de": "▸ Hinweis: {n} Dublette(n) gefunden → 'dubletten'",
        "en": "▸ Hint: {n} duplicate(s) found → 'duplicates'",
    },
    "rec.para_top": {
        "de": "▸ Vorlage (PARA): '{top}' ist die größte Kategorie ({n}) — Abgeschlossenes ins Archiv "
              "verschieben?",
        "en": "▸ Preset (PARA): '{top}' is the biggest category ({n}) — move finished items to the "
              "archive?",
    },
    # analysiere <id> (F2)
    "help.d.reanalyze": {
        "de": "Eintrag neu analysieren — fragt, bevor umsortiert wird",
        "en": "Re-analyse an entry — asks before re-filing",
    },
    "r.reana.usage": {
        "de": "Nutzung: analysiere <id>  (die id zeigt 'liste')",
        "en": "Usage: reanalyze <id>  ('list' shows the id)",
    },
    "r.reana.missing": {
        "de": "Datei nicht gefunden: {name}",
        "en": "File not found: {name}",
    },
    "r.reana.working": {
        "de": "Analysiere {name} neu …",
        "en": "Re-analysing {name} …",
    },
    "r.reana.failed": {
        "de": "Analyse fehlgeschlagen: {reason}",
        "en": "Analysis failed: {reason}",
    },
    "r.reana.done": {
        "de": "Neu erfasst: {title}",
        "en": "Re-captured: {title}",
    },
    "r.reana.same": {
        "de": "Kategorie bleibt: {cat}",
        "en": "Category stays: {cat}",
    },
    "r.reana.move": {
        "de": "Die neue Analyse sagt {new} statt {old}. Umsortieren? [J/n]: ",
        "en": "The new analysis says {new} instead of {old}. Re-file? [Y/n]: ",
    },

    # ------------------------------------------------------------------ #
    #  Flugbrett — die Browser-Oberfläche (web/). Bienen-Begriff + Klartext,
    #  ohne Konsolen-Befehle in den Sätzen (die Seite hat Knöpfe statt Kürzeln).
    # ------------------------------------------------------------------ #
    "web.nav": {"de": "Navigation", "en": "Navigation"},
    "web.nav.home": {"de": "Zuhause", "en": "Home"},
    "web.nav.home.k": {"de": "Übersicht", "en": "Overview"},
    "web.nav.inbox": {"de": "Flugloch", "en": "Entrance"},
    "web.nav.inbox.k": {"de": "Eingang sortieren", "en": "Sort the inbox"},
    "web.nav.review": {"de": "Rückfragen", "en": "Review"},
    "web.nav.review.k": {"de": "Unsichere Fälle", "en": "Unsure files"},
    "web.nav.combs": {"de": "Waben", "en": "Combs"},
    "web.nav.combs.k": {"de": "Kategorien", "en": "Categories"},
    "web.nav.swarm": {"de": "Schwarm", "en": "Swarm"},
    "web.nav.swarm.k": {"de": "Überblick & Termine", "en": "Overview & deadlines"},
    "web.nav.rules": {"de": "Wachstafel", "en": "Wax tablet"},
    "web.nav.rules.k": {"de": "Gelernte Regeln", "en": "Learned rules"},
    "web.nav.trash": {"de": "Quarantäne", "en": "Quarantine"},
    "web.nav.trash.k": {"de": "Aussortiertes", "en": "Set aside"},
    "web.nav.workshop": {"de": "Werkstatt", "en": "Workshop"},
    "web.nav.workshop.k": {"de": "Einstellungen", "en": "Settings"},
    "web.skip": {"de": "Zum Inhalt springen", "en": "Skip to content"},
    "web.project": {"de": "Projekt", "en": "Project"},
    "web.project.new": {"de": "Neues Projekt einrichten …", "en": "Set up a new project …"},
    "web.mode.title": {
        "de": "KI-Modus dieses Projekts — in der Werkstatt änderbar",
        "en": "AI mode of this project — change it in the workshop",
    },
    "web.watch.off": {"de": "Wache aus", "en": "Watch off"},
    "web.watch.notify": {"de": "Wache meldet", "en": "Watch: notify"},
    "web.watch.move": {"de": "Wache sortiert", "en": "Watch: sorting"},
    "web.watch.pause": {"de": "Wache pausieren", "en": "Pause the watch"},
    "web.watch.resume": {"de": "Wache am Flugloch aufstellen", "en": "Post the watch at the entrance"},
    "web.watchmode.off": {"de": "aus", "en": "off"},
    "web.watchmode.notify": {"de": "nur melden", "en": "notify only"},
    "web.watchmode.move": {"de": "sofort sortieren", "en": "sort immediately"},
    "web.undo": {"de": "Rückflug", "en": "Undo"},
    "web.undo.title": {
        "de": "Rückflug: die letzte Verschiebung rückgängig machen",
        "en": "Undo the last move",
    },
    "web.undo.done": {"de": "Rückflug gelandet", "en": "Move undone"},
    "web.count": {"de": "{n} offen", "en": "{n} open"},
    "web.log": {"de": "Protokoll", "en": "Log"},
    "web.log.title": {"de": "Bienen-Protokoll", "en": "Bee log"},
    "web.log.empty": {"de": "Noch ist nichts passiert.", "en": "Nothing has happened yet."},
    "web.polly.hello": {"de": "Die Bienen sind bereit.", "en": "The bees are ready."},
    "web.active": {"de": "aktiv", "en": "active"},
    "web.welcome": {"de": "Willkommen", "en": "Welcome"},
    "web.setup.start": {"de": "Projekt einrichten", "en": "Set up a project"},
    "web.btn.preview": {"de": "Vorschau zeigen", "en": "Show preview"},
    "web.btn.sort": {"de": "Jetzt sortieren", "en": "Sort now"},
    "web.btn.apply": {"de": "Anwenden", "en": "Apply"},
    "web.btn.discard": {"de": "Verwerfen", "en": "Discard"},
    "web.btn.answer": {"de": "Beantworten", "en": "Answer"},
    "web.btn.combs": {"de": "Waben ansehen", "en": "Open combs"},
    "web.btn.show": {"de": "Ansehen", "en": "Show"},
    "web.btn.calendar": {"de": "Zum Kalender", "en": "Open calendar"},
    "web.btn.open": {"de": "Öffnen", "en": "Open"},
    "web.btn.open_existing": {"de": "Bestehendes Projekt öffnen", "en": "Open the existing project"},
    "web.btn.home": {"de": "Zur Übersicht", "en": "Back to overview"},
    "web.btn.accept": {"de": "Vorschlag übernehmen", "en": "Accept suggestion"},
    "web.btn.accept_short": {"de": "Übernehmen", "en": "Accept"},
    "web.btn.skip": {"de": "Überspringen", "en": "Skip"},
    "web.btn.view": {"de": "Datei ansehen", "en": "View file"},
    "web.btn.newcomb": {"de": "In neue Wabe", "en": "New comb"},
    "web.btn.reanalyze": {"de": "Neu analysieren", "en": "Re-analyse"},
    "web.btn.quarantine": {"de": "In die Quarantäne", "en": "Move to quarantine"},
    "web.btn.save": {"de": "Speichern", "en": "Save"},
    "web.btn.remove": {"de": "Entfernen", "en": "Remove"},
    "web.btn.keep": {"de": "Behalten", "en": "Keep"},
    "web.btn.charter": {"de": "Projekt bauen", "en": "Build project"},
    "web.btn.notify": {"de": "Wächterbienen ausschicken", "en": "Send the guard bees"},
    "web.btn.reflect": {"de": "Regeln aus Korrekturen ableiten", "en": "Derive rules from corrections"},
    "web.btn.inscribe": {"de": "In die Wachstafel ritzen", "en": "Inscribe on the tablet"},
    "web.btn.wipe": {"de": "Wachstafel abwischen", "en": "Wipe the tablet"},
    "web.btn.rebuild": {"de": "Gedächtnis neu aufbauen", "en": "Rebuild memory"},
    "web.btn.restore": {"de": "Zurückholen", "en": "Restore"},
    "web.btn.dups": {"de": "{n} Dublette(n) in die Quarantäne", "en": "Move {n} duplicate(s) to quarantine"},
    "web.btn.empty": {"de": "Quarantäne endgültig leeren …", "en": "Empty quarantine for good …"},
    "web.btn.check_modes": {"de": "Verfügbarkeit prüfen", "en": "Check availability"},
    "web.btn.check": {"de": "Stock-Check starten", "en": "Run hive check"},
    "web.btn.check_path": {"de": "Ordner prüfen", "en": "Check folder"},
    "web.btn.scout": {"de": "Spähbienen ausschicken", "en": "Send out the scout bees"},
    "web.btn.back": {"de": "Zurück", "en": "Back"},
    "web.btn.next": {"de": "Weiter", "en": "Next"},
    "web.btn.setup": {"de": "Projekt einrichten", "en": "Set up project"},
    "web.btn.cancel": {"de": "Abbrechen", "en": "Cancel"},
    "web.btn.ok": {"de": "Ja, weiter", "en": "Yes, continue"},
    "web.btn.close": {"de": "Schließen", "en": "Close"},
    "web.btn.import": {"de": "Importieren", "en": "Import"},
    "web.btn.scan": {"de": "Ordner scannen", "en": "Scan folder"},
    "web.btn.move": {"de": "Umsortieren", "en": "Re-file"},
    "web.st.assigned": {"de": "einsortiert", "en": "filed"},
    "web.st.indexed": {"de": "erfasst", "en": "indexed"},
    "web.st.needs_review": {"de": "Rückfrage", "en": "to review"},
    "web.st.error": {"de": "Fehler", "en": "Errors"},
    "web.st.dublette": {"de": "Dublette", "en": "duplicate"},
    "web.st.quarantined": {"de": "Quarantäne", "en": "quarantined"},
    "web.st.missing": {"de": "verschwunden", "en": "missing"},
    "web.st.superseded": {"de": "ersetzt", "en": "superseded"},
    "web.st.pending": {"de": "in Arbeit", "en": "in progress"},
    "web.st.plan": {"de": "wird einsortiert", "en": "will be filed"},
    "web.home.inbox": {"de": "Eingang", "en": "Inbox"},
    "web.home.inbox.some": {
        "de": "lose Datei(en) warten aufs Sortieren",
        "en": "loose file(s) waiting to be sorted",
    },
    "web.home.review.some": {
        "de": "Dateien sind unsicher — ordne sie kurz selbst zu.",
        "en": "files are unsure — assign them yourself in a moment.",
    },
    "web.home.sorted": {"de": "Dateien in {n} Waben", "en": "files in {n} combs"},
    "web.home.errors": {"de": "Dateien konnten nicht gelesen werden.", "en": "files could not be read."},
    "web.home.deadlines": {
        "de": "Deadline(s) in den nächsten 7 Tagen",
        "en": "deadline(s) within the next 7 days",
    },
    "web.stock.only_real": {
        "de": "Zählt nur echte Arbeit — Öffnen und Vorschau zählen nicht.",
        "en": "Only real work counts — opening the app or previewing doesn't.",
    },
    "web.stock.earned": {"de": "verdient", "en": "earned"},
    "web.stock.open": {"de": "noch offen", "en": "not yet earned"},
    "web.inbox.loose": {"de": "lose Dateien", "en": "loose files"},
    "web.inbox.explain": {
        "de": "Die Vorschau zeigt, wohin jede Datei käme — verschoben wird erst nach „Anwenden“, ohne "
              "zweite KI-Anfragen. Unsichere Dateien bleiben liegen und landen in den Rückfragen. Nichts "
              "wird gelöscht; der Rückflug macht jede Verschiebung rückgängig.",
        "en": "The preview shows where each file would go — nothing moves until you apply it, and applying "
              "costs no second AI calls. Unsure files stay put and go to review. Nothing is deleted; undo "
              "reverses any move.",
    },
    "web.inbox.files": {"de": "Im Eingang", "en": "In the inbox"},
    "web.turbo": {"de": "Ultra Swarm — viele Dateien parallel", "en": "Ultra Swarm — many files in parallel"},
    "web.tools": {"de": "Weitere Werkzeuge: Import & Scan", "en": "More tools: import & scan"},
    "web.import.title": {"de": "Aus einem anderen Ordner importieren", "en": "Import from another folder"},
    "web.import.label": {"de": "Ordner", "en": "Folder"},
    "web.scan.title": {"de": "Handarbeit erkennen", "en": "Detect manual changes"},
    "web.scan.result": {
        "de": "{neu} neu · {geaendert} geändert · {verschoben} verschoben · {verschwunden} verschwunden · "
              "{gelernt} gelernt",
        "en": "{neu} new · {geaendert} changed · {verschoben} moved · {verschwunden} missing · {gelernt} "
              "learned",
    },
    "web.run.preview": {
        "de": "Spurbienen schauen nach — nichts wird bewegt …",
        "en": "Scout bees are looking — nothing is moved …",
    },
    "web.run.sort": {"de": "Spurbienen fliegen aus …", "en": "Scout bees are flying out …"},
    "web.run.preview.title": {"de": "Vorschau läuft", "en": "Preview running"},
    "web.run.sort.title": {"de": "Sortierlauf", "en": "Sorting run"},
    "web.preview.title": {"de": "Vorschau: Datei → Wabe", "en": "Preview: file → comb"},
    "web.preview.would": {"de": "{n} würden einsortiert", "en": "{n} would be filed"},
    "web.preview.review": {"de": "{n} Rückfrage(n)", "en": "{n} to review"},
    "web.preview.dups": {"de": "{n} Dublette(n)", "en": "{n} duplicate(s)"},
    "web.preview.errors": {"de": "{n} Fehler", "en": "{n} error(s)"},
    "web.preview.cache": {
        "de": "„Anwenden“ nutzt diese Analyse noch einmal — es entstehen keine zweiten KI-Anfragen.",
        "en": "Applying reuses this analysis — there are no second AI calls.",
    },
    "web.result.title": {"de": "Ergebnis des Sortierlaufs", "en": "Sorting result"},
    "web.result.none": {"de": "Diesmal wurde nichts einsortiert.", "en": "Nothing was filed this time."},
    "web.col.target": {"de": "Ziel-Wabe", "en": "Target comb"},
    "web.col.confidence": {"de": "Sicherheit", "en": "Confidence"},
    "web.col.status": {"de": "Status", "en": "Status"},
    "web.col.size": {"de": "Größe", "en": "Size"},
    "web.col.changed": {"de": "Geändert", "en": "Modified"},
    "web.col.date": {"de": "Erfasst", "en": "Captured"},
    "web.col.actions": {"de": "Aktionen", "en": "Actions"},
    "web.review.case": {"de": "Fall {i} von {n}", "en": "Case {i} of {n}"},
    "web.review.function": {"de": "Funktion", "en": "Purpose"},
    "web.review.suggestion": {"de": "Vorschlag", "en": "Suggestion"},
    "web.review.nosuggestion": {"de": "Kein sicherer Vorschlag", "en": "No confident suggestion"},
    "web.review.summary": {"de": "Kurzfassung", "en": "Summary"},
    "web.review.which": {
        "de": "In welche Wabe gehört die Datei?",
        "en": "Which comb does this file belong in?",
    },
    "web.review.newcomb": {"de": "Neue Wabe, z. B. versicherungen", "en": "New comb, e.g. insurance"},
    "web.review.learns": {
        "de": "Jede Antwort trainiert das Gedächtnis.",
        "en": "Every answer trains the memory.",
    },
    "web.review.learned": {"de": "Gelernt: → {cat}", "en": "Learned: → {cat}"},
    "web.review.alldone": {
        "de": "Alle Rückfragen beantwortet — das Gedächtnis hat dazugelernt.",
        "en": "All questions answered — the memory has learned.",
    },
    "web.combs.all": {"de": "Alle Waben ({n})", "en": "All combs ({n})"},
    "web.combs.total": {"de": "{n} Dateien einsortiert", "en": "{n} files filed"},
    "web.combs.count": {"de": "{n} Einträge", "en": "{n} entries"},
    "web.combs.project": {"de": "Projekt", "en": "Project"},
    "web.combs.search": {"de": "Titel, Stichwort, Inhalt …", "en": "Title, keyword, content …"},
    "web.combs.search_hits": {"de": "Treffer für „{q}“", "en": "Results for “{q}”"},
    "web.combs.move": {"de": "Umsortieren nach …", "en": "Re-file to …"},
    "web.combs.drag": {
        "de": "Tipp: Einen Eintrag auf eine Wabe ziehen sortiert ihn um — PollySort lernt daraus eine Regel.",
        "en": "Tip: drag an entry onto a comb to re-file it — PollySort learns a rule from it.",
    },
    "web.combs.pattern": {"de": "Muster", "en": "Pattern"},
    "web.charter.title": {
        "de": "Wabenbau — aus der Wabe ein Projekt machen",
        "en": "Charter — turn this comb into a project",
    },
    "web.charter.who": {
        "de": "Zuständig (Namen, durch Komma getrennt)",
        "en": "Responsible (names, comma-separated)",
    },
    "web.charter.goal": {"de": "Projektziel (ein Satz)", "en": "Project goal (one sentence)"},
    "web.charter.deadline": {"de": "Deadline", "en": "Deadline"},
    "web.charter.built": {
        "de": "Baubienen haben gebaut — es gibt noch offene Aufgaben.",
        "en": "Builder bees are done — some tasks are still open.",
    },
    "web.reana.title": {"de": "Neu einordnen?", "en": "Re-file?"},
    "web.reana.text": {
        "de": "Die neue Analyse sagt {new} statt {old}. Soll die Datei umziehen?",
        "en": "The new analysis says {new} instead of {old}. Move the file?",
    },
    "web.role.queen": {"de": "Königin", "en": "Queen"},
    "web.role.queen.text": {
        "de": "Steuert den Schwarm: {waben} Waben, {docs} Dokumente im Katalog.",
        "en": "Coordinates the swarm: {waben} combs, {docs} documents in the catalogue.",
    },
    "web.role.scouts": {"de": "Spurbienen", "en": "Scout bees"},
    "web.role.scouts.text": {
        "de": "Sortieren den Eingang. Offen: {review} Rückfrage(n), {errors} Fehler.",
        "en": "Sort the inbox. Open: {review} to review, {errors} error(s).",
    },
    "web.role.builders": {"de": "Baubienen", "en": "Builder bees"},
    "web.role.builders.text": {
        "de": "Machen aus Waben Projekte mit Steckbrief (Bienenstock.md) und Deadlines.",
        "en": "Turn combs into projects with a charter (Bienenstock.md) and deadlines.",
    },
    "web.role.guards": {"de": "Wächterbienen", "en": "Guard bees"},
    "web.role.guards.routes": {
        "de": "Deadlines in den nächsten 7 Tagen — sie melden sich über deine Flugrouten.",
        "en": "Deadlines within the next 7 days — reported via your notification routes.",
    },
    "web.role.guards.noroutes": {
        "de": "Deadlines in den nächsten 7 Tagen. Ohne Flugrouten melden sich die Wächterbienen nur hier.",
        "en": "Deadlines within the next 7 days. Without notification routes the guard bees only report "
              "here.",
    },
    "web.role.foragers": {"de": "Sammelbienen", "en": "Forager bees"},
    "web.role.foragers.text": {
        "de": "Merken sich, wo du welche Wabe tatsächlich ablegst.",
        "en": "Remember where you actually keep each comb.",
    },
    "web.cal.hint": {
        "de": "Deadlines entstehen beim Wabenbau. Die Datei .honig/kalender.ics lässt sich in Outlook, "
              "Google oder Apple Kalender abonnieren.",
        "en": "Deadlines come from building a charter. The file .honig/kalender.ics can be subscribed to "
              "in Outlook, Google or Apple Calendar.",
    },
    "web.cal.sent": {
        "de": "Wächterbienen haben nachgesehen: {n} fällige Deadline(s).",
        "en": "Guard bees checked: {n} deadline(s) due.",
    },
    "web.recommend.title": {"de": "Empfehlungen für die Ablage", "en": "Filing recommendations"},
    "web.recommend.para": {"de": "PARA", "en": "PARA"},
    "web.recommend.johnny": {"de": "Johnny Decimal", "en": "Johnny Decimal"},
    "web.recommend.dewey": {"de": "Dewey", "en": "Dewey"},
    "web.rules.none": {
        "de": "Noch keine Regeln. Korrigiere Zuordnungen (Rückfragen, Umsortieren) — daraus leitet die "
              "Königin Regeln ab.",
        "en": "No rules yet. Correct some assignments (review, re-filing) — the queen derives rules from "
              "them.",
    },
    "web.rules.corrections": {"de": "{n} Korrektur(en) bisher", "en": "{n} correction(s) so far"},
    "web.rules.safe": {
        "de": "Sicher und projektgebunden: Es wird nie Code erzeugt, nur diese Textdatei "
              "(.honig/wachstafel.md). Die Regeln gelten nur in diesem Projekt.",
        "en": "Safe and project-scoped: no code is ever generated, only this text file "
              "(.honig/wachstafel.md). The rules apply only within this project.",
    },
    "web.rules.from": {"de": "aus {n} Korrektur(en)", "en": "from {n} correction(s)"},
    "web.rules.confirm": {
        "de": "Alle gelernten Regeln werden verworfen. Deine Korrekturen bleiben erhalten — die Königin "
              "kann die Regeln später neu ableiten.",
        "en": "All learned rules will be discarded. Your corrections are kept — the queen can derive the "
              "rules again later.",
    },
    "web.memory.title": {"de": "Gedächtnis", "en": "Memory"},
    "web.memory.vectors": {"de": "{n} Dokumente im Gedächtnis", "en": "{n} documents in memory"},
    "web.memory.proposals": {"de": "Vorschläge der Königin", "en": "The queen's proposals"},
    "web.memory.rebuild": {
        "de": "Alle einsortierten Einträge werden mit dem aktuellen Modell neu eingebettet. Das dauert "
              "einen Moment.",
        "en": "All filed entries are re-embedded with the current model. This takes a moment.",
    },
    "web.trash.explain": {
        "de": "Hier liegt, was du aussortiert hast. Nichts davon ist gelöscht — du kannst alles "
              "zurückholen, bis du die Quarantäne ausdrücklich leerst.",
        "en": "This is what you have set aside. None of it is deleted — you can restore everything until "
              "you explicitly empty the quarantine.",
    },
    "web.trash.items": {"de": "In der Quarantäne", "en": "In quarantine"},
    "web.trash.dups": {"de": "Dubletten", "en": "Duplicates"},
    "web.trash.original": {"de": "Original: {orig} ({cat})", "en": "Original: {orig} ({cat})"},
    "web.trash.danger": {"de": "Endgültig löschen", "en": "Delete for good"},
    "web.trash.danger.text": {
        "de": "{n} Datei(en) liegen in der Quarantäne. Leeren löscht sie unwiderruflich — der einzige Weg, "
              "auf dem PollySort überhaupt etwas löscht.",
        "en": "{n} file(s) are in quarantine. Emptying deletes them permanently — the only way PollySort "
              "ever deletes anything.",
    },
    "web.trash.confirm": {
        "de": "{n} Datei(en) werden unwiderruflich gelöscht. Dafür gibt es keinen Rückflug.",
        "en": "{n} file(s) will be deleted permanently. There is no undo for this.",
    },
    "web.trash.type": {
        "de": "Zur Bestätigung die Anzahl eintippen: {n}",
        "en": "Type the number to confirm: {n}",
    },
    "web.dup.confirm": {
        "de": "{n} Dublette(n) in die Quarantäne verschieben? Gelöscht wird dabei nichts.",
        "en": "Move {n} duplicate(s) to quarantine? Nothing is deleted.",
    },
    "web.ws.look": {"de": "Darstellung", "en": "Appearance"},
    "web.ws.workmode": {"de": "Arbeitsmodus", "en": "Work mode"},
    "web.ws.workmode.text": {
        "de": "Für den Büroalltag: dezente Animationen, Stufen und Abzeichen ausgeblendet, Klartext vor "
              "den Bienen-Begriffen.",
        "en": "For the working day: subtle animations, levels and badges hidden, plain words before the "
              "bee terms.",
    },
    "web.ws.workmode.on": {"de": "Arbeitsmodus ist an", "en": "Work mode is on"},
    "web.ws.workmode.off": {"de": "Arbeitsmodus einschalten", "en": "Turn on work mode"},
    "web.ws.theme": {"de": "Thema", "en": "Theme"},
    "web.ws.language": {"de": "Sprache", "en": "Language"},
    "web.lang.de": {"de": "Deutsch", "en": "Deutsch"},
    "web.lang.en": {"de": "English", "en": "English"},
    "web.ws.anim": {"de": "Animationen", "en": "Animations"},
    "web.anim.voll": {"de": "Voll", "en": "Full"},
    "web.anim.dezent": {"de": "Dezent", "en": "Subtle"},
    "web.anim.aus": {"de": "Aus", "en": "Off"},
    "web.ws.anim.text": {
        "de": "Dezent: Fortschritt ja, fliegende Bienen nein. Die Systemeinstellung „Bewegung reduzieren“ "
              "gilt immer.",
        "en": "Subtle: progress yes, flying bees no. The system setting “reduce motion” always applies.",
    },
    "web.ws.progress": {"de": "Stufen & Abzeichen", "en": "Levels & badges"},
    "web.ws.progress.text": {
        "de": "Zeigt den wachsenden Bienenstock. Gezählt wird trotzdem — nur nicht angezeigt.",
        "en": "Shows your growing hive. Progress is still counted — just not shown.",
    },
    "web.ws.plain": {"de": "Klartext zuerst", "en": "Plain words first"},
    "web.ws.plain.text": {
        "de": "„Kategorien“ statt „Waben“ als Hauptbeschriftung; der Bienen-Begriff steht klein darunter.",
        "en": "“Categories” instead of “combs” as the main label; the bee term stays underneath in small "
              "print.",
    },
    "web.ws.project": {"de": "Dieses Projekt", "en": "This project"},
    "web.ws.enrich": {"de": "Nacherfassung (nur Lokal)", "en": "Enrichment (local only)"},
    "web.ws.model_hint": {
        "de": "Die Nektar-Sorte gilt nur im Modus Cloud.",
        "en": "The model only applies in cloud mode.",
    },
    "web.ws.access": {"de": "Zugänge", "en": "Access"},
    "web.ws.access.text": {
        "de": "Zugangsdaten trägst du aus Sicherheitsgründen nur in der Konsole ein. Sie bleiben lokal und "
              "erscheinen nie im Browser, im Protokoll oder in einem KI-Prompt.",
        "en": "For security, credentials are only entered in the console. They stay local and never appear "
              "in the browser, the log or an AI prompt.",
    },
    "web.key.env": {"de": "aus Umgebungsvariable", "en": "from environment variable"},
    "web.key.datei": {"de": "lokal gespeichert", "en": "stored locally"},
    "web.key.console": {
        "de": "Braucht einen OpenRouter-Schlüssel — in der Konsole: schluessel setzen",
        "en": "Needs an OpenRouter key — in the console: key set",
    },
    "web.routes.discord": {"de": "Discord", "en": "Discord"},
    "web.routes.email": {"de": "E-Mail", "en": "Email"},
    "web.routes.kalender": {"de": "Kalender", "en": "Calendar"},
    "web.ws.check": {"de": "Stock-Check", "en": "Hive check"},
    "web.ws.about": {
        "de": "Konsole: pollysort · Browser: pollysort-web",
        "en": "Console: pollysort · Browser: pollysort-web",
    },
    "web.su.title": {"de": "Projekt einrichten", "en": "Set up a project"},
    "web.su.title.k": {"de": "Einrichtungs-Assistent", "en": "Setup wizard"},
    "web.su.step.look": {"de": "Darstellung", "en": "Appearance"},
    "web.su.step.folder": {"de": "Ordner", "en": "Folder"},
    "web.su.step.name": {"de": "Name", "en": "Name"},
    "web.su.step.mode": {"de": "Modus", "en": "Mode"},
    "web.su.step.combs": {"de": "Waben", "en": "Combs"},
    "web.su.step.sub": {"de": "Unterordner", "en": "Subfolders"},
    "web.su.step.watch": {"de": "Wache", "en": "Watch"},
    "web.su.step.done": {"de": "Fertig", "en": "Done"},
    "web.su.progress": {"de": "Schritt {i} von {n}", "en": "Step {i} of {n}"},
    "web.su.look": {"de": "Wie soll PollySort aussehen?", "en": "How should PollySort look?"},
    "web.su.folder": {"de": "Welcher Ordner soll sortiert werden?", "en": "Which folder should be sorted?"},
    "web.su.folder.hint": {
        "de": "Den Pfad z. B. im Explorer aus der Adresszeile kopieren und hier einfügen. Die losen "
              "Dateien darin sind dein Eingang.",
        "en": "Copy the path from your file manager's address bar and paste it here. The loose files in it "
              "are your inbox.",
    },
    "web.su.found": {
        "de": "Ordner gefunden — {n} lose Datei(en) im Eingang.",
        "en": "Folder found — {n} loose file(s) in the inbox.",
    },
    "web.su.create": {"de": "Den Ordner {path} neu anlegen", "en": "Create the folder {path}"},
    "web.su.redo": {
        "de": "Oder weiter: Das richtet das Projekt neu ein (die Konfiguration wird überschrieben, deine "
              "Dateien bleiben, wo sie sind).",
        "en": "Or continue: this sets the project up again (the configuration is overwritten, your files "
              "stay where they are).",
    },
    "web.su.name": {"de": "Wie soll das Projekt heißen?", "en": "What should the project be called?"},
    "web.su.name.label": {"de": "Projektname", "en": "Project name"},
    "web.su.checking": {
        "de": "Die Spähbienen prüfen, welche KI erreichbar ist …",
        "en": "Scout bees are checking which AI is reachable …",
    },
    "web.su.cat.propose": {"de": "Vorschlag", "en": "Proposal"},
    "web.su.cat.standard": {"de": "Standard", "en": "Standard"},
    "web.su.cat.own": {"de": "Eigene", "en": "Custom"},
    "web.su.cat.own.label": {"de": "Kategorien, durch Komma getrennt", "en": "Categories, comma-separated"},
    "web.su.cat.empty": {
        "de": "Bitte mindestens eine Wabe wählen.",
        "en": "Please choose at least one comb.",
    },
    "web.su.scout.hint": {
        "de": "Die Spähbienen sehen sich die losen Dateien und die vorhandenen Unterordner an und schlagen "
              "Waben vor, die zu dem passen, was schon da ist.",
        "en": "The scout bees look at the loose files and the existing subfolders and suggest combs that "
              "fit what is already there.",
    },
    "web.su.added": {"de": "selbst ergänzt", "en": "added by you"},
    "web.su.sub.none": {
        "de": "Keine der Waben braucht eine Gliederung nach Datum.",
        "en": "None of the combs needs a date structure.",
    },
    "web.su.watch.hint": {
        "de": "Die Wache läuft, solange PollySort im Browser geöffnet ist. Sie fasst nur neu hinzukommende "
              "Dateien an.",
        "en": "The watch runs while PollySort is open in the browser. It only touches newly arriving files.",
    },
    "web.su.summary": {"de": "Zusammenfassung", "en": "Summary"},
    "web.su.done": {
        "de": "„{name}“ ist eingerichtet: {n} Waben stehen bereit.",
        "en": "“{name}” is set up: {n} combs are ready.",
    },
    "web.su.file_now": {"de": "Jetzt {n} Datei(en) einlagern", "en": "File {n} file(s) now"},
    "web.su.abort": {
        "de": "Abbrechen geht jederzeit: einfach eine andere Seite wählen. Gespeichert wird erst mit "
              "„Projekt einrichten“.",
        "en": "You can stop at any time: just go to another page. Nothing is saved until you click “Set up "
              "project”.",
    },
    "web.toast.error": {"de": "Das hat nicht geklappt", "en": "That didn't work"},
    "web.toast.sorted": {"de": "{n} Datei(en) eingelagert.", "en": "{n} file(s) filed."},
    "web.toast.badge": {"de": "Neues Abzeichen: {name}", "en": "New badge: {name}"},
    "web.toast.levelup": {"de": "Dein Bienenstock ist gewachsen.", "en": "Your hive has grown."},
    "web.toast.watch_sorted": {
        "de": "Wache: {n} neue Datei(en) einsortiert",
        "en": "Watch: {n} new file(s) filed",
    },
    "web.toast.new_files": {"de": "{n} neue Datei(en) im Eingang", "en": "{n} new file(s) in the inbox"},
    "web.toast.new_files.text": {
        "de": "Im Flugloch sortieren oder erst die Vorschau ansehen.",
        "en": "Sort them at the entrance or check the preview first.",
    },
    "web.err.busy": {
        "de": "Die Bienen arbeiten gerade — gleich wieder.",
        "en": "The bees are busy — one moment.",
    },
    "web.err.locked": {
        "de": "Ein anderer PollySort-Prozess (z. B. die Konsole) arbeitet gerade in diesem Projekt. Bitte "
              "kurz warten.",
        "en": "Another PollySort process (e.g. the console) is working in this project. Please wait a "
              "moment.",
    },
    "web.err.noproject": {
        "de": "Kein Projekt aktiv — richte zuerst eins ein.",
        "en": "No active project — set one up first.",
    },
    "web.err.params": {"de": "Ungültige Anfrage.", "en": "Invalid request."},
    "web.err.mode": {
        "de": "Unbekannter Modus. Möglich: Sparmodus, Lokal, Cloud.",
        "en": "Unknown mode. Options: low-power, local, cloud.",
    },
    "web.err.nokey": {
        "de": "Für Cloud fehlt der OpenRouter-Schlüssel. In der Konsole: schluessel setzen",
        "en": "Cloud needs an OpenRouter key. In the console: key set",
    },
    "web.err.confirm_count": {
        "de": "Die Bestätigung passt nicht — bitte genau {n} eintippen.",
        "en": "The confirmation doesn't match — please type exactly {n}.",
    },
    "web.err.date": {
        "de": "Bitte ein Datum im Format JJJJ-MM-TT angeben.",
        "en": "Please give a date as YYYY-MM-DD.",
    },
    "web.err.path": {"de": "Bitte einen Ordner-Pfad angeben.", "en": "Please enter a folder path."},
    "web.err.path_missing": {
        "de": "Den Ordner {path} gibt es noch nicht.",
        "en": "The folder {path} doesn't exist yet.",
    },
    "web.err.token": {
        "de": "Diese Sitzung ist abgelaufen. Bitte die Adresse aus der Konsole neu öffnen (pollysort-web).",
        "en": "This session has expired. Please open the address from the console again (pollysort-web).",
    },
    "web.err.offline": {
        "de": "PollySort ist nicht erreichbar — läuft pollysort-web noch?",
        "en": "PollySort isn't reachable — is pollysort-web still running?",
    },
    "web.err.unknown": {"de": "Unbekannter Fehler.", "en": "Unknown error."},
    "web.cli.desc": {
        "de": "PollySort im Browser — das Flugbrett, nur auf diesem Rechner erreichbar.",
        "en": "PollySort in the browser, reachable only on this computer.",
    },
    "web.cli.arg_path": {
        "de": "Projekt-Ordner (sonst das zuletzt genutzte Projekt)",
        "en": "Project folder (otherwise the last used project)",
    },
    "web.cli.arg_port": {
        "de": "Port auf 127.0.0.1 (Standard 8737)",
        "en": "Port on 127.0.0.1 (default 8737)",
    },
    "web.cli.arg_nobrowser": {
        "de": "Browser nicht automatisch öffnen",
        "en": "Don't open the browser automatically",
    },
    "web.cli.open": {"de": "Flugbrett offen: {url}", "en": "PollySort in the browser: {url}"},
    "web.cli.stop": {"de": "Strg-C schließt das Flugbrett.", "en": "Ctrl-C closes it."},
    "web.cli.closed": {"de": "Flugbrett geschlossen.", "en": "Browser interface closed."},
    "web.cli.failed": {
        "de": "Das Flugbrett konnte nicht starten: {err}",
        "en": "The browser interface couldn't start: {err}",
    },
    "help.d.web": {"de": "PollySort im Browser öffnen (Flugbrett)", "en": "Open PollySort in the browser"},
    "web.review.title": {"de": "Titel", "en": "Title"},
    "help.d.app": {"de": "PollySort im eigenen Programmfenster öffnen",
                   "en": "Open PollySort in its own window"},
    "web.app.desc": {"de": "PollySort als eigene Anwendung — das Flugbrett im Programmfenster.",
                     "en": "PollySort as its own application — in a program window."},
    "web.app.arg_window": {
        "de": "Fenster-Art: auto (Standard), nativ (pywebview), app (Edge/Chrome), browser",
        "en": "Window type: auto (default), nativ (pywebview), app (Edge/Chrome), browser",
    },
    "web.app.open": {"de": "Öffne das PollySort-Fenster — schließen bringt dich hierher zurück.",
                     "en": "Opening the PollySort window — close it to come back here."},
    "web.app.closed": {"de": "PollySort-Fenster geschlossen.", "en": "PollySort window closed."},
    "web.app.failed": {"de": "PollySort konnte nicht starten: {err}",
                       "en": "PollySort could not start: {err}"},
    "web.app.nowindow": {
        "de": "Es ließ sich kein Fenster öffnen — weder pywebview noch Edge/Chrome noch ein Browser. "
              "Installiere das Extra [app] oder starte pollysort-web.",
        "en": "No window could be opened — neither pywebview nor Edge/Chrome nor a browser. Install "
              "the [app] extra or run pollysort-web.",
    },
    "web.toast.moved": {"de": "{datei} → {neu}", "en": "{datei} → {neu}"},
    "web.trash.dups.hint": {
        "de": "Gleicher Inhalt wie eine schon einsortierte Datei. In der Quarantäne liegen sie sicher — "
              "gelöscht wird erst, wenn du die Quarantäne ausdrücklich leerst.",
        "en": "Same content as a file that is already filed. They are safe in quarantine — nothing is "
              "deleted until you explicitly empty it.",
    },
    "web.su.ollama_hint": {
        "de": "Kein lokales Ollama erreichbar. Starte Ollama (ollama serve) und prüfe dann noch einmal.",
        "en": "No local Ollama reachable. Start Ollama (ollama serve) and check again.",
    },
    # Flugbrett × BeeNara — Werkstatt, Assistent, Sortierplan
    "web.btn.bn_pull": {"de": "Herunterladen", "en": "Download"},
    "web.btn.bn_finish": {"de": "Vervollständigen", "en": "Complete"},
    "web.btn.bn_remove": {"de": "Entfernen", "en": "Remove"},
    "web.bn.use": {"de": "Beim Sortieren", "en": "When sorting"},
    "web.bn.chip.on": {"de": "sortiert mit", "en": "sorting with it"},
    "web.bn.chip.off": {"de": "ausgeschaltet", "en": "switched off"},
    "web.bn.chip.incomplete": {"de": "unvollständig", "en": "incomplete"},
    "web.bn.chip.missing": {"de": "nicht geladen", "en": "not downloaded"},
    "web.bn.remove.text": {
        "de": "BeeNara ({mb} MB) von diesem Rechner entfernen? Sortiert wird danach wieder wie "
              "vorher. Deine Dokumente bleiben, wie sie sind.",
        "en": "Remove BeeNara ({mb} MB) from this computer? Sorting then works as it did before. "
              "Your documents stay as they are.",
    },
    "web.bn.mode_note": {"de": "mit BeeNara: ein lokales Modell wählt den Ordner",
                         "en": "with BeeNara: a local model picks the folder"},
    "web.run.beenara.title": {"de": "BeeNara laden", "en": "Downloading BeeNara"},
    "web.toast.bn.ready": {"de": "BeeNara ist bereit", "en": "BeeNara is ready"},
    "web.toast.bn.ready.text": {"de": "Ab dem nächsten Sortierlauf entscheidet es mit.",
                                "en": "It takes part from the next sorting run."},
    "web.toast.bn.failed": {"de": "BeeNara ist noch nicht bereit", "en": "BeeNara is not ready yet"},
    "web.toast.bn.failed.text": {"de": "Was fehlt, steht im Protokoll und in der Werkstatt.",
                                 "en": "What is missing is in the log and in the workshop."},
    "web.btn.bb_pull": {"de": "Herunterladen (ca. 4,7 GB)", "en": "Download (about 4.7 GB)"},
    "web.bb.chip.gpu": {"de": "GPU fehlt", "en": "no GPU"},
    "web.bb.modell": {"de": "Welches Modell sortiert", "en": "Which model sorts"},
    "web.bb.auto": {"de": "Automatisch", "en": "Automatic"},
    "web.bb.klein": {"de": "Nur BeeNara", "en": "BeeNara only"},
    "web.bb.big": {"de": "Nur Big", "en": "Big only"},
    "web.bb.remove.text": {
        "de": "BeeNara Big ({mb} MB, mit Basismodell) von diesem Rechner entfernen? Deine "
              "Dokumente bleiben, wie sie sind.",
        "en": "Remove BeeNara Big ({mb} MB, with base model) from this computer? Your documents "
              "stay as they are.",
    },
    "web.run.bb.title": {"de": "BeeNara Big laden", "en": "Downloading BeeNara Big"},
    "web.toast.bb.ready": {"de": "BeeNara Big ist bereit", "en": "BeeNara Big is ready"},
    "web.toast.bb.ready.text": {"de": "Ab dem nächsten Sortierlauf schlägt es Ordner vor.",
                                "en": "It suggests folders from the next sorting run."},
    "web.toast.bb.failed": {"de": "BeeNara Big ist noch nicht bereit",
                            "en": "BeeNara Big is not ready yet"},
    "web.su.bn.label": {"de": "BeeNara nach dem Einrichten mit herunterladen",
                        "en": "Also download BeeNara after setup"},
    "web.su.bn.row": {"de": "BeeNara", "en": "BeeNara"},
    "web.su.bn.yes": {"de": "wird nach dem Einrichten geladen", "en": "downloads after setup"},
    "web.su.bn.no": {"de": "später — jederzeit in der Werkstatt", "en": "later — any time in the workshop"},
    "web.su.bn.ready": {"de": "schon bereit", "en": "already ready"},
    "web.src.gedaechtnis": {"de": "Gedächtnis", "en": "memory"},
    "web.src.beenara": {"de": "BeeNara", "en": "BeeNara"},
    "web.src.nummer": {"de": "KI-Kurzentscheid", "en": "quick AI decision"},
    "web.src.analyse": {"de": "Vollanalyse", "en": "full analysis"},
    "web.src.heuristik": {"de": "Heuristik", "en": "heuristics"},
}


def katalog(lang: str | None = None) -> dict[str, str]:
    """Alle Texte einer Sprache (Fallback Deutsch) — für die Browser-Oberfläche (``web/``).

    Die Platzhalter bleiben stehen; die Seite setzt sie selbst ein.
    """
    lang = lang or _LANG
    return {key: entry.get(lang) or entry.get("de") or key for key, entry in _CATALOG.items()}


def set_language(lang: str) -> None:
    global _LANG
    _LANG = "en" if str(lang).lower().startswith("en") else "de"


def get_language() -> str:
    return _LANG


def modus_name(provider: str) -> str:
    """Sichtbarer Name eines Modus — ``offline`` → „Sparmodus", ``ollama`` → „Lokal",
    ``openrouter`` → „Cloud". Intern (hive.toml, Config) bleiben die alten Werte stehen,
    damit jedes bestehende Projekt ohne Umbau weiterläuft."""
    key = f"mode.{provider}"
    return t(key) if key in _CATALOG else str(provider)


def vorhanden(key: str) -> bool:
    """Gibt es einen Text unter ``key``?"""
    return key in _CATALOG


def t(key: str, /, **kw) -> str:
    entry = _CATALOG.get(key, {})
    text = entry.get(_LANG) or entry.get("de") or key
    if kw:
        try:
            return text.format(**kw)
        except (KeyError, IndexError):
            return text
    return text

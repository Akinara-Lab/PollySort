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
        "de": "{n} Analyse(n) — offline, ohne KI-Anfrage und ohne Kosten",
        "en": "{n} analysis/analyses — offline, no AI request and no cost",
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

    "su.mode.q": {"de": "KI-Modus — womit sollen Dokumente eingeordnet werden?",
                  "en": "AI mode — how should documents be classified?"},
    "su.mode.or_key": {"de": "OpenRouter — beste Qualität (Key hinterlegt)",
                       "en": "OpenRouter — best quality (key on file)"},
    "su.mode.or_nokey": {"de": "OpenRouter — beste Qualität (Key jetzt hinterlegen)",
                         "en": "OpenRouter — best quality (add a key now)"},
    "su.mode.nokey": {"de": "Kein Key → Offline-Modus.", "en": "No key → offline mode."},

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
        "de": "Der Vorschlag unten basiert nur auf der Offline-Heuristik. Tipp: KI-Backend "
              "prüfen ('modus', 'schluessel test') und 'setup' später erneut ausführen.",
        "en": "The suggestion below is heuristics only. Tip: check the AI backend "
              "('mode', 'key test') and run 'setup' again later.",
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
        "de": "Offline — Heuristik, kostenlos, ohne Internet",
        "en": "Offline — heuristics, free, no internet needed",
    },
    "fr.ai.ollama": {
        "de": "Lokale KI (Ollama) — gratis & privat",
        "en": "Local AI (Ollama) — free & private",
    },
    "fr.ai.openrouter": {
        "de": "OpenRouter — beste Qualität, kostenpflichtig",
        "en": "OpenRouter — best quality, paid",
    },
    "fr.ai.found": {"de": "✅ erkannt", "en": "✅ detected"},
    "fr.ai.notfound": {"de": "— nicht erreichbar", "en": "— not reachable"},
    "fr.ai.keyset": {"de": "✅ Key hinterlegt", "en": "✅ key on file"},
    "fr.ai.keyneeded": {"de": "🔑 Key nötig", "en": "🔑 key needed"},

    # Kurzformen fuer die Zusammenfassung (kein Zerschneiden der Langtexte).
    "fr.short.dark": {"de": "Dunkel", "en": "Dark"},
    "fr.short.light": {"de": "Hell", "en": "Light"},
    "fr.short.auto": {"de": "Automatik", "en": "Auto"},
    "fr.short.offline": {"de": "Offline", "en": "Offline"},
    "fr.short.ollama": {"de": "Ollama (lokal)", "en": "Ollama (local)"},
    "fr.short.openrouter": {"de": "OpenRouter", "en": "OpenRouter"},
    "fr.ai.ollama_missing": {
        "de": "Es antwortet kein lokaler Ollama-Server — vorerst Offline-Modus.",
        "en": "No local Ollama server is responding — staying offline for now.",
    },
    "fr.ai.ollama_hint": {
        "de": "Starte Ollama ('ollama serve') und wechsle dann mit 'modus ollama'.",
        "en": "Start Ollama ('ollama serve'), then switch with 'mode ollama'.",
    },
    "fr.ai.key_where": {
        "de": "Key holen: openrouter.ai/keys — er bleibt lokal (chmod 600).",
        "en": "Get a key at openrouter.ai/keys — it stays local (chmod 600).",
    },
    "fr.ai.key_prompt": {"de": "OpenRouter-API-Key (leer = überspringen): ",
                         "en": "OpenRouter API key (empty = skip): "},
    "fr.ai.key_skipped": {
        "de": "Kein Key — Offline-Modus. Später jederzeit: 'schluessel setzen'.",
        "en": "No key — offline mode. Any time later: 'key set'.",
    },
    "fr.ai.key_failed": {"de": "Key konnte nicht gespeichert werden — Offline-Modus.",
                         "en": "Could not save the key — offline mode."},
    "fr.ai.key_saved": {"de": "Key gespeichert (nur lokal, chmod 600).",
                        "en": "Key saved (local only, chmod 600)."},

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
    "help.d.mode": {"de": "KI-Backend für dieses Projekt", "en": "AI backend for this project"},
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
    "doctor.provider": {"de": "KI-Provider", "en": "AI provider"},
    "doctor.models": {"de": "Modelle", "en": "Models"},
    "doctor.db": {"de": "Datenbank", "en": "Database"},
    "doctor.extract": {"de": "Extraktion", "en": "Extraction"},
    "doctor.memory": {"de": "Gedächtnis", "en": "Memory"},
    "doctor.noproject": {"de": "kein Projekt aktiv", "en": "no project active"},
    "doctor.py.need": {"de": " (benötigt 3.12+)", "en": " (needs 3.12+)"},
    "doctor.prov.offline": {"de": "offline (Heuristik, kostenlos)", "en": "offline (heuristics, free)"},
    "doctor.prov.ollama_ok": {"de": "ollama erreichbar", "en": "ollama reachable"},
    "doctor.prov.ollama_down": {"de": "ollama NICHT erreichbar (Server starten)",
                                "en": "ollama NOT reachable (start the server)"},
    "doctor.prov.or_nokey": {"de": "openrouter ohne Schlüssel → Offline-Fallback",
                             "en": "openrouter without key → offline fallback"},
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
    # Dreistufige Entscheidung & Nacherfassung (Plan §8.3)
    "pl.quellen": {
        "de": "Entschieden: {mem} aus dem Gedächtnis · {num} per KI-Kurzentscheid · "
              "{voll} per Vollanalyse",
        "en": "Decided: {mem} from memory · {num} by quick AI decision · {voll} by full analysis",
    },
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
    "nx.nollm": {"de": "Die Nacherfassung gibt es im Ollama-Modus.",
                 "en": "Refining is available in Ollama mode."},
    "help.d.enrich": {"de": "Titel/Zusammenfassung nach dem Sortieren per KI verfeinern",
                      "en": "Refine titles/summaries with AI after sorting"},
}


def set_language(lang: str) -> None:
    global _LANG
    _LANG = "en" if str(lang).lower().startswith("en") else "de"


def get_language() -> str:
    return _LANG


def t(key: str, /, **kw) -> str:
    entry = _CATALOG.get(key, {})
    text = entry.get(_LANG) or entry.get("de") or key
    if kw:
        try:
            return text.format(**kw)
        except (KeyError, IndexError):
            return text
    return text

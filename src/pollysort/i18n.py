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

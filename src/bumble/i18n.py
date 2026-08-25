"""Leichtgewichtige i18n für die Konsole (DE/EN).

``t(key, **kw)`` liefert den Text in der aktiven Sprache. Fehlt ein Schlüssel in der
Zielsprache, fällt es auf Deutsch zurück (dann auf den Schlüssel selbst) — nie ein Crash.
Die Bienen-Metaphern werden bewusst sinngemäß übersetzt, nicht Wort für Wort.

Die aktive Sprache wird beim Start aus der Config gesetzt (`set_language`).
"""

from __future__ import annotations

_LANG = "de"

_CATALOG: dict[str, dict[str, str]] = {
    # Tutorial (Erststart)
    "tut.title": {"de": "🐝 In 3 Schritten loslegen", "en": "🐝 Get started in 3 steps"},
    "tut.step1": {
        "de": "1) 📂  Ordner wählen — der Assistent fragt gleich nach dem Pfad",
        "en": "1) 📂  Pick a folder — the wizard will ask for the path next",
    },
    "tut.step1b": {
        "de": "      (dessen lose Dateien sind dein Eingang).",
        "en": "      (its loose files are your inbox).",
    },
    "tut.step2": {
        "de": "2) 👀  [honey]vorschau[/honey] (v) — zeigt, wohin sortiert würde, "
              "und fragt: anwenden? [J/n]",
        "en": "2) 👀  [honey]preview[/honey] (v) — shows where things would go, "
              "then asks: apply? [Y/n]",
    },
    "tut.step3": {
        "de": "3) 🍯  [honey]sortiere[/honey] (s) — räumt die Dateien in "
              "Kategorie-Ordner (Waben) ein.",
        "en": "3) 🍯  [honey]sort[/honey] (s) — files the documents into "
              "category folders (combs).",
    },
    "tut.more": {
        "de": "   Später:  [honey]home[/honey] Übersicht · [honey]scan[/honey] lernt aus "
              "manuellen Moves · [honey]hilfe[/honey] alle Befehle.",
        "en": "   Later:  [honey]home[/honey] overview · [honey]scan[/honey] learns from "
              "manual moves · [honey]help[/honey] all commands.",
    },
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

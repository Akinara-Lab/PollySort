"""Phase 2: ENG Mode — leichtgewichtige i18n (DE/EN)."""

from __future__ import annotations

import bumble.i18n as i18n


def test_language_switch_and_fallback():
    i18n.set_language("de")
    assert i18n.get_language() == "de"
    assert "loslegen" in i18n.t("tut.title").lower()

    i18n.set_language("en")
    assert i18n.get_language() == "en"
    assert i18n.t("tut.title") == "🐝 Get started in 3 steps"
    # Platzhalter werden gefüllt.
    assert i18n.t("inbox.some", n=4) == "4 loose file(s) waiting — type 'sort' (s)"
    # Unbekannter Schlüssel → gibt den Schlüssel zurück (nie ein Crash).
    assert i18n.t("does.not.exist") == "does.not.exist"

    i18n.set_language("de")     # sauber zurücksetzen für andere Tests


def test_english_aliases_exist():
    from bumble.repl import BeehiveShell
    # Englische Befehls-Aliase zeigen auf dieselben Handler wie die deutschen.
    assert BeehiveShell.do_sort is BeehiveShell.do_sortiere
    assert BeehiveShell.do_preview is BeehiveShell.do_vorschau
    assert BeehiveShell.do_list is BeehiveShell.do_liste
    assert BeehiveShell.do_trash is BeehiveShell.do_papierkorb
    assert BeehiveShell.do_language is BeehiveShell.do_sprache

"""Phase 2: ENG Mode — leichtgewichtige i18n (DE/EN)."""

from __future__ import annotations

import pollysort.i18n as i18n


def test_language_switch_and_fallback():
    i18n.set_language("de")
    assert i18n.get_language() == "de"
    assert i18n.t("fr.next.title") == "So geht es los"

    i18n.set_language("en")
    assert i18n.get_language() == "en"
    assert i18n.t("fr.next.title") == "How to get going"
    # Platzhalter werden gefüllt.
    assert i18n.t("inbox.some", n=4) == "4 loose file(s) waiting — type 'sort' (s)"
    # Unbekannter Schlüssel → gibt den Schlüssel zurück (nie ein Crash).
    assert i18n.t("does.not.exist") == "does.not.exist"

    i18n.set_language("de")     # sauber zurücksetzen für andere Tests


def test_every_key_has_both_languages():
    """Jeder Katalog-Eintrag muss DE **und** EN haben.

    Ohne diesen Wächter fällt ein vergessener Schlüssel still auf Deutsch zurück — im
    englischen Erststart fiele das erst dem Nutzer auf.
    """
    missing = [k for k, v in i18n._CATALOG.items() if not v.get("de") or not v.get("en")]
    assert not missing, f"Schlüssel ohne beide Sprachen: {missing}"


def test_placeholders_match_across_languages():
    """DE und EN müssen dieselben Platzhalter benutzen — sonst wirft t() in einer
    Sprache einen KeyError-Fallback und zeigt den Rohtext."""
    import re
    for key, entry in i18n._CATALOG.items():
        de = set(re.findall(r"\{(\w+)\}", entry["de"]))
        en = set(re.findall(r"\{(\w+)\}", entry["en"]))
        assert de == en, f"{key}: DE {sorted(de)} != EN {sorted(en)}"


def test_english_aliases_exist():
    from pollysort.repl import BeehiveShell
    # Englische Befehls-Aliase zeigen auf dieselben Handler wie die deutschen.
    assert BeehiveShell.do_sort is BeehiveShell.do_sortiere
    assert BeehiveShell.do_preview is BeehiveShell.do_vorschau
    assert BeehiveShell.do_list is BeehiveShell.do_liste
    assert BeehiveShell.do_trash is BeehiveShell.do_papierkorb
    assert BeehiveShell.do_language is BeehiveShell.do_sprache

"""Der Alltagspfad spricht die gewählte Sprache (2026-09-10).

Hilfe, unbekannte Befehle, Kopfzeile/Prompt — und die Befehlsnamen, die das README
verspricht, müssen auch existieren. Die Hilfe ist datengetrieben; ein Test stellt sicher,
dass sie keinen Namen nennt, den die Konsole nicht kennt.
"""

from __future__ import annotations

import io
import re

import pollysort.i18n as i18n
from pollysort.console import BeeConsole
from pollysort.repl import BeehiveShell


def _shell() -> BeehiveShell:
    sh = BeehiveShell.__new__(BeehiveShell)     # ohne __init__ (keine globale Config-Kopplung)
    sh.con = BeeConsole(quiet=True)
    sh.hive = None
    sh._theme_pref = "dark"
    return sh


def _help_text(lang: str) -> str:
    from rich.console import Console
    sh = _shell()
    rc = Console(record=True, width=140, file=io.StringIO(), force_terminal=False,
                 color_system=None)
    lines: list[str] = []
    sh.con.raw = lambda *a, **k: rc.print(*a, **k)          # Tabellen wirklich rendern
    sh.con.rule = lambda title="": lines.append(title)
    sh.con.info = lambda msg, *a, **k: lines.append(msg)
    i18n.set_language(lang)
    try:
        sh.do_hilfe("")
    finally:
        i18n.set_language("de")
    return "\n".join(lines) + "\n" + rc.export_text()


def test_help_is_english_in_english_mode():
    text = _help_text("en")
    assert "🐝 Daily" in text and "sort  (s)" in text and "charter [category]" in text
    assert "Täglich" not in text and "sortiere  (s)" not in text
    assert "{year}/{month}" in text                          # kein deutscher Platzhalter


def test_help_is_german_in_german_mode():
    text = _help_text("de")
    assert "Täglich benötigt" in text and "sortiere  (s)" in text and "wabenbau [kategorie]" in text
    assert "{jahr}/{monat}" in text


def test_every_help_row_names_a_real_command():
    """Jeder Name in der Hilfe muss ein echter Befehl sein — sonst schickt die Hilfe
    Nutzer zu einem Wort, das die Konsole nicht kennt (so wie früher 'swarm' im README)."""
    names = {n[3:] for n in dir(BeehiveShell) if n.startswith("do_")}
    for rows in BeehiveShell._HELP.values():
        for de, en, key in rows:
            assert key in i18n._CATALOG, f"Hilfe-Beschreibung fehlt: {key}"
            for spec in (de, en):
                for part in re.split(r"\s+·\s+", spec):
                    first = part.split()[0]
                    assert first in names, f"Hilfe nennt unbekannten Befehl {first!r} ({spec})"


def test_unknown_command_suggests_a_near_match():
    sh = _shell()
    msgs: list[str] = []
    sh.con.error = lambda msg, *a, **k: msgs.append(msg)
    i18n.set_language("en")
    try:
        sh.default("sortire")
        sh.default("xyzzy")
    finally:
        i18n.set_language("de")
    assert "Did you mean" in msgs[0] and "'sortiere'" in msgs[0]
    assert msgs[1].startswith("Unknown:") and "'help'" in msgs[1]


def test_readme_promised_aliases_exist():
    assert BeehiveShell.do_swarm is BeehiveShell.do_schwarm
    assert BeehiveShell.do_charter is BeehiveShell.do_wabenbau
    assert BeehiveShell.do_find is BeehiveShell.do_suche
    assert BeehiveShell.do_search is BeehiveShell.do_suche


def test_header_and_prompt_follow_language():
    sh = _shell()
    i18n.set_language("en")
    try:
        sh._sync_prompt()
        assert "no project" in sh.prompt
        assert "theme " in sh._header_status()
    finally:
        i18n.set_language("de")
    sh._sync_prompt()
    assert "kein Projekt" in sh.prompt


def test_keine_feste_deutsche_meldung_mehr():
    """Wächter (2026-09-24): Jede Konsolen-Meldung und jede Eingabe-Frage läuft über i18n.

    Erlaubt sind nur sprachneutrale Zeilen — Datenzeilen, Emojis, „^C", „Port [587]".
    Wer hier eine Zeile ergänzen muss, sollte zuerst prüfen, ob sie nicht übersetzt gehört.
    """
    import ast
    import re
    from pathlib import Path

    src_root = Path(__file__).resolve().parent.parent / "src" / "pollysort"
    dateien = ["repl.py", "review.py", "daemon.py", "sweeper.py", "recommender.py",
               "swarm/waechterbiene.py", "swarm/baubiene.py", "doctor.py", "pipeline.py"]
    wortmuster = re.compile(r"[A-Za-zÄÖÜäöüß]{3,}")
    # „🩺 Doctor", „Port [587]", [honey]-Markup, „(conf 0.62)" in der Rückfrage-Zeile
    erlaubt = {"Doctor", "Port", "honey", "conf"}
    funde = []
    for rel in dateien:
        src = (src_root / rel).read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(src)):
            if not (isinstance(node, ast.Call) and node.args):
                continue
            f = node.func
            if isinstance(f, ast.Attribute):
                ziel = ast.get_source_segment(src, f.value) or ""
                treffer = (f.attr in ("info", "honey", "ask", "error", "bloom", "celebrate", "raw",
                                      "rule") and "con" in ziel) or f.attr in ("_ask", "_ja",
                                                                               "_ja_default")
            else:
                treffer = isinstance(f, ast.Name) and f.id in ("ask", "input")
            if not treffer:
                continue
            a0 = node.args[0]
            teile = ([a0.value] if isinstance(a0, ast.Constant) and isinstance(a0.value, str)
                     else [v.value for v in a0.values if isinstance(v, ast.Constant)]
                     if isinstance(a0, ast.JoinedStr) else [])
            woerter = set(wortmuster.findall(" ".join(teile))) - erlaubt
            if woerter:
                funde.append(f"{rel}:{node.lineno} {sorted(woerter)[:4]}")
    assert not funde, "Feste Texte ohne i18n:\n" + "\n".join(funde)

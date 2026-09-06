"""Erststart-Assistent (firstrun.py) — Sprache → Darstellung → KI → Überblick.

Der Ablauf ist bewusst ohne Terminal testbar gebaut: alle Außenkontakte (fragen, Ollama
prüfen, Key speichern, Thema anwenden) werden hineingereicht. Diese Tests decken genau
die Entscheidungen ab, bei denen ein Fehler den Nutzer in einer Einstellung landen lässt,
die er nicht gewählt hat — oder in einer, die sofort scheitern würde.
"""

from __future__ import annotations

import pytest

from pollysort import firstrun, i18n


class FakeConsole:
    """Sammelt die Ausgaben, statt sie zu drucken."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def _add(self, msg: str = "", *_a, **_k) -> None:
        self.lines.append(str(msg))

    raw = info = honey = error = ask = bloom = rule = _add

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def scripted(*answers: str):
    """Eine ``ask``-Funktion, die die vorgegebenen Antworten der Reihe nach liefert."""
    queue = list(answers)

    def ask(_prompt: str) -> str:
        if not queue:
            raise AssertionError("Assistent fragt mehr als erwartet")
        return queue.pop(0)

    return ask


@pytest.fixture(autouse=True)
def _reset_language():
    """Die Sprache ist Modulzustand — nach jedem Test sauber zurücksetzen."""
    yield
    i18n.set_language("de")


# --------------------------------------------------------------------------- #
#  Schritt 1 — Sprache
# --------------------------------------------------------------------------- #
def test_language_defaults_to_english_on_enter():
    """Leere Eingabe = Englisch: die Community-Version ist englischsprachig."""
    assert firstrun.step_language(FakeConsole(), scripted("")) == "en"
    assert i18n.get_language() == "en"


@pytest.mark.parametrize("answer", ["2", "de", "deutsch", "German"])
def test_language_accepts_number_and_words(answer):
    assert firstrun.step_language(FakeConsole(), scripted(answer)) == "de"
    assert i18n.get_language() == "de"


def test_language_asks_again_after_nonsense():
    """Unsinn darf NICHT still den Default nehmen — sonst bekommt der Nutzer eine
    Sprache, die er nicht gewählt hat."""
    assert firstrun.step_language(FakeConsole(), scripted("42", "quatsch", "2")) == "de"


# --------------------------------------------------------------------------- #
#  Schritt 2 — Darstellung
# --------------------------------------------------------------------------- #
def test_theme_is_applied_immediately():
    applied: list[str] = []
    theme = firstrun.step_theme(FakeConsole(), scripted("3"), applied.append)
    assert theme == "auto"
    assert applied == ["auto"], "Das Thema muss sofort wirken, nicht erst beim nächsten Befehl"


def test_theme_default_is_dark_and_words_work():
    assert firstrun.step_theme(FakeConsole(), scripted(""), None) == "dark"
    assert firstrun.step_theme(FakeConsole(), scripted("hell"), None) == "light"


# --------------------------------------------------------------------------- #
#  Schritt 3 — KI-Backend
# --------------------------------------------------------------------------- #
def _ai(con, ask, *, ollama=False, key=False, saved=None):
    return firstrun.step_ai(
        con, ask,
        ollama_probe=lambda: ollama,
        has_key=lambda: key,
        save_key=(saved if saved is not None else (lambda _k: True)),
    )


def test_ai_default_prefers_reachable_ollama():
    """Läuft ein lokaler Ollama, ist er die Vorauswahl — gratis, privat, verfügbar."""
    assert _ai(FakeConsole(), scripted(""), ollama=True) == ("ollama", False)


def test_ai_default_is_offline_without_ollama_and_without_key():
    assert _ai(FakeConsole(), scripted("")) == ("offline", False)


def test_ai_default_is_openrouter_when_key_is_on_file():
    assert _ai(FakeConsole(), scripted(""), key=True) == ("openrouter", False)


def test_ai_unreachable_ollama_falls_back_instead_of_failing_later():
    """Wählt der Nutzer Ollama, obwohl keins antwortet, darf das Tool ihn nicht in einen
    Modus schicken, der beim ersten Sortierlauf scheitert."""
    con = FakeConsole()
    assert _ai(con, scripted("2"), ollama=False) == ("offline", False)
    assert "ollama" in con.text.lower()


def test_ai_openrouter_saves_entered_key():
    seen: list[str] = []
    con = FakeConsole()
    result = _ai(con, scripted("3", "  sk-or-testkey  "), saved=lambda k: seen.append(k) or True)
    assert result == ("openrouter", True)
    assert seen == ["sk-or-testkey"], "Der Key muss getrimmt weitergereicht werden"
    assert "sk-or-testkey" not in con.text, "🔒 Der Key darf nie auf der Konsole landen"


def test_ai_empty_key_falls_back_to_offline():
    assert _ai(FakeConsole(), scripted("3", "")) == ("offline", False)


def test_ai_failed_key_save_falls_back_to_offline():
    assert _ai(FakeConsole(), scripted("3", "sk-x"), saved=lambda _k: False) == ("offline", False)


# --------------------------------------------------------------------------- #
#  Gesamtlauf
# --------------------------------------------------------------------------- #
def test_full_run_collects_every_choice():
    con = FakeConsole()
    applied: list[str] = []
    res = firstrun.run(
        con, scripted("2", "2", "1"),          # Deutsch · Hell · Offline
        ollama_probe=lambda: False,
        has_key=lambda: False,
        save_key=lambda _k: True,
        apply_theme=applied.append,
    )
    assert (res.language, res.theme, res.provider, res.key_saved) == ("de", "light", "offline",
                                                                     False)
    assert applied == ["light"]
    # Der Überblick nennt jede getroffene Einstellung und die ersten Handgriffe.
    assert "Deutsch" in con.text and "Hell" in con.text and "Offline" in con.text
    assert "sortiere" in con.text


def test_full_run_is_english_end_to_end():
    con = FakeConsole()
    res = firstrun.run(
        con, scripted("1", "1", "1"),
        ollama_probe=lambda: False, has_key=lambda: False,
        save_key=lambda _k: True, apply_theme=None,
    )
    assert res.language == "en"
    assert "How to get going" in con.text
    assert "Wahl" not in con.text, "Im EN-Modus darf keine deutsche Zeile stehen bleiben"


def test_abort_propagates_and_persists_nothing():
    """Bricht der Nutzer ab (``ask`` wirft), muss das nach oben durchschlagen —
    die REPL schreibt erst NACH einem vollständigen Durchlauf in die Config."""

    class Abort(Exception):
        pass

    def ask(_p: str) -> str:
        raise Abort

    with pytest.raises(Abort):
        firstrun.run(FakeConsole(), ask, ollama_probe=lambda: False,
                     has_key=lambda: False, save_key=lambda _k: True)


# --------------------------------------------------------------------------- #
#  Verdrahtung in der REPL
# --------------------------------------------------------------------------- #
def test_ollama_probe_is_lazy_and_cached(monkeypatch):
    """Die Erreichbarkeits-Prüfung lief früher bei JEDEM Start.

    Ohne laufenden Ollama kostete das jedes Mal den vollen Verbindungs-Timeout, bevor
    überhaupt das Banner erschien. Jetzt wird erst geprüft, wenn jemand die Antwort
    braucht — und danach für die Sitzung gemerkt.
    """
    import pollysort.llm.client as client
    from pollysort.repl import BeehiveShell

    calls: list[int] = []
    monkeypatch.setattr(client, "ollama_available", lambda *_a, **_k: calls.append(1) or True)

    sh = BeehiveShell.__new__(BeehiveShell)
    sh._ollama = None
    assert calls == [], "Beim Bauen der Shell darf noch nichts geprüft werden"

    assert sh._ollama_ready() is True
    assert sh._ollama_ready() is True
    assert len(calls) == 1, "Das Ergebnis muss für die Sitzung gemerkt werden"

    assert sh._ollama_ready(refresh=True) is True
    assert len(calls) == 2, "Ein bewusster Moduswechsel muss frisch prüfen"


def test_yes_no_defaults_and_english_answers(monkeypatch):
    """[J/n] und [j/N] müssen sich unterscheiden — und 'yes' muss im EN-Modus wirken."""
    import builtins

    from pollysort.console import BeeConsole
    from pollysort.repl import BeehiveShell

    sh = BeehiveShell.__new__(BeehiveShell)
    sh.con = BeeConsole(quiet=True)

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert sh._ja_default("[Y/n]: ") is True
    assert sh._ja("[y/N]: ") is False

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "yes")
    assert sh._ja("[y/N]: ") is True

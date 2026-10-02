"""Erststart-Assistent — die globale Grundeinrichtung vor dem ersten Projekt.

Fünf Schritte in fester Reihenfolge: **Sprache → Darstellung → KI-Backend → BeeNara →
Überblick**.

Die Reihenfolge ist Absicht:

* **Sprache zuerst**, damit jede weitere Frage schon in der gewählten Sprache steht.
  Vorher wird bewusst zweisprachig gefragt — der Nutzer soll nicht raten müssen.
* **Darstellung sofort angewandt**, damit die Wirkung sichtbar ist, bevor es weitergeht.
* **KI-Backend mit ehrlicher Verfügbarkeits-Anzeige**: Ollama wird genau hier einmal
  geprüft (nicht bei jedem Start), und eine nicht erreichbare Option wird als solche
  gezeigt statt angeboten und dann zu scheitern.
* **BeeNara nur auf Zusage**: Das lokale Entscheider-Modell ist ein Download von rund
  370 MB. Er läuft nur, wenn der Nutzer ihn ausdrücklich wählt — Enter heißt „später".
* **Überblick am Ende** — was ist eingestellt, was kommt als Nächstes.

Das Modul ist bewusst frei von Terminal- und Shell-Details: alles, was der Assistent von
außen braucht (fragen, Ollama prüfen, Key speichern, Thema anwenden, Modell laden), wird
hineingereicht.
Dadurch ist der komplette Ablauf ohne echtes Terminal testbar — vorher steckte er
untestbar in der REPL.

🔒 Wachssiegel: Der API-Key wird nur über die hereingereichte ``save_key``-Funktion
weitergegeben (die ihn nach ``~/.beehive/credentials``, chmod 600, schreibt). Er wird hier
nie geloggt, nie ausgegeben und nie in einen Prompt geschrieben.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from . import config, i18n

#: Reihenfolge der angebotenen Optionen — Index+1 ist die Nummer, die der Nutzer tippt.
LANGUAGES = ("en", "de")
THEMES = ("dark", "light", "auto")
PROVIDERS = ("offline", "ollama", "openrouter")

_STEPS = 5


@dataclass
class FirstRun:
    """Was der Nutzer in der Grundeinrichtung gewählt hat."""

    language: str = "en"
    theme: str = "dark"
    provider: str = "offline"
    key_saved: bool = False
    beenara: bool = False          # liegt das Modell nach der Einrichtung vollständig da?


# --------------------------------------------------------------------------- #
#  Eingabe-Helfer
# --------------------------------------------------------------------------- #
def _choose(ask: Callable[[str], str], prompt: str, *, count: int, default: int,
            words: dict[str, int] | None = None) -> int:
    """Eine nummerierte Auswahl abfragen und die Nummer (1-basiert) zurückgeben.

    Leere Eingabe = ``default``. Neben der Zahl werden auch Stichwörter akzeptiert
    (``words``), damit „english"/„offline" genauso funktionieren wie „1". Unsinnige
    Eingaben fragen erneut statt still den Default zu nehmen — sonst landet der Nutzer
    in einer Einstellung, die er nicht gewählt hat.
    """
    words = words or {}
    for _ in range(3):
        raw = ask(prompt).strip().lower()
        if not raw:
            return default
        if raw in words:
            return words[raw]
        if raw.isdigit() and 1 <= int(raw) <= count:
            return int(raw)
    return default


def _label(con, text: str) -> None:
    """Eine eingerückte Zeile des Assistenten ausgeben."""
    con.raw(f"      {text}")


# --------------------------------------------------------------------------- #
#  Die Schritte
# --------------------------------------------------------------------------- #
def step_language(con, ask: Callable[[str], str]) -> str:
    """Schritt 1 — Sprache. Zweisprachig gefragt, weil die Wahl ja erst hier fällt."""
    con.honey(f"1/{_STEPS} · Language / Sprache", "🌍")
    _label(con, "[1] English      [2] Deutsch")
    n = _choose(ask, "      Choice / Wahl [1]: ", count=2, default=1,
                words={"en": 1, "eng": 1, "english": 1, "englisch": 1,
                       "de": 2, "ger": 2, "deutsch": 2, "german": 2})
    lang = LANGUAGES[n - 1]
    i18n.set_language(lang)
    return lang


def step_theme(con, ask: Callable[[str], str],
               apply_theme: Callable[[str], str] | None = None) -> str:
    """Schritt 2 — Darstellung. Wird sofort angewandt, damit man sie sieht."""
    con.raw("")
    con.honey(f"2/{_STEPS} · {i18n.t('fr.theme.title')}", "🎨")
    _label(con, f"[1] {i18n.t('fr.theme.dark')}")
    _label(con, f"[2] {i18n.t('fr.theme.light')}")
    _label(con, f"[3] {i18n.t('fr.theme.auto')}")
    n = _choose(ask, "      " + i18n.t("fr.choice", default=1), count=3, default=1,
                words={"dark": 1, "dunkel": 1, "light": 2, "hell": 2,
                       "auto": 3, "automatik": 3, "automatisch": 3})
    theme = THEMES[n - 1]
    if apply_theme is not None:
        apply_theme(theme)          # sofort sichtbar — nicht erst beim nächsten Befehl
    return theme


def step_ai(con, ask: Callable[[str], str], *,
            ollama_probe: Callable[[], bool],
            has_key: Callable[[], bool],
            save_key: Callable[[str], bool]) -> tuple[str, bool]:
    """Schritt 3 — KI-Backend. Gibt ``(provider, key_saved)`` zurück.

    Ollama wird **hier** geprüft (einmalig, nicht bei jedem Start). Eine nicht erreichbare
    Option wird sichtbar als nicht erreichbar markiert, statt sie anzubieten und dann im
    ersten Sortierlauf zu scheitern.
    """
    con.raw("")
    con.honey(f"3/{_STEPS} · {i18n.t('fr.ai.title')}", "🧠")

    ollama = bool(ollama_probe())
    key = bool(has_key())
    ollama_tag = i18n.t("fr.ai.found") if ollama else i18n.t("fr.ai.notfound")
    key_tag = i18n.t("fr.ai.keyset") if key else i18n.t("fr.ai.keyneeded")

    # Auf feste Breite gepolstert, damit die Status-Marker untereinander stehen und
    # die Zeile auch in einem 80-Spalten-Terminal nicht mitten im Marker umbricht.
    _label(con, f"[1] {i18n.t('fr.ai.offline')}")
    _label(con, f"[2] {i18n.t('fr.ai.ollama'):<44} {ollama_tag}")
    _label(con, f"[3] {i18n.t('fr.ai.openrouter'):<44} {key_tag}")

    # Die beste *verfügbare* Option vorschlagen — nie eine, die sofort scheitern würde.
    default = 2 if ollama else (3 if key else 1)
    n = _choose(ask, "      " + i18n.t("fr.choice", default=default), count=3, default=default,
                words={w: PROVIDERS.index(p) + 1 for w, p in config.MODUS_WOERTER.items()})
    provider = PROVIDERS[n - 1]

    if provider == "ollama" and not ollama:
        con.error(i18n.t("fr.ai.ollama_missing"))
        _label(con, i18n.t("fr.ai.ollama_hint"))
        return "offline", False

    if provider == "openrouter" and not key:
        con.raw("")
        _label(con, i18n.t("fr.ai.key_where"))
        entered = ask("      🔑 " + i18n.t("fr.ai.key_prompt")).strip()
        if not entered:
            con.info(i18n.t("fr.ai.key_skipped"), "🐝")
            return "offline", False
        if not save_key(entered):
            con.error(i18n.t("fr.ai.key_failed"))
            return "offline", False
        con.honey(i18n.t("fr.ai.key_saved"), "✅")
        return "openrouter", True

    return provider, False


def step_beenara(con, ask: Callable[[str], str], *,
                 present: Callable[[], bool],
                 pull: Callable[[], bool]) -> bool:
    """Schritt 4 — BeeNara von Hugging Face laden? Gibt zurück, ob das Modell danach da ist.

    Vorauswahl ist „später": Ein Download von 370 MB passiert nie, nur weil jemand die
    Einrichtung mit Enter durchklickt. Liegt das Modell schon da, wird nicht gefragt.
    """
    from .beenara import REPO, UNGEFAEHR_MB
    con.raw("")
    con.honey(f"4/{_STEPS} · {i18n.t('fr.bn.title')}", "🐝")
    if present():
        _label(con, i18n.t("fr.bn.present"))
        return True
    _label(con, i18n.t("fr.bn.what"))
    _label(con, i18n.t("fr.bn.size", repo=REPO, mb=UNGEFAEHR_MB))
    _label(con, f"[1] {i18n.t('fr.bn.now')}")
    _label(con, f"[2] {i18n.t('fr.bn.later')}")
    n = _choose(ask, "      " + i18n.t("fr.choice", default=2), count=2, default=2,
                words={"j": 1, "ja": 1, "y": 1, "yes": 1, "laden": 1, "pull": 1,
                       "n": 2, "nein": 2, "no": 2, "später": 2, "spaeter": 2, "later": 2})
    if n == 2:
        _label(con, i18n.t("fr.bn.skipped"))
        return False
    return bool(pull())


def show_next_steps(con) -> None:
    """Die drei ersten Handgriffe zeigen (ersetzt das frühere Extra-Tutorial).

    Steht am Ende der Einrichtung — und wird für Bestandsnutzer, die die Einrichtung
    schon hinter sich haben, das Tutorial aber noch nicht gesehen haben, einzeln gerufen.
    """
    con.raw("")
    con.honey(i18n.t("fr.next.title"), "🚀")
    _label(con, i18n.t("fr.next.step1"))
    _label(con, i18n.t("fr.next.step2"))
    _label(con, i18n.t("fr.next.step3"))
    _label(con, i18n.t("fr.next.hint"))


def step_summary(con, result: FirstRun) -> None:
    """Schritt 5 — Überblick: was ist jetzt eingestellt, was kommt als Nächstes."""
    lang_lbl = "English" if result.language == "en" else "Deutsch"
    theme_lbl = i18n.t(f"fr.short.{result.theme}")
    ai_lbl = i18n.t(f"fr.short.{result.provider}")

    con.raw("")
    con.honey(f"5/{_STEPS} · {i18n.t('fr.done.title')}", "✅")
    _label(con, i18n.t("fr.done.summary", language=lang_lbl, theme=theme_lbl, ai=ai_lbl))
    _label(con, i18n.t("fr.done.bn_yes" if result.beenara else "fr.done.bn_no"))
    _label(con, i18n.t("fr.done.change"))
    show_next_steps(con)


# --------------------------------------------------------------------------- #
#  Der Assistent
# --------------------------------------------------------------------------- #
def run(con, ask: Callable[[str], str], *,
        ollama_probe: Callable[[], bool],
        has_key: Callable[[], bool],
        save_key: Callable[[str], bool],
        beenara_present: Callable[[], bool],
        beenara_pull: Callable[[], bool],
        apply_theme: Callable[[str], str] | None = None) -> FirstRun:
    """Die Grundeinrichtung durchlaufen und die Auswahl zurückgeben.

    Schreibt **nichts** in die Config — das macht der Aufrufer, damit ein Abbruch
    (``AbortAction`` aus ``ask``) sauber nach oben durchschlägt und nichts halb
    Gespeichertes hinterlässt. Der BeeNara-Download ist die Ausnahme: Er ist der letzte
    Schritt mit einer Frage, und ``beenara_pull`` meldet Fehler und Strg-C selbst.
    """
    con.rule("Setup · Einrichtung")
    result = FirstRun()
    result.language = step_language(con, ask)
    result.theme = step_theme(con, ask, apply_theme)
    result.provider, result.key_saved = step_ai(
        con, ask, ollama_probe=ollama_probe, has_key=has_key, save_key=save_key)
    result.beenara = step_beenara(con, ask, present=beenara_present, pull=beenara_pull)
    step_summary(con, result)
    con.rule()
    return result

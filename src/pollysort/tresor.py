"""Tresor — Zugangsdaten in der Anmeldeinformationsverwaltung des Betriebssystems.

🔒 Wachssiegel, zweite Stufe: Der OpenRouter-Schlüssel, das Discord-Bot-Token und das
E-Mail-Passwort lagen bisher im Klartext in ``~/.pollysort`` — lesbar für jedes Programm und
jede Datensicherung, die an den Benutzerordner kommt. Hier wandern sie in den Speicher, den das
Betriebssystem dafür hat: die Windows-Anmeldeinformationsverwaltung, den macOS-Schlüsselbund
oder den Schlüsselbund des Linux-Desktops (Secret Service). Den Zugriff übernimmt das Paket
``keyring``.

In der Datei bleibt dann nur der Platzhalter :data:`IM_TRESOR` stehen — er sagt „der Wert liegt
im Tresor". Gibt es keinen Tresor (Server ohne Desktop, Container, ``keyring`` fehlt, per
``POLLYSORT_TRESOR=aus`` abgeschaltet), bleibt alles beim Alten: Klartext in der Datei, und
die Oberflächen sagen das dazu. **Ein Geheimnis geht dabei nie verloren:** Der Klartext
verschwindet erst aus der Datei, wenn der Wert nachweislich wieder aus dem Tresor herauskommt.

Die Einträge gehören zu einer Ablage (``POLLYSORT_HOME``). Die übliche Ablage ``~/.pollysort``
heißt im Tresor schlicht „PollySort"; jede andere bekommt ihren Pfad in den Namen, damit
Testläufe und Zweit-Installationen die echten Einträge nicht anfassen.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import config

#: Steht in der Datei anstelle des Geheimnisses: „der Wert liegt im Tresor".
IM_TRESOR = "@tresor"

# Namen der Einträge (im Windows-Tresor zu sehen als „<name>@PollySort").
OPENROUTER = "openrouter-schluessel"
DISCORD_TOKEN = "discord-bot-token"
EMAIL_PASSWORT = "email-passwort"

#: Umgebungsvariable, die den Tresor abschaltet (Container, Skripte, eigene Vorliebe).
AUS_VARIABLE = "POLLYSORT_TRESOR"
_AUS_WERTE = ("aus", "off", "0", "nein", "no", "datei", "file")

#: Hat der Tresor in diesem Programmlauf einmal beim Lesen versagt, fasst ihn bis zum Neustart
#: niemand mehr an — sonst würde ein leer gelesener Wert beim nächsten Speichern den echten
#: Eintrag überschreiben oder löschen.
_gestoert = False


def _pruefen() -> tuple[object | None, str]:
    """Das ``keyring``-Modul, wenn ein echter Speicher dahintersteht — sonst ``None`` mit Grund.

    Gründe: ``aus`` (abgeschaltet), ``fehlt`` (Paket nicht installiert), ``kein_speicher``
    (kein Schlüsselbund auf diesem System), ``gestoert`` (Lesefehler in diesem Lauf).
    """
    if os.environ.get(AUS_VARIABLE, "").strip().lower() in _AUS_WERTE:
        return None, "aus"
    if _gestoert:
        return None, "gestoert"
    try:
        import keyring
        from keyring.backends import fail, null
    except ImportError:
        return None, "fehlt"
    try:
        speicher = keyring.get_keyring()
    except Exception:
        return None, "kein_speicher"
    if isinstance(speicher, (fail.Keyring, null.Keyring)):
        return None, "kein_speicher"
    return keyring, ""


def verfuegbar() -> bool:
    """Gibt es auf diesem Rechner gerade einen Tresor, in den geschrieben werden kann?"""
    return _pruefen()[0] is not None


def grund() -> str:
    """Warum es keinen Tresor gibt (``""``, wenn es einen gibt) — siehe :func:`_pruefen`."""
    return _pruefen()[1]


def ort() -> str:
    """Wie der Tresor auf diesem Betriebssystem heißt — für Meldungen an den Menschen."""
    from . import i18n
    if sys.platform == "win32":
        return i18n.t("tresor.ort.windows")
    if sys.platform == "darwin":
        return i18n.t("tresor.ort.mac")
    return i18n.t("tresor.ort.linux")


def dienst() -> str:
    """Unter welchem Namen die Einträge dieser Ablage im Tresor stehen."""
    home = Path(config.POLLYSORT_HOME)
    standard = Path.home() / ".pollysort"
    if os.path.normcase(os.path.abspath(home)) == os.path.normcase(os.path.abspath(standard)):
        return "PollySort"
    return f"PollySort ({os.path.abspath(home)})"


def lesen(name: str) -> str | None:
    """Ein Geheimnis holen. ``None`` = nicht da oder Tresor nicht benutzbar."""
    global _gestoert
    kr, _ = _pruefen()
    if kr is None:
        return None
    try:
        return kr.get_password(dienst(), name) or None
    except Exception:
        _gestoert = True
        return None


def schreiben(name: str, wert: str) -> bool:
    """Ein Geheimnis ablegen. ``True`` nur, wenn es danach nachweislich wieder herauskommt."""
    kr, _ = _pruefen()
    if kr is None or not wert:
        return False
    try:
        kr.set_password(dienst(), name, wert)
        return kr.get_password(dienst(), name) == wert
    except Exception:
        # Zu lang für den Tresor, gesperrt, abgelehnt — der Aufrufer bleibt bei der Datei.
        return False


def loeschen(name: str) -> None:
    """Einen Eintrag entfernen, falls es ihn gibt. Fehler sind hier kein Thema."""
    kr, _ = _pruefen()
    if kr is None:
        return
    try:
        kr.delete_password(dienst(), name)
    except Exception:
        pass


def ablegen(name: str, wert: str) -> str:
    """Ein Geheimnis unterbringen und zurückgeben, was dafür **in die Datei** gehört.

    - Platzhalter (beim Laden nicht lesbar gewesen): unverändert durchreichen, Tresor in Ruhe lassen.
    - leer: Eintrag im Tresor entfernen, in der Datei steht nichts.
    - sonst: in den Tresor → Platzhalter; klappt das nicht → der Klartext wie bisher.
    """
    if wert == IM_TRESOR:
        return wert
    if not wert:
        loeschen(name)
        return ""
    return IM_TRESOR if schreiben(name, wert) else wert


def ablageort(roh: str, name: str) -> str:
    """Wo liegt das Geheimnis, dessen Datei-Eintrag ``roh`` lautet?

    ``"tresor"`` · ``"datei"`` (Klartext) · ``"unlesbar"`` (Platzhalter, aber der Tresor gibt
    nichts her) · ``""`` (keins hinterlegt).
    """
    if not roh:
        return ""
    if roh != IM_TRESOR:
        return "datei"
    return "tresor" if lesen(name) else "unlesbar"


def lage_text(lage: str, datei: Path | str) -> str:
    """Ein Satz für den Menschen zu einem Ablageort aus :func:`ablageort` (``""`` → ``""``).

    Beim Klartext steht der Grund dabei — „liegt offen herum" ohne „warum" hilft niemandem.
    """
    from . import i18n
    if lage == "tresor":
        return i18n.t("tresor.lage.tresor", ort=ort())
    if lage == "unlesbar":
        return i18n.t("tresor.lage.unlesbar", ort=ort())
    if lage == "datei":
        return i18n.t("tresor.lage.datei", datei=datei,
                      grund=i18n.t("tresor.grund." + (grund() or "abgelehnt")))
    return ""


#: Reihenfolge, in der mehrere Ablageorte gemeldet werden — das Dringendste zuerst.
LAGEN = ("unlesbar", "datei", "tresor")

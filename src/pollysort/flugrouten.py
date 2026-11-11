"""Flugrouten — Konfiguration der Kommunikations-Kanäle der Wächterbienen (§v0.3).

🔒 DAS WACHSSIEGEL (harte Sicherheitsregel):
Diese Datei beschreibt die Kanäle (Discord-Channel, E-Mail-Adresse, Mailserver). Sie liegt
**global** in ``~/.pollysort/flugrouten.toml`` (chmod 600 best-effort), NIE im Projekt-``.honig/``,
und wird **niemals** in einen LLM-Prompt/-Payload eingebaut oder im Klartext geloggt.

Die beiden Geheimnisse (Discord-Bot-Token, E-Mail-Passwort) liegen im Tresor des
Betriebssystems (:mod:`pollysort.tresor`); in der Datei steht dann nur der Platzhalter
``@tresor``. Ohne Tresor stehen sie wie früher im Klartext hier. Zusätzlich sind sie per
Umgebungsvariable überschreibbar (``POLLYSORT_DISCORD_TOKEN``, ``POLLYSORT_EMAIL_PASSWORD``;
die Altnamen ``BEEHIVE_…`` gelten weiter) und werden dann nirgends gespeichert.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import config, tresor
from .config import _toml_val

# SMTP-Presets für den E-Mail-Kanal: name -> (host, port, use_tls)
EMAIL_PRESETS: dict[str, tuple[str, int, bool]] = {
    "gmail": ("smtp.gmail.com", 587, True),
    "outlook": ("smtp-mail.outlook.com", 587, True),
}

# Feld-Namen, die als Geheimnis gelten (für Log-Redaction & Anzeige-Maskierung).
SECRET_HINTS = ("token", "password", "passwort", "secret", "key", "auth", "credential")


def is_secret_key(name: str) -> bool:
    n = str(name).lower()
    return any(h in n for h in SECRET_HINTS)


def mask(value: str) -> str:
    """Ein Geheimnis für die Anzeige maskieren (nur die letzten 4 Zeichen bleiben)."""
    v = str(value or "")
    if not v:
        return "—"
    return "****" if len(v) <= 4 else "****" + v[-4:]


# ---------------------------------------------------------------------------
# Config-Struktur
# ---------------------------------------------------------------------------
@dataclass
class DiscordConfig:
    enabled: bool = False
    bot_token: str = ""          # SECRET — im Speicher der Wert, in der Datei meist "@tresor"
    channel_id: str = ""


@dataclass
class EmailConfig:
    enabled: bool = False
    provider: str = ""           # gmail | outlook | custom
    address: str = ""            # PII
    password: str = ""           # SECRET (App-Passwort empfohlen) — wie bot_token
    smtp_host: str = ""
    smtp_port: int = 587
    use_tls: bool = True
    recipient: str = ""          # leer = an die eigene Adresse


@dataclass
class CalendarConfig:
    enabled: bool = False
    kind: str = "ical"           # ohne Funktion; bleibt nur, damit alte Dateien lesbar sind


@dataclass
class Flugrouten:
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    calendar: CalendarConfig = field(default_factory=CalendarConfig)

    def any_enabled(self) -> bool:
        return self.discord.enabled or self.email.enabled


def default_path() -> Path:
    """Global, im Benutzerprofil — bewusst NICHT im Projekt-.honig/ (Wachssiegel)."""
    return config.POLLYSORT_HOME / "flugrouten.toml"


# ---------------------------------------------------------------------------
# Effektive Secrets (Env hat Vorrang und wird nie persistiert)
# ---------------------------------------------------------------------------
def _aus_umgebung(name: str, gespeichert: str) -> str:
    """``POLLYSORT_<name>`` vor dem Altnamen ``BEEHIVE_<name>`` vor dem gespeicherten Wert."""
    for praefix in ("POLLYSORT_", "BEEHIVE_"):
        wert = os.environ.get(praefix + name, "").strip()
        if wert:
            return wert
    # Ein Platzhalter, den der Tresor nicht auflösen konnte, ist kein Geheimnis.
    return "" if gespeichert == tresor.IM_TRESOR else gespeichert.strip()


def discord_token(fr: Flugrouten) -> str:
    return _aus_umgebung("DISCORD_TOKEN", fr.discord.bot_token)


def email_password(fr: Flugrouten) -> str:
    return _aus_umgebung("EMAIL_PASSWORD", fr.email.password)


# ---------------------------------------------------------------------------
# Laden / Speichern
# ---------------------------------------------------------------------------
#: Dateien, deren Klartext-Geheimnisse in diesem Programmlauf schon einmal umgezogen werden
#: sollten — klappt es nicht (Wert zu lang, Tresor lehnt ab), probiert nicht jedes Laden es neu.
_UMZUG_VERSUCHT: set[str] = set()


def _roh(path: Path) -> dict:
    """Die Datei so, wie sie dasteht — ``{}`` bei fehlender oder defekter Datei."""
    if not path.exists():
        return {}
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except (tomllib.TOMLDecodeError, OSError):
        return {}                        # defektes File blockiert nie den Start


def _aus_tresor(name: str, roh: str) -> str:
    """Den Platzhalter gegen den Wert aus dem Tresor tauschen.

    Gibt der Tresor nichts her, bleibt der Platzhalter stehen: So schreibt ein späteres
    Speichern ihn unverändert zurück, statt den Eintrag im Tresor zu löschen.
    """
    if roh != tresor.IM_TRESOR:
        return roh
    return tresor.lesen(name) or roh


def ablage(path: Path | None = None) -> dict[str, str]:
    """Wo die Geheimnisse der Kanäle liegen: je ``tresor`` · ``datei`` · ``unlesbar`` · ``""``."""
    path = path or default_path()
    load_flugrouten(path)                # erst umziehen, dann nachsehen
    data = _roh(path)
    return {
        "discord": tresor.ablageort(str(data.get("discord", {}).get("bot_token", "")),
                                    tresor.DISCORD_TOKEN),
        "email": tresor.ablageort(str(data.get("email", {}).get("password", "")),
                                  tresor.EMAIL_PASSWORT),
    }


def load_flugrouten(path: Path | None = None) -> Flugrouten:
    path = path or default_path()
    fr = Flugrouten()
    data = _roh(path)
    if not data:
        return fr
    d = data.get("discord", {})
    e = data.get("email", {})
    c = data.get("calendar", {})
    fr.discord = DiscordConfig(
        enabled=bool(d.get("enabled", False)),
        bot_token=str(d.get("bot_token", "")),
        channel_id=str(d.get("channel_id", "")),
    )
    fr.email = EmailConfig(
        enabled=bool(e.get("enabled", False)),
        provider=str(e.get("provider", "")),
        address=str(e.get("address", "")),
        password=str(e.get("password", "")),
        smtp_host=str(e.get("smtp_host", "")),
        smtp_port=int(e.get("smtp_port", 587)),
        use_tls=bool(e.get("use_tls", True)),
        recipient=str(e.get("recipient", "")),
    )
    fr.calendar = CalendarConfig(
        enabled=bool(c.get("enabled", False)),
        kind=str(c.get("kind", "ical")),
    )
    klartext = any(w and w != tresor.IM_TRESOR for w in (fr.discord.bot_token, fr.email.password))
    fr.discord.bot_token = _aus_tresor(tresor.DISCORD_TOKEN, fr.discord.bot_token)
    fr.email.password = _aus_tresor(tresor.EMAIL_PASSWORT, fr.email.password)
    # Umzug: Steht noch ein Geheimnis im Klartext da und gibt es einen Tresor, schreibt ein
    # Speichern es dorthin und lässt in der Datei nur den Platzhalter zurück.
    if klartext and str(path) not in _UMZUG_VERSUCHT and tresor.verfuegbar():
        _UMZUG_VERSUCHT.add(str(path))
        try:
            save_flugrouten(fr, path)
        except OSError:
            pass                         # Datei nicht schreibbar → sie bleibt, wie sie ist
    return fr


def save_flugrouten(fr: Flugrouten, path: Path | None = None) -> None:
    path = path or default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    d, e, c = fr.discord, fr.email, fr.calendar
    # Die Geheimnisse gehen in den Tresor; in der Datei steht dann nur der Platzhalter. Ohne
    # Tresor (oder wenn er ablehnt) bleibt der Klartext — verloren geht so oder so nichts.
    token = tresor.ablegen(tresor.DISCORD_TOKEN, d.bot_token)
    passwort = tresor.ablegen(tresor.EMAIL_PASSWORT, e.password)
    content = (
        "# PollySort — Flugrouten der Wächterbienen (§v0.3)\n"
        "# 🔒 Wachssiegel: Zugangsdaten. Wird NIE an ein LLM übergeben oder im Klartext geloggt.\n"
        f'# "{tresor.IM_TRESOR}" heißt: Der Wert liegt im Tresor des Betriebssystems, nicht hier.\n'
        "# Secrets via Env überschreibbar: POLLYSORT_DISCORD_TOKEN, POLLYSORT_EMAIL_PASSWORD.\n\n"
        "[discord]\n"
        f"enabled    = {_toml_val(d.enabled)}\n"
        f"bot_token  = {_toml_val(token)}\n"
        f"channel_id = {_toml_val(d.channel_id)}\n\n"
        "[email]\n"
        f"enabled   = {_toml_val(e.enabled)}\n"
        f"provider  = {_toml_val(e.provider)}\n"
        f"address   = {_toml_val(e.address)}\n"
        f"password  = {_toml_val(passwort)}\n"
        f"smtp_host = {_toml_val(e.smtp_host)}\n"
        f"smtp_port = {_toml_val(e.smtp_port)}\n"
        f"use_tls   = {_toml_val(e.use_tls)}\n"
        f"recipient = {_toml_val(e.recipient)}\n\n"
        "[calendar]\n"
        f"enabled = {_toml_val(c.enabled)}\n"
        f"kind    = {_toml_val(c.kind)}\n"
    )
    path.write_text(content, encoding="utf-8")
    try:
        os.chmod(path, 0o600)            # best effort; unter Windows teils No-Op
    except OSError:
        pass

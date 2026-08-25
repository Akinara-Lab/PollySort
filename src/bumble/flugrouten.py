"""Flugrouten — Konfiguration der Kommunikations-Kanäle der Wächterbienen (§v0.3).

🔒 DAS WACHSSIEGEL (harte Sicherheitsregel):
Diese Datei hält Zugangsdaten (Discord-Bot-Token, E-Mail-Adresse/-Passwort). Sie liegt
**global** in ``~/.beehive/flugrouten.toml`` (chmod 600 best-effort), NIE im Projekt-``.honig/``,
und wird **niemals** in einen LLM-Prompt/-Payload eingebaut oder im Klartext geloggt.
Secrets sind zusätzlich per Umgebungsvariable überschreibbar (``BEEHIVE_DISCORD_TOKEN``,
``BEEHIVE_EMAIL_PASSWORD``) und werden dann nie auf Platte geschrieben.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import config
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
    bot_token: str = ""          # SECRET
    channel_id: str = ""


@dataclass
class EmailConfig:
    enabled: bool = False
    provider: str = ""           # gmail | outlook | custom
    address: str = ""            # PII
    password: str = ""           # SECRET (App-Passwort empfohlen)
    smtp_host: str = ""
    smtp_port: int = 587
    use_tls: bool = True
    recipient: str = ""          # leer = an die eigene Adresse


@dataclass
class CalendarConfig:
    enabled: bool = False
    kind: str = "ical"           # Platzhalter — Sync-Anbindung folgt später


@dataclass
class Flugrouten:
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    calendar: CalendarConfig = field(default_factory=CalendarConfig)

    def any_enabled(self) -> bool:
        return self.discord.enabled or self.email.enabled


def default_path() -> Path:
    """Global, im Benutzerprofil — bewusst NICHT im Projekt-.honig/ (Wachssiegel)."""
    return config.BEEHIVE_HOME / "flugrouten.toml"


# ---------------------------------------------------------------------------
# Effektive Secrets (Env hat Vorrang und wird nie persistiert)
# ---------------------------------------------------------------------------
def discord_token(fr: Flugrouten) -> str:
    return os.environ.get("BEEHIVE_DISCORD_TOKEN", fr.discord.bot_token).strip()


def email_password(fr: Flugrouten) -> str:
    return os.environ.get("BEEHIVE_EMAIL_PASSWORD", fr.email.password).strip()


# ---------------------------------------------------------------------------
# Laden / Speichern
# ---------------------------------------------------------------------------
def load_flugrouten(path: Path | None = None) -> Flugrouten:
    path = path or default_path()
    fr = Flugrouten()
    if not path.exists():
        return fr
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (tomllib.TOMLDecodeError, OSError):
        return fr                        # defektes File blockiert nie den Start
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
    return fr


def save_flugrouten(fr: Flugrouten, path: Path | None = None) -> None:
    path = path or default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    d, e, c = fr.discord, fr.email, fr.calendar
    content = (
        "# Bumble Beebliothek — Flugrouten der Wächterbienen (§v0.3)\n"
        "# 🔒 Wachssiegel: Zugangsdaten. Wird NIE an ein LLM übergeben oder im Klartext geloggt.\n"
        "# Secrets via Env überschreibbar: BEEHIVE_DISCORD_TOKEN, BEEHIVE_EMAIL_PASSWORD.\n\n"
        "[discord]\n"
        f"enabled    = {_toml_val(d.enabled)}\n"
        f"bot_token  = {_toml_val(d.bot_token)}\n"
        f"channel_id = {_toml_val(d.channel_id)}\n\n"
        "[email]\n"
        f"enabled   = {_toml_val(e.enabled)}\n"
        f"provider  = {_toml_val(e.provider)}\n"
        f"address   = {_toml_val(e.address)}\n"
        f"password  = {_toml_val(e.password)}\n"
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

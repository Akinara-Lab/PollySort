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


@dataclass(frozen=True)
class Anbieter:
    """Ein E-Mail-Anbieter mit seinem Postausgangsserver (SMTP).

    Port 587 wechselt per STARTTLS in die Verschlüsselung, Port 465 spricht von Anfang an
    verschlüsselt — beides kann :class:`pollysort.swarm.kanaele.EmailKanal`. ``hinweis`` ist
    ein Text-Schlüssel: was man bei diesem Anbieter wissen muss, damit die Anmeldung klappt.
    """

    name: str
    host: str
    port: int
    hinweis: str = ""
    imap: str = ""               # Posteingangsserver (IMAP, Port 993) — zum Abholen von Anhängen


#: Die in Deutschland üblichen Anbieter. Alles andere geht über „custom" (Server und Port frei).
EMAIL_ANBIETER: dict[str, Anbieter] = {
    "gmail": Anbieter("Gmail", "smtp.gmail.com", 587, "anbieter.hinweis.gmail", "imap.gmail.com"),
    "outlook": Anbieter("Outlook.com / Hotmail", "smtp-mail.outlook.com", 587,
                        "r.routes.outlook_hint", "outlook.office365.com"),
    "microsoft365": Anbieter("Microsoft 365", "smtp.office365.com", 587,
                             "anbieter.hinweis.microsoft365", "outlook.office365.com"),
    "gmx": Anbieter("GMX", "mail.gmx.net", 587, "anbieter.hinweis.gmx", "imap.gmx.net"),
    "webde": Anbieter("WEB.DE", "smtp.web.de", 587, "anbieter.hinweis.webde", "imap.web.de"),
    "t-online": Anbieter("T-Online", "securesmtp.t-online.de", 465, "anbieter.hinweis.t-online",
                         "secureimap.t-online.de"),
    "freenet": Anbieter("freenet", "mx.freenet.de", 587, imap="mx.freenet.de"),
    "posteo": Anbieter("Posteo", "posteo.de", 587, imap="posteo.de"),
    "mailbox": Anbieter("mailbox.org", "smtp.mailbox.org", 465, imap="imap.mailbox.org"),
    "icloud": Anbieter("iCloud Mail", "smtp.mail.me.com", 587, "anbieter.hinweis.icloud",
                       "imap.mail.me.com"),
    "yahoo": Anbieter("Yahoo Mail", "smtp.mail.yahoo.com", 465, "anbieter.hinweis.yahoo",
                      "imap.mail.yahoo.com"),
    "ionos": Anbieter("IONOS (1&1)", "smtp.ionos.de", 587, imap="imap.ionos.de"),
    "strato": Anbieter("Strato", "smtp.strato.de", 465, imap="imap.strato.de"),
}

# Ältere Schreibweise derselben Liste: name -> (host, port, use_tls).
EMAIL_PRESETS: dict[str, tuple[str, int, bool]] = {
    kurz: (a.host, a.port, True) for kurz, a in EMAIL_ANBIETER.items()
}


def anbieter_fuer_host(host: str) -> Anbieter | None:
    """Der bekannte Anbieter zu einem Mailserver (Ausgang oder Eingang) — für Hinweise bei
    Anmeldefehlern."""
    host = (host or "").strip().lower()
    return next((a for a in EMAIL_ANBIETER.values() if host in (a.host, a.imap)), None)


#: Wie Discord erreicht wird — siehe :func:`discord_art`.
DISCORD_ARTEN = ("webhook", "kanal", "direkt")


class FlugroutenFehler(ValueError):
    """Eine Eingabe für die Flugrouten passt nicht — der Text ist für den Menschen gedacht."""

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
    """Drei Wege zu Discord (:func:`discord_art`):

    - **Webhook:** eine Adresse, die Discord für genau einen Kanal ausgibt — kein Bot nötig.
    - **Kanal:** ein eigener Bot schreibt in einen Kanal (Token + Kanal-ID).
    - **Direkt:** ohne Kanal und ohne Webhook schreibt der Bot die Nutzer in ``user_ids``
      einzeln an.

    Bei Webhook und Kanal werden die Nutzer in ``user_ids`` in der Nachricht erwähnt.
    """

    enabled: bool = False
    bot_token: str = ""          # SECRET — im Speicher der Wert, in der Datei meist "@tresor"
    channel_id: str = ""
    webhook_url: str = ""        # SECRET (die Adresse enthält ihr eigenes Token) — wie bot_token
    user_ids: list[str] = field(default_factory=list)


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
    imap_host: str = ""          # Posteingangsserver — nur zum Abholen von Anhängen (postfach.py)
    imap_port: int = 993         # 993 = von Anfang an verschlüsselt, sonst STARTTLS
    # Womit sich PollySort anmeldet: "passwort" oder "microsoft" (Anmeldung auf der
    # Microsoft-Seite, siehe microsoft.py — dann gilt oauth_token statt password).
    auth: str = "passwort"
    oauth_token: str = ""        # SECRET: Erneuerungstoken der Microsoft-Anmeldung — wie bot_token
    oauth_client_id: str = ""    # Kennung der Anwendung bei Microsoft (kein Geheimnis)
    oauth_tenant: str = "common"  # Mandant; "common" = private Konten und Firmenkonten


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


def discord_webhook(fr: Flugrouten) -> str:
    return _aus_umgebung("DISCORD_WEBHOOK", fr.discord.webhook_url)


def email_password(fr: Flugrouten) -> str:
    return _aus_umgebung("EMAIL_PASSWORD", fr.email.password)


def discord_art(fr: Flugrouten) -> str:
    """Welcher der drei Wege gilt: ``webhook`` · ``kanal`` · ``direkt`` · ``""`` (keiner)."""
    if discord_webhook(fr):
        return "webhook"
    if discord_token(fr) and fr.discord.channel_id:
        return "kanal"
    if discord_token(fr) and fr.discord.user_ids:
        return "direkt"
    return ""


# ---------------------------------------------------------------------------
# Eingaben prüfen und übernehmen — gemeinsam für Konsole und Werkstatt
# ---------------------------------------------------------------------------
#: Hinter diesen Rechnernamen stehen Discord-Webhooks. Andere Adressen werden abgelehnt, damit
#: PollySort Erinnerungen nicht an beliebige Server schickt.
_WEBHOOK_HOSTS = ("discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com")


def webhook_pruefen(url: str) -> str:
    """Eine Discord-Webhook-Adresse prüfen und bereinigt zurückgeben."""
    from urllib.parse import urlsplit

    from . import i18n
    url = (url or "").strip()
    teile = urlsplit(url)
    pfad = [t for t in teile.path.split("/") if t]
    if (teile.scheme != "https" or (teile.hostname or "").lower() not in _WEBHOOK_HOSTS
            or len(pfad) != 4 or pfad[:2] != ["api", "webhooks"] or not pfad[2].isdigit()):
        raise FlugroutenFehler(i18n.t("routen.err.webhook"))
    return f"https://{teile.hostname.lower()}/api/webhooks/{pfad[2]}/{pfad[3]}"


def ids_pruefen(eingabe, *, was: str) -> list[str]:
    """Discord-IDs aus Text (``"1, 2"``) oder Liste lesen — nur Ziffern, ohne Doppelte.

    ``was`` ist der Text-Schlüssel der Fehlermeldung (Kanal oder Nutzer).
    """
    from . import i18n
    if isinstance(eingabe, str):
        eingabe = eingabe.replace(";", ",").replace(" ", ",").split(",")
    ids: list[str] = []
    for roh in eingabe or []:
        wert = str(roh).strip().removeprefix("<@").removesuffix(">")
        if not wert:
            continue
        if not wert.isdigit() or not 15 <= len(wert) <= 20:
            raise FlugroutenFehler(i18n.t(was, id=wert))
        if wert not in ids:
            ids.append(wert)
    return ids


def discord_setzen(fr: Flugrouten, art: str, *, webhook: str = "", token: str = "",
                   kanal: str = "", nutzer=None) -> None:
    """Discord auf einen der drei Wege einstellen und einschalten.

    Ein leeres Geheimnis (``webhook``/``token``) heißt „das gespeicherte behalten". ``nutzer``
    = ``None`` lässt die Liste, wie sie ist. Was zum gewählten Weg nicht gehört, wird geleert —
    sonst gingen Erinnerungen über einen Weg hinaus, den niemand mehr auf dem Schirm hat.
    """
    from . import i18n
    d = fr.discord
    art = (art or "").strip().lower()
    if art not in DISCORD_ARTEN:
        raise FlugroutenFehler(i18n.t("routen.err.art"))
    ids = list(d.user_ids) if nutzer is None else ids_pruefen(nutzer, was="routen.err.nutzer")
    token = (token or "").strip() or d.bot_token
    if art == "webhook":
        neu = webhook_pruefen(webhook) if (webhook or "").strip() else d.webhook_url
        if not neu and not discord_webhook(fr):      # aus der Umgebungsvariable reicht auch
            raise FlugroutenFehler(i18n.t("routen.err.webhook"))
        fr.discord = DiscordConfig(enabled=True, webhook_url=neu, user_ids=ids)
        return
    if not token and not discord_token(fr):
        raise FlugroutenFehler(i18n.t("routen.err.token"))
    if art == "kanal":
        kanaele = ids_pruefen(kanal or d.channel_id, was="routen.err.kanal")
        if len(kanaele) != 1:
            raise FlugroutenFehler(i18n.t("routen.err.kanal", id=kanal or "—"))
        fr.discord = DiscordConfig(enabled=True, bot_token=token, channel_id=kanaele[0],
                                   user_ids=ids)
        return
    if not ids:
        raise FlugroutenFehler(i18n.t("routen.err.nutzer_fehlt"))
    fr.discord = DiscordConfig(enabled=True, bot_token=token, user_ids=ids)


def _imap_von_anbieter(kurz: str) -> str:
    return EMAIL_ANBIETER[kurz].imap if kurz in EMAIL_ANBIETER else ""


def _host_pruefen(host: str) -> str:
    from . import i18n
    host = (host or "").strip()
    if not host or " " in host or "/" in host:
        raise FlugroutenFehler(i18n.t("routen.err.host"))
    return host


def _port_pruefen(port) -> int:
    from . import i18n
    port = int(port) if str(port).strip().isdigit() else 0
    if not 1 <= port <= 65535:
        raise FlugroutenFehler(i18n.t("routen.err.port"))
    return port


def email_setzen(fr: Flugrouten, anbieter: str, *, adresse: str, passwort: str = "",
                 host: str = "", port: int | str = 0, empfaenger: str = "",
                 imap_host: str = "", imap_port: int | str = 0) -> None:
    """E-Mail einstellen und einschalten. Leeres ``passwort`` = das gespeicherte behalten.

    ``anbieter`` ist ein Kürzel aus :data:`EMAIL_ANBIETER` oder ``custom`` — dann gelten
    ``host`` und ``port`` (587 mit STARTTLS oder 465, von Anfang an verschlüsselt). Den
    Posteingangsserver zum Abholen von Anhängen bringt ein bekannter Anbieter mit; bei ``custom``
    ist ``imap_host`` freiwillig (ohne ihn wird nur gemeldet, nichts abgeholt).
    """
    from . import i18n
    anbieter = (anbieter or "").strip().lower()
    adresse, empfaenger = (adresse or "").strip(), (empfaenger or "").strip()
    for wert in (adresse, empfaenger):
        if wert and ("@" not in wert.strip("@") or " " in wert):
            raise FlugroutenFehler(i18n.t("routen.err.adresse", adresse=wert))
    if not adresse:
        raise FlugroutenFehler(i18n.t("routen.err.adresse", adresse="—"))
    if anbieter in EMAIL_ANBIETER:
        host, port = EMAIL_ANBIETER[anbieter].host, EMAIL_ANBIETER[anbieter].port
        imap_host, imap_port = EMAIL_ANBIETER[anbieter].imap, 993
    elif anbieter == "custom":
        host, port = _host_pruefen(host), _port_pruefen(port)
        imap_host = (imap_host or "").strip()
        if imap_host:
            imap_host = _host_pruefen(imap_host)
            imap_port = _port_pruefen(imap_port or 993)
        else:
            imap_port = 993
    else:
        raise FlugroutenFehler(i18n.t("routen.err.anbieter"))
    passwort = passwort or fr.email.password
    if not passwort and not email_password(fr):
        raise FlugroutenFehler(i18n.t("routen.err.passwort"))
    fr.email = EmailConfig(enabled=True, provider=anbieter, address=adresse, password=passwort,
                           smtp_host=host, smtp_port=int(port), use_tls=True,
                           recipient=empfaenger, imap_host=imap_host, imap_port=int(imap_port),
                           # Die Kennung der Anwendung bleibt für eine spätere Microsoft-Anmeldung.
                           oauth_client_id=fr.email.oauth_client_id,
                           oauth_tenant=fr.email.oauth_tenant)


def email_microsoft_setzen(fr: Flugrouten, anbieter: str, *, adresse: str, erneuerung: str,
                           kennung: str = "", mandant: str = "", empfaenger: str = "") -> None:
    """E-Mail über die Microsoft-Anmeldung einstellen und einschalten (``microsoft.py``).

    ``erneuerung`` ist das Erneuerungstoken aus der Anmeldung; ein Passwort gibt es dann nicht.
    ``kennung`` (Client-ID) und ``mandant`` bleiben, wie sie waren, wenn sie leer sind.
    """
    from . import i18n
    anbieter = (anbieter or "").strip().lower()
    adresse, empfaenger = (adresse or "").strip(), (empfaenger or "").strip()
    if anbieter not in ("outlook", "microsoft365"):
        raise FlugroutenFehler(i18n.t("routen.err.anbieter"))
    for wert in (adresse, empfaenger):
        if wert and ("@" not in wert.strip("@") or " " in wert):
            raise FlugroutenFehler(i18n.t("routen.err.adresse", adresse=wert))
    if not adresse:
        raise FlugroutenFehler(i18n.t("routen.err.adresse", adresse="—"))
    if not erneuerung:
        raise FlugroutenFehler(i18n.t("ms.err.neu_anmelden"))
    a = EMAIL_ANBIETER[anbieter]
    fr.email = EmailConfig(enabled=True, provider=anbieter, address=adresse, password="",
                           smtp_host=a.host, smtp_port=a.port, use_tls=True, recipient=empfaenger,
                           imap_host=a.imap, imap_port=993, auth="microsoft",
                           oauth_token=erneuerung,
                           oauth_client_id=(kennung or "").strip() or fr.email.oauth_client_id,
                           oauth_tenant=(mandant or "").strip() or fr.email.oauth_tenant)


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
        "webhook": tresor.ablageort(str(data.get("discord", {}).get("webhook_url", "")),
                                    tresor.DISCORD_WEBHOOK),
        "anmeldung": tresor.ablageort(str(data.get("email", {}).get("oauth_token", "")),
                                      tresor.EMAIL_ANMELDUNG),
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
        webhook_url=str(d.get("webhook_url", "")),
        user_ids=[str(u) for u in d.get("user_ids", []) if str(u).strip()]
        if isinstance(d.get("user_ids", []), list) else [],
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
        # Ältere Dateien kennen den Posteingangsserver nicht → vom Anbieter ableiten.
        imap_host=str(e.get("imap_host", "") or _imap_von_anbieter(str(e.get("provider", "")))),
        imap_port=int(e.get("imap_port", 993)),
        auth="microsoft" if str(e.get("auth", "")) == "microsoft" else "passwort",
        oauth_token=str(e.get("oauth_token", "")),
        oauth_client_id=str(e.get("oauth_client_id", "")),
        oauth_tenant=str(e.get("oauth_tenant", "") or "common"),
    )
    fr.calendar = CalendarConfig(
        enabled=bool(c.get("enabled", False)),
        kind=str(c.get("kind", "ical")),
    )
    klartext = any(w and w != tresor.IM_TRESOR
                   for w in (fr.discord.bot_token, fr.discord.webhook_url, fr.email.password,
                             fr.email.oauth_token))
    fr.discord.bot_token = _aus_tresor(tresor.DISCORD_TOKEN, fr.discord.bot_token)
    fr.discord.webhook_url = _aus_tresor(tresor.DISCORD_WEBHOOK, fr.discord.webhook_url)
    fr.email.password = _aus_tresor(tresor.EMAIL_PASSWORT, fr.email.password)
    fr.email.oauth_token = _aus_tresor(tresor.EMAIL_ANMELDUNG, fr.email.oauth_token)
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
    webhook = tresor.ablegen(tresor.DISCORD_WEBHOOK, d.webhook_url)
    passwort = tresor.ablegen(tresor.EMAIL_PASSWORT, e.password)
    anmeldung = tresor.ablegen(tresor.EMAIL_ANMELDUNG, e.oauth_token)
    content = (
        "# PollySort — Flugrouten der Wächterbienen (§v0.3)\n"
        "# 🔒 Wachssiegel: Zugangsdaten. Wird NIE an ein LLM übergeben oder im Klartext geloggt.\n"
        f'# "{tresor.IM_TRESOR}" heißt: Der Wert liegt im Tresor des Betriebssystems, nicht hier.\n'
        "# Secrets via Env überschreibbar: POLLYSORT_DISCORD_TOKEN, POLLYSORT_DISCORD_WEBHOOK,\n"
        "# POLLYSORT_EMAIL_PASSWORD.\n\n"
        "[discord]\n"
        f"enabled    = {_toml_val(d.enabled)}\n"
        f"bot_token  = {_toml_val(token)}\n"
        f"channel_id = {_toml_val(d.channel_id)}\n"
        f"webhook_url = {_toml_val(webhook)}\n"
        f"user_ids   = {_toml_val(list(d.user_ids))}\n\n"
        "[email]\n"
        f"enabled   = {_toml_val(e.enabled)}\n"
        f"provider  = {_toml_val(e.provider)}\n"
        f"address   = {_toml_val(e.address)}\n"
        f"password  = {_toml_val(passwort)}\n"
        f"smtp_host = {_toml_val(e.smtp_host)}\n"
        f"smtp_port = {_toml_val(e.smtp_port)}\n"
        f"use_tls   = {_toml_val(e.use_tls)}\n"
        f"recipient = {_toml_val(e.recipient)}\n"
        f"imap_host = {_toml_val(e.imap_host)}\n"
        f"imap_port = {_toml_val(e.imap_port)}\n"
        f"auth      = {_toml_val(e.auth)}\n"
        f"oauth_token = {_toml_val(anmeldung)}\n"
        f"oauth_client_id = {_toml_val(e.oauth_client_id)}\n"
        f"oauth_tenant = {_toml_val(e.oauth_tenant)}\n\n"
        "[calendar]\n"
        f"enabled = {_toml_val(c.enabled)}\n"
        f"kind    = {_toml_val(c.kind)}\n"
    )
    path.write_text(content, encoding="utf-8")
    try:
        os.chmod(path, 0o600)            # best effort; unter Windows teils No-Op
    except OSError:
        pass

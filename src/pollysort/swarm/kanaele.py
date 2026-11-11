"""Kommunikations-Kanäle (§v0.3) — die echten „Flugrouten" der Wächterbienen.

Discord via ``httpx``, E-Mail via ``smtplib``. Diese Sender sind **vollständig unabhängig**
von der LLM-Generierung: sie beziehen Credentials ausschließlich aus der lokalen
Flugrouten-Config, nie aus einem Modell-Kontext. Jeder Kanal bietet dieselbe Schnittstelle
``senden(titel, text)`` und wirft bei Fehlern ``KanalError``.
"""

from __future__ import annotations

from .. import i18n, microsoft
from ..flugrouten import (
    Flugrouten,
    anbieter_fuer_host,
    discord_token,
    discord_webhook,
    email_password,
)
from ..microsoft import AnmeldeFehler


class KanalError(RuntimeError):
    """Ein Flugrouten-Versand ist fehlgeschlagen (Netz/Auth/SMTP). Nie mit Secret im Text."""


class KanalAbgelehnt(KanalError):
    """Der Empfänger nimmt auf diesem Weg dauerhaft nichts an (z. B. Direktnachrichten gesperrt).

    Anders als ein Netzfehler wird das durch Warten nicht besser: Die Wächterbiene hält deshalb
    eine Deadline nicht ewig offen, nur weil ein einzelner Empfänger abgelehnt hat.
    """


def _schluessel(art: str, ziel: str) -> str:
    """Ein fester Name für „diesen Empfänger auf diesem Weg" — ohne das Ziel selbst.

    Die Wächterbiene merkt sich damit im Projektordner, wer eine Deadline schon bekommen hat.
    Projektordner werden geteilt und gesichert; Adresse, Kanal- oder Nutzer-ID gehören dort
    nicht hinein, deshalb steht nur eine Prüfsumme da.
    """
    import hashlib
    return f"{art}:{hashlib.sha1(str(ziel).lower().encode()).hexdigest()[:10]}"


MAX_ZEICHEN = 2000                           # mehr nimmt Discord je Nachricht nicht an
API = "https://discord.com/api/v10"          # versionierter, stabiler Endpoint


def _discord_inhalt(titel: str, text: str, user_ids=()) -> dict:
    """Der Nachrichtenkörper für Discord — mit Erwähnung der angegebenen Nutzer.

    ``allowed_mentions`` lässt **nur** diese Nutzer benachrichtigen: Ein ``@everyone`` oder eine
    fremde Erwähnung, die über einen Deadline-Titel hereinkommt, bleibt bloßer Text.
    """
    ids = [str(u) for u in user_ids]
    ruf = " ".join(f"<@{u}>" for u in ids)
    inhalt = (f"{ruf}\n" if ruf else "") + f"🐝 **{titel}**\n{text}"
    return {"content": inhalt[:MAX_ZEICHEN], "allowed_mentions": {"parse": [], "users": ids}}


def _discord_post(url: str, inhalt: dict, *, token: str = ""):
    """Ein Aufruf an Discord. Netzfehler werden zu ``KanalError`` — nur mit dem Fehlertyp,
    nie mit Token oder Adresse (die Webhook-Adresse ist selbst ein Geheimnis)."""
    import httpx
    kopf = {"Content-Type": "application/json"}
    if token:
        kopf["Authorization"] = f"Bot {token}"
    try:
        return httpx.post(url, headers=kopf, json=inhalt, timeout=15.0)
    except httpx.HTTPError as exc:
        raise KanalError(f"Discord nicht erreichbar ({exc.__class__.__name__})") from None


def _discord_allgemein(r) -> None:
    """Die Antworten, die auf jedem Weg dasselbe bedeuten."""
    if r.status_code == 429:
        raise KanalError(i18n.t("kanal.discord.429"))
    if r.status_code >= 400:
        raise KanalError(f"Discord antwortete mit HTTP {r.status_code}")


class DiscordKanal:
    """Schickt eine Nachricht in einen Discord-Channel (Bot-Token, unabhängig vom LLM).

    Echter Botenflug: POST an die Discord-API mit ``Authorization: Bot <token>``. Das Token
    landet ausschließlich im HTTP-Header — nie in Payload, Konsole, Log oder LLM-Prompt.
    """

    name = "Discord"
    STOCK = "Discord-Wabe"
    API = API
    MAX_ZEICHEN = MAX_ZEICHEN

    def __init__(self, token: str, channel_id: str, user_ids=()):
        self._token = token
        self.channel_id = channel_id
        self.user_ids = list(user_ids)
        self.schluessel = _schluessel("discord-kanal", channel_id)

    def _payload(self, titel: str, text: str) -> dict:
        return _discord_inhalt(titel, text, self.user_ids)

    def senden(self, titel: str, text: str) -> None:
        r = _discord_post(f"{self.API}/channels/{self.channel_id}/messages",
                          self._payload(titel, text), token=self._token)
        # Sauberes Abfangen — Token taucht in KEINER dieser Meldungen auf.
        if r.status_code == 401:
            raise KanalError("Discord lehnt den Bot-Token ab (401 Unauthorized) — Token prüfen")
        if r.status_code in (403, 404):
            raise KanalError(f"Discord-Channel nicht erreichbar ({r.status_code}) — Channel-ID/"
                             "Bot-Rechte prüfen")
        _discord_allgemein(r)


class DiscordWebhookKanal:
    """Schickt über einen Webhook in genau den Kanal, für den Discord ihn ausgegeben hat.

    Kein Bot, kein Token: Die Adresse ist der Schlüssel — deshalb gilt sie als Geheimnis und
    taucht in keiner Meldung auf.
    """

    name = "Discord-Webhook"
    STOCK = "Discord-Wabe"
    schluessel = "discord-webhook"

    def __init__(self, url: str, user_ids=()):
        self._url = url
        self.user_ids = list(user_ids)

    def _payload(self, titel: str, text: str) -> dict:
        return _discord_inhalt(titel, text, self.user_ids)

    def senden(self, titel: str, text: str) -> None:
        r = _discord_post(self._url, self._payload(titel, text))
        if r.status_code in (401, 403, 404):
            raise KanalError(i18n.t("kanal.discord.webhook_weg", status=r.status_code))
        _discord_allgemein(r)


class DiscordDirektKanal:
    """Der Bot schreibt **einen** Nutzer direkt an (je Nutzer ein eigener Kanal).

    Discord erlaubt das nur, wenn Bot und Nutzer einen gemeinsamen Server haben und der Nutzer
    Direktnachrichten von Servermitgliedern zulässt. Lehnt Discord ab, ist das ein
    :class:`KanalAbgelehnt` — die anderen Nutzer bekommen ihre Nachricht trotzdem.
    """

    STOCK = "Discord-Wabe"
    API = API

    def __init__(self, token: str, user_id: str):
        self._token = token
        self.user_id = str(user_id)
        self.name = f"Discord-Nutzer {self.user_id}"
        self.schluessel = _schluessel("discord-nutzer", self.user_id)

    def _pruefen(self, r) -> None:
        if r.status_code == 401:
            raise KanalError("Discord lehnt den Bot-Token ab (401 Unauthorized) — Token prüfen")
        if r.status_code in (400, 403, 404):
            raise KanalAbgelehnt(i18n.t("kanal.discord.dm_abgelehnt", status=r.status_code))
        _discord_allgemein(r)

    def senden(self, titel: str, text: str) -> None:
        # Erst das Gespräch öffnen (liefert die Kanal-ID der Direktnachricht), dann schreiben.
        r = _discord_post(f"{self.API}/users/@me/channels", {"recipient_id": self.user_id},
                          token=self._token)
        self._pruefen(r)
        try:
            kanal = str(r.json()["id"])
        except (ValueError, KeyError, TypeError):
            raise KanalError("Discord antwortete unerwartet") from None
        r = _discord_post(f"{self.API}/channels/{kanal}/messages", _discord_inhalt(titel, text),
                          token=self._token)
        self._pruefen(r)


class EmailKanal:
    """Verschickt eine E-Mail per SMTP (Adresse/Passwort nur aus der lokalen Config).

    Port 465 spricht von Anfang an verschlüsselt, alle anderen Ports wechseln per STARTTLS —
    in beiden Fällen wird das Zertifikat des Servers geprüft.
    """

    name = "E-Mail"
    STOCK = "E-Mail-Wabe"

    def __init__(self, address: str, password: str, smtp_host: str, smtp_port: int,
                 use_tls: bool = True, recipient: str = "", *, token_holen=None):
        self.address = address
        self._password = password
        # Anmeldung über Microsoft statt mit Passwort: liefert bei Bedarf ein Zugriffstoken.
        self._token_holen = token_holen
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.use_tls = use_tls
        self.recipient = recipient or address        # leer = an sich selbst
        self.schluessel = _schluessel("email", self.recipient)

    def _message(self, titel: str, text: str):
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["From"] = self.address
        msg["To"] = self.recipient
        msg["Subject"] = f"🐝 {titel}"
        msg.set_content(text)
        return msg

    #: Port, auf dem Mailserver von Anfang an verschlüsselt sprechen (statt STARTTLS auf 587).
    PORT_TLS_SOFORT = 465

    def senden(self, titel: str, text: str) -> None:
        import smtplib
        import ssl
        msg = self._message(titel, text)
        # Ohne eigenen Kontext prüft smtplib das Zertifikat des Servers NICHT — das Passwort
        # ginge dann auch an jeden, der sich als Mailserver ausgibt. Dieser Kontext prüft
        # Zertifikat und Servernamen gegen die Zertifikate des Betriebssystems.
        kontext = ssl.create_default_context()
        sofort = self.smtp_port == self.PORT_TLS_SOFORT
        try:
            if sofort:
                smtp = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=20, context=kontext)
            else:
                smtp = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=20)
            with smtp:
                if self.use_tls and not sofort:
                    smtp.starttls(context=kontext)
                if self._token_holen is not None:
                    from ..microsoft import xoauth2
                    zeile = xoauth2(self.address, self._token_holen())
                    smtp.ehlo_or_helo_if_needed()
                    # Lehnt der Server ab, schickt er erst eine Rückfrage — darauf folgt nur eine
                    # leere Zeile, nie noch einmal das Token.
                    smtp.auth("XOAUTH2", lambda rueckfrage=None: zeile if rueckfrage is None else "")
                else:
                    smtp.login(self.address, self._password)
                smtp.send_message(msg)
        except AnmeldeFehler as exc:
            raise KanalError(str(exc)) from None
        except ssl.SSLCertVerificationError:
            raise KanalError(i18n.t("kanal.cert")) from None
        except smtplib.SMTPAuthenticationError:
            if self._token_holen is not None:
                raise KanalError(i18n.t("kanal.auth.oauth")) from None
            raise KanalError(i18n.t("kanal.auth") + self._anbieter_hinweis()) from None
        except (smtplib.SMTPException, OSError, ValueError) as exc:
            raise KanalError(f"SMTP-Versand fehlgeschlagen ({exc.__class__.__name__})") from None

    def _anbieter_hinweis(self) -> str:
        """Bekannter Grund je Anbieter, warum ein richtiges Passwort trotzdem abgelehnt wird."""
        host = self.smtp_host.lower()
        if host.endswith(("outlook.com", "office365.com", "hotmail.com", "live.com")):
            return ". " + i18n.t("kanal.auth.microsoft")
        if host.endswith(("gmail.com", "googlemail.com")):
            return ". " + i18n.t("kanal.auth.gmail")
        anbieter = anbieter_fuer_host(host)
        if anbieter is not None and anbieter.hinweis:
            return ". " + i18n.t(anbieter.hinweis)
        return ""


def build_kanaele(fr: Flugrouten) -> list:
    """Aktive Kanäle aus der Flugrouten-Config bauen (Secrets inkl. Env-Vorrang).

    Discord: ein Webhook und/oder ein Bot im Kanal — die Nutzer aus ``user_ids`` werden dort
    erwähnt. Gibt es keins von beiden, schreibt der Bot diese Nutzer einzeln direkt an.
    """
    kanaele: list = []
    d = fr.discord
    if d.enabled:
        token, webhook = discord_token(fr), discord_webhook(fr)
        if webhook:
            kanaele.append(DiscordWebhookKanal(webhook, d.user_ids))
        if token and d.channel_id:
            kanaele.append(DiscordKanal(token, d.channel_id, d.user_ids))
        elif token and not webhook:
            kanaele.extend(DiscordDirektKanal(token, u) for u in d.user_ids)
    e = fr.email
    if e.enabled and e.address and e.smtp_host:
        if e.auth == "microsoft":
            if microsoft.bereit(fr):
                kanaele.append(EmailKanal(e.address, "", e.smtp_host, e.smtp_port, e.use_tls,
                                          e.recipient,
                                          token_holen=lambda: microsoft.zugriffstoken(fr)))
        elif email_password(fr):
            kanaele.append(EmailKanal(e.address, email_password(fr), e.smtp_host, e.smtp_port,
                                      e.use_tls, e.recipient))
    return kanaele

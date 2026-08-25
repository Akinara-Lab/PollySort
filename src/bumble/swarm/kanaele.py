"""Kommunikations-Kanäle (§v0.3) — die echten „Flugrouten" der Wächterbienen.

Discord via ``httpx``, E-Mail via ``smtplib``. Diese Sender sind **vollständig unabhängig**
von der LLM-Generierung: sie beziehen Credentials ausschließlich aus der lokalen
Flugrouten-Config, nie aus einem Modell-Kontext. Jeder Kanal bietet dieselbe Schnittstelle
``senden(titel, text)`` und wirft bei Fehlern ``KanalError``.
"""

from __future__ import annotations

from ..flugrouten import Flugrouten, discord_token, email_password


class KanalError(RuntimeError):
    """Ein Flugrouten-Versand ist fehlgeschlagen (Netz/Auth/SMTP). Nie mit Secret im Text."""


class DiscordKanal:
    """Schickt eine Nachricht in einen Discord-Channel (Bot-Token, unabhängig vom LLM).

    Echter Botenflug: POST an die Discord-API mit ``Authorization: Bot <token>``. Das Token
    landet ausschließlich im HTTP-Header — nie in Payload, Konsole, Log oder LLM-Prompt.
    """

    name = "Discord"
    STOCK = "Discord-Wabe"
    API = "https://discord.com/api/v10"      # versionierter, stabiler Endpoint

    def __init__(self, token: str, channel_id: str):
        self._token = token
        self.channel_id = channel_id

    def _payload(self, titel: str, text: str) -> dict:
        return {"content": f"🐝 **{titel}**\n{text}"}

    def senden(self, titel: str, text: str) -> None:
        import httpx
        try:
            r = httpx.post(
                f"{self.API}/channels/{self.channel_id}/messages",
                headers={"Authorization": f"Bot {self._token}",
                         "Content-Type": "application/json"},
                json=self._payload(titel, text),
                timeout=15.0,
            )
        except httpx.HTTPError as exc:
            # Nur der Fehlertyp, nie Token/URL-mit-Secret.
            raise KanalError(f"Discord nicht erreichbar ({exc.__class__.__name__})") from None
        # Sauberes Abfangen — Token taucht in KEINER dieser Meldungen auf.
        if r.status_code == 401:
            raise KanalError("Discord lehnt den Bot-Token ab (401 Unauthorized) — Token prüfen")
        if r.status_code in (403, 404):
            raise KanalError(f"Discord-Channel nicht erreichbar ({r.status_code}) — Channel-ID/"
                             "Bot-Rechte prüfen")
        if r.status_code >= 400:
            raise KanalError(f"Discord antwortete mit HTTP {r.status_code}")


class EmailKanal:
    """Verschickt eine E-Mail per SMTP+STARTTLS (Adresse/Passwort nur aus der lokalen Config)."""

    name = "E-Mail"
    STOCK = "E-Mail-Wabe"

    def __init__(self, address: str, password: str, smtp_host: str, smtp_port: int,
                 use_tls: bool = True, recipient: str = ""):
        self.address = address
        self._password = password
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.use_tls = use_tls
        self.recipient = recipient or address        # leer = an sich selbst

    def _message(self, titel: str, text: str):
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["From"] = self.address
        msg["To"] = self.recipient
        msg["Subject"] = f"🐝 {titel}"
        msg.set_content(text)
        return msg

    def senden(self, titel: str, text: str) -> None:
        import smtplib
        msg = self._message(titel, text)
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=20) as smtp:
                if self.use_tls:
                    smtp.starttls()
                smtp.login(self.address, self._password)
                smtp.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            raise KanalError(f"SMTP-Versand fehlgeschlagen ({exc.__class__.__name__})") from None


def build_kanaele(fr: Flugrouten) -> list:
    """Aktive Kanäle aus der Flugrouten-Config bauen (Secrets inkl. Env-Vorrang)."""
    kanaele: list = []
    if fr.discord.enabled and fr.discord.channel_id and discord_token(fr):
        kanaele.append(DiscordKanal(discord_token(fr), fr.discord.channel_id))
    if fr.email.enabled and fr.email.address and email_password(fr) and fr.email.smtp_host:
        kanaele.append(EmailKanal(
            fr.email.address, email_password(fr), fr.email.smtp_host,
            fr.email.smtp_port, fr.email.use_tls, fr.email.recipient))
    return kanaele

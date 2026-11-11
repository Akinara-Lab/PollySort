"""Microsoft-Anmeldung für E-Mail — Outlook.com, Hotmail und Microsoft 365 ohne Passwort.

Microsoft nimmt für private Konten kein Passwort mehr an und schaltet es für Firmenkonten ab.
Stattdessen meldet man sich **auf der Microsoft-Seite** an und erlaubt PollySort dort, E-Mails zu
senden und das Postfach zu lesen. PollySort bekommt dafür kein Passwort, sondern zwei Schlüssel:

- ein **Zugriffstoken** (gilt etwa eine Stunde) — lebt nur im Arbeitsspeicher;
- ein **Erneuerungstoken**, mit dem PollySort sich ein frisches Zugriffstoken holt — liegt im
  Tresor des Betriebssystems wie ein Passwort (🔒 Wachssiegel: nie in Meldungen, Journal, Prompt).

Der Ablauf heißt „Gerätecode": PollySort zeigt eine Adresse und einen kurzen Code, der Mensch
gibt den Code im Browser ein und meldet sich an, PollySort fragt derweil nach, ob es so weit ist.
Dafür braucht es keinen eigenen Webserver und kein Geheimnis der Anwendung — nur ihre öffentliche
Kennung (Client-ID) aus der Anmeldung der Anwendung bei Microsoft.

Quellen: Microsoft Learn „OAuth 2.0 device authorization grant flow" und „Authenticate an IMAP,
POP or SMTP connection using OAuth".
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from . import i18n

#: Kennung, unter der PollySort bei Microsoft angemeldet ist. Solange hier nichts steht, trägt
#: man die eigene ein (``flugrouten setup`` fragt danach) oder setzt die Umgebungsvariable.
CLIENT_ID = ""
CLIENT_ID_VARIABLE = "POLLYSORT_MICROSOFT_CLIENT_ID"
#: „common" = private Konten und Firmenkonten. Firmen mit eigener Vorgabe tragen ihre Mandanten-ID ein.
MANDANT = "common"
BASIS = "https://login.microsoftonline.com"
#: Genau das, was PollySort darf: Postfach lesen, Mail senden, die Anmeldung erneuern.
BERECHTIGUNGEN = ("https://outlook.office.com/IMAP.AccessAsUser.All "
                  "https://outlook.office.com/SMTP.Send offline_access")
#: Anbieter aus ``flugrouten.EMAIL_ANBIETER``, die sich so anmelden.
ANBIETER = ("outlook", "microsoft365")
#: So viel früher gilt ein Zugriffstoken als abgelaufen — damit es nicht mitten im Versand endet.
_RESERVE = 120


class AnmeldeFehler(RuntimeError):
    """Die Anmeldung bei Microsoft hat nicht geklappt — der Text enthält kein Token."""


@dataclass
class Geraetecode:
    """Was der Mensch sehen muss (Adresse, Code) — und was nur PollySort behält (``device_code``)."""

    device_code: str = field(repr=False)
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


@dataclass
class Token:
    zugriff: str = field(repr=False)
    erneuerung: str = field(repr=False)
    gilt_bis: float                     # time.monotonic()


def client_id(gespeichert: str = "") -> str:
    """Die Kennung der Anwendung: Umgebungsvariable vor dem Gespeicherten vor der eingebauten."""
    return os.environ.get(CLIENT_ID_VARIABLE, "").strip() or (gespeichert or "").strip() or CLIENT_ID


def _anfrage(pfad: str, mandant: str, daten: dict) -> tuple[int, dict]:
    """Ein Aufruf an die Microsoft-Anmeldung. Netzfehler ohne Inhalt, Antworten als ``dict``."""
    import httpx
    try:
        r = httpx.post(f"{BASIS}/{mandant or MANDANT}/oauth2/v2.0/{pfad}", data=daten, timeout=20.0)
    except httpx.HTTPError as exc:
        raise AnmeldeFehler(i18n.t("ms.err.netz", typ=exc.__class__.__name__)) from None
    try:
        antwort = r.json()
    except ValueError:
        antwort = {}
    return r.status_code, antwort if isinstance(antwort, dict) else {}


def _token(antwort: dict, *, bisher: str = "") -> Token:
    zugriff = str(antwort.get("access_token") or "")
    if not zugriff:
        raise AnmeldeFehler(i18n.t("ms.err.antwort"))
    dauer = antwort.get("expires_in")
    dauer = int(dauer) if str(dauer).isdigit() else 3600
    # Microsoft kann das Erneuerungstoken bei jeder Erneuerung austauschen — dann gilt das neue.
    return Token(zugriff, str(antwort.get("refresh_token") or bisher),
                 time.monotonic() + max(0, dauer - _RESERVE))


def geraetecode_holen(kennung: str, mandant: str = MANDANT) -> Geraetecode:
    """Schritt 1: Adresse und Code holen, die der Mensch im Browser eingibt."""
    if not kennung:
        raise AnmeldeFehler(i18n.t("ms.err.kennung"))
    status, a = _anfrage("devicecode", mandant, {"client_id": kennung, "scope": BERECHTIGUNGEN})
    if status != 200 or not a.get("device_code") or not a.get("user_code"):
        raise AnmeldeFehler(i18n.t("ms.err.start", grund=str(a.get("error") or status)))
    return Geraetecode(str(a["device_code"]), str(a["user_code"]),
                       str(a.get("verification_uri") or "https://microsoft.com/devicelogin"),
                       int(a.get("expires_in") or 900), max(1, int(a.get("interval") or 5)))


def nachfragen(kennung: str, code: Geraetecode, mandant: str = MANDANT) -> Token | None:
    """Schritt 2, einmal: Hat sich der Mensch schon angemeldet? ``None`` = noch nicht."""
    status, a = _anfrage("token", mandant, {
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "client_id": kennung, "device_code": code.device_code})
    if status == 200:
        token = _token(a)
        if not token.erneuerung:
            raise AnmeldeFehler(i18n.t("ms.err.antwort"))
        return token
    fehler = str(a.get("error") or "")
    if fehler == "authorization_pending":
        return None
    if fehler == "slow_down":                   # der Server bittet um längere Pausen
        code.interval += 5
        return None
    if fehler in ("authorization_declined", "access_denied"):
        raise AnmeldeFehler(i18n.t("ms.err.abgelehnt"))
    if fehler in ("expired_token", "bad_verification_code"):
        raise AnmeldeFehler(i18n.t("ms.err.abgelaufen"))
    raise AnmeldeFehler(i18n.t("ms.err.start", grund=fehler or str(status)))


def warten(kennung: str, code: Geraetecode, mandant: str = MANDANT, *, schlafen=time.sleep,
           uhr=time.monotonic) -> Token:
    """Schritt 2, bis zum Ende: nachfragen, bis die Anmeldung da ist oder der Code abläuft."""
    ende = uhr() + code.expires_in
    while uhr() < ende:
        schlafen(code.interval)
        token = nachfragen(kennung, code, mandant)
        if token is not None:
            return token
    raise AnmeldeFehler(i18n.t("ms.err.abgelaufen"))


def erneuern(kennung: str, erneuerung: str, mandant: str = MANDANT) -> Token:
    """Mit dem Erneuerungstoken ein frisches Zugriffstoken holen."""
    if not kennung or not erneuerung:
        raise AnmeldeFehler(i18n.t("ms.err.neu_anmelden"))
    status, a = _anfrage("token", mandant, {
        "grant_type": "refresh_token", "client_id": kennung, "refresh_token": erneuerung,
        "scope": BERECHTIGUNGEN})
    if status == 200:
        return _token(a, bisher=erneuerung)
    if str(a.get("error") or "") in ("invalid_grant", "interaction_required"):
        # Zurückgezogen, zu lange unbenutzt oder Passwort geändert — nur neu anmelden hilft.
        raise AnmeldeFehler(i18n.t("ms.err.neu_anmelden"))
    raise AnmeldeFehler(i18n.t("ms.err.start", grund=str(a.get("error") or status)))


def xoauth2(adresse: str, zugriff: str) -> str:
    """Die Anmeldezeile, die Mailserver statt eines Passworts annehmen (SASL XOAUTH2)."""
    return f"user={adresse}\x01auth=Bearer {zugriff}\x01\x01"


# --------------------------------------------------------------------------- #
#  Für die Flugrouten: ein gültiges Zugriffstoken, ohne dass jemand daran denken muss
# --------------------------------------------------------------------------- #
#: Zugriffstoken je Konto — nur im Arbeitsspeicher, nie auf der Platte.
_ZUGRIFF: dict[str, Token] = {}


def bereit(fr) -> bool:
    """Ist die E-Mail-Flugroute über Microsoft angemeldet (Erneuerungstoken und Kennung da)?"""
    from . import tresor
    e = fr.email
    return bool(e.auth == "microsoft" and e.address and e.oauth_token
                and e.oauth_token != tresor.IM_TRESOR and client_id(e.oauth_client_id))


def zugriffstoken(fr) -> str:
    """Ein gültiges Zugriffstoken für das E-Mail-Konto der Flugrouten.

    Holt bei Bedarf ein frisches. Hat Microsoft dabei das Erneuerungstoken ausgetauscht, wird
    das neue gespeichert — sonst wäre die Anmeldung beim nächsten Programmstart verloren.
    """
    if not bereit(fr):
        raise AnmeldeFehler(i18n.t("ms.err.neu_anmelden"))
    e = fr.email
    schluessel = e.address.lower()
    token = _ZUGRIFF.get(schluessel)
    if token is None or time.monotonic() >= token.gilt_bis or token.erneuerung != e.oauth_token:
        token = erneuern(client_id(e.oauth_client_id), e.oauth_token, e.oauth_tenant)
        _ZUGRIFF[schluessel] = token
        if token.erneuerung and token.erneuerung != e.oauth_token:
            from .flugrouten import save_flugrouten
            e.oauth_token = token.erneuerung
            try:
                save_flugrouten(fr)
            except OSError:
                pass
    return token.zugriff


def vergessen(adresse: str = "") -> None:
    """Zugriffstoken aus dem Arbeitsspeicher werfen (nach Abmelden oder neuer Anmeldung)."""
    if adresse:
        _ZUGRIFF.pop(adresse.lower(), None)
    else:
        _ZUGRIFF.clear()

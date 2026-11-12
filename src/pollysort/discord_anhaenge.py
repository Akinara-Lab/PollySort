"""Discord-Anhänge — Dateien aus einem Discord-Kanal ins Flugloch (den Eingang) eines Projekts.

Die Idee: Jedes Projekt bekommt **einen** Kanal auf Discord. Was dort als Datei hochgeladen oder
hinein weitergeleitet wird, landet im Eingang des Projekts und wird wie jede andere Datei sortiert.
Abgeholt wird mit dem Bot der Discord-Flugroute — ein Webhook kann nur schreiben, nicht lesen.

Dieselben drei Zusagen wie beim Postfach (:mod:`pollysort.postfach`):

- **Nur lesen.** An Discord gehen ausschließlich lesende Anfragen. Im Kanal wird nichts gelöscht,
  nichts geschrieben, nichts markiert.
- **Nichts doppelt, nichts überschrieben.** Je Projekt merkt sich ``.honig/discord.json``, bis zu
  welcher Nachricht abgeholt wurde und welche Inhalte (SHA-256) schon da waren. Eine Datei im
  Eingang wird nie ersetzt — bei gleichem Namen bekommt die neue eine Nummer.
- 🔒 **Wachssiegel.** Das Bot-Token geht nur im Kopf der Anfragen an ``discord.com`` — nie an den
  Dateispeicher von Discord, nie in eine Meldung, ein Journal oder einen Prompt. Text, Verfasser
  und Zeit der Nachrichten werden nicht gespeichert; Dateinamen werden entschärft, bevor sie die
  Platte sehen, und geladen wird nur von den Dateispeichern von Discord.

Damit Discord einem Bot die Anhänge fremder Nachrichten überhaupt zeigt, muss beim Bot im
Entwicklerportal „Message Content Intent" eingeschaltet sein. Fehlt das, sagt der Abruf es und
überspringt nichts.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from . import config, i18n
from .flugrouten import Flugrouten, discord_token
from .postfach import _ablegen as _in_den_eingang
from .postfach import sicherer_name

API = "https://discord.com/api/v10"
#: Nur von hier werden Dateien geladen — die Adresse eines Anhangs kommt aus einer Antwort.
DATEI_HOSTS = ("cdn.discordapp.com", "media.discordapp.net")
#: So viele Nachrichten gibt Discord je Anfrage höchstens heraus.
SEITE = 100
#: So viele Nachrichten sieht ein Abruf höchstens an — der Rest kommt beim nächsten Mal dran.
MAX_NACHRICHTEN = 500
#: So oft sieht die Wache von selbst nach (Sekunden).
PAUSE = 10 * 60
#: Kanäle, in denen Menschen schreiben: Textkanal und Ankündigungskanal.
_TEXTKANAL = (0, 5)
#: So viele Server fragt ``kanal_liste`` höchstens ab.
_MAX_SERVER = 25
#: Gewöhnliche Nachricht und Antwort — nur bei diesen lässt sich „leer" deuten.
_GEWOEHNLICH = (0, 19)
#: Merkmale der Anwendung: Der Bot darf Nachrichteninhalte lesen (ab bzw. unter 100 Servern).
_INHALT_ERLAUBT = (1 << 18) | (1 << 19)


class DiscordFehler(RuntimeError):
    """Der Abruf ist gescheitert — der Text ist für den Menschen und enthält kein Geheimnis."""


@dataclass
class Abruf:
    """Was ein Abruf gebracht hat."""

    nachrichten: int = 0                                  # angesehene neue Nachrichten
    geholt: list[str] = field(default_factory=list)       # neue Dateien im Eingang
    bekannt: int = 0                                      # Anhänge, die schon einmal geholt wurden
    zu_gross: list[str] = field(default_factory=list)     # über dem Größenlimit des Projekts
    verloren: list[str] = field(default_factory=list)     # Discord gibt die Datei nicht mehr heraus
    mehr: bool = False                                    # es gibt weitere, noch nicht angesehene


def token(fr: Flugrouten) -> str:
    """Das Bot-Token der Discord-Flugroute — leer, solange kein Bot eingerichtet ist. Ob die
    Flugroute zum *Melden* eingeschaltet ist, spielt keine Rolle."""
    return discord_token(fr) or ""


def kanal_pruefen(eingabe: str) -> str:
    """Die Kanal-ID aus dem, was Menschen einfügen: die ID, ``<#ID>`` oder der Link zum Kanal
    (``https://discord.com/channels/<Server>/<Kanal>``). Leer bleibt leer (= aus)."""
    wert = str(eingabe or "").strip()
    if not wert:
        return ""
    m = re.fullmatch(r"https://(?:[a-z]+\.)?discord(?:app)?\.com/channels/\d+/(\d+)(?:/\d+)?/?", wert)
    if m:
        wert = m.group(1)
    wert = wert.removeprefix("<#").removesuffix(">")
    if not wert.isdigit() or not 15 <= len(wert) <= 20:
        raise DiscordFehler(i18n.t("discord.err.kanal_id"))
    return wert


# --------------------------------------------------------------------------- #
#  Anfragen an Discord — ausschließlich lesend
# --------------------------------------------------------------------------- #
def _lesen(pfad: str, bot_token: str, **parameter):
    """Eine lesende Anfrage. Fehler ohne Token und ohne die Antwort des Servers."""
    import httpx
    try:
        r = httpx.get(f"{API}{pfad}", headers={"Authorization": f"Bot {bot_token}"},
                      params=parameter or None, timeout=20.0)
    except httpx.HTTPError as exc:
        raise DiscordFehler(i18n.t("discord.err.netz", typ=exc.__class__.__name__)) from None
    if r.status_code == 401:
        raise DiscordFehler(i18n.t("discord.err.token"))
    if r.status_code in (403, 404):
        raise DiscordFehler(i18n.t("discord.err.kanal", status=r.status_code))
    if r.status_code == 429:
        raise DiscordFehler(i18n.t("kanal.discord.429"))
    if r.status_code >= 400:
        raise DiscordFehler(i18n.t("discord.err.status", status=r.status_code))
    try:
        return r.json()
    except ValueError:
        raise DiscordFehler(i18n.t("discord.err.antwort")) from None


def kanal_liste(bot_token: str) -> list[dict]:
    """Die Textkanäle, die der Bot sieht — ``{"server", "name", "id"}`` — damit niemand eine ID
    suchen muss. Server, deren Kanäle der Bot nicht lesen darf, fehlen einfach."""
    server = _lesen("/users/@me/guilds", bot_token, limit=200)
    if not isinstance(server, list):
        raise DiscordFehler(i18n.t("discord.err.antwort"))
    gefunden, fehler = [], None
    for s in server[:_MAX_SERVER]:
        if not isinstance(s, dict) or not str(s.get("id", "")).isdigit():
            continue
        try:
            kanaele = _lesen(f"/guilds/{s['id']}/channels", bot_token)
        except DiscordFehler as exc:
            fehler = exc
            continue
        for k in kanaele if isinstance(kanaele, list) else []:
            if isinstance(k, dict) and k.get("type") in _TEXTKANAL and str(k.get("id", "")).isdigit():
                gefunden.append({"server": str(s.get("name") or ""), "name": str(k.get("name") or ""),
                                 "id": str(k["id"]), "_platz": int(k.get("position") or 0)})
    if not gefunden and fehler is not None:
        raise fehler                                      # kein einziger Server ließ sich lesen
    gefunden.sort(key=lambda k: (k["server"].lower(), k["_platz"], k["name"].lower()))
    return [{"server": k["server"], "name": k["name"], "id": k["id"]} for k in gefunden]


def _inhalt_erlaubt(bot_token: str) -> bool:
    """Steht in den Einstellungen des Bots, dass er Nachrichteninhalte lesen darf?"""
    daten = _lesen("/applications/@me", bot_token)
    try:
        return bool(int(daten.get("flags") or 0) & _INHALT_ERLAUBT)
    except (AttributeError, TypeError, ValueError):
        return False


def _wirkt_leer(nachricht: dict) -> bool:
    """Eine gewöhnliche Nachricht eines Menschen ganz ohne Inhalt gibt es bei Discord nicht — so
    sieht eine Nachricht aus, deren Inhalt Discord dem Bot vorenthält."""
    if nachricht.get("type") not in _GEWOEHNLICH or (nachricht.get("author") or {}).get("bot"):
        return False
    return not any(nachricht.get(feld) for feld in (
        "content", "attachments", "embeds", "components", "sticker_items", "poll",
        "message_snapshots", "activity", "call"))


def _anhaenge(nachricht: dict) -> list[dict]:
    """Die Anhänge einer Nachricht — auch die einer hinein weitergeleiteten Nachricht."""
    gefunden = list(nachricht.get("attachments") or [])
    for bild in nachricht.get("message_snapshots") or []:
        if isinstance(bild, dict) and isinstance(bild.get("message"), dict):
            gefunden.extend(bild["message"].get("attachments") or [])
    return [a for a in gefunden if isinstance(a, dict)]


class _ZuGross(Exception):
    """Die Datei ist größer, als Discord angekündigt hat — und größer als das Limit."""


def _laden(adresse: str, grenze: int) -> bytes | None:
    """Eine Datei vom Dateispeicher von Discord laden — ohne Token. ``None`` = nicht (mehr) da.
    Von anderen Adressen wird nie geladen; über ``grenze`` Bytes bricht das Laden ab."""
    import httpx
    teile = urlsplit(str(adresse or ""))
    if teile.scheme != "https" or teile.hostname not in DATEI_HOSTS:
        return None
    try:
        with httpx.stream("GET", adresse, timeout=60.0) as r:
            if r.status_code in (403, 404, 410):
                return None
            if r.status_code != 200:
                raise DiscordFehler(i18n.t("discord.err.status", status=r.status_code))
            stuecke, summe = [], 0
            for stueck in r.iter_bytes():
                summe += len(stueck)
                if summe > grenze:
                    raise _ZuGross
                stuecke.append(stueck)
    except httpx.HTTPError as exc:
        raise DiscordFehler(i18n.t("discord.err.netz", typ=exc.__class__.__name__)) from None
    return b"".join(stuecke)


# --------------------------------------------------------------------------- #
#  Was wir uns je Projekt merken
# --------------------------------------------------------------------------- #
def _stand_pfad(hive: Path) -> Path:
    return config.honig(hive) / "discord.json"


def stand(hive: Path) -> dict:
    """Der gemerkte Stand: Kanal, bis wohin abgeholt wurde, bekannte Inhalte, letzter Abruf."""
    try:
        daten = json.loads(_stand_pfad(hive).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        daten = {}
    if not isinstance(daten, dict):
        daten = {}
    letzte = str(daten.get("letzte_id") or "0")
    return {"kanal": str(daten.get("kanal") or ""),
            "letzte_id": letzte if letzte.isdigit() else "0",
            "hashes": list(daten.get("hashes") or []),
            "letzter_abruf": str(daten.get("letzter_abruf") or ""),
            "geholt": int(daten.get("geholt") or 0)}


def _stand_schreiben(hive: Path, daten: dict) -> None:
    pfad = _stand_pfad(hive)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
#  Abholen
# --------------------------------------------------------------------------- #
def abholen(hive: Path, bot_token: str, kanal: str, *, max_mb: int = 100) -> Abruf:
    """Neue Anhänge aus ``kanal`` in den Eingang von ``hive`` legen.

    Hält sich an die drei Zusagen im Kopf dieses Moduls. Bricht der Abruf mittendrin ab, ist
    alles bis dahin Geholte gemerkt; der nächste Abruf macht dort weiter.
    """
    kanal = kanal_pruefen(kanal)
    if not kanal:
        raise DiscordFehler(i18n.t("dc.none"))
    if not bot_token:
        raise DiscordFehler(i18n.t("dc.nobot"))
    merk = stand(hive)
    if merk["kanal"] != kanal:
        # Anderer Kanal → von vorn. Die bekannten Inhalte bleiben gemerkt, also nichts doppelt.
        merk.update(kanal=kanal, letzte_id="0")
    ergebnis = Abruf()
    grenze = max_mb * 1024 * 1024
    bekannt = set(merk["hashes"])
    inhalt_geprueft = False
    try:
        while True:
            seite = _lesen(f"/channels/{kanal}/messages", bot_token,
                           after=merk["letzte_id"], limit=SEITE)
            if not isinstance(seite, list):
                raise DiscordFehler(i18n.t("discord.err.antwort"))
            # Discord liefert die neueste zuerst — abgearbeitet wird von alt nach neu, damit
            # „bis hierhin erledigt" immer stimmt.
            seite = sorted((n for n in seite if isinstance(n, dict)
                            and str(n.get("id", "")).isdigit()), key=lambda n: int(n["id"]))
            if not seite:
                break
            if not inhalt_geprueft and any(_wirkt_leer(n) for n in seite):
                # Sieht so aus, als hielte Discord die Inhalte zurück. Weiterzählen hieße, die
                # Anhänge dieser Nachrichten für immer zu überspringen — erst nachsehen.
                if not _inhalt_erlaubt(bot_token):
                    raise DiscordFehler(i18n.t("discord.err.inhalt"))
                inhalt_geprueft = True
            for nachricht in seite:
                ergebnis.nachrichten += 1
                for anhang in _anhaenge(nachricht):
                    name = sicherer_name(str(anhang.get("filename") or ""))
                    try:
                        groesse = int(anhang.get("size") or 0)
                    except (TypeError, ValueError):
                        groesse = 0
                    if groesse > grenze:
                        ergebnis.zu_gross.append(name)
                        continue
                    try:
                        inhalt = _laden(anhang.get("url"), grenze)
                    except _ZuGross:
                        ergebnis.zu_gross.append(name)
                        continue
                    if inhalt is None:
                        ergebnis.verloren.append(name)
                        continue
                    summe = hashlib.sha256(inhalt).hexdigest()
                    if summe in bekannt:
                        ergebnis.bekannt += 1
                        continue
                    try:
                        ergebnis.geholt.append(_in_den_eingang(hive, name, inhalt))
                    except OSError as exc:
                        raise DiscordFehler(i18n.t("postfach.err.schreiben",
                                                   typ=exc.__class__.__name__)) from None
                    bekannt.add(summe)
                    merk["hashes"].append(summe)
                merk["letzte_id"] = str(nachricht["id"])  # erst jetzt gilt die Nachricht als erledigt
            if len(seite) < SEITE:
                break
            if ergebnis.nachrichten >= MAX_NACHRICHTEN:
                ergebnis.mehr = True
                break
    finally:
        merk["geholt"] += len(ergebnis.geholt)
        merk["letzter_abruf"] = datetime.now(UTC).replace(microsecond=0).isoformat()
        try:
            _stand_schreiben(hive, merk)
        except OSError:
            pass
    return ergebnis


# --------------------------------------------------------------------------- #
#  Für die Wache: von selbst nachsehen, aber nicht bei jedem Takt
# --------------------------------------------------------------------------- #
_LETZTER_VERSUCH: dict[str, float] = {}
_LETZTER_FEHLER: dict[str, str] = {}


def automatisch(hive: Path, *, kanal: str, max_mb: int, journal=None) -> tuple[Abruf | None, str]:
    """Für die Wache: höchstens alle :data:`PAUSE` Sekunden abholen.

    Gibt ``(Abruf, "")`` zurück, ``(None, Fehlertext)`` bei einem **neuen** Fehler und
    ``(None, "")``, wenn nichts zu tun war (nicht eingerichtet, noch nicht wieder dran, derselbe
    Fehler wie beim letzten Mal — der soll nicht alle zehn Minuten im Protokoll stehen).
    """
    from .flugrouten import load_flugrouten
    if not (kanal or "").strip():
        return None, ""
    schluessel = str(hive)
    zuletzt = _LETZTER_VERSUCH.get(schluessel)
    if zuletzt is not None and time.monotonic() - zuletzt < PAUSE:
        return None, ""
    _LETZTER_VERSUCH[schluessel] = time.monotonic()
    bot_token = token(load_flugrouten())
    if not bot_token:
        return None, ""
    try:
        ergebnis = abholen(hive, bot_token, kanal, max_mb=max_mb)
    except DiscordFehler as exc:
        neu = str(exc) != _LETZTER_FEHLER.get(schluessel)
        _LETZTER_FEHLER[schluessel] = str(exc)
        return None, (str(exc) if neu else "")
    _LETZTER_FEHLER.pop(schluessel, None)
    protokollieren(journal, ergebnis)
    return ergebnis, ""


def melden(con, ergebnis: Abruf, *, max_mb: int) -> None:
    """Das Ergebnis eines Abrufs sagen — für Konsole und Flugbrett gleich."""
    if ergebnis.geholt:
        namen = ", ".join(ergebnis.geholt[:8]) + (" …" if len(ergebnis.geholt) > 8 else "")
        con.honey(i18n.t("pf.got", n=len(ergebnis.geholt), names=namen), "📥")
    else:
        con.info(i18n.t("pf.nothing"), "🐝")
    if ergebnis.bekannt:
        con.info(i18n.t("pf.known", n=ergebnis.bekannt), "🐝")
    if ergebnis.zu_gross:
        con.ask(i18n.t("pf.toobig", mb=max_mb, names=", ".join(ergebnis.zu_gross[:8])), "⚠️")
    if ergebnis.verloren:
        con.ask(i18n.t("dc.lost", names=", ".join(ergebnis.verloren[:8])), "⚠️")
    if ergebnis.mehr:
        con.info(i18n.t("dc.more"), "🐝")


def protokollieren(journal, ergebnis: Abruf) -> None:
    """Ins Journal: nur Zahlen und die Namen der neuen Dateien — nie Verfasser oder Text."""
    if journal is not None and (ergebnis.geholt or ergebnis.zu_gross or ergebnis.verloren):
        journal.event("discord_abruf", geholt=list(ergebnis.geholt), bekannt=ergebnis.bekannt,
                      zu_gross=len(ergebnis.zu_gross), verloren=len(ergebnis.verloren),
                      nachrichten=ergebnis.nachrichten)

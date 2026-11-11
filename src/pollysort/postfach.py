"""Postfach — Anhänge aus einem E-Mail-Ordner ins Flugloch (den Eingang) eines Projekts holen.

Die Idee: Im Postfach gibt es je Projekt einen Ordner (z. B. „PollySort/Büro"). Was man dort
hineinschiebt oder per Regel einsortieren lässt, landet als Datei im Eingang des Projekts und
wird von dort wie jede andere Datei sortiert.

Drei Zusagen, an denen nichts rüttelt:

- **Nur lesen.** Der Ordner wird schreibgeschützt geöffnet (``readonly``), die Nachrichten werden
  mit ``BODY.PEEK`` geholt: Im Postfach wird nichts gelöscht, verschoben oder als gelesen markiert.
- **Nichts doppelt, nichts überschrieben.** Je Projekt merkt sich ``.honig/postfach.json``, bis zu
  welcher Nachricht abgeholt wurde und welche Inhalte (SHA-256) schon da waren. Eine Datei im
  Eingang wird nie ersetzt — bei gleichem Namen bekommt die neue eine Nummer.
- 🔒 **Wachssiegel.** Angemeldet wird über eine geprüfte TLS-Verbindung mit den Zugangsdaten der
  E-Mail-Flugroute (Tresor). Passwort, Absender und Betreff stehen in keiner Meldung, keinem
  Journal und keinem Prompt; Dateinamen aus E-Mails werden entschärft, bevor sie die Platte sehen.

Der Abruf spricht IMAP, das Protokoll, mit dem auch E-Mail-Programme das Postfach lesen.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from . import config, i18n
from .flugrouten import Flugrouten, anbieter_fuer_host, email_password

#: Üblicher Port: IMAP von Anfang an verschlüsselt. Jeder andere Port wechselt per STARTTLS.
IMAP_PORT = 993
#: So viele Nachrichten sieht ein Abruf höchstens an — der Rest kommt beim nächsten Mal dran.
MAX_NACHRICHTEN = 200
#: So oft sieht die Wache von selbst nach (Sekunden).
PAUSE = 10 * 60
#: Eine E-Mail ist größer als ihre Anhänge (Base64 bläht um ein Drittel auf) — Aufschlag fürs Limit.
_MAIL_AUFSCHLAG = 1.4

#: Signaturen und Verpackung, die kein Mensch als „Anhang" meint.
_KEIN_ANHANG_TYP = ("application/pkcs7-signature", "application/x-pkcs7-signature",
                    "application/pgp-signature", "application/pgp-keys")
_KEIN_ANHANG_NAME = ("smime.p7s", "signature.asc", "winmail.dat")
#: Gerätenamen, die Windows als Dateinamen nicht annimmt.
_RESERVIERT = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
               *(f"lpt{i}" for i in range(1, 10))}


class PostfachFehler(RuntimeError):
    """Der Abruf ist gescheitert — der Text ist für den Menschen und enthält kein Geheimnis."""


@dataclass
class Zugang:
    """Womit sich PollySort am Postfach anmeldet. Das Passwort erscheint in keinem ``repr``."""

    host: str
    port: int
    adresse: str
    passwort: str = field(repr=False)


@dataclass
class Abruf:
    """Was ein Abruf gebracht hat."""

    nachrichten: int = 0                                  # angesehene neue Nachrichten
    geholt: list[str] = field(default_factory=list)       # neue Dateien im Eingang
    bekannt: int = 0                                      # Anhänge, die schon einmal geholt wurden
    zu_gross: list[str] = field(default_factory=list)     # über dem Größenlimit des Projekts
    rest: int = 0                                         # Nachrichten für den nächsten Abruf


def zugang(fr: Flugrouten) -> Zugang | None:
    """Der Zugang aus der E-Mail-Flugroute — ``None``, solange Adresse, Passwort oder der
    Posteingangsserver fehlen. Ob die Flugroute zum *Melden* eingeschaltet ist, spielt keine Rolle."""
    e = fr.email
    passwort = email_password(fr)
    if not (e.address and passwort and e.imap_host):
        return None
    return Zugang(e.imap_host, int(e.imap_port or IMAP_PORT), e.address, passwort)


# --------------------------------------------------------------------------- #
#  Ordnernamen: IMAP schreibt Umlaute in einer eigenen Kodierung („modified UTF-7")
# --------------------------------------------------------------------------- #
def _utf7_kodieren(name: str) -> str:
    aus, block = [], []

    def leeren() -> None:
        if block:
            roh = base64.b64encode("".join(block).encode("utf-16-be")).decode("ascii")
            aus.append("&" + roh.rstrip("=").replace("/", ",") + "-")
            block.clear()

    for zeichen in name:
        if 0x20 <= ord(zeichen) <= 0x7E:
            leeren()
            aus.append("&-" if zeichen == "&" else zeichen)
        else:
            block.append(zeichen)
    leeren()
    return "".join(aus)


def _utf7_dekodieren(name: str) -> str:
    def ersetzen(m: re.Match) -> str:
        if not m.group(1):
            return "&"
        roh = m.group(1).replace(",", "/")
        try:
            return base64.b64decode(roh + "=" * (-len(roh) % 4)).decode("utf-16-be")
        except (ValueError, UnicodeDecodeError):
            return m.group(0)                             # unlesbar → so lassen, wie es dasteht
    return re.sub(r"&([^-]*)-", ersetzen, name)


def _imap_name(ordner: str) -> str:
    """Ein Ordnername so, wie ihn der Server erwartet: kodiert und in Anführungszeichen."""
    kodiert = _utf7_kodieren(ordner).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{kodiert}"'


# --------------------------------------------------------------------------- #
#  Verbindung
# --------------------------------------------------------------------------- #
def _verbinden(z: Zugang):
    """Anmelden über eine Verbindung, deren Zertifikat geprüft ist. Fehler ohne Geheimnis."""
    import imaplib
    import ssl
    kontext = ssl.create_default_context()
    try:
        if z.port == IMAP_PORT:
            imap = imaplib.IMAP4_SSL(z.host, z.port, ssl_context=kontext, timeout=30)
        else:
            imap = imaplib.IMAP4(z.host, z.port, timeout=30)
            imap.starttls(ssl_context=kontext)
    except ssl.SSLCertVerificationError:
        raise PostfachFehler(i18n.t("kanal.cert")) from None
    except (OSError, imaplib.IMAP4.error) as exc:
        raise PostfachFehler(i18n.t("postfach.err.netz", typ=exc.__class__.__name__)) from None
    try:
        imap.login(z.adresse, z.passwort)
    except imaplib.IMAP4.error:
        # Die Antwort des Servers kann die Anmeldedaten wiederholen — deshalb nie durchreichen.
        _abmelden(imap)
        anbieter = anbieter_fuer_host(z.host)
        hinweis = (" " + i18n.t(anbieter.hinweis)
                   if anbieter is not None and anbieter.hinweis else "")
        raise PostfachFehler(i18n.t("postfach.err.anmeldung") + hinweis) from None
    except OSError as exc:
        raise PostfachFehler(i18n.t("postfach.err.netz", typ=exc.__class__.__name__)) from None
    return imap


def _abmelden(imap) -> None:
    try:
        imap.logout()
    except Exception:
        pass


def _text(daten) -> str:
    """Eine IMAP-Antwort (Liste aus Bytes und Tupeln) als ein Stück Text — zum Durchsuchen."""
    teile = []
    for d in daten or []:
        if isinstance(d, tuple):
            d = d[0]
        if isinstance(d, bytes):
            teile.append(d.decode("ascii", "replace"))
    return " ".join(teile)


def ordner_liste(z: Zugang) -> list[str]:
    """Die Ordner des Postfachs — damit man den Namen nicht raten muss."""
    import imaplib
    imap = _verbinden(z)
    try:
        typ, daten = imap.list()
    except (OSError, imaplib.IMAP4.error) as exc:
        raise PostfachFehler(i18n.t("postfach.err.netz", typ=exc.__class__.__name__)) from None
    finally:
        _abmelden(imap)
    if typ != "OK":
        raise PostfachFehler(i18n.t("postfach.err.antwort"))
    namen = []
    for zeile in daten or []:
        if not isinstance(zeile, bytes):
            continue
        # (\HasNoChildren) "/" "Ordner/Name" — der Name steht am Ende, mit oder ohne Anführungszeichen
        m = re.match(rb'\((?P<flags>[^)]*)\)\s+(?:"[^"]*"|NIL)\s+(?P<name>.+)$', zeile.strip())
        if not m or b"\\noselect" in m.group("flags").lower():
            continue
        name = m.group("name").decode("ascii", "replace").strip()
        if name.startswith('"') and name.endswith('"'):
            name = name[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        namen.append(_utf7_dekodieren(name))
    return sorted(namen, key=str.lower)


# --------------------------------------------------------------------------- #
#  Was wir uns je Projekt merken
# --------------------------------------------------------------------------- #
def _stand_pfad(hive: Path) -> Path:
    return config.honig(hive) / "postfach.json"


def stand(hive: Path) -> dict:
    """Der gemerkte Stand: Ordner, bis wohin abgeholt wurde, bekannte Inhalte, letzter Abruf."""
    try:
        daten = json.loads(_stand_pfad(hive).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        daten = {}
    if not isinstance(daten, dict):
        daten = {}
    return {"ordner": str(daten.get("ordner") or ""),
            "uidvalidity": str(daten.get("uidvalidity") or ""),
            "letzte_uid": int(daten.get("letzte_uid") or 0),
            "hashes": list(daten.get("hashes") or []),
            "letzter_abruf": str(daten.get("letzter_abruf") or ""),
            "geholt": int(daten.get("geholt") or 0)}


def _stand_schreiben(hive: Path, daten: dict) -> None:
    pfad = _stand_pfad(hive)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
#  Anhänge
# --------------------------------------------------------------------------- #
def sicherer_name(roh: str) -> str:
    """Aus dem Dateinamen einer E-Mail einen machen, der nur im Eingang landen kann.

    Der Name kommt von außen: Er darf keinen Pfad enthalten (``..\\..\\Autostart\\x.bat``), keine
    Zeichen, die Windows ablehnt, keinen Gerätenamen und keinen führenden Punkt (versteckte
    Dateien, ``.honig``).
    """
    name = str(roh or "").replace("\\", "/").split("/")[-1]
    name = re.sub(r'[<>:"|?*\x00-\x1f\x7f]', "_", name).strip(" .")
    if not name:
        return "anhang"
    stamm, punkt, endung = name.rpartition(".")
    if not punkt or not stamm:
        stamm, endung = name, ""
    if stamm.lower() in _RESERVIERT:
        stamm = "_" + stamm
    endung = endung[:20]
    stamm = stamm[: 120 - len(endung)]
    return f"{stamm}.{endung}" if endung else stamm


def _anhaenge(roh: bytes) -> list[tuple[str, bytes]]:
    """``(Dateiname, Inhalt)`` für jeden echten Anhang einer Nachricht.

    Bilder, die im Text stehen (Logos in Signaturen), und kryptografische Signaturen zählen
    nicht. Weitergeleitete Nachrichten werden mit durchsucht.
    """
    import email
    import email.policy
    try:
        nachricht = email.message_from_bytes(roh, policy=email.policy.default)
    except Exception:
        return []
    gefunden = []
    for teil in nachricht.walk():
        if teil.is_multipart():
            continue
        try:
            name = teil.get_filename()
            if not name or name.lower() in _KEIN_ANHANG_NAME:
                continue
            if teil.get_content_type() in _KEIN_ANHANG_TYP:
                continue
            if (teil.get_content_disposition() == "inline"
                    and teil.get_content_maintype() == "image"):
                continue
            inhalt = teil.get_payload(decode=True)
        except Exception:
            continue                                      # ein kaputter Teil kippt nicht die Nachricht
        if inhalt:
            gefunden.append((sicherer_name(name), bytes(inhalt)))
    return gefunden


def _ablegen(hive: Path, name: str, inhalt: bytes) -> str:
    """Einen Anhang in den Eingang legen, ohne je eine Datei zu ersetzen. Gibt den Namen zurück."""
    stamm, punkt, endung = name.rpartition(".")
    if not punkt:
        stamm, endung = name, ""
    halb = config.honig(hive) / f"postfach.teil-{time.monotonic_ns()}"
    halb.parent.mkdir(parents=True, exist_ok=True)
    halb.write_bytes(inhalt)                              # erst fertig schreiben …
    try:
        for nr in range(1, 1000):
            zusatz = "" if nr == 1 else f" ({nr})"
            kandidat = f"{stamm}{zusatz}.{endung}" if endung else f"{stamm}{zusatz}"
            try:
                _einsetzen(halb, hive / kandidat)         # … dann in einem Schritt in den Eingang
                return kandidat
            except FileExistsError:
                continue
        raise OSError("kein freier Dateiname")
    finally:
        halb.unlink(missing_ok=True)


def _einsetzen(halb: Path, ziel: Path) -> None:
    """Die fertige Datei unter ``ziel`` erscheinen lassen — ``FileExistsError`` statt Ersetzen.

    Eine harte Verknüpfung entsteht in einem Schritt und überschreibt nie (anders als Umbenennen
    unter Linux und macOS). Kann das Dateisystem das nicht, wird die Datei ausschließlich neu
    angelegt (``x``) und beschrieben.
    """
    import os
    try:
        os.link(halb, ziel)
    except FileExistsError:
        raise
    except OSError:
        with open(ziel, "xb") as fh:
            fh.write(halb.read_bytes())


def abholen(hive: Path, z: Zugang, ordner: str, *, max_mb: int = 100) -> Abruf:
    """Neue Anhänge aus ``ordner`` in den Eingang von ``hive`` legen.

    Hält sich an die drei Zusagen im Kopf dieses Moduls. Bricht der Abruf mittendrin ab, ist
    alles bis dahin Geholte gemerkt; der nächste Abruf macht dort weiter.
    """
    import imaplib
    ordner = (ordner or "").strip()
    if not ordner:
        raise PostfachFehler(i18n.t("pf.none"))
    merk = stand(hive)
    ergebnis = Abruf()
    imap = _verbinden(z)
    try:
        try:
            typ, daten = imap.select(_imap_name(ordner), readonly=True)
        except imaplib.IMAP4.error:
            typ = "NO"
        if typ != "OK":
            raise PostfachFehler(i18n.t("postfach.err.ordner", ordner=ordner))
        typ, daten = imap.status(_imap_name(ordner), "(UIDVALIDITY)")
        m = re.search(r"UIDVALIDITY (\d+)", _text(daten)) if typ == "OK" else None
        gueltigkeit = m.group(1) if m else ""
        # Anderer Ordner oder vom Server neu nummeriert → von vorn zählen. Die bekannten Inhalte
        # bleiben gemerkt, deshalb kommt trotzdem nichts doppelt an.
        if merk["ordner"] != ordner or merk["uidvalidity"] != gueltigkeit:
            merk.update(ordner=ordner, uidvalidity=gueltigkeit, letzte_uid=0)
        typ, daten = imap.uid("SEARCH", None, f"UID {merk['letzte_uid'] + 1}:*")
        if typ != "OK":
            raise PostfachFehler(i18n.t("postfach.err.antwort"))
        # „n:*" liefert immer mindestens die höchste Nummer — auch wenn sie nicht neu ist.
        uids = sorted({int(u) for u in _text(daten).split() if u.isdigit()
                       and int(u) > merk["letzte_uid"]})
        ergebnis.rest = max(0, len(uids) - MAX_NACHRICHTEN)
        uids = uids[:MAX_NACHRICHTEN]
        groessen: dict[int, int] = {}
        if uids:
            typ, daten = imap.uid("FETCH", ",".join(map(str, uids)), "(RFC822.SIZE)")
            for m in re.finditer(r"\(([^()]*)\)", _text(daten) if typ == "OK" else ""):
                uid = re.search(r"UID (\d+)", m.group(1))
                groesse = re.search(r"RFC822\.SIZE (\d+)", m.group(1))
                if uid and groesse:
                    groessen[int(uid.group(1))] = int(groesse.group(1))
        grenze = max_mb * 1024 * 1024
        bekannt = set(merk["hashes"])
        for uid in uids:
            ergebnis.nachrichten += 1
            if groessen.get(uid, 0) > grenze * _MAIL_AUFSCHLAG + 1024 * 1024:
                ergebnis.zu_gross.append(i18n.t("pf.mail_gross", mb=groessen[uid] // (1024 * 1024)))
                merk["letzte_uid"] = uid
                continue
            typ, daten = imap.uid("FETCH", str(uid), "(BODY.PEEK[])")
            roh = next((d[1] for d in daten or [] if isinstance(d, tuple) and len(d) > 1), None)
            if typ != "OK" or not isinstance(roh, bytes):
                raise PostfachFehler(i18n.t("postfach.err.antwort"))
            for name, inhalt in _anhaenge(roh):
                if len(inhalt) > grenze:
                    ergebnis.zu_gross.append(name)
                    continue
                summe = hashlib.sha256(inhalt).hexdigest()
                if summe in bekannt:
                    ergebnis.bekannt += 1
                    continue
                try:
                    ergebnis.geholt.append(_ablegen(hive, name, inhalt))
                except OSError as exc:
                    raise PostfachFehler(i18n.t("postfach.err.schreiben",
                                                typ=exc.__class__.__name__)) from None
                bekannt.add(summe)
                merk["hashes"].append(summe)
            merk["letzte_uid"] = uid                      # erst jetzt gilt die Nachricht als erledigt
    except (OSError, imaplib.IMAP4.error) as exc:
        raise PostfachFehler(i18n.t("postfach.err.netz", typ=exc.__class__.__name__)) from None
    finally:
        _abmelden(imap)
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


def automatisch(hive: Path, *, ordner: str, max_mb: int, journal=None) -> tuple[Abruf | None, str]:
    """Für die Wache: höchstens alle :data:`PAUSE` Sekunden abholen.

    Gibt ``(Abruf, "")`` zurück, ``(None, Fehlertext)`` bei einem **neuen** Fehler und
    ``(None, "")``, wenn nichts zu tun war (nicht eingerichtet, noch nicht wieder dran, derselbe
    Fehler wie beim letzten Mal — der soll nicht alle zehn Minuten im Protokoll stehen).
    """
    from .flugrouten import load_flugrouten
    if not (ordner or "").strip():
        return None, ""
    schluessel = str(hive)
    zuletzt = _LETZTER_VERSUCH.get(schluessel)
    if zuletzt is not None and time.monotonic() - zuletzt < PAUSE:
        return None, ""
    _LETZTER_VERSUCH[schluessel] = time.monotonic()
    z = zugang(load_flugrouten())
    if z is None:
        return None, ""
    try:
        ergebnis = abholen(hive, z, ordner, max_mb=max_mb)
    except PostfachFehler as exc:
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
    if ergebnis.rest:
        con.info(i18n.t("pf.rest", n=ergebnis.rest), "🐝")


def protokollieren(journal, ergebnis: Abruf) -> None:
    """Ins Journal: nur Zahlen und die Namen der neuen Dateien — nie Absender oder Betreff."""
    if journal is not None and (ergebnis.geholt or ergebnis.zu_gross):
        journal.event("postfach_abruf", geholt=list(ergebnis.geholt), bekannt=ergebnis.bekannt,
                      zu_gross=len(ergebnis.zu_gross), nachrichten=ergebnis.nachrichten)

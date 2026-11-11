"""Wachdienst der Wächterbienen — was „gemeldet" heißt und wie sicher E-Mail verschickt wird.

Sichert zu:
- ``gemeldet`` wird nur gesetzt, wenn wirklich verschickt wurde. Ansehen (``kalender``) und die
  Wache ohne Flugrouten lassen den Termin offen — sonst bliebe er nach dem Einrichten stumm.
- Die Wache zeigt eine Deadline ohne Flugrouten einmal je Programmlauf an, nicht bei jedem Takt,
  und wiederholt einen gescheiterten Versand nicht im Sekundentakt.
- Alte, zu Unrecht gesetzte Merker werden einmal gegen das Journal abgeglichen.
- SMTP prüft das Zertifikat des Servers (STARTTLS und Port 465); 🔒 kein Passwort in Fehlern.
- Umgebungsvariablen: ``POLLYSORT_…`` vor dem Altnamen ``BEEHIVE_…``.
"""

from __future__ import annotations

import json
import smtplib
import ssl

import pytest

from pollysort.config import AppConfig, HiveSeed, honig
from pollysort.console import BeeConsole
from pollysort.flugrouten import DiscordConfig, EmailConfig, Flugrouten, discord_token, email_password
from pollysort.journal import Journal
from pollysort.llm.client import OfflineClient
from pollysort.pipeline import Context
from pollysort.swarm import Kalender, Waechterbiene
from pollysort.swarm import waechterbiene as wb
from pollysort.swarm.kanaele import DiscordKanal, EmailKanal, KanalError

PASSWORT = "app-PASSWORT-xyz789"


def _ctx(hive):
    hive.mkdir(parents=True, exist_ok=True)
    seed = HiveSeed(categories=["rechnungen"], responsibility={"rechnungen": []})
    return Context.build(hive=hive, cfg=AppConfig(llm_provider="offline"), seed=seed,
                         client=OfflineClient(seed.categories), console=BeeConsole(quiet=True),
                         journal=Journal(hive))


class _Kanal:
    name = "Discord"
    STOCK = "Discord-Wabe"

    def __init__(self, *, kaputt: bool = False):
        self.calls = 0
        self.kaputt = kaputt

    def senden(self, titel, text):
        self.calls += 1
        if self.kaputt:
            raise KanalError("Discord nicht erreichbar (ConnectError)")


def _waechter(ctx, *kanaele):
    return Waechterbiene(ctx, flugrouten=Flugrouten(), kanaele=list(kanaele))


def _ereignisse(hive, art: str) -> list[dict]:
    log = honig(hive) / "log.jsonl"
    if not log.exists():
        return []
    zeilen = [json.loads(z) for z in log.read_text(encoding="utf-8").splitlines() if z.strip()]
    return [z for z in zeilen if z.get("event") == art]


def _gemeldet(hive) -> list[bool]:
    return [t.gemeldet for t in Kalender(hive)._all()]


# ---- „gemeldet" heißt: wirklich verschickt --------------------------------
def test_ansehen_markiert_nicht_als_gemeldet(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    w = _waechter(ctx)
    w.kalender.eintragen("Miete", "2000-01-01")

    w.deadlines_pruefen(senden=False)                   # 'kalender' in der Konsole
    assert _gemeldet(hive) == [False]

    kanal = _Kanal()                                    # später: Flugrouten eingerichtet
    _waechter(ctx, kanal).deadlines_pruefen(senden=True)  # 'kalender melden'
    assert kanal.calls == 1 and _gemeldet(hive) == [True]


def test_melden_ohne_flugrouten_markiert_nicht(tmp_path):
    hive = tmp_path / "hive"
    w = _waechter(_ctx(hive))
    w.kalender.eintragen("Miete", "2000-01-01")
    w.deadlines_pruefen(senden=True)                    # 'kalender melden' ohne Flugrouten
    assert _gemeldet(hive) == [False]


def test_wache_ohne_flugrouten_zeigt_einmal_und_laesst_offen(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    _waechter(ctx).kalender.eintragen("Miete", "2000-01-01")

    for _ in range(3):                                  # drei Takte der Wache
        _waechter(ctx).deadlines_pruefen()
    assert len(_ereignisse(hive, "waechter_reminder")) == 1, "nicht bei jedem Takt neu anzeigen"
    assert _gemeldet(hive) == [False]

    kanal = _Kanal()                                    # Flugrouten kommen dazu → jetzt fliegt sie
    _waechter(ctx, kanal).deadlines_pruefen()
    assert kanal.calls == 1 and _gemeldet(hive) == [True]


def test_gescheiterter_versand_wird_nicht_im_takt_wiederholt(tmp_path, monkeypatch):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    kanal = _Kanal(kaputt=True)
    w = _waechter(ctx, kanal)
    w.kalender.eintragen("Miete", "2000-01-01")

    w.deadlines_pruefen()
    w.deadlines_pruefen()                               # nächster Takt, Sekunden später
    assert kanal.calls == 1 and _gemeldet(hive) == [False]

    w.deadlines_pruefen(senden=True)                    # von Hand geht immer
    assert kanal.calls == 2

    monkeypatch.setattr(wb, "VERSUCH_PAUSE", 0)         # Pause vorbei → die Wache probiert erneut
    kanal.kaputt = False
    w.deadlines_pruefen()
    assert kanal.calls == 3 and _gemeldet(hive) == [True]


# ---- Altlast: Merker aus älteren Versionen --------------------------------
def test_alte_merker_ohne_versand_werden_einmal_zurueckgenommen(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    kal = Kalender(hive)
    nie = kal.eintragen("Miete", "2000-01-01")          # von der alten Ansicht „gemeldet"
    echt = kal.eintragen("Steuer", "2000-02-01")        # wirklich verschickt (steht im Journal)
    kal.markiere_gemeldet(nie.id)
    kal.markiere_gemeldet(echt.id)
    ctx.journal.event("waechter_versand", kanal="Discord", termin=echt.id, erfolg=True)
    ctx.journal.event("waechter_versand", kanal="E-Mail", termin=nie.id, erfolg=False)

    kanal = _Kanal()
    _waechter(ctx, kanal).deadlines_pruefen(senden=True)
    assert kanal.calls == 1, "nur der nie verschickte Termin fliegt"
    assert (honig(hive) / wb.ABGLEICH_MARKE).exists()

    # Der Abgleich läuft genau einmal: ein später von Hand gesetzter Merker bleibt stehen.
    spaeter = kal.eintragen("Kündigung", "2000-03-01")
    kal.markiere_gemeldet(spaeter.id)
    _waechter(ctx, kanal).deadlines_pruefen(senden=True)
    assert kanal.calls == 1


# ---- SMTP: Zertifikat prüfen, Port 465, keine Geheimnisse in Fehlern -------
class _Smtp:
    """Stellt smtplib.SMTP / SMTP_SSL nach und merkt sich, was aufgerufen wurde."""

    protokoll: list = []
    fehler: Exception | None = None

    def __init__(self, host, port, timeout=None, context=None):
        type(self).protokoll.append((type(self).__name__, host, port, context))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def starttls(self, context=None):
        type(self).protokoll.append(("starttls", context))

    def login(self, adresse, passwort):
        if type(self).fehler is not None:
            raise type(self).fehler
        type(self).protokoll.append(("login", adresse))

    def send_message(self, msg):
        type(self).protokoll.append(("send", msg["To"]))


class _SmtpSsl(_Smtp):
    pass


@pytest.fixture
def smtp(monkeypatch):
    _Smtp.protokoll = []
    _Smtp.fehler = None
    monkeypatch.setattr(smtplib, "SMTP", _Smtp)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _SmtpSsl)
    return _Smtp


def _prueft_zertifikat(kontext) -> bool:
    return (isinstance(kontext, ssl.SSLContext) and kontext.verify_mode == ssl.CERT_REQUIRED
            and kontext.check_hostname)


def test_starttls_prueft_das_zertifikat(smtp):
    EmailKanal("ich@example.com", PASSWORT, "smtp.example.com", 587).senden("Deadline", "heute")
    schritte = [s[0] for s in smtp.protokoll]
    assert schritte == ["_Smtp", "starttls", "login", "send"]
    assert _prueft_zertifikat(smtp.protokoll[1][1]), "starttls() ohne Kontext prüft nichts"


def test_port_465_verschluesselt_von_anfang_an(smtp):
    EmailKanal("ich@example.com", PASSWORT, "smtp.example.com", 465).senden("Deadline", "heute")
    schritte = [s[0] for s in smtp.protokoll]
    assert schritte == ["_SmtpSsl", "login", "send"], "auf 465 gibt es kein STARTTLS"
    assert _prueft_zertifikat(smtp.protokoll[0][3])


@pytest.mark.parametrize("fehler, stichwort", [
    (smtplib.SMTPAuthenticationError(535, b"5.7.139 basic authentication is disabled"), "Anmeldung"),
    (ssl.SSLCertVerificationError("self-signed certificate"), "Zertifikat"),
    (ConnectionRefusedError("refused"), "ConnectionRefusedError"),
])
def test_smtp_fehler_ohne_geheimnis(smtp, fehler, stichwort):
    smtp.fehler = fehler
    with pytest.raises(KanalError) as info:
        EmailKanal("ich@example.com", PASSWORT, "smtp-mail.outlook.com", 587).senden("x", "y")
    text = str(info.value)
    assert stichwort in text and PASSWORT not in text
    assert not any(s[0] == "send" for s in smtp.protokoll), "nach einem Fehler geht nichts raus"


def test_outlook_ablehnung_nennt_den_grund(smtp):
    smtp.fehler = smtplib.SMTPAuthenticationError(535, b"denied")
    with pytest.raises(KanalError, match="Microsoft"):
        EmailKanal("ich@example.com", PASSWORT, "smtp-mail.outlook.com", 587).senden("x", "y")
    with pytest.raises(KanalError) as info:
        EmailKanal("ich@example.com", PASSWORT, "mail.gmx.net", 587).senden("x", "y")
    assert "Microsoft" not in str(info.value)


# ---- Discord: Längengrenze -------------------------------------------------
def test_discord_kuerzt_auf_die_laengengrenze():
    inhalt = DiscordKanal("token", "42")._payload("Deadline", "x" * 5000)["content"]
    assert len(inhalt) == DiscordKanal.MAX_ZEICHEN


# ---- Umgebungsvariablen: neuer Name vor Altname vor Datei ------------------
def test_umgebung_neuer_name_vor_altname(monkeypatch):
    fr = Flugrouten()
    fr.discord = DiscordConfig(enabled=True, bot_token="aus-der-datei", channel_id="1")
    fr.email = EmailConfig(enabled=True, password="aus-der-datei")
    for name in ("POLLYSORT_DISCORD_TOKEN", "BEEHIVE_DISCORD_TOKEN",
                 "POLLYSORT_EMAIL_PASSWORD", "BEEHIVE_EMAIL_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    assert discord_token(fr) == "aus-der-datei" and email_password(fr) == "aus-der-datei"

    monkeypatch.setenv("BEEHIVE_DISCORD_TOKEN", "alt")
    monkeypatch.setenv("BEEHIVE_EMAIL_PASSWORD", "alt")
    assert discord_token(fr) == "alt" and email_password(fr) == "alt"

    monkeypatch.setenv("POLLYSORT_DISCORD_TOKEN", "neu")
    monkeypatch.setenv("POLLYSORT_EMAIL_PASSWORD", "neu")
    assert discord_token(fr) == "neu" and email_password(fr) == "neu"

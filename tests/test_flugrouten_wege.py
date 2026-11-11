"""Die Wege der Flugrouten: Discord per Webhook, Bot im Kanal oder Direktnachricht — und E-Mail
über die üblichen Anbieter.

Sichert zu:
- Eingaben werden geprüft, bevor etwas gespeichert wird; ein Fehler lässt alles, wie es war.
- Die Webhook-Adresse ist ein Geheimnis: Sie steht in keiner Fehlermeldung, liegt im Tresor und
  geht nur an Discord.
- Erwähnt und angeschrieben werden nur die eingetragenen Nutzer — nie ``@everyone``.
- Je Flugroute wird gemerkt, wer eine Deadline schon bekommen hat: Scheitert eine, bekommt beim
  nächsten Versuch nur sie die Nachricht. Lehnt ein Empfänger dauerhaft ab, bleibt die Deadline
  nicht ewig offen.
- Die Funktionen für das Formular in der Werkstatt geben nie ein Geheimnis heraus.
"""

from __future__ import annotations

import json
import types
from datetime import date

import httpx
import pytest

from pollysort import config, flugrouten, i18n, tresor
from pollysort.config import AppConfig, HiveSeed
from pollysort.console import BeeConsole
from pollysort.flugrouten import (
    EMAIL_ANBIETER,
    DiscordConfig,
    EmailConfig,
    Flugrouten,
    FlugroutenFehler,
    discord_art,
    discord_setzen,
    email_setzen,
    ids_pruefen,
    load_flugrouten,
    save_flugrouten,
    webhook_pruefen,
)
from pollysort.journal import Journal
from pollysort.llm.client import OfflineClient
from pollysort.pipeline import Context
from pollysort.swarm import Kalender, Waechterbiene
from pollysort.swarm.kanaele import (
    DiscordDirektKanal,
    DiscordKanal,
    DiscordWebhookKanal,
    EmailKanal,
    KanalAbgelehnt,
    KanalError,
    build_kanaele,
)
from pollysort.web.dienst import Dienst, Ungueltig

WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/GEHEIMES-webhook-TOKEN_abcd"
TOKEN = "SECRET-BOT-TOKEN-wxyz9876"
PASSWORT = "mail-PASSWORT-geheim-4321"
KANAL = "998877665544332211"
ANNA, BEN = "111111111111111111", "222222222222222222"


@pytest.fixture(autouse=True)
def _eigenes_zuhause(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(config, "POLLYSORT_HOME", home)
    monkeypatch.setattr(config, "CONFIG_PATH", home / "config.toml")
    monkeypatch.setattr(config, "CREDENTIALS_PATH", home / "credentials")
    monkeypatch.setattr(config, "PROJECTS_PATH", home / "projects.txt")
    for name in ("DISCORD_TOKEN", "DISCORD_WEBHOOK", "EMAIL_PASSWORD"):
        monkeypatch.delenv("POLLYSORT_" + name, raising=False)
        monkeypatch.delenv("BEEHIVE_" + name, raising=False)
    yield
    i18n.set_language("de")


def _antwort(status: int, daten: dict | None = None):
    return types.SimpleNamespace(status_code=status, json=lambda: daten or {})


class _Discord:
    """Steht für ``httpx.post``: merkt sich jeden Aufruf und antwortet nach Plan."""

    def __init__(self, monkeypatch, antworten=None):
        self.aufrufe: list[dict] = []
        self.antworten = antworten or {}
        monkeypatch.setattr(httpx, "post", self)

    def __call__(self, url, **kw):
        self.aufrufe.append({"url": url, "headers": kw.get("headers") or {}, "json": kw.get("json")})
        for teil, antwort in self.antworten.items():
            if teil in url:
                return antwort
        return _antwort(200, {"id": "555000555000555000"})


# --------------------------------------------------------------------------- #
#  Eingaben prüfen
# --------------------------------------------------------------------------- #
def test_webhook_adresse_wird_geprueft():
    assert webhook_pruefen(f"  {WEBHOOK}  ") == WEBHOOK
    assert webhook_pruefen(WEBHOOK.replace("discord.com", "ptb.discord.com")).startswith("https://ptb.")
    for falsch in ("", "http://discord.com/api/webhooks/1/x", "https://example.org/api/webhooks/1/x",
                   "https://discord.com.example.org/api/webhooks/1/x",
                   "https://discord.com/api/webhooks/keine-zahl/x", "https://discord.com/api/webhooks/1",
                   "https://discord.com/channels/1/2"):
        with pytest.raises(FlugroutenFehler):
            webhook_pruefen(falsch)


def test_fehlermeldung_zur_webhook_adresse_wiederholt_sie_nicht():
    with pytest.raises(FlugroutenFehler) as ei:
        webhook_pruefen("https://example.org/api/webhooks/1/GEHEIM-xyz")
    assert "GEHEIM-xyz" not in str(ei.value)


def test_ids_aus_text_und_liste():
    assert ids_pruefen(f"{ANNA}, {BEN} ; <@{ANNA}>", was="routen.err.nutzer") == [ANNA, BEN]
    assert ids_pruefen([ANNA, int(BEN)], was="routen.err.nutzer") == [ANNA, BEN]
    assert ids_pruefen("", was="routen.err.nutzer") == []
    for falsch in ("anna", "12345", "@everyone", f"{ANNA}x"):
        with pytest.raises(FlugroutenFehler):
            ids_pruefen(falsch, was="routen.err.nutzer")


def test_discord_drei_wege_und_wechsel_raeumt_auf():
    fr = Flugrouten()
    discord_setzen(fr, "kanal", token=TOKEN, kanal=KANAL, nutzer=f"{ANNA},{BEN}")
    assert discord_art(fr) == "kanal" and fr.discord.user_ids == [ANNA, BEN] and fr.discord.enabled

    discord_setzen(fr, "direkt")                    # Token und Nutzer bleiben, der Kanal geht
    assert discord_art(fr) == "direkt" and fr.discord.channel_id == ""
    assert fr.discord.bot_token == TOKEN and fr.discord.user_ids == [ANNA, BEN]

    discord_setzen(fr, "webhook", webhook=WEBHOOK, nutzer=[ANNA])
    assert discord_art(fr) == "webhook" and fr.discord.user_ids == [ANNA]
    assert fr.discord.bot_token == "", "der Bot gehört nicht zum Webhook — kein stiller Zweitweg"

    discord_setzen(fr, "webhook")                   # leeres Geheimnis = das gespeicherte behalten
    assert fr.discord.webhook_url == WEBHOOK


@pytest.mark.parametrize("art, angaben", [
    ("webhook", {}), ("kanal", {"kanal": KANAL}), ("kanal", {"token": TOKEN}),
    ("kanal", {"token": TOKEN, "kanal": "allgemein"}), ("direkt", {"token": TOKEN}),
    ("direkt", {"token": TOKEN, "nutzer": "anna"}), ("brieftaube", {"token": TOKEN}),
])
def test_unvollstaendige_angaben_aendern_nichts(art, angaben):
    fr = Flugrouten(discord=DiscordConfig(enabled=False, channel_id="7"))
    with pytest.raises(FlugroutenFehler):
        discord_setzen(fr, art, **angaben)
    assert fr.discord == DiscordConfig(enabled=False, channel_id="7")


# --------------------------------------------------------------------------- #
#  Discord: was wirklich hinausgeht
# --------------------------------------------------------------------------- #
def test_webhook_geht_ohne_bot_an_die_adresse_und_erwaehnt_nur_die_nutzer(monkeypatch):
    discord = _Discord(monkeypatch)
    DiscordWebhookKanal(WEBHOOK, [ANNA]).senden("Deadline: @everyone Miete", "heute")
    (aufruf,) = discord.aufrufe
    assert aufruf["url"] == WEBHOOK and "Authorization" not in aufruf["headers"]
    assert aufruf["json"]["content"].startswith(f"<@{ANNA}>\n")
    assert aufruf["json"]["allowed_mentions"] == {"parse": [], "users": [ANNA]}, \
        "ein @everyone im Titel darf niemanden benachrichtigen"


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
def test_webhook_fehler_ohne_adresse(monkeypatch, status):
    _Discord(monkeypatch, {"webhooks": _antwort(status)})
    with pytest.raises(KanalError) as ei:
        DiscordWebhookKanal(WEBHOOK).senden("t", "x")
    assert "GEHEIMES" not in str(ei.value) and "webhooks/" not in str(ei.value)


def test_webhook_netzfehler_ohne_adresse(monkeypatch):
    def kaputt(url, **kw):
        raise httpx.ConnectError(f"keine Verbindung zu {url}")
    monkeypatch.setattr(httpx, "post", kaputt)
    with pytest.raises(KanalError) as ei:
        DiscordWebhookKanal(WEBHOOK).senden("t", "x")
    assert "GEHEIMES" not in str(ei.value)


def test_kanal_erwaehnt_die_nutzer(monkeypatch):
    discord = _Discord(monkeypatch)
    DiscordKanal(TOKEN, KANAL, [ANNA, BEN]).senden("Deadline", "heute")
    inhalt = discord.aufrufe[0]["json"]
    assert inhalt["content"].startswith(f"<@{ANNA}> <@{BEN}>\n") and "Deadline" in inhalt["content"]
    assert inhalt["allowed_mentions"]["users"] == [ANNA, BEN]
    assert DiscordKanal(TOKEN, KANAL)._payload("t", "x")["content"].startswith("🐝")


def test_direktnachricht_oeffnet_erst_das_gespraech(monkeypatch):
    discord = _Discord(monkeypatch, {"users/@me/channels": _antwort(200, {"id": "424242424242424242"})})
    DiscordDirektKanal(TOKEN, ANNA).senden("Deadline", "heute")
    erst, dann = discord.aufrufe
    assert erst["url"].endswith("/users/@me/channels") and erst["json"] == {"recipient_id": ANNA}
    assert dann["url"].endswith("/channels/424242424242424242/messages")
    assert all(a["headers"]["Authorization"] == f"Bot {TOKEN}" for a in discord.aufrufe)
    assert TOKEN not in json.dumps([a["json"] for a in discord.aufrufe])


@pytest.mark.parametrize("stelle", ["users/@me/channels", "/messages"])
def test_direktnachricht_abgelehnt_ist_dauerhaft(monkeypatch, stelle):
    _Discord(monkeypatch, {stelle: _antwort(403)})
    with pytest.raises(KanalAbgelehnt) as ei:
        DiscordDirektKanal(TOKEN, ANNA).senden("t", "x")
    assert TOKEN not in str(ei.value) and "gemeinsamen Server" in str(ei.value)


def test_falsches_token_ist_kein_abgelehnter_nutzer(monkeypatch):
    _Discord(monkeypatch, {"users/@me/channels": _antwort(401)})
    with pytest.raises(KanalError) as ei:
        DiscordDirektKanal(TOKEN, ANNA).senden("t", "x")
    assert not isinstance(ei.value, KanalAbgelehnt), "das Token zu korrigieren hilft allen Nutzern"


def test_welche_kanaele_aus_den_einstellungen_werden():
    def arten(**discord):
        fr = Flugrouten(discord=DiscordConfig(enabled=True, **discord))
        return [type(k).__name__ for k in build_kanaele(fr)]

    assert arten(webhook_url=WEBHOOK, user_ids=[ANNA]) == ["DiscordWebhookKanal"]
    assert arten(bot_token=TOKEN, channel_id=KANAL, user_ids=[ANNA]) == ["DiscordKanal"]
    assert arten(bot_token=TOKEN, user_ids=[ANNA, BEN]) == ["DiscordDirektKanal"] * 2
    assert arten(bot_token=TOKEN) == [], "ohne Kanal und ohne Nutzer gibt es niemanden"
    assert arten(webhook_url=WEBHOOK, bot_token=TOKEN, user_ids=[ANNA]) == ["DiscordWebhookKanal"], \
        "der Webhook ist der Kanal — die Nutzer werden dort erwähnt, nicht zusätzlich angeschrieben"
    fr = Flugrouten(discord=DiscordConfig(enabled=False, webhook_url=WEBHOOK))
    assert build_kanaele(fr) == [], "ausgeschaltet heißt ausgeschaltet"


def test_kennungen_verraten_weder_adresse_noch_ids():
    kanaele = [DiscordWebhookKanal(WEBHOOK), DiscordKanal(TOKEN, KANAL), DiscordDirektKanal(TOKEN, ANNA),
               DiscordDirektKanal(TOKEN, BEN),
               EmailKanal("ich@example.org", PASSWORT, "smtp.example.org", 587)]
    kennungen = [k.schluessel for k in kanaele]
    assert len(set(kennungen)) == len(kennungen), "jeder Empfänger hat seine eigene"
    alles = " ".join(kennungen)
    for geheim in (KANAL, ANNA, BEN, "example.org", "GEHEIMES", TOKEN):
        assert geheim not in alles


# --------------------------------------------------------------------------- #
#  Wächterbiene: Zustellung je Flugroute
# --------------------------------------------------------------------------- #
def _ctx(hive):
    hive.mkdir(parents=True, exist_ok=True)
    seed = HiveSeed(categories=["rechnungen"], responsibility={"rechnungen": []})
    return Context.build(hive=hive, cfg=AppConfig(llm_provider="offline"), seed=seed,
                         client=OfflineClient(seed.categories), console=BeeConsole(quiet=True),
                         journal=Journal(hive))


class _Kanal:
    STOCK = "Test-Wabe"

    def __init__(self, name: str, fehler: Exception | None = None):
        self.name, self.schluessel, self.fehler, self.calls = name, f"test:{name}", fehler, 0

    def senden(self, titel, text):
        self.calls += 1
        if self.fehler:
            raise self.fehler


def _faellig(tmp_path):
    ctx = _ctx(tmp_path / "stock")
    Kalender(ctx.hive).eintragen("Miete", date.today().isoformat(), projekt="haus")
    return ctx


def _melden(ctx, *kanaele):
    Waechterbiene(ctx, flugrouten=Flugrouten(), kanaele=list(kanaele)).deadlines_pruefen(senden=True)
    return [t.gemeldet for t in Kalender(ctx.hive)._all()]


def test_gescheiterte_flugroute_wiederholt_nur_sich_selbst(tmp_path):
    ctx = _faellig(tmp_path)
    discord, mail = _Kanal("discord"), _Kanal("mail", KanalError("SMTP-Versand fehlgeschlagen"))
    assert _melden(ctx, discord, mail) == [False], "noch nicht überall angekommen"
    assert _melden(ctx, discord, mail) == [False]
    assert (discord.calls, mail.calls) == (1, 2), "Discord bekommt die Nachricht kein zweites Mal"

    mail.fehler = None                               # der Mailserver ist wieder da
    assert _melden(ctx, discord, mail) == [True]
    assert (discord.calls, mail.calls) == (1, 3)
    assert _melden(ctx, discord, mail) == [True] and mail.calls == 3, "danach ist Ruhe"


def test_ablehnender_nutzer_haelt_die_deadline_nicht_offen(tmp_path):
    ctx = _faellig(tmp_path)
    anna, ben = _Kanal("anna"), _Kanal("ben", KanalAbgelehnt("Direktnachrichten gesperrt"))
    assert _melden(ctx, anna, ben) == [True], "Anna hat sie — Ben nimmt dauerhaft nichts an"
    assert (anna.calls, ben.calls) == (1, 1)


def test_lehnen_alle_ab_bleibt_die_deadline_offen(tmp_path):
    ctx = _faellig(tmp_path)
    ben = _Kanal("ben", KanalAbgelehnt("Direktnachrichten gesperrt"))
    assert _melden(ctx, ben) == [False], "niemand hat sie bekommen — das darf nicht „gemeldet“ heißen"


def test_zustellung_steht_neben_dem_kalender_nicht_darin(tmp_path):
    """Ältere Versionen verwerfen Termine mit unbekannten Feldern — der Kalender bleibt, wie er ist."""
    ctx = _faellig(tmp_path)
    _melden(ctx, _Kanal("discord"), _Kanal("mail", KanalError("x")))
    kal = Kalender(ctx.hive)
    felder = set(json.loads(kal.path.read_text(encoding="utf-8").splitlines()[0]))
    assert felder == {"id", "titel", "faellig", "projekt", "notiz", "erledigt", "gemeldet"}
    (tid,) = [t.id for t in kal._all()]
    assert kal.zustellung(tid) == ({"test:discord"}, set())
    kal.erledigen(tid)
    kal.zustellung_merken("gibt-es-nicht", set(), set())
    assert kal._zustellungen() == {}, "Erledigtes wird nicht ewig mitgeschleppt"


# --------------------------------------------------------------------------- #
#  E-Mail-Anbieter
# --------------------------------------------------------------------------- #
def test_anbieterliste_ist_vollstaendig_und_stimmig():
    for kurz in ("gmail", "outlook", "microsoft365", "gmx", "webde", "t-online"):
        assert kurz in EMAIL_ANBIETER
    for kurz, a in EMAIL_ANBIETER.items():
        assert a.port in (465, 587) and "." in a.host and " " not in a.host, kurz
        if a.hinweis:
            for sprache in ("de", "en"):
                assert i18n.katalog(sprache).get(a.hinweis), f"{kurz}: Hinweis fehlt ({sprache})"
    assert flugrouten.EMAIL_PRESETS["gmx"] == ("mail.gmx.net", 587, True)
    assert flugrouten.anbieter_fuer_host("SMTP.WEB.DE").name == "WEB.DE"


def test_email_anbieter_und_eigener_server():
    fr = Flugrouten()
    email_setzen(fr, "t-online", adresse="ich@t-online.de", passwort=PASSWORT)
    assert (fr.email.smtp_host, fr.email.smtp_port, fr.email.enabled) == ("securesmtp.t-online.de", 465, True)

    email_setzen(fr, "custom", adresse="ich@example.org", host="mail.example.org", port="465",
                 empfaenger="team@example.org")
    assert (fr.email.smtp_host, fr.email.smtp_port) == ("mail.example.org", 465)
    assert fr.email.password == PASSWORT, "leeres Passwort = das gespeicherte behalten"
    assert fr.email.recipient == "team@example.org"


@pytest.mark.parametrize("anbieter, angaben", [
    ("gmx", {"adresse": "keine-adresse", "passwort": "x"}), ("gmx", {"adresse": "", "passwort": "x"}),
    ("gmx", {"adresse": "ich@gmx.de"}), ("brieftaube", {"adresse": "ich@gmx.de", "passwort": "x"}),
    ("custom", {"adresse": "a@b.de", "passwort": "x"}),
    ("custom", {"adresse": "a@b.de", "passwort": "x", "host": "mail.b.de", "port": "0"}),
    ("custom", {"adresse": "a@b.de", "passwort": "x", "host": "https://mail.b.de/", "port": "587"}),
    ("gmx", {"adresse": "ich@gmx.de", "passwort": "x", "empfaenger": "wer"}),
])
def test_email_fehler_aendern_nichts(anbieter, angaben):
    fr = Flugrouten()
    with pytest.raises(FlugroutenFehler):
        email_setzen(fr, anbieter, **angaben)
    assert fr.email == EmailConfig()


def test_abgelehnte_anmeldung_nennt_den_grund_des_anbieters(monkeypatch):
    import smtplib

    class _Smtp:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self, **kw):
            pass

        def login(self, *a):
            raise smtplib.SMTPAuthenticationError(535, b"nein")

    monkeypatch.setattr(smtplib, "SMTP", _Smtp)
    with pytest.raises(KanalError) as ei:
        EmailKanal("ich@gmx.de", PASSWORT, "mail.gmx.net", 587).senden("x", "y")
    assert "POP3 & IMAP" in str(ei.value) and PASSWORT not in str(ei.value)


# --------------------------------------------------------------------------- #
#  Tresor und Datei
# --------------------------------------------------------------------------- #
def test_webhook_liegt_im_tresor_und_die_nutzer_in_der_datei(tresor_im_speicher):
    fr = Flugrouten()
    discord_setzen(fr, "webhook", webhook=WEBHOOK, nutzer=[ANNA, BEN])
    save_flugrouten(fr)
    text = flugrouten.default_path().read_text(encoding="utf-8")
    assert "GEHEIMES" not in text and f'webhook_url = "{tresor.IM_TRESOR}"' in text
    assert ANNA in text and BEN in text
    neu = load_flugrouten()
    assert neu.discord.webhook_url == WEBHOOK and neu.discord.user_ids == [ANNA, BEN]
    assert flugrouten.ablage()["webhook"] == "tresor"


def test_alte_datei_ohne_die_neuen_felder_laedt_wie_bisher():
    pfad = flugrouten.default_path()
    pfad.write_text(f'[discord]\nenabled = true\nbot_token = "{TOKEN}"\nchannel_id = "{KANAL}"\n',
                    encoding="utf-8")
    fr = load_flugrouten()
    assert (fr.discord.webhook_url, fr.discord.user_ids) == ("", [])
    assert [type(k).__name__ for k in build_kanaele(fr)] == ["DiscordKanal"]


def test_umgebungsvariable_fuer_den_webhook(monkeypatch):
    monkeypatch.setenv("POLLYSORT_DISCORD_WEBHOOK", WEBHOOK)
    fr = Flugrouten(discord=DiscordConfig(enabled=True))
    assert discord_art(fr) == "webhook"
    assert [type(k).__name__ for k in build_kanaele(fr)] == ["DiscordWebhookKanal"]


# --------------------------------------------------------------------------- #
#  Dienst: die Funktionen hinter dem Formular in der Werkstatt
# --------------------------------------------------------------------------- #
def test_formular_speichern_zeigt_geheimnisse_nur_maskiert(tresor_im_speicher):
    d = Dienst()
    antwort = d.flugrouten_speichern(
        discord={"art": "webhook", "webhook": WEBHOOK, "nutzer": f"{ANNA}, {BEN}"},
        email={"anbieter": "gmx", "adresse": "ich@gmx.de", "passwort": PASSWORT})
    stand = antwort["ergebnis"]
    assert stand["discord"] == {"aktiv": True, "art": "webhook", "kanal": "", "nutzer": [ANNA, BEN],
                                "token": "", "webhook": "****abcd"}
    assert stand["email"]["host"] == "mail.gmx.net" and stand["email"]["passwort"] == "****4321"
    assert stand["hinweis"] == "" and stand["tresor"]["aktiv"] is True
    alles = json.dumps([antwort, d.flugrouten_stand(), d.werkstatt()], ensure_ascii=False)
    for geheim in (WEBHOOK, "GEHEIMES", PASSWORT):
        assert geheim not in alles
    assert {a["id"] for a in stand["anbieter"]} >= {"gmail", "gmx", "webde", "t-online", "microsoft365"}
    assert next(a for a in stand["anbieter"] if a["id"] == "gmail")["hinweis"]


def test_formular_leeres_geheimnis_behaelt_das_gespeicherte():
    d = Dienst()
    d.flugrouten_speichern(discord={"art": "kanal", "token": TOKEN, "kanal": KANAL})
    d.flugrouten_speichern(discord={"art": "kanal", "token": "", "kanal": KANAL, "nutzer": [ANNA]})
    fr = load_flugrouten()
    assert fr.discord.bot_token == TOKEN and fr.discord.user_ids == [ANNA]


@pytest.mark.parametrize("anfrage", [
    {"discord": {"art": "webhook", "webhook": "https://example.org/x"}},
    {"discord": {"art": "kanal", "token": TOKEN, "kanal": KANAL, "unbekannt": 1}},
    {"discord": "webhook"}, {"discord": {"art": "direkt", "token": TOKEN, "nutzer": {"a": 1}}},
    {"email": {"anbieter": "gmx", "adresse": "ich@gmx.de"}},
])
def test_formular_ungueltige_angaben_speichern_nichts(anfrage):
    d = Dienst()
    with pytest.raises(Ungueltig) as ei:
        d.flugrouten_speichern(**anfrage)
    assert TOKEN not in str(ei.value)
    assert not flugrouten.default_path().exists()


def test_formular_schalten_und_entfernen(tresor_im_speicher):
    d = Dienst()
    with pytest.raises(Ungueltig):
        d.flugrouten_schalten(kanal="discord", an=True)        # nichts eingerichtet
    with pytest.raises(Ungueltig):
        d.flugrouten_schalten(kanal="fax", an=False)
    d.flugrouten_speichern(discord={"art": "webhook", "webhook": WEBHOOK})

    aus = d.flugrouten_schalten(kanal="discord", an=False)["ergebnis"]
    assert aus["discord"]["aktiv"] is False and aus["discord"]["webhook"] == "****abcd"
    assert build_kanaele(load_flugrouten()) == []
    assert d.flugrouten_schalten(kanal="discord", an=True)["ergebnis"]["discord"]["aktiv"] is True

    weg = d.flugrouten_entfernen(kanal="discord")["ergebnis"]
    assert weg["discord"]["art"] == "" and weg["discord"]["webhook"] == ""
    assert not tresor_im_speicher.inhalt, "auch der Tresor ist leer"


def test_formular_testflug_meldet_je_empfaenger(monkeypatch):
    d = Dienst()
    d.flugrouten_speichern(discord={"art": "direkt", "token": TOKEN, "nutzer": [ANNA, BEN]})

    def antworten(url, **kw):                      # Ben (Gespräch 777) hat Direktnachrichten gesperrt
        if url.endswith("/users/@me/channels"):
            wer = kw["json"]["recipient_id"]
            return _antwort(200, {"id": "777" if wer == BEN else "888"})
        return _antwort(403 if "/channels/777/" in url else 200)
    monkeypatch.setattr(httpx, "post", antworten)

    ergebnis = d.flugrouten_testen()["ergebnis"]["kanaele"]
    assert [(k["name"], k["ok"]) for k in ergebnis] == [(f"Discord-Nutzer {ANNA}", True),
                                                        (f"Discord-Nutzer {BEN}", False)]
    assert "gemeinsamen Server" in ergebnis[1]["fehler"] and TOKEN not in json.dumps(ergebnis)

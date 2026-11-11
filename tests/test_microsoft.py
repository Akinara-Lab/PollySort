"""Microsoft-Anmeldung für E-Mail (Outlook.com, Hotmail, Microsoft 365) per Gerätecode.

Die Microsoft-Seite ist nachgestellt (``_Microsoft`` steht für ``httpx.post``), der Mailserver
ist der Übungsserver aus ``test_postfach``. Geprüft wird der Ablauf nach Microsofts
Beschreibung — und dass kein Token je in einer Meldung, Antwort oder Klartext-Datei landet.
"""

from __future__ import annotations

import base64
import json
import smtplib
import types

import httpx
import pytest
from test_postfach import PDF, MiniImap, _mail

from pollysort import config, flugrouten, i18n, microsoft, postfach, tresor
from pollysort.config import HiveSeed
from pollysort.console import BeeConsole
from pollysort.flugrouten import (
    EmailConfig,
    Flugrouten,
    FlugroutenFehler,
    email_microsoft_setzen,
    email_setzen,
    load_flugrouten,
    save_flugrouten,
)
from pollysort.microsoft import AnmeldeFehler, Geraetecode
from pollysort.repl import BeehiveShell
from pollysort.swarm.kanaele import EmailKanal, KanalError, build_kanaele
from pollysort.web.dienst import Dienst, Ungueltig

KENNUNG = "11111111-2222-3333-4444-555555555555"
GERAET = "GERAETECODE-geheim-" + "g" * 40
ZUGRIFF = "ZUGRIFF-geheim-" + "z" * 60
ERNEUERUNG = "ERNEUERUNG-geheim-" + "e" * 1500          # länger, als ein Tresor-Eintrag fasst
ADRESSE = "ich@example.org"


def _antwort(status: int, daten: dict):
    return types.SimpleNamespace(status_code=status, json=lambda: daten)


class _Microsoft:
    """Die Anmeldeseite von Microsoft: merkt sich jede Anfrage, antwortet nach Plan."""

    def __init__(self, monkeypatch):
        self.anfragen: list[dict] = []
        self.offen = 0                          # so oft heißt es erst „noch nicht angemeldet"
        self.fehler = ""                        # z. B. authorization_declined, invalid_grant
        self.neue_erneuerung = ""               # Microsoft tauscht das Erneuerungstoken aus
        self.zugriff = ZUGRIFF
        monkeypatch.setattr(httpx, "post", self)

    def __call__(self, url, data=None, **kw):
        self.anfragen.append({"url": url, **(data or {})})
        if url.endswith("/devicecode"):
            if data["client_id"] != KENNUNG:
                return _antwort(400, {"error": "unauthorized_client"})
            return _antwort(200, {"device_code": GERAET, "user_code": "ABCD-EFGH",
                                  "verification_uri": "https://microsoft.com/devicelogin",
                                  "expires_in": 900, "interval": 5, "message": "..."})
        if self.fehler:
            return _antwort(400, {"error": self.fehler, "error_description": "Trace " + GERAET})
        if data["grant_type"].endswith("device_code") and self.offen > 0:
            self.offen -= 1
            return _antwort(400, {"error": "authorization_pending"})
        return _antwort(200, {"token_type": "Bearer", "expires_in": 3600, "access_token": self.zugriff,
                              "refresh_token": self.neue_erneuerung or ERNEUERUNG})


@pytest.fixture(autouse=True)
def _umgebung(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(config, "POLLYSORT_HOME", home)
    monkeypatch.setattr(config, "CONFIG_PATH", home / "config.toml")
    monkeypatch.setattr(config, "CREDENTIALS_PATH", home / "credentials")
    monkeypatch.setattr(config, "PROJECTS_PATH", home / "projects.txt")
    for name in ("POLLYSORT_EMAIL_PASSWORD", "BEEHIVE_EMAIL_PASSWORD", microsoft.CLIENT_ID_VARIABLE):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(microsoft, "_ZUGRIFF", {})
    yield
    i18n.set_language("de")


@pytest.fixture
def ms(monkeypatch):
    return _Microsoft(monkeypatch)


def _code() -> Geraetecode:
    return Geraetecode(GERAET, "ABCD-EFGH", "https://microsoft.com/devicelogin", 900, 5)


def _angemeldet() -> Flugrouten:
    fr = Flugrouten()
    email_microsoft_setzen(fr, "outlook", adresse=ADRESSE, erneuerung=ERNEUERUNG, kennung=KENNUNG)
    return fr


# --------------------------------------------------------------------------- #
#  Der Ablauf bei Microsoft
# --------------------------------------------------------------------------- #
def test_geraetecode_fragt_genau_die_noetigen_rechte_an(ms):
    code = microsoft.geraetecode_holen(KENNUNG)
    assert (code.user_code, code.verification_uri, code.interval) == \
        ("ABCD-EFGH", "https://microsoft.com/devicelogin", 5)
    (anfrage,) = ms.anfragen
    assert anfrage["url"] == "https://login.microsoftonline.com/common/oauth2/v2.0/devicecode"
    assert anfrage["client_id"] == KENNUNG
    assert set(anfrage["scope"].split()) == {
        "https://outlook.office.com/IMAP.AccessAsUser.All", "https://outlook.office.com/SMTP.Send",
        "offline_access"}
    assert GERAET not in repr(code), "der Schlüssel der Anmeldung steht in keiner Ausgabe"


def test_ohne_kennung_gibt_es_keine_anfrage(ms):
    with pytest.raises(AnmeldeFehler) as ei:
        microsoft.geraetecode_holen("")
    assert "Client-ID" in str(ei.value) and not ms.anfragen
    with pytest.raises(AnmeldeFehler):
        microsoft.geraetecode_holen("falsche-kennung")


def test_nachfragen_bis_die_anmeldung_da_ist(ms):
    ms.offen = 2
    code = _code()
    assert microsoft.nachfragen(KENNUNG, code) is None
    pausen = []
    token = microsoft.warten(KENNUNG, code, schlafen=pausen.append)
    assert (token.zugriff, token.erneuerung) == (ZUGRIFF, ERNEUERUNG) and pausen == [5, 5]
    letzte = ms.anfragen[-1]
    assert letzte["url"].endswith("/common/oauth2/v2.0/token")
    assert letzte["grant_type"] == "urn:ietf:params:oauth:grant-type:device_code"
    assert letzte["device_code"] == GERAET
    assert ZUGRIFF not in repr(token) and ERNEUERUNG not in repr(token)


def test_bittet_microsoft_um_geduld_wird_die_pause_laenger(ms):
    ms.fehler = "slow_down"
    code = _code()
    assert microsoft.nachfragen(KENNUNG, code) is None and code.interval == 10


@pytest.mark.parametrize("fehler, stichwort", [
    ("authorization_declined", "abgelehnt"), ("expired_token", "abgelaufen"),
    ("bad_verification_code", "abgelaufen"), ("server_error", "server_error"),
])
def test_fehler_der_anmeldung_ohne_schluessel(ms, fehler, stichwort):
    ms.fehler = fehler
    with pytest.raises(AnmeldeFehler) as ei:
        microsoft.nachfragen(KENNUNG, _code())
    assert stichwort in str(ei.value) and GERAET not in str(ei.value)


def test_abgelaufener_code_beendet_das_warten(ms):
    ms.offen = 10**6
    zeit = iter(range(0, 10**6, 400))
    with pytest.raises(AnmeldeFehler) as ei:
        microsoft.warten(KENNUNG, _code(), schlafen=lambda s: None, uhr=lambda: next(zeit))
    assert "abgelaufen" in str(ei.value)


def test_erneuern_und_ausgetauschtes_erneuerungstoken(ms):
    assert microsoft.erneuern(KENNUNG, ERNEUERUNG).erneuerung == ERNEUERUNG
    ms.neue_erneuerung = "NEU-" + ERNEUERUNG
    assert microsoft.erneuern(KENNUNG, ERNEUERUNG).erneuerung == "NEU-" + ERNEUERUNG
    letzte = ms.anfragen[-1]
    assert letzte["grant_type"] == "refresh_token" and letzte["refresh_token"] == ERNEUERUNG

    ms.fehler = "invalid_grant"
    with pytest.raises(AnmeldeFehler) as ei:
        microsoft.erneuern(KENNUNG, ERNEUERUNG)
    assert "flugrouten microsoft" in str(ei.value) and ERNEUERUNG not in str(ei.value)


def test_netzfehler_verraet_nichts(monkeypatch):
    def kaputt(url, **kw):
        raise httpx.ConnectError(f"keine Verbindung, gesendet: {kw}")
    monkeypatch.setattr(httpx, "post", kaputt)
    with pytest.raises(AnmeldeFehler) as ei:
        microsoft.erneuern(KENNUNG, ERNEUERUNG)
    assert ERNEUERUNG not in str(ei.value) and "nicht erreichbar" in str(ei.value)


def test_anmeldezeile_fuer_mailserver():
    assert microsoft.xoauth2("a@b.de", "TOK") == "user=a@b.de\x01auth=Bearer TOK\x01\x01"


def test_kennung_umgebung_vor_gespeichert(monkeypatch):
    assert microsoft.client_id("") == microsoft.CLIENT_ID
    assert microsoft.client_id(" gespeichert ") == "gespeichert"
    monkeypatch.setenv(microsoft.CLIENT_ID_VARIABLE, "aus-der-umgebung")
    assert microsoft.client_id("gespeichert") == "aus-der-umgebung"


# --------------------------------------------------------------------------- #
#  Zugriffstoken: holen, behalten, erneuern
# --------------------------------------------------------------------------- #
def test_zugriffstoken_wird_nur_bei_bedarf_geholt(ms, monkeypatch):
    fr = _angemeldet()
    assert microsoft.zugriffstoken(fr) == ZUGRIFF and microsoft.zugriffstoken(fr) == ZUGRIFF
    assert len(ms.anfragen) == 1, "das zweite Mal kommt es aus dem Arbeitsspeicher"

    ms.zugriff = "FRISCH-" + ZUGRIFF
    monkeypatch.setattr(microsoft.time, "monotonic", lambda: 10**9)       # eine Stunde später
    assert microsoft.zugriffstoken(fr) == "FRISCH-" + ZUGRIFF and len(ms.anfragen) == 2


def test_ausgetauschtes_erneuerungstoken_wird_gespeichert(ms, tresor_im_speicher):
    save_flugrouten(_angemeldet())
    ms.neue_erneuerung = "NEU-" + ERNEUERUNG
    microsoft.zugriffstoken(load_flugrouten())
    assert load_flugrouten().email.oauth_token == "NEU-" + ERNEUERUNG, "sonst wäre die Anmeldung weg"


def test_ohne_anmeldung_kein_zugriffstoken(ms):
    for fr in (Flugrouten(), Flugrouten(email=EmailConfig(auth="microsoft", address=ADRESSE))):
        assert not microsoft.bereit(fr)
        with pytest.raises(AnmeldeFehler):
            microsoft.zugriffstoken(fr)
    assert not ms.anfragen


# --------------------------------------------------------------------------- #
#  Tresor: lange Werte
# --------------------------------------------------------------------------- #
def test_lange_werte_werden_aufgeteilt_und_wieder_zusammengesetzt(tresor_im_speicher):
    tresor_im_speicher.max_zeichen = 1280                  # so viel nimmt Windows je Eintrag
    lang = "x" * 999 + "y" * 1000 + "z" * 700
    assert tresor.schreiben("probe", lang) and tresor.lesen("probe") == lang
    assert len(tresor_im_speicher.inhalt) == 4, "ein Zeiger und drei Stücke"
    assert max(map(len, tresor_im_speicher.inhalt.values())) <= tresor.TEIL_ZEICHEN

    assert tresor.schreiben("probe", "kurz") and tresor.lesen("probe") == "kurz"
    assert list(tresor_im_speicher.inhalt.values()) == ["kurz"], "alte Stücke sind weg"

    tresor.schreiben("probe", lang)
    tresor.loeschen("probe")
    assert not tresor_im_speicher.inhalt


def test_fehlt_ein_stueck_ist_der_wert_nicht_lesbar(tresor_im_speicher):
    tresor.schreiben("probe", "a" * 2500)
    del tresor_im_speicher.inhalt[(tresor.dienst(), "probe#2")]
    assert tresor.lesen("probe") is None
    assert tresor.ablageort(tresor.IM_TRESOR, "probe") == "unlesbar"


# --------------------------------------------------------------------------- #
#  Einstellungen
# --------------------------------------------------------------------------- #
def test_anmeldung_liegt_im_tresor_die_kennung_in_der_datei(tresor_im_speicher):
    tresor_im_speicher.max_zeichen = 1280
    save_flugrouten(_angemeldet())
    text = flugrouten.default_path().read_text(encoding="utf-8")
    assert "ERNEUERUNG" not in text and f'oauth_token = "{tresor.IM_TRESOR}"' in text
    assert KENNUNG in text and 'auth      = "microsoft"' in text
    fr = load_flugrouten()
    e = fr.email
    assert (e.auth, e.oauth_token, e.oauth_client_id, e.password) == ("microsoft", ERNEUERUNG, KENNUNG, "")
    assert (e.smtp_host, e.imap_host) == ("smtp-mail.outlook.com", "outlook.office365.com")
    assert flugrouten.ablage()["anmeldung"] == "tresor" and microsoft.bereit(fr)


def test_ohne_tresor_steht_die_anmeldung_wie_ein_passwort_in_der_datei():
    save_flugrouten(_angemeldet())
    assert load_flugrouten().email.oauth_token == ERNEUERUNG
    assert flugrouten.ablage()["anmeldung"] == "datei", "und die Oberflächen sagen das dazu"


def test_microsoft_anmeldung_nur_fuer_microsoft_konten():
    fr = Flugrouten()
    for anbieter, angaben in [("gmx", {"adresse": ADRESSE, "erneuerung": "x"}),
                              ("outlook", {"adresse": "keine-adresse", "erneuerung": "x"}),
                              ("outlook", {"adresse": ADRESSE, "erneuerung": ""})]:
        with pytest.raises(FlugroutenFehler):
            email_microsoft_setzen(fr, anbieter, **angaben)
    assert fr.email == EmailConfig()


def test_wechsel_zum_passwort_behaelt_die_kennung():
    fr = _angemeldet()
    email_setzen(fr, "gmx", adresse="ich@gmx.de", passwort="geheim")
    assert (fr.email.auth, fr.email.oauth_token, fr.email.oauth_client_id) == ("passwort", "", KENNUNG)


def test_alte_datei_ohne_anmeldefelder_meldet_sich_mit_passwort_an():
    fr = Flugrouten()
    email_setzen(fr, "gmx", adresse="ich@gmx.de", passwort="geheim")
    save_flugrouten(fr)
    pfad = flugrouten.default_path()
    alt = "\n".join(z for z in pfad.read_text(encoding="utf-8").splitlines() if "auth" not in z)
    pfad.write_text(alt + "\n", encoding="utf-8")
    e = load_flugrouten().email
    assert (e.auth, e.oauth_token, e.oauth_tenant, e.password) == ("passwort", "", "common", "geheim")


# --------------------------------------------------------------------------- #
#  E-Mail senden mit Zugriffstoken
# --------------------------------------------------------------------------- #
class _Smtp(smtplib.SMTP):
    """Ein Mailserver, der nur die Anmeldung mitschreibt — die echte ``auth``-Logik läuft."""

    befehle: list[str] = []
    annehmen = True

    def __init__(self, *a, **kw):
        type(self).befehle = []

    def __exit__(self, *a):
        return False

    def starttls(self, **kw):
        return 220, b"ok"

    def ehlo_or_helo_if_needed(self):
        pass

    def docmd(self, cmd, args=""):
        type(self).befehle.append(f"{cmd} {args}".strip())
        if self.annehmen:
            return 235, b"2.7.0 Authentication successful"
        return (334, b"eyJzdGF0dXMiOiI0MDAifQ==") if cmd == "AUTH" else (535, b"5.7.3 unsuccessful")

    def send_message(self, msg, *a, **kw):
        type(self).befehle.append("GESENDET an " + msg["To"])


def test_versand_meldet_sich_mit_zugriffstoken_an(ms, monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", _Smtp)
    _Smtp.annehmen = True
    (kanal,) = build_kanaele(_angemeldet())
    kanal.senden("Deadline", "heute")
    anmeldung, gesendet = _Smtp.befehle
    assert anmeldung.startswith("AUTH XOAUTH2 ") and gesendet == f"GESENDET an {ADRESSE}"
    zeile = base64.b64decode(anmeldung.split()[-1]).decode()
    assert zeile == f"user={ADRESSE}\x01auth=Bearer {ZUGRIFF}\x01\x01"


def test_abgelehnte_token_anmeldung_schickt_das_token_nicht_noch_einmal(ms, monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", _Smtp)
    _Smtp.annehmen = False
    (kanal,) = build_kanaele(_angemeldet())
    with pytest.raises(KanalError) as ei:
        kanal.senden("Deadline", "heute")
    assert len(_Smtp.befehle) == 2 and _Smtp.befehle[1] == "", "auf die Rückfrage folgt eine leere Zeile"
    assert "flugrouten microsoft" in str(ei.value) and ZUGRIFF not in str(ei.value)


def test_abgelaufene_anmeldung_wird_beim_versand_verstaendlich_gemeldet(ms, monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", _Smtp)
    ms.fehler = "invalid_grant"
    (kanal,) = build_kanaele(_angemeldet())
    with pytest.raises(KanalError) as ei:
        kanal.senden("Deadline", "heute")
    assert "neu anmelden" in str(ei.value) and _Smtp.befehle == [], "ohne Token kein Anmeldeversuch"


def test_ohne_anmeldung_gibt_es_den_kanal_nicht():
    fr = Flugrouten(email=EmailConfig(enabled=True, provider="outlook", address=ADRESSE,
                                      smtp_host="smtp-mail.outlook.com", auth="microsoft"))
    assert build_kanaele(fr) == []
    assert isinstance(EmailKanal(ADRESSE, "pw", "smtp.example.org", 587), EmailKanal)


# --------------------------------------------------------------------------- #
#  Postfach mit Zugriffstoken
# --------------------------------------------------------------------------- #
@pytest.fixture
def mailserver(monkeypatch):
    import imaplib
    monkeypatch.setattr(imaplib.IMAP4, "starttls", lambda self, ssl_context=None: ("OK", []))
    s = MiniImap({"INBOX": [_mail(("beleg.pdf", PDF))]})
    yield s
    s.schliessen()


def _postfach_zugang(mailserver) -> postfach.Zugang:
    fr = _angemeldet()
    fr.email.imap_host, fr.email.imap_port = "127.0.0.1", mailserver.port
    return postfach.zugang(fr)


def test_postfach_meldet_sich_mit_zugriffstoken_an(ms, mailserver, tmp_path):
    hive = tmp_path / "haus"
    hive.mkdir()
    config.write_seed(hive, HiveSeed(name="Haus"))
    mailserver.token = ZUGRIFF
    z = _postfach_zugang(mailserver)
    assert z is not None and ZUGRIFF not in repr(z) and not ms.anfragen, "erst beim Verbinden"
    assert postfach.abholen(hive, z, "INBOX").geholt == ["beleg.pdf"]
    assert "LOGIN" not in " ".join(mailserver.befehle).upper(), "kein Passwort im Spiel"


def test_postfach_lehnt_token_ab(ms, mailserver, tmp_path):
    mailserver.token = "ein-anderes"
    with pytest.raises(postfach.PostfachFehler) as ei:
        postfach.abholen(tmp_path, _postfach_zugang(mailserver), "INBOX")
    assert "flugrouten microsoft" in str(ei.value) and ZUGRIFF not in str(ei.value)
    assert mailserver.anmeldezeilen[1:] == [""], "auf die Rückfrage folgt eine leere Zeile"


def test_postfach_ohne_anmeldung_ist_nicht_bereit():
    fr = Flugrouten(email=EmailConfig(provider="outlook", address=ADRESSE, auth="microsoft",
                                      imap_host="outlook.office365.com"))
    assert postfach.zugang(fr) is None


# --------------------------------------------------------------------------- #
#  Dienst: die zwei Schritte für das Formular
# --------------------------------------------------------------------------- #
def test_dienst_anmeldung_in_zwei_schritten(ms, tresor_im_speicher):
    d = Dienst()
    with pytest.raises(Ungueltig):
        d.flugrouten_microsoft_abschluss()                 # nichts begonnen
    ms.offen = 1
    start = d.flugrouten_microsoft_start(anbieter="outlook", adresse=ADRESSE, client_id=KENNUNG)
    assert start["ergebnis"] == {"seite": "https://microsoft.com/devicelogin", "code": "ABCD-EFGH",
                                 "minuten": 15, "pause": 5}
    assert d.flugrouten_microsoft_abschluss()["ergebnis"] == {"fertig": False, "pause": 5}
    assert not flugrouten.default_path().exists(), "vor der Anmeldung wird nichts gespeichert"

    fertig = d.flugrouten_microsoft_abschluss()["ergebnis"]
    assert fertig["fertig"] is True
    email = fertig["stand"]["email"]
    assert (email["anmeldung"], email["angemeldet"], email["kennung"]) == ("microsoft", True, True)
    assert email["adresse"] == ADRESSE and email["passwort"] == ""
    assert load_flugrouten().email.oauth_client_id == KENNUNG

    alles = json.dumps([start, fertig, d.flugrouten_stand(), d.werkstatt()], ensure_ascii=False)
    for geheim in (GERAET, ZUGRIFF, "ERNEUERUNG"):
        assert geheim not in alles
    anbieter = {a["id"]: a["microsoft"] for a in fertig["stand"]["anbieter"]}
    assert anbieter["outlook"] and anbieter["microsoft365"] and not anbieter["gmx"]


@pytest.mark.parametrize("angaben", [
    {"anbieter": "gmx", "adresse": ADRESSE, "client_id": KENNUNG},
    {"anbieter": "outlook", "adresse": "keine-adresse", "client_id": KENNUNG},
    {"anbieter": "outlook", "adresse": ADRESSE},                       # Kennung fehlt
])
def test_dienst_prueft_die_angaben_vor_der_anmeldung(ms, angaben):
    d = Dienst()
    with pytest.raises(Ungueltig):
        d.flugrouten_microsoft_start(**angaben)
    with pytest.raises(Ungueltig):
        d.flugrouten_microsoft_abschluss()


def test_dienst_abgelehnte_anmeldung_raeumt_auf(ms):
    d = Dienst()
    d.flugrouten_microsoft_start(anbieter="outlook", adresse=ADRESSE, client_id=KENNUNG)
    ms.fehler = "authorization_declined"
    with pytest.raises(Ungueltig) as ei:
        d.flugrouten_microsoft_abschluss()
    assert "abgelehnt" in str(ei.value) and not flugrouten.default_path().exists()
    with pytest.raises(Ungueltig):
        d.flugrouten_microsoft_abschluss()


# --------------------------------------------------------------------------- #
#  Konsole
# --------------------------------------------------------------------------- #
def _konsole(monkeypatch, eingaben: list[str]):
    sh = BeehiveShell.__new__(BeehiveShell)
    gesagt: list[str] = []
    sh.con = BeeConsole(quiet=True)
    for art in ("info", "honey", "ask", "error", "raw", "rule", "bloom"):
        monkeypatch.setattr(sh.con, art, lambda text="", *a, **kw: gesagt.append(str(text)))
    sh.hive = None
    antworten = iter(eingaben)
    monkeypatch.setattr(sh, "_ask", lambda prompt, **kw: next(antworten))
    monkeypatch.setattr(microsoft.time, "sleep", lambda s: None)
    return sh, gesagt


def test_assistent_fuehrt_bei_outlook_zur_microsoft_seite(ms, monkeypatch, tresor_im_speicher):
    # Discord: nein · E-Mail: ja · Anbieter 2 (Outlook) · Adresse · Empfänger · Kennung
    sh, gesagt = _konsole(monkeypatch, ["n", "j", "2", ADRESSE, "", KENNUNG])
    sh._flugrouten_setup()
    text = " ".join(gesagt)
    assert "https://microsoft.com/devicelogin" in text and "ABCD-EFGH" in text
    for geheim in (GERAET, ZUGRIFF, "ERNEUERUNG"):
        assert geheim not in text
    e = load_flugrouten().email
    assert (e.enabled, e.auth, e.oauth_token, e.oauth_client_id) == (True, "microsoft", ERNEUERUNG, KENNUNG)


def test_assistent_ohne_kennung_bricht_sauber_ab(ms, monkeypatch):
    sh, gesagt = _konsole(monkeypatch, ["n", "j", "2", ADRESSE, "", ""])
    sh._flugrouten_setup()
    assert not load_flugrouten().email.enabled and not ms.anfragen
    assert "README" in " ".join(gesagt)


def test_neu_anmelden_mit_flugrouten_microsoft(ms, monkeypatch):
    save_flugrouten(_angemeldet())
    ms.neue_erneuerung = "NEU-" + ERNEUERUNG
    sh, gesagt = _konsole(monkeypatch, [])                 # die Kennung ist da — keine Frage nötig
    sh.do_flugrouten("microsoft")
    assert load_flugrouten().email.oauth_token == "NEU-" + ERNEUERUNG

    save_flugrouten(Flugrouten())
    sh.do_flugrouten("microsoft")
    assert "flugrouten setup" in gesagt[-1]

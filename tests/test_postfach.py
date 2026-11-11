"""Postfach — Anhänge aus einem E-Mail-Ordner in den Eingang holen.

Die Tests sprechen mit einem kleinen Übungs-Mailserver (``MiniImap``), der nur auf diesem Rechner
lauscht und das IMAP-Protokoll so weit spricht, wie der Abruf es braucht. So läuft der echte
Weg durch ``imaplib`` — und der Server schreibt mit, was PollySort ihm schickt.

Sichert zu:
- Im Postfach wird nichts verändert (schreibgeschützt geöffnet, ``BODY.PEEK``, kein ``STORE``).
- Nichts kommt doppelt an, keine Datei im Eingang wird ersetzt.
- Dateinamen aus E-Mails können nur im Eingang landen.
- Passwort, Absender und Betreff stehen in keiner Meldung und in keinem Journal.
- Ein Abbruch mittendrin verliert nichts und holt später nichts doppelt.
"""

from __future__ import annotations

import imaplib
import json
import re
import socket
import ssl
import threading
from email.message import EmailMessage

import pytest

from pollysort import config, i18n, postfach
from pollysort.config import HiveSeed
from pollysort.flugrouten import (
    EMAIL_ANBIETER,
    EmailConfig,
    Flugrouten,
    email_setzen,
    load_flugrouten,
    save_flugrouten,
)
from pollysort.journal import Journal
from pollysort.postfach import Abruf, PostfachFehler, Zugang, abholen, sicherer_name
from pollysort.web.dienst import Dienst, Ungueltig

PASSWORT = "postfach-PASSWORT-geheim"
ABSENDER = "chef@firma-geheim.example"
BETREFF = "Vertraulich: Gehaltsliste"
PDF = b"%PDF-1.4 Rechnung ACME 4200 EUR"
PDF2 = b"%PDF-1.4 Mietvertrag Wohnung"


# --------------------------------------------------------------------------- #
#  Übungs-Mailserver
# --------------------------------------------------------------------------- #
class MiniImap(threading.Thread):
    """Ein IMAP-Server für Tests: Ordner mit Nachrichten, Nummer (UID) = Platz in der Liste."""

    def __init__(self, ordner: dict[str, list[bytes]], *, gueltigkeit: int = 7):
        super().__init__(daemon=True)
        self.ordner, self.gueltigkeit = ordner, gueltigkeit
        self.befehle: list[str] = []            # was PollySort geschickt hat (ohne Passwort)
        self.abbruch_bei: int | None = None     # bei dieser Nachricht reißt die Verbindung ab
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self.port = self._sock.getsockname()[1]
        self.start()

    def run(self) -> None:
        while True:
            try:
                verbindung, _ = self._sock.accept()
            except OSError:
                return
            try:
                self._bedienen(verbindung)
            except OSError:
                pass
            finally:
                verbindung.close()

    def schliessen(self) -> None:
        self._sock.close()

    def _bedienen(self, v: socket.socket) -> None:
        datei = v.makefile("rb")
        v.sendall(b"* OK Uebungsserver bereit\r\n")
        gewaehlt: list[bytes] = []
        while True:
            zeile = datei.readline()
            if not zeile:
                return
            tag, _, rest = zeile.decode("ascii").strip().partition(" ")
            befehl = rest.upper()
            self.befehle.append(re.sub(r'(?i)^(login \S+) .*$', r"\1 ***", rest))

            def ok(text: str = "fertig", tag: str = tag) -> None:
                v.sendall(f"{tag} OK {text}\r\n".encode())

            if befehl.startswith("CAPABILITY"):
                v.sendall(b"* CAPABILITY IMAP4rev1\r\n")
                ok()
            elif befehl.startswith("LOGIN"):
                if rest.endswith(f'"{PASSWORT}"'):
                    ok()
                else:       # echte Server wiederholen hier gern, was man geschickt hat
                    v.sendall(f"{tag} NO [AUTHENTICATIONFAILED] falsch: {rest}\r\n".encode())
            elif befehl.startswith(("EXAMINE", "SELECT", "STATUS")):
                name = re.search(r'"((?:[^"\\]|\\.)*)"', rest).group(1)
                if name not in self.ordner:
                    v.sendall(f"{tag} NO gibt es nicht\r\n".encode())
                elif befehl.startswith("STATUS"):
                    v.sendall(f'* STATUS "{name}" (UIDVALIDITY {self.gueltigkeit})\r\n'.encode())
                    ok()
                else:
                    gewaehlt = self.ordner[name]
                    v.sendall(f"* {len(gewaehlt)} EXISTS\r\n"
                              f"* OK [UIDVALIDITY {self.gueltigkeit}] gilt\r\n".encode())
                    ok("[READ-ONLY] gewaehlt")
            elif befehl.startswith("UID SEARCH"):
                ab = int(re.search(r"UID (\d+):\*", befehl).group(1))
                treffer = [u for u in range(1, len(gewaehlt) + 1) if u >= ab]
                if not treffer and gewaehlt:            # „n:*" nennt immer die höchste Nummer
                    treffer = [len(gewaehlt)]
                v.sendall(("* SEARCH " + " ".join(map(str, treffer))).rstrip().encode() + b"\r\n")
                ok()
            elif befehl.startswith("UID FETCH") and "RFC822.SIZE" in befehl:
                for u in map(int, rest.split()[2].split(",")):
                    v.sendall(f"* {u} FETCH (UID {u} RFC822.SIZE {len(gewaehlt[u - 1])})\r\n".encode())
                ok()
            elif befehl.startswith("UID FETCH"):
                u = int(rest.split()[2])
                if u == self.abbruch_bei:
                    v.shutdown(socket.SHUT_RDWR)
                    return
                roh = gewaehlt[u - 1]
                v.sendall(f"* {u} FETCH (UID {u} BODY[] {{{len(roh)}}}\r\n".encode() + roh + b")\r\n")
                ok()
            elif befehl.startswith("LIST"):
                for name in self.ordner:
                    v.sendall(f'* LIST (\\HasNoChildren) "/" "{name}"\r\n'.encode())
                v.sendall(b'* LIST (\\Noselect \\HasChildren) "/" "[Gmail]"\r\n')
                ok()
            elif befehl.startswith("LOGOUT"):
                v.sendall(b"* BYE bis bald\r\n")
                ok()
                return
            else:
                v.sendall(f"{tag} BAD unbekannt\r\n".encode())


def _mail(*anhaenge: tuple[str, bytes], inline_bild: bool = False, signatur: bool = False) -> bytes:
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = ABSENDER, "ich@example.org", BETREFF
    m.set_content("Anbei die Unterlagen.")
    for name, inhalt in anhaenge:
        m.add_attachment(inhalt, maintype="application", subtype="octet-stream", filename=name)
    if inline_bild:
        m.add_attachment(b"\x89PNG logo", maintype="image", subtype="png", filename="logo.png",
                         disposition="inline")
    if signatur:
        m.add_attachment(b"signatur", maintype="application", subtype="pkcs7-signature",
                         filename="smime.p7s")
    return m.as_bytes()


@pytest.fixture(autouse=True)
def _umgebung(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(config, "POLLYSORT_HOME", home)
    monkeypatch.setattr(config, "CONFIG_PATH", home / "config.toml")
    monkeypatch.setattr(config, "CREDENTIALS_PATH", home / "credentials")
    monkeypatch.setattr(config, "PROJECTS_PATH", home / "projects.txt")
    for name in ("POLLYSORT_EMAIL_PASSWORD", "BEEHIVE_EMAIL_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    # Der Übungsserver spricht unverschlüsselt; die Prüfung der echten TLS-Verbindung steht unten.
    monkeypatch.setattr(imaplib.IMAP4, "starttls", lambda self, ssl_context=None: ("OK", []))
    monkeypatch.setattr(postfach, "_LETZTER_VERSUCH", {})
    monkeypatch.setattr(postfach, "_LETZTER_FEHLER", {})
    yield
    i18n.set_language("de")


@pytest.fixture
def server():
    s = MiniImap({"INBOX": [], "Projekte/Haus": [_mail(("rechnung.pdf", PDF)),
                                                 _mail(("vertrag.pdf", PDF2))]})
    yield s
    s.schliessen()


@pytest.fixture
def hive(tmp_path):
    h = tmp_path / "haus"
    h.mkdir()
    config.write_seed(h, HiveSeed(name="Haus"))
    return h


def _zugang(server, passwort: str = PASSWORT) -> Zugang:
    return Zugang("127.0.0.1", server.port, "ich@example.org", passwort)


def _eingang(hive) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in hive.iterdir() if p.is_file()}


# --------------------------------------------------------------------------- #
#  Abholen
# --------------------------------------------------------------------------- #
def test_anhaenge_landen_im_eingang_und_nur_einmal(server, hive):
    erst = abholen(hive, _zugang(server), "Projekte/Haus")
    assert sorted(erst.geholt) == ["rechnung.pdf", "vertrag.pdf"] and erst.nachrichten == 2
    assert _eingang(hive) == {"rechnung.pdf": PDF, "vertrag.pdf": PDF2}

    nochmal = abholen(hive, _zugang(server), "Projekte/Haus")
    assert (nochmal.geholt, nochmal.nachrichten, nochmal.bekannt) == ([], 0, 0)

    server.ordner["Projekte/Haus"].append(_mail(("neu.pdf", b"neu")))
    assert abholen(hive, _zugang(server), "Projekte/Haus").geholt == ["neu.pdf"]
    assert postfach.stand(hive)["geholt"] == 3


def test_im_postfach_wird_nichts_veraendert(server, hive):
    abholen(hive, _zugang(server), "Projekte/Haus")
    befehle = " | ".join(server.befehle).upper()
    assert "EXAMINE" in befehle and "SELECT" not in befehle, "schreibgeschützt öffnen"
    assert "BODY.PEEK[]" in befehle, "holen, ohne als gelesen zu markieren"
    for verboten in ("STORE", "EXPUNGE", "DELETE", "COPY", "MOVE", "APPEND", "RFC822)", "BODY[]"):
        assert verboten not in befehle, verboten
    assert PASSWORT not in " ".join(server.befehle)        # (der Server schwärzt es schon selbst)


def test_gleicher_inhalt_kommt_nicht_doppelt(server, hive):
    server.ordner["Projekte/Haus"].append(_mail(("rechnung-kopie.pdf", PDF)))
    ergebnis = abholen(hive, _zugang(server), "Projekte/Haus")
    assert sorted(ergebnis.geholt) == ["rechnung.pdf", "vertrag.pdf"] and ergebnis.bekannt == 1


def test_vorhandene_datei_wird_nie_ersetzt(server, hive):
    (hive / "rechnung.pdf").write_bytes(b"meine eigene Datei")
    ergebnis = abholen(hive, _zugang(server), "Projekte/Haus")
    assert "rechnung (2).pdf" in ergebnis.geholt
    assert (hive / "rechnung.pdf").read_bytes() == b"meine eigene Datei"
    assert (hive / "rechnung (2).pdf").read_bytes() == PDF
    assert not list(config.honig(hive).glob("postfach.teil-*")), "keine halben Dateien übrig"


def test_logos_und_signaturen_sind_keine_anhaenge(server, hive):
    server.ordner["INBOX"].append(_mail(("brief.pdf", PDF), inline_bild=True, signatur=True))
    assert abholen(hive, _zugang(server), "INBOX").geholt == ["brief.pdf"]


def test_anhang_in_weitergeleiteter_nachricht_wird_gefunden(server, hive):
    aussen = EmailMessage()
    aussen["Subject"] = "WG: " + BETREFF
    aussen.set_content("siehe unten")
    aussen.add_attachment(EmailMessage(), filename="weitergeleitet.eml")
    innen = aussen.get_payload()[1].get_payload()[0]
    innen["Subject"] = BETREFF
    innen.set_content("Original")
    innen.add_attachment(PDF, maintype="application", subtype="pdf", filename="original.pdf")
    server.ordner["INBOX"].append(aussen.as_bytes())
    assert abholen(hive, _zugang(server), "INBOX").geholt == ["original.pdf"]


def test_zu_grosse_anhaenge_bleiben_im_postfach(server, hive):
    ergebnis = abholen(hive, _zugang(server), "Projekte/Haus", max_mb=0)
    assert ergebnis.geholt == [] and sorted(ergebnis.zu_gross) == ["rechnung.pdf", "vertrag.pdf"]
    assert _eingang(hive) == {}


def test_viele_nachrichten_kommen_in_raten(server, hive, monkeypatch):
    monkeypatch.setattr(postfach, "MAX_NACHRICHTEN", 1)
    erst = abholen(hive, _zugang(server), "Projekte/Haus")
    assert (erst.geholt, erst.rest) == (["rechnung.pdf"], 1)
    assert abholen(hive, _zugang(server), "Projekte/Haus").geholt == ["vertrag.pdf"]


# --------------------------------------------------------------------------- #
#  Dateinamen von außen
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("roh, sicher", [
    ("rechnung.pdf", "rechnung.pdf"),
    ("..\\..\\Autostart\\boese.bat", "boese.bat"),
    ("../../../etc/passwd", "passwd"),
    ("C:\\Windows\\system32\\x.dll", "x.dll"),
    (".honig", "honig"), ("...", "anhang"), ("", "anhang"), ("  .versteckt.txt ", "versteckt.txt"),
    ('was<>:"|?*.pdf', "was_______.pdf"),
    ("CON.txt", "_CON.txt"), ("nul", "_nul"), ("Lpt1.pdf", "_Lpt1.pdf"),
    ("zeile\numbruch\x00.pdf", "zeile_umbruch_.pdf"),
    ("Größe & Maße (final).xlsx", "Größe & Maße (final).xlsx"),
])
def test_sicherer_name(roh, sicher):
    assert sicherer_name(roh) == sicher


def test_sehr_lange_namen_werden_gekuerzt_die_endung_bleibt():
    name = sicherer_name("a" * 400 + ".pdf")
    assert len(name) <= 121 and name.endswith(".pdf")


def test_boeser_dateiname_landet_nur_im_eingang(server, hive, tmp_path):
    server.ordner["INBOX"].append(_mail(("..\\..\\ausbruch.bat", b"echo"), ("../.honig/hive.toml", b"x")))
    vorher = (config.honig(hive) / "hive.toml").read_bytes()
    ergebnis = abholen(hive, _zugang(server), "INBOX")
    assert sorted(ergebnis.geholt) == ["ausbruch.bat", "hive.toml"]
    assert not (tmp_path / "ausbruch.bat").exists() and not (tmp_path.parent / "ausbruch.bat").exists()
    assert (config.honig(hive) / "hive.toml").read_bytes() == vorher, "Projekt-Einstellungen unberührt"
    assert set(_eingang(hive)) == {"ausbruch.bat", "hive.toml"}


# --------------------------------------------------------------------------- #
#  Fehler — und was dabei nicht verraten wird
# --------------------------------------------------------------------------- #
def test_falsches_passwort_ohne_echo_des_servers(server, hive):
    with pytest.raises(PostfachFehler) as ei:
        abholen(hive, _zugang(server, "falsch-GEHEIM-123"), "Projekte/Haus")
    text = str(ei.value)
    assert "Anmeldung" in text
    assert "falsch-GEHEIM-123" not in text and "AUTHENTICATIONFAILED" not in text
    assert _eingang(hive) == {}


def test_anmeldefehler_nennt_den_hinweis_des_anbieters(monkeypatch):
    class _Abgelehnt:
        def __init__(self, *a, **kw):
            pass

        def login(self, *a):
            raise imaplib.IMAP4.error(b"[AUTHENTICATIONFAILED] " + PASSWORT.encode())

        def logout(self):
            pass

    monkeypatch.setattr(imaplib, "IMAP4_SSL", _Abgelehnt)
    with pytest.raises(PostfachFehler) as ei:
        postfach._verbinden(Zugang("imap.gmx.net", 993, "ich@gmx.de", PASSWORT))
    assert "POP3 & IMAP" in str(ei.value) and PASSWORT not in str(ei.value)


def test_unbekannter_ordner_wird_beim_namen_genannt(server, hive):
    with pytest.raises(PostfachFehler) as ei:
        abholen(hive, _zugang(server), "Gibt/Es/Nicht")
    assert "Gibt/Es/Nicht" in str(ei.value) and "postfach liste" in str(ei.value)


def test_server_nicht_erreichbar(hive):
    frei = socket.socket()
    frei.bind(("127.0.0.1", 0))
    port = frei.getsockname()[1]
    frei.close()
    with pytest.raises(PostfachFehler) as ei:
        abholen(hive, Zugang("127.0.0.1", port, "ich@example.org", PASSWORT), "INBOX")
    assert PASSWORT not in str(ei.value) and "nicht erreichbar" in str(ei.value)


def test_abbruch_mittendrin_verliert_nichts_und_holt_nichts_doppelt(server, hive):
    server.abbruch_bei = 2
    with pytest.raises(PostfachFehler):
        abholen(hive, _zugang(server), "Projekte/Haus")
    assert _eingang(hive) == {"rechnung.pdf": PDF}, "die erste Nachricht ist da"
    assert postfach.stand(hive)["letzte_uid"] == 1

    server.abbruch_bei = None
    assert abholen(hive, _zugang(server), "Projekte/Haus").geholt == ["vertrag.pdf"]
    assert _eingang(hive) == {"rechnung.pdf": PDF, "vertrag.pdf": PDF2}


def test_neu_nummeriertes_postfach_bringt_nichts_doppelt(server, hive):
    abholen(hive, _zugang(server), "Projekte/Haus")
    server.gueltigkeit = 8                      # der Server hat den Ordner neu aufgebaut
    ergebnis = abholen(hive, _zugang(server), "Projekte/Haus")
    assert (ergebnis.geholt, ergebnis.bekannt, ergebnis.nachrichten) == ([], 2, 2)


def test_verbindung_wird_geprueft_verschluesselt(monkeypatch):
    gesehen = {}

    class _Ssl:
        def __init__(self, host, port, *, ssl_context=None, timeout=None):
            gesehen["direkt"] = ssl_context

        def login(self, *a):
            pass

    class _Klar(_Ssl):
        def __init__(self, host, port, timeout=None):
            pass

        def starttls(self, ssl_context=None):
            gesehen["starttls"] = ssl_context

    monkeypatch.setattr(imaplib, "IMAP4_SSL", _Ssl)
    monkeypatch.setattr(imaplib, "IMAP4", _Klar)
    postfach._verbinden(Zugang("imap.example.org", 993, "a@b.de", PASSWORT))
    postfach._verbinden(Zugang("imap.example.org", 143, "a@b.de", PASSWORT))
    for art in ("direkt", "starttls"):
        kontext = gesehen[art]
        assert kontext.verify_mode == ssl.CERT_REQUIRED and kontext.check_hostname, art


# --------------------------------------------------------------------------- #
#  Ordnernamen
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("klar, kodiert", [
    ("INBOX", "INBOX"), ("Büro", "B&APw-ro"),
    ("Projekte/Häuser & Gärten", "Projekte/H&AOQ-user &- G&AOQ-rten"),
    ("Entwürfe", "Entw&APw-rfe"), ("日本語", "&ZeVnLIqe-"),
])
def test_ordnernamen_mit_umlauten(klar, kodiert):
    assert postfach._utf7_kodieren(klar) == kodiert
    assert postfach._utf7_dekodieren(kodiert) == klar


def test_ordner_mit_umlaut_wird_gefunden_und_gelistet(hive):
    server = MiniImap({"INBOX": [], "B&APw-ro": [_mail(("beleg.pdf", PDF))]})
    try:
        assert postfach.ordner_liste(_zugang(server)) == ["Büro", "INBOX"], "ohne Schein-Ordner"
        assert abholen(hive, _zugang(server), "Büro").geholt == ["beleg.pdf"]
    finally:
        server.schliessen()


# --------------------------------------------------------------------------- #
#  Einstellungen
# --------------------------------------------------------------------------- #
def test_jeder_anbieter_bringt_seinen_posteingangsserver_mit():
    for kurz, a in EMAIL_ANBIETER.items():
        assert a.imap and "." in a.imap and " " not in a.imap, kurz
    fr = Flugrouten()
    email_setzen(fr, "gmx", adresse="ich@gmx.de", passwort=PASSWORT)
    assert (fr.email.imap_host, fr.email.imap_port) == ("imap.gmx.net", 993)
    z = postfach.zugang(fr)
    assert (z.host, z.port, z.adresse) == ("imap.gmx.net", 993, "ich@gmx.de") and PASSWORT not in repr(z)


def test_eigener_server_abholen_ist_freiwillig():
    fr = Flugrouten()
    email_setzen(fr, "custom", adresse="a@b.de", passwort=PASSWORT, host="smtp.b.de", port=587)
    assert postfach.zugang(fr) is None, "ohne Posteingangsserver wird nur gemeldet"
    email_setzen(fr, "custom", adresse="a@b.de", host="smtp.b.de", port=587, imap_host="imap.b.de")
    assert postfach.zugang(fr).host == "imap.b.de"


def test_abholen_geht_auch_wenn_das_melden_per_mail_aus_ist():
    fr = Flugrouten(email=EmailConfig(enabled=False, address="a@b.de", password=PASSWORT,
                                      imap_host="imap.b.de"))
    assert postfach.zugang(fr) is not None


def test_aeltere_einstellungen_ohne_posteingangsserver():
    fr = Flugrouten()
    email_setzen(fr, "webde", adresse="ich@web.de", passwort=PASSWORT)
    save_flugrouten(fr)
    pfad = config.POLLYSORT_HOME / "flugrouten.toml"
    alt = "\n".join(z for z in pfad.read_text(encoding="utf-8").splitlines() if "imap_" not in z)
    pfad.write_text(alt + "\n", encoding="utf-8")
    assert load_flugrouten().email.imap_host == "imap.web.de", "aus dem Anbieter abgeleitet"


def test_postfach_ordner_steht_in_den_projekt_einstellungen(hive):
    assert config.load_seed(hive).postfach_ordner == ""
    assert "[postfach]" not in (config.honig(hive) / "hive.toml").read_text(encoding="utf-8")
    seed = config.load_seed(hive)
    seed.postfach_ordner = 'Projekte/Haus "Süd"'
    seed.subrouting = {"rechnungen": "{jahr}"}
    config.write_seed(hive, seed)
    neu = config.load_seed(hive)
    assert neu.postfach_ordner == 'Projekte/Haus "Süd"' and neu.subrouting == {"rechnungen": "{jahr}"}


# --------------------------------------------------------------------------- #
#  Wache
# --------------------------------------------------------------------------- #
def test_wache_holt_nicht_bei_jedem_takt(server, hive, monkeypatch):
    fr = Flugrouten(email=EmailConfig(address="ich@example.org", password=PASSWORT,
                                      imap_host="127.0.0.1", imap_port=server.port))
    save_flugrouten(fr)
    journal = Journal(hive)
    ergebnis, fehler = postfach.automatisch(hive, ordner="Projekte/Haus", max_mb=100, journal=journal)
    assert sorted(ergebnis.geholt) == ["rechnung.pdf", "vertrag.pdf"] and fehler == ""
    server.ordner["Projekte/Haus"].append(_mail(("spaeter.pdf", b"spaeter")))
    nichts = postfach.automatisch(hive, ordner="Projekte/Haus", max_mb=100)
    assert nichts == (None, ""), "noch nicht wieder dran"

    monkeypatch.setattr(postfach, "PAUSE", 0)
    assert postfach.automatisch(hive, ordner="Projekte/Haus", max_mb=100)[0].geholt == ["spaeter.pdf"]
    assert postfach.automatisch(hive, ordner="", max_mb=100) == (None, ""), "nicht eingestellt"

    protokoll = (config.honig(hive) / "log.jsonl").read_text(encoding="utf-8")
    assert "postfach_abruf" in protokoll and "rechnung.pdf" in protokoll
    for geheim in (ABSENDER, BETREFF, "Gehaltsliste", PASSWORT):
        assert geheim not in protokoll


def test_wache_meldet_denselben_fehler_nur_einmal(server, hive, monkeypatch):
    monkeypatch.setattr(postfach, "PAUSE", 0)
    save_flugrouten(Flugrouten(email=EmailConfig(address="ich@example.org", password="falsch",
                                                 imap_host="127.0.0.1", imap_port=server.port)))
    _, fehler = postfach.automatisch(hive, ordner="Projekte/Haus", max_mb=100)
    assert "Anmeldung" in fehler
    assert postfach.automatisch(hive, ordner="Projekte/Haus", max_mb=100) == (None, "")


def test_ergebnis_wird_verstaendlich_gemeldet():
    gesagt = []

    class _Konsole:
        def __getattr__(self, art):
            return lambda text, *a: gesagt.append(text)

    postfach.melden(_Konsole(), Abruf(nachrichten=3, geholt=["a.pdf"], bekannt=2,
                                      zu_gross=["film.mp4"], rest=5), max_mb=100)
    text = " ".join(gesagt)
    for teil in ("a.pdf", "schon einmal", "100 MB", "film.mp4", "5 weitere"):
        assert teil in text
    gesagt.clear()
    postfach.melden(_Konsole(), Abruf(), max_mb=100)
    assert gesagt == [i18n.t("pf.nothing")]


# --------------------------------------------------------------------------- #
#  Dienst
# --------------------------------------------------------------------------- #
def test_dienst_postfach_einstellen_und_abholen(server, hive):
    save_flugrouten(Flugrouten(email=EmailConfig(address="ich@example.org", password=PASSWORT,
                                                 imap_host="127.0.0.1", imap_port=server.port)))
    d = Dienst(hive)
    with pytest.raises(Ungueltig):
        d.postfach_abholen()                                    # noch kein Ordner eingestellt
    assert d.postfach_ordner()["ergebnis"]["ordner"] == ["INBOX", "Projekte/Haus"]

    stand = d.postfach_einstellen(ordner=" Projekte/Haus ")["ergebnis"]
    assert stand["ordner"] == "Projekte/Haus" and stand["bereit"] and stand["letzter_abruf"] == ""
    antwort = d.postfach_abholen()
    assert sorted(antwort["ergebnis"]["geholt"]) == ["rechnung.pdf", "vertrag.pdf"]
    assert d.postfach_stand()["geholt"] == 2 and d.postfach_stand()["letzter_abruf"]
    alles = json.dumps([antwort, d.postfach_stand()], ensure_ascii=False)
    for geheim in (PASSWORT, ABSENDER, BETREFF):
        assert geheim not in alles

    assert d.postfach_einstellen(ordner="")["ergebnis"]["ordner"] == ""
    with pytest.raises(Ungueltig):
        d.postfach_einstellen(ordner="x\ny")


def test_dienst_ohne_zugang_sagt_was_fehlt(hive):
    d = Dienst(hive)
    assert d.postfach_stand()["bereit"] is False
    d.postfach_einstellen(ordner="INBOX")
    with pytest.raises(Ungueltig) as ei:
        d.postfach_abholen()
    assert "flugrouten setup" in str(ei.value)

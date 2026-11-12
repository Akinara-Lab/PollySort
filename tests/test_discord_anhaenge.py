"""Discord-Anhänge — Dateien aus dem Discord-Kanal eines Projekts in den Eingang holen.

Die Tests sprechen mit einem nachgestellten Discord (``_Discord``), das für ``httpx.get`` und
``httpx.stream`` einspringt und mitschreibt, was PollySort ihm schickt. Adressen, Felder und
Fehlercodes folgen der Discord-Dokumentation (nachgelesen am 12.11.2026).

Sichert zu:
- An Discord gehen nur lesende Anfragen; im Kanal wird nichts verändert.
- Das Bot-Token geht nur an die Schnittstelle von Discord — nie an den Dateispeicher, nie in eine
  Meldung, eine Antwort des Dienstes oder das Journal. Text und Verfasser ebenso wenig.
- Nichts kommt doppelt an, keine Datei im Eingang wird ersetzt, Dateinamen landen nur im Eingang.
- Geladen wird nur von den Dateispeichern von Discord.
- Hält Discord die Inhalte zurück (Message Content Intent fehlt), wird nichts übersprungen.
- Ein Abbruch mittendrin verliert nichts und holt später nichts doppelt.
"""

from __future__ import annotations

import json

import httpx
import pytest

from pollysort import config, discord_anhaenge, i18n
from pollysort.config import HiveSeed
from pollysort.console import BeeConsole
from pollysort.discord_anhaenge import API, Abruf, DiscordFehler, abholen, kanal_liste, kanal_pruefen
from pollysort.flugrouten import DiscordConfig, Flugrouten, save_flugrouten
from pollysort.journal import Journal
from pollysort.repl import BeehiveShell
from pollysort.web.dienst import Dienst, Ungueltig

TOKEN = "bot-TOKEN-streng-geheim.abc.def"
KANAL = "112233445566778899"
ANDERER = "998877665544332211"
SERVER = "555555555555555555"
VERFASSER = "chefin-geheim"
TEXT = "Vertraulich: Gehaltsliste anbei"
PDF = b"%PDF-1.4 Rechnung ACME 4200 EUR"
PDF2 = b"%PDF-1.4 Mietvertrag Wohnung"
BASIS = 1_300_000_000_000_000_000


# --------------------------------------------------------------------------- #
#  Nachgestelltes Discord
# --------------------------------------------------------------------------- #
class _Antwort:
    def __init__(self, status: int, daten=None):
        self.status_code, self._daten = status, daten

    def json(self):
        if self._daten is None:
            raise ValueError("kein JSON")
        return self._daten


class _Datei:
    """Steht für die Antwort von ``httpx.stream``: liefert den Inhalt in Stücken."""

    def __init__(self, status: int, inhalt: bytes = b""):
        self.status_code, self._inhalt = status, inhalt

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_bytes(self):
        for i in range(0, len(self._inhalt), 7):
            yield self._inhalt[i:i + 7]


class _Discord:
    def __init__(self, monkeypatch):
        self.kanaele: dict[str, list[dict]] = {KANAL: [], ANDERER: []}
        self.dateien: dict[str, bytes] = {}
        self.merkmale = 1 << 19                 # Message Content Intent an (Bot unter 100 Servern)
        self.inhalt_sichtbar = True             # False: Discord hält die Inhalte zurück
        self.status: dict[str, int] = {}        # Pfad → erzwungener Fehlercode
        self.kaputt: set[str] = set()           # Datei-Adressen, bei denen die Verbindung reißt
        self.server = [{"id": SERVER, "name": "Haus-Server"}]
        self.server_kanaele = {SERVER: [
            {"id": ANDERER, "name": "plaudern", "type": 0, "position": 2},
            {"id": KANAL, "name": "haus-unterlagen", "type": 0, "position": 1},
            {"id": "444444444444444444", "name": "Sprechzimmer", "type": 2, "position": 0},
            {"id": "333333333333333333", "name": "neuigkeiten", "type": 5, "position": 3}]}
        self.anfragen: list[tuple[str, str]] = []           # (Art, Adresse)
        self.koepfe: list[dict] = []
        monkeypatch.setattr(httpx, "get", self.get)
        monkeypatch.setattr(httpx, "stream", self.stream)
        for schreibend in ("post", "put", "patch", "delete", "request"):
            monkeypatch.setattr(httpx, schreibend, self._verboten)

    def _verboten(self, *a, **kw):
        raise AssertionError("PollySort darf an Discord nur lesende Anfragen schicken")

    def nachricht(self, kanal: str, nr: int, *anhaenge: tuple[str, bytes], bot: bool = False,
                  typ: int = 0, text: str = TEXT, **mehr) -> dict:
        nid = str(BASIS + nr)
        liste = []
        for i, (name, inhalt) in enumerate(anhaenge):
            adresse = f"https://cdn.discordapp.com/attachments/{kanal}/{nid}{i}/datei?ex=1&is=2&hm=3"
            self.dateien[adresse] = inhalt
            liste.append({"id": f"{nid}{i}", "filename": name, "size": len(inhalt), "url": adresse,
                          "proxy_url": adresse.replace("cdn.discordapp.com", "media.discordapp.net")})
        n = {"id": nid, "type": typ, "content": text, "attachments": liste, "embeds": [],
             "author": {"id": "42", "username": VERFASSER, "bot": bot},
             "timestamp": "2026-11-12T08:00:00+00:00", **mehr}
        self.kanaele[kanal].append(n)
        return n

    def get(self, url, headers=None, params=None, timeout=None):
        self.anfragen.append(("GET", url))
        self.koepfe.append(dict(headers or {}))
        assert url.startswith(API + "/"), "das Token darf nur an die Schnittstelle von Discord"
        pfad = url[len(API):]
        if pfad in self.status:
            return _Antwort(self.status[pfad], {"message": f"Fehler für {TOKEN}"})
        if (headers or {}).get("Authorization") != f"Bot {TOKEN}":
            return _Antwort(401, {"message": "401: Unauthorized"})
        if pfad == "/applications/@me":
            return _Antwort(200, {"id": "1", "flags": self.merkmale})
        if pfad == "/users/@me/guilds":
            return _Antwort(200, self.server)
        if pfad.startswith("/guilds/"):
            return _Antwort(200, self.server_kanaele[pfad.split("/")[2]])
        kanal = pfad.split("/")[2]
        if kanal not in self.kanaele:
            return _Antwort(404, {"message": "Unknown Channel"})
        nach, anzahl = int(params["after"]), int(params["limit"])
        assert 1 <= anzahl <= 100
        seite = [n for n in self.kanaele[kanal] if int(n["id"]) > nach][:anzahl]
        if not self.inhalt_sichtbar:
            seite = [n if n["author"]["bot"] else {**n, "content": "", "attachments": [], "embeds": []}
                     for n in seite]
        return _Antwort(200, list(reversed(seite)))             # Discord: die neueste zuerst

    def stream(self, methode, url, timeout=None, **kw):
        self.anfragen.append(("DATEI", url))
        assert methode == "GET"
        assert not kw.get("headers"), "an den Dateispeicher geht kein Token"
        if url in self.kaputt:
            raise httpx.ReadError("Verbindung gerissen")
        if url not in self.dateien:
            return _Datei(404)
        return _Datei(200, self.dateien[url])

    def geladen(self) -> list[str]:
        return [adresse for art, adresse in self.anfragen if art == "DATEI"]


@pytest.fixture(autouse=True)
def _umgebung(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(config, "POLLYSORT_HOME", home)
    monkeypatch.setattr(config, "CONFIG_PATH", home / "config.toml")
    monkeypatch.setattr(config, "CREDENTIALS_PATH", home / "credentials")
    monkeypatch.setattr(config, "PROJECTS_PATH", home / "projects.txt")
    for name in ("POLLYSORT_DISCORD_TOKEN", "BEEHIVE_DISCORD_TOKEN",
                 "POLLYSORT_DISCORD_WEBHOOK", "BEEHIVE_DISCORD_WEBHOOK"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(discord_anhaenge, "_LETZTER_VERSUCH", {})
    monkeypatch.setattr(discord_anhaenge, "_LETZTER_FEHLER", {})
    yield
    i18n.set_language("de")


@pytest.fixture
def discord(monkeypatch):
    d = _Discord(monkeypatch)
    d.nachricht(KANAL, 1, ("rechnung.pdf", PDF))
    d.nachricht(KANAL, 2)                                       # nur Text
    d.nachricht(KANAL, 3, ("vertrag.pdf", PDF2))
    return d


@pytest.fixture
def hive(tmp_path):
    h = tmp_path / "haus"
    h.mkdir()
    config.write_seed(h, HiveSeed(name="Haus"))
    return h


def _eingang(hive) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in hive.iterdir() if p.is_file()}


def _bot_einrichten() -> None:
    save_flugrouten(Flugrouten(discord=DiscordConfig(bot_token=TOKEN)))


# --------------------------------------------------------------------------- #
#  Abholen
# --------------------------------------------------------------------------- #
def test_anhaenge_landen_im_eingang_und_nur_einmal(discord, hive):
    e = abholen(hive, TOKEN, KANAL)
    assert (e.nachrichten, e.geholt, e.bekannt, e.mehr) == (3, ["rechnung.pdf", "vertrag.pdf"], 0, False)
    assert _eingang(hive) == {"rechnung.pdf": PDF, "vertrag.pdf": PDF2}
    st = discord_anhaenge.stand(hive)
    assert (st["kanal"], st["letzte_id"], st["geholt"]) == (KANAL, str(BASIS + 3), 2)
    assert st["letzter_abruf"]

    zweiter = abholen(hive, TOKEN, KANAL)
    assert (zweiter.nachrichten, zweiter.geholt) == (0, [])
    discord.nachricht(KANAL, 4, ("spaeter.pdf", b"spaeter"))
    assert abholen(hive, TOKEN, KANAL).geholt == ["spaeter.pdf"]
    assert discord_anhaenge.stand(hive)["geholt"] == 3


def test_an_discord_gehen_nur_lesende_anfragen_und_das_token_nur_an_die_schnittstelle(discord, hive):
    abholen(hive, TOKEN, KANAL)                 # jede schreibende Anfrage ließe den Test scheitern
    assert {art for art, _ in discord.anfragen} == {"GET", "DATEI"}
    assert all(k == {"Authorization": f"Bot {TOKEN}"} for k in discord.koepfe)
    assert len(discord.geladen()) == 2
    assert all(TOKEN not in adresse for _, adresse in discord.anfragen)


def test_nichts_von_der_nachricht_wird_gespeichert_ausser_dem_stand(discord, hive):
    abholen(hive, TOKEN, KANAL)
    alles = "".join(p.read_text(encoding="utf-8", errors="replace")
                    for p in config.honig(hive).rglob("*") if p.is_file())
    for geheim in (TOKEN, VERFASSER, TEXT, "Gehaltsliste"):
        assert geheim not in alles


def test_viele_nachrichten_kommen_seitenweise_und_in_raten(discord, hive, monkeypatch):
    monkeypatch.setattr(discord_anhaenge, "SEITE", 2)
    monkeypatch.setattr(discord_anhaenge, "MAX_NACHRICHTEN", 4)
    for nr in range(4, 8):
        discord.nachricht(KANAL, nr, (f"datei{nr}.txt", f"inhalt {nr}".encode()))
    erster = abholen(hive, TOKEN, KANAL)
    assert (erster.nachrichten, erster.mehr) == (4, True)
    assert erster.geholt == ["rechnung.pdf", "vertrag.pdf", "datei4.txt"], "von alt nach neu"
    zweiter = abholen(hive, TOKEN, KANAL)
    assert (zweiter.nachrichten, zweiter.mehr) == (3, False)
    assert zweiter.geholt == ["datei5.txt", "datei6.txt", "datei7.txt"]


def test_gleicher_inhalt_kommt_nicht_doppelt(discord, hive):
    discord.nachricht(KANAL, 4, ("kopie.pdf", PDF))
    e = abholen(hive, TOKEN, KANAL)
    assert (e.geholt, e.bekannt) == (["rechnung.pdf", "vertrag.pdf"], 1)


def test_vorhandene_datei_wird_nie_ersetzt(discord, hive):
    (hive / "rechnung.pdf").write_bytes(b"meine eigene Rechnung")
    e = abholen(hive, TOKEN, KANAL)
    assert e.geholt == ["rechnung (2).pdf", "vertrag.pdf"]
    assert _eingang(hive)["rechnung.pdf"] == b"meine eigene Rechnung"


def test_anhang_einer_weitergeleiteten_nachricht_wird_gefunden(discord, hive):
    innen = discord.nachricht(ANDERER, 9, ("weitergeleitet.pdf", b"weiter"))
    discord.nachricht(KANAL, 4, text="", message_reference={"type": 1},
                      message_snapshots=[{"message": {"content": TEXT,
                                                      "attachments": innen["attachments"]}}])
    assert abholen(hive, TOKEN, KANAL).geholt == ["rechnung.pdf", "vertrag.pdf", "weitergeleitet.pdf"]


def test_zu_grosse_anhaenge_werden_gar_nicht_erst_geladen(discord, hive):
    discord.nachricht(KANAL, 4, ("film.mp4", b"x" * (2 * 1024 * 1024)))
    e = abholen(hive, TOKEN, KANAL, max_mb=1)
    assert e.zu_gross == ["film.mp4"] and "film.mp4" not in _eingang(hive)
    assert len(discord.geladen()) == 2
    assert discord_anhaenge.stand(hive)["letzte_id"] == str(BASIS + 4), "gilt als erledigt"


def test_eine_datei_die_groesser_ist_als_angekuendigt_bricht_ab(discord, hive):
    n = discord.nachricht(KANAL, 4, ("geschummelt.bin", b"x" * (2 * 1024 * 1024)))
    n["attachments"][0]["size"] = 10
    e = abholen(hive, TOKEN, KANAL, max_mb=1)
    assert e.zu_gross == ["geschummelt.bin"] and "geschummelt.bin" not in _eingang(hive)


def test_boeser_dateiname_landet_nur_im_eingang(discord, hive, tmp_path):
    discord.nachricht(KANAL, 4, ("..\\..\\Autostart\\boese.bat", b"echo"),
                      ("../../.honig/hive.toml", b"kaputt"), ("CON.txt", b"geraet"))
    e = abholen(hive, TOKEN, KANAL)
    assert e.geholt[2:] == ["boese.bat", "hive.toml", "_CON.txt"]
    assert not (tmp_path / "Autostart").exists()
    assert "kaputt" not in (config.honig(hive) / "hive.toml").read_text(encoding="utf-8")


@pytest.mark.parametrize("adresse", [
    "https://boese.example/attachments/1/2/datei",
    "http://cdn.discordapp.com/attachments/1/2/datei",
    "https://cdn.discordapp.com.boese.example/datei",
    "file:///C:/Windows/win.ini",
    "",
])
def test_geladen_wird_nur_vom_dateispeicher_von_discord(discord, hive, adresse):
    n = discord.nachricht(KANAL, 4, ("fremd.pdf", b"fremd"))
    n["attachments"][0]["url"] = adresse
    e = abholen(hive, TOKEN, KANAL)
    assert e.verloren == ["fremd.pdf"] and "fremd.pdf" not in _eingang(hive)
    assert adresse not in discord.geladen()


def test_eine_datei_die_discord_nicht_mehr_hat_haelt_den_rest_nicht_auf(discord, hive):
    n = discord.nachricht(KANAL, 4, ("weg.pdf", b"weg"))
    del discord.dateien[n["attachments"][0]["url"]]
    discord.nachricht(KANAL, 5, ("danach.pdf", b"danach"))
    e = abholen(hive, TOKEN, KANAL)
    assert e.verloren == ["weg.pdf"] and e.geholt[-1] == "danach.pdf"


# --------------------------------------------------------------------------- #
#  Discord hält die Inhalte zurück (Message Content Intent)
# --------------------------------------------------------------------------- #
def test_ohne_freigabe_der_inhalte_wird_nichts_uebersprungen(discord, hive):
    discord.inhalt_sichtbar, discord.merkmale = False, 0
    with pytest.raises(DiscordFehler) as ei:
        abholen(hive, TOKEN, KANAL)
    assert "Message Content Intent" in str(ei.value) and TOKEN not in str(ei.value)
    assert discord_anhaenge.stand(hive)["letzte_id"] == "0" and _eingang(hive) == {}

    discord.inhalt_sichtbar, discord.merkmale = True, 1 << 19   # im Entwicklerportal eingeschaltet
    assert abholen(hive, TOKEN, KANAL).geholt == ["rechnung.pdf", "vertrag.pdf"]


def test_leere_nachricht_bei_erlaubten_inhalten_ist_kein_fehler(discord, hive):
    discord.nachricht(KANAL, 4, text="")                        # etwas, das wir nicht kennen
    discord.nachricht(KANAL, 5, ("danach.pdf", b"danach"))
    e = abholen(hive, TOKEN, KANAL)
    assert e.geholt[-1] == "danach.pdf" and e.nachrichten == 5
    assert [a for a in discord.anfragen if a[1].endswith("/applications/@me")], "nachgesehen"


def test_nachrichten_von_bots_und_systemmeldungen_zaehlen_nicht_als_leer(discord, hive):
    discord.merkmale = 0
    discord.nachricht(KANAL, 4, text="", bot=True)
    discord.nachricht(KANAL, 5, text="", typ=7)                 # „ist dem Server beigetreten"
    assert abholen(hive, TOKEN, KANAL).nachrichten == 5


# --------------------------------------------------------------------------- #
#  Fehler — immer ohne Token und ohne die Antwort des Servers
# --------------------------------------------------------------------------- #
def test_falsches_token_ohne_echo(discord, hive):
    with pytest.raises(DiscordFehler) as ei:
        abholen(hive, "falsches-token-XYZ", KANAL)
    assert "Bot-Token" in str(ei.value) and "falsches-token-XYZ" not in str(ei.value)


@pytest.mark.parametrize("status, teil", [(403, "Nachrichtenverlauf"), (404, "Kanal-ID"),
                                          (429, "später"), (500, "500")])
def test_fehler_von_discord_werden_erklaert(discord, hive, status, teil):
    discord.status[f"/channels/{KANAL}/messages"] = status
    with pytest.raises(DiscordFehler) as ei:
        abholen(hive, TOKEN, KANAL)
    assert teil in str(ei.value) and TOKEN not in str(ei.value)
    assert _eingang(hive) == {}


def test_discord_nicht_erreichbar(hive, monkeypatch):
    def kaputt(url, **kw):
        raise httpx.ConnectError(f"keine Verbindung, Kopf {kw.get('headers')}")
    monkeypatch.setattr(httpx, "get", kaputt)
    with pytest.raises(DiscordFehler) as ei:
        abholen(hive, TOKEN, KANAL)
    assert "ConnectError" in str(ei.value) and TOKEN not in str(ei.value)


def test_ohne_kanal_oder_ohne_bot_sagt_der_abruf_was_fehlt(discord, hive):
    with pytest.raises(DiscordFehler) as ei:
        abholen(hive, TOKEN, "")
    assert "discord kanal" in str(ei.value)
    with pytest.raises(DiscordFehler) as ei:
        abholen(hive, "", KANAL)
    assert "Webhook" in str(ei.value)
    assert discord.anfragen == []


def test_abbruch_mittendrin_verliert_nichts_und_holt_nichts_doppelt(discord, hive):
    zweite = discord.kanaele[KANAL][2]["attachments"][0]["url"]
    discord.kaputt.add(zweite)
    with pytest.raises(DiscordFehler) as ei:
        abholen(hive, TOKEN, KANAL)
    assert "ReadError" in str(ei.value)
    assert _eingang(hive) == {"rechnung.pdf": PDF}
    st = discord_anhaenge.stand(hive)
    assert (st["letzte_id"], st["geholt"]) == (str(BASIS + 2), 1)

    discord.kaputt.clear()
    assert abholen(hive, TOKEN, KANAL).geholt == ["vertrag.pdf"]
    assert _eingang(hive) == {"rechnung.pdf": PDF, "vertrag.pdf": PDF2}


def test_anderer_kanal_faengt_von_vorn_an_ohne_doppelte(discord, hive):
    abholen(hive, TOKEN, KANAL)
    discord.nachricht(ANDERER, 1, ("rechnung-kopie.pdf", PDF), ("neu.pdf", b"neu"))
    e = abholen(hive, TOKEN, ANDERER)
    assert (e.geholt, e.bekannt) == (["neu.pdf"], 1)
    assert discord_anhaenge.stand(hive)["kanal"] == ANDERER


def test_kaputter_stand_ist_ein_neuanfang(discord, hive):
    (config.honig(hive) / "discord.json").write_text('{"letzte_id": "abc", "kanal": 7}', "utf-8")
    assert discord_anhaenge.stand(hive)["letzte_id"] == "0"
    assert abholen(hive, TOKEN, KANAL).geholt == ["rechnung.pdf", "vertrag.pdf"]


# --------------------------------------------------------------------------- #
#  Kanal festlegen und finden
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("eingabe", [
    KANAL, f"  {KANAL} ", f"<#{KANAL}>",
    f"https://discord.com/channels/{SERVER}/{KANAL}",
    f"https://discord.com/channels/{SERVER}/{KANAL}/1300000000000000001",
    f"https://ptb.discord.com/channels/{SERVER}/{KANAL}/",
])
def test_kanal_als_id_erwaehnung_oder_link(eingabe):
    assert kanal_pruefen(eingabe) == KANAL


@pytest.mark.parametrize("eingabe", ["haus-unterlagen", "12345", "1" * 25, f"{KANAL}/../x",
                                     f"https://boese.example/channels/{SERVER}/{KANAL}"])
def test_was_keine_kanal_id_ist_wird_abgelehnt(eingabe):
    with pytest.raises(DiscordFehler):
        kanal_pruefen(eingabe)
    assert kanal_pruefen("") == ""


def test_kanal_liste_zeigt_nur_textkanaele_in_der_reihenfolge_des_servers(discord):
    assert kanal_liste(TOKEN) == [
        {"server": "Haus-Server", "name": "haus-unterlagen", "id": KANAL},
        {"server": "Haus-Server", "name": "plaudern", "id": ANDERER},
        {"server": "Haus-Server", "name": "neuigkeiten", "id": "333333333333333333"}]


def test_kanal_liste_laesst_unlesbare_server_aus(discord):
    discord.server.append({"id": "666666666666666666", "name": "Gesperrt"})
    discord.status["/guilds/666666666666666666/channels"] = 403
    assert len(kanal_liste(TOKEN)) == 3
    discord.status[f"/guilds/{SERVER}/channels"] = 403
    with pytest.raises(DiscordFehler):
        kanal_liste(TOKEN)


def test_discord_kanal_steht_in_den_projekt_einstellungen(hive):
    assert config.load_seed(hive).discord_kanal == ""
    assert "[discord]" not in (config.honig(hive) / "hive.toml").read_text(encoding="utf-8")
    seed = config.load_seed(hive)
    seed.discord_kanal, seed.postfach_ordner = KANAL, "Projekte/Haus"
    seed.subrouting = {"rechnungen": "{jahr}"}
    config.write_seed(hive, seed)
    neu = config.load_seed(hive)
    assert (neu.discord_kanal, neu.postfach_ordner, neu.subrouting) == (
        KANAL, "Projekte/Haus", {"rechnungen": "{jahr}"})


# --------------------------------------------------------------------------- #
#  Wache
# --------------------------------------------------------------------------- #
def test_wache_holt_nicht_bei_jedem_takt(discord, hive, monkeypatch):
    _bot_einrichten()
    ergebnis, fehler = discord_anhaenge.automatisch(hive, kanal=KANAL, max_mb=100,
                                                    journal=Journal(hive))
    assert ergebnis.geholt == ["rechnung.pdf", "vertrag.pdf"] and fehler == ""
    discord.nachricht(KANAL, 4, ("spaeter.pdf", b"spaeter"))
    assert discord_anhaenge.automatisch(hive, kanal=KANAL, max_mb=100) == (None, ""), "noch nicht dran"

    monkeypatch.setattr(discord_anhaenge, "PAUSE", 0)
    assert discord_anhaenge.automatisch(hive, kanal=KANAL, max_mb=100)[0].geholt == ["spaeter.pdf"]
    assert discord_anhaenge.automatisch(hive, kanal="", max_mb=100) == (None, ""), "nicht eingestellt"

    protokoll = (config.honig(hive) / "log.jsonl").read_text(encoding="utf-8")
    assert "discord_abruf" in protokoll and "rechnung.pdf" in protokoll
    for geheim in (TOKEN, VERFASSER, TEXT, "Gehaltsliste"):
        assert geheim not in protokoll


def test_wache_meldet_denselben_fehler_nur_einmal(discord, hive, monkeypatch):
    monkeypatch.setattr(discord_anhaenge, "PAUSE", 0)
    _bot_einrichten()
    discord.status[f"/channels/{KANAL}/messages"] = 403
    _, fehler = discord_anhaenge.automatisch(hive, kanal=KANAL, max_mb=100)
    assert "Nachrichtenverlauf" in fehler
    assert discord_anhaenge.automatisch(hive, kanal=KANAL, max_mb=100) == (None, "")


def test_wache_ohne_bot_tut_nichts(discord, hive):
    save_flugrouten(Flugrouten(discord=DiscordConfig(
        enabled=True, webhook_url="https://discord.com/api/webhooks/123456789012345678/abc")))
    assert discord_anhaenge.automatisch(hive, kanal=KANAL, max_mb=100) == (None, "")
    assert discord.anfragen == []


def test_ergebnis_wird_verstaendlich_gemeldet():
    gesagt = []

    class _Konsole:
        def __getattr__(self, art):
            return lambda text, *a: gesagt.append(text)

    discord_anhaenge.melden(_Konsole(), Abruf(nachrichten=3, geholt=["a.pdf"], bekannt=2,
                                              zu_gross=["film.mp4"], verloren=["weg.pdf"],
                                              mehr=True), max_mb=100)
    text = " ".join(gesagt)
    for teil in ("a.pdf", "schon einmal", "100 MB", "film.mp4", "weg.pdf", "nächsten Abruf"):
        assert teil in text
    gesagt.clear()
    discord_anhaenge.melden(_Konsole(), Abruf(), max_mb=100)
    assert gesagt == [i18n.t("pf.nothing")]


# --------------------------------------------------------------------------- #
#  Dienst
# --------------------------------------------------------------------------- #
def test_dienst_discord_einstellen_und_abholen(discord, hive):
    _bot_einrichten()
    d = Dienst(hive)
    with pytest.raises(Ungueltig):
        d.discord_abholen()                                     # noch kein Kanal eingestellt
    assert [k["name"] for k in d.discord_kanaele()["ergebnis"]["kanaele"]] == [
        "haus-unterlagen", "plaudern", "neuigkeiten"]

    stand = d.discord_einstellen(kanal=f"https://discord.com/channels/{SERVER}/{KANAL}")["ergebnis"]
    assert stand["kanal"] == KANAL and stand["bereit"] and stand["letzter_abruf"] == ""
    assert config.load_seed(hive).discord_kanal == KANAL
    antwort = d.discord_abholen()
    assert antwort["ergebnis"]["geholt"] == ["rechnung.pdf", "vertrag.pdf"]
    assert d.discord_stand()["geholt"] == 2 and d.discord_stand()["letzter_abruf"]
    alles = json.dumps([antwort, d.discord_stand(), d.discord_kanaele()], ensure_ascii=False)
    for geheim in (TOKEN, VERFASSER, TEXT):
        assert geheim not in alles

    with pytest.raises(Ungueltig):
        d.discord_einstellen(kanal="haus-unterlagen")
    assert config.load_seed(hive).discord_kanal == KANAL, "eine falsche Eingabe ändert nichts"
    assert d.discord_einstellen(kanal="")["ergebnis"]["kanal"] == ""


def test_dienst_ohne_bot_sagt_was_fehlt(discord, hive):
    d = Dienst(hive)
    assert d.discord_stand()["bereit"] is False
    d.discord_einstellen(kanal=KANAL)
    for aufruf in (d.discord_abholen, d.discord_kanaele):
        with pytest.raises(Ungueltig) as ei:
            aufruf()
        assert "flugrouten setup" in str(ei.value)


# --------------------------------------------------------------------------- #
#  Konsole
# --------------------------------------------------------------------------- #
def _konsole(monkeypatch, hive):
    sh = BeehiveShell.__new__(BeehiveShell)
    gesagt: list[str] = []
    sh.con = BeeConsole(quiet=True)
    for art in ("info", "honey", "ask", "error", "raw", "rule", "bloom"):
        monkeypatch.setattr(sh.con, art, lambda text="", *a, **kw: gesagt.append(str(text)))
    sh.hive = hive
    return sh, gesagt


def test_konsole_kanal_festlegen_abholen_und_abschalten(discord, hive, monkeypatch):
    _bot_einrichten()
    sh, gesagt = _konsole(monkeypatch, hive)
    sh.do_discord("")
    assert "kein Discord-Kanal" in " ".join(gesagt)
    sh.do_discord("liste")
    assert f"Haus-Server · #haus-unterlagen   {KANAL}" in " ".join(gesagt)

    sh.do_discord("kanal nicht-die-id")
    assert config.load_seed(hive).discord_kanal == ""
    sh.do_discord(f"kanal <#{KANAL}>")
    assert config.load_seed(hive).discord_kanal == KANAL
    gesagt.clear()
    sh.do_discord("abholen")
    assert "rechnung.pdf" in " ".join(gesagt) and _eingang(hive)["vertrag.pdf"] == PDF2
    gesagt.clear()
    sh.do_discord("")
    assert KANAL in " ".join(gesagt) and "bisher 2 Anhänge" in " ".join(gesagt)
    sh.do_discord("aus")
    assert config.load_seed(hive).discord_kanal == ""
    for geheim in (TOKEN, VERFASSER, TEXT):
        assert geheim not in " ".join(gesagt)


def test_konsole_ohne_bot_weist_auf_die_einrichtung_hin(discord, hive, monkeypatch):
    sh, gesagt = _konsole(monkeypatch, hive)
    sh._update_seed(discord_kanal=KANAL)
    for befehl in ("abholen", "liste", ""):
        gesagt.clear()
        sh.do_discord(befehl)
        assert "flugrouten setup" in " ".join(gesagt)
    assert discord.anfragen == []

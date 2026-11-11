"""Zugangsdaten im Tresor des Betriebssystems statt im Klartext.

Die Tests arbeiten mit einem Tresor, der nur im Arbeitsspeicher liegt (``tresor_im_speicher``
aus ``conftest.py``) — der echte Tresor des Rechners bleibt unberührt. Geprüft wird vor allem
das Versprechen des Moduls: **Ein Geheimnis geht nie verloren**, egal ob der Tresor fehlt,
ablehnt oder mitten im Betrieb ausfällt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pollysort import config, doctor, flugrouten, i18n, tresor
from pollysort.flugrouten import (
    DiscordConfig,
    EmailConfig,
    Flugrouten,
    discord_token,
    email_password,
    load_flugrouten,
    save_flugrouten,
)

TOKEN = "discord-token-geheim-1234"
PASSWORT = "mail-passwort-geheim-5678"
SCHLUESSEL = "sk-or-v1-geheim-9012"

#: Die echte Prüfung, festgehalten beim Import — in jedem Test ersetzt conftest sie durch „kein Tresor".
_ECHT_PRUEFEN = tresor._pruefen


@pytest.fixture
def ablage_ordner(tmp_path, monkeypatch):
    """Eine eigene Ablage mit ``credentials`` und ``flugrouten.toml`` im Wegwerf-Ordner."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(config, "POLLYSORT_HOME", home)
    monkeypatch.setattr(config, "CREDENTIALS_PATH", home / "credentials")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    for name in ("DISCORD_TOKEN", "EMAIL_PASSWORD"):
        monkeypatch.delenv("POLLYSORT_" + name, raising=False)
        monkeypatch.delenv("BEEHIVE_" + name, raising=False)
    return home


def _routen() -> Flugrouten:
    return Flugrouten(
        discord=DiscordConfig(enabled=True, bot_token=TOKEN, channel_id="42"),
        email=EmailConfig(enabled=True, provider="custom", address="ich@example.org",
                          password=PASSWORT, smtp_host="smtp.example.org", smtp_port=465),
    )


def _datei(home: Path) -> str:
    return (home / "flugrouten.toml").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
#  Flugrouten
# --------------------------------------------------------------------------- #
def test_speichern_legt_geheimnisse_in_den_tresor(ablage_ordner, tresor_im_speicher):
    save_flugrouten(_routen())
    text = _datei(ablage_ordner)
    assert TOKEN not in text and PASSWORT not in text, "kein Geheimnis mehr in der Datei"
    assert text.count(f'= "{tresor.IM_TRESOR}"') == 2
    assert "ich@example.org" in text, "alles andere steht weiter lesbar da"
    assert set(tresor_im_speicher.inhalt.values()) == {TOKEN, PASSWORT}

    fr = load_flugrouten()
    assert (fr.discord.bot_token, fr.email.password) == (TOKEN, PASSWORT)
    assert flugrouten.ablage() == {"discord": "tresor", "webhook": "", "email": "tresor"}


def test_ohne_tresor_bleibt_es_bei_der_datei(ablage_ordner):
    save_flugrouten(_routen())
    assert TOKEN in _datei(ablage_ordner) and PASSWORT in _datei(ablage_ordner)
    fr = load_flugrouten()
    assert (fr.discord.bot_token, fr.email.password) == (TOKEN, PASSWORT)
    assert flugrouten.ablage() == {"discord": "datei", "webhook": "", "email": "datei"}


def test_alte_klartext_datei_zieht_beim_laden_um(ablage_ordner, tresor_im_speicher, monkeypatch):
    monkeypatch.setattr(tresor, "_pruefen", lambda: (None, "kein_speicher"))
    save_flugrouten(_routen())                       # so sah die Datei vor dem Tresor aus
    assert TOKEN in _datei(ablage_ordner)
    monkeypatch.setattr(tresor, "_pruefen", lambda: (tresor_im_speicher, ""))

    fr = load_flugrouten()
    assert (fr.discord.bot_token, fr.email.password) == (TOKEN, PASSWORT), "Werte bleiben nutzbar"
    assert TOKEN not in _datei(ablage_ordner) and PASSWORT not in _datei(ablage_ordner)
    assert set(tresor_im_speicher.inhalt.values()) == {TOKEN, PASSWORT}
    assert discord_token(load_flugrouten()) == TOKEN, "auch beim nächsten Laden"


def test_lehnt_der_tresor_ab_bleibt_der_klartext(ablage_ordner, tresor_im_speicher):
    """Zu lange Werte nimmt z. B. Windows nicht an — dann darf nichts verloren gehen."""
    tresor_im_speicher.max_zeichen = 5
    save_flugrouten(_routen())
    assert TOKEN in _datei(ablage_ordner) and PASSWORT in _datei(ablage_ordner)
    assert not tresor_im_speicher.inhalt
    assert discord_token(load_flugrouten()) == TOKEN
    assert flugrouten.ablage()["discord"] == "datei"
    assert "nicht angenommen" in tresor.lage_text("datei", "x")


def test_umzug_wird_je_lauf_nur_einmal_versucht(ablage_ordner, tresor_im_speicher, monkeypatch):
    tresor_im_speicher.max_zeichen = 5
    monkeypatch.setattr(tresor, "_pruefen", lambda: (None, "kein_speicher"))
    save_flugrouten(_routen())
    monkeypatch.setattr(tresor, "_pruefen", lambda: (tresor_im_speicher, ""))
    versuche = []
    echt = flugrouten.save_flugrouten
    monkeypatch.setattr(flugrouten, "save_flugrouten",
                        lambda fr, path=None: (versuche.append(1), echt(fr, path))[1])
    for _ in range(3):
        assert discord_token(load_flugrouten()) == TOKEN
    assert len(versuche) == 1, "die Wache lädt alle paar Sekunden — kein Schreiben im Takt"


def test_ausgefallener_tresor_loescht_nichts(ablage_ordner, tresor_im_speicher):
    """Fällt der Tresor beim Lesen aus, darf ein späteres Speichern den Eintrag nicht zerstören."""
    save_flugrouten(_routen())
    vorher = dict(tresor_im_speicher.inhalt)

    tresor_im_speicher.kaputt = True
    fr = load_flugrouten()
    assert discord_token(fr) == "" and email_password(fr) == "", "nichts Lesbares — kein Versand"
    assert flugrouten.ablage()["discord"] == "unlesbar"
    fr.discord.channel_id = "43"                    # jemand ändert etwas anderes und speichert
    save_flugrouten(fr)
    assert _datei(ablage_ordner).count(f'= "{tresor.IM_TRESOR}"') == 2, "Platzhalter bleiben stehen"

    tresor_im_speicher.kaputt = False               # „nächster Programmstart"
    tresor._gestoert = False
    assert tresor_im_speicher.inhalt == vorher
    fr = load_flugrouten()
    assert discord_token(fr) == TOKEN and fr.discord.channel_id == "43"


def test_flugrouten_aus_raeumt_den_tresor(ablage_ordner, tresor_im_speicher):
    save_flugrouten(_routen())
    save_flugrouten(Flugrouten())                   # das macht 'flugrouten aus'
    assert not tresor_im_speicher.inhalt
    assert flugrouten.ablage() == {"discord": "", "webhook": "", "email": ""}


def test_umgebungsvariable_schlaegt_den_tresor(ablage_ordner, tresor_im_speicher, monkeypatch):
    save_flugrouten(_routen())
    monkeypatch.setenv("POLLYSORT_DISCORD_TOKEN", "aus-der-umgebung")
    assert discord_token(load_flugrouten()) == "aus-der-umgebung"


# --------------------------------------------------------------------------- #
#  OpenRouter-Schlüssel
# --------------------------------------------------------------------------- #
def test_schluessel_liegt_im_tresor(ablage_ordner, tresor_im_speicher):
    config.save_credentials(SCHLUESSEL)
    assert config.CREDENTIALS_PATH.read_text(encoding="utf-8") == tresor.IM_TRESOR
    assert config.load_credentials() == SCHLUESSEL
    assert config.credentials_ort() == "tresor"


def test_alter_klartext_schluessel_zieht_um(ablage_ordner, tresor_im_speicher):
    config.CREDENTIALS_PATH.write_text(SCHLUESSEL + "\n", encoding="utf-8")
    assert config.load_credentials() == SCHLUESSEL, "schon der erste Aufruf liefert den Schlüssel"
    assert config.CREDENTIALS_PATH.read_text(encoding="utf-8") == tresor.IM_TRESOR
    assert config.load_credentials() == SCHLUESSEL


def test_anzeige_zieht_erst_um_und_meldet_dann(ablage_ordner, tresor_im_speicher, monkeypatch):
    """Doctor und Werkstatt fragen nur nach dem Ort — auch das muss den Umzug auslösen, sonst
    steht dort „Klartext", obwohl ein Tresor da ist."""
    monkeypatch.setattr(tresor, "_pruefen", lambda: (None, "kein_speicher"))
    config.save_credentials(SCHLUESSEL)
    save_flugrouten(_routen())
    monkeypatch.setattr(tresor, "_pruefen", lambda: (tresor_im_speicher, ""))
    assert config.credentials_ort() == "tresor"
    assert flugrouten.ablage() == {"discord": "tresor", "webhook": "", "email": "tresor"}


def test_schluessel_ohne_tresor_wie_bisher(ablage_ordner):
    config.save_credentials(SCHLUESSEL)
    assert config.CREDENTIALS_PATH.read_text(encoding="utf-8") == SCHLUESSEL
    assert config.load_credentials() == SCHLUESSEL
    assert config.credentials_ort() == "datei"


def test_schluessel_entfernen_raeumt_beides(ablage_ordner, tresor_im_speicher):
    config.save_credentials(SCHLUESSEL)
    config.delete_credentials()
    assert not config.CREDENTIALS_PATH.exists() and not tresor_im_speicher.inhalt
    assert config.load_credentials() is None and config.credentials_ort() == ""
    config.delete_credentials()                     # zweimal ist kein Fehler


def test_umgebungsvariable_wird_nie_gespeichert(ablage_ordner, tresor_im_speicher, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "nur-umgebung")
    assert config.load_credentials() == "nur-umgebung"
    assert not tresor_im_speicher.inhalt and not config.CREDENTIALS_PATH.exists()


# --------------------------------------------------------------------------- #
#  Das Modul selbst
# --------------------------------------------------------------------------- #
def test_jede_ablage_hat_ihre_eigenen_eintraege(tmp_path, monkeypatch):
    """Eine Test- oder Zweit-Ablage darf die Einträge der üblichen Ablage nicht anfassen."""
    monkeypatch.setattr(config, "POLLYSORT_HOME", Path.home() / ".pollysort")
    assert tresor.dienst() == "PollySort"
    monkeypatch.setattr(config, "POLLYSORT_HOME", tmp_path / "andere")
    assert tresor.dienst() != "PollySort" and "andere" in tresor.dienst()


def test_abschalten_per_umgebungsvariable(monkeypatch):
    monkeypatch.setenv(tresor.AUS_VARIABLE, "aus")  # zuerst — danach erst das echte _pruefen
    monkeypatch.setattr(tresor, "_pruefen", _ECHT_PRUEFEN)
    assert tresor._pruefen() == (None, "aus")
    assert not tresor.schreiben("x", "y") and tresor.lesen("x") is None


def test_schreiben_zaehlt_nur_wenn_es_wieder_herauskommt(tresor_im_speicher, monkeypatch):
    monkeypatch.setattr(tresor_im_speicher, "get_password", lambda dienst, name: None)
    assert tresor.schreiben("x", "wert") is False


@pytest.mark.parametrize("lage", ["tresor", "datei", "unlesbar"])
@pytest.mark.parametrize("sprache", ["de", "en"])
def test_lage_text_in_beiden_sprachen(lage, sprache, monkeypatch):
    monkeypatch.setattr(i18n, "_LANG", sprache)
    text = tresor.lage_text(lage, "C:/x/datei")
    assert text and "{" not in text
    assert tresor.lage_text("", "x") == ""


@pytest.mark.parametrize("grund", ["aus", "fehlt", "kein_speicher", "gestoert", "abgelehnt"])
def test_jeder_grund_hat_einen_text(grund):
    assert i18n.t("tresor.grund." + grund) != "tresor.grund." + grund


# --------------------------------------------------------------------------- #
#  Sichtbarkeit: Doctor
# --------------------------------------------------------------------------- #
def _zugangsdaten_check():
    return {c[0]: c for c in doctor.run_checks(None)}.get(i18n.t("doctor.tresor"))


def test_doctor_schweigt_ohne_zugangsdaten(ablage_ordner):
    assert _zugangsdaten_check() is None


def test_doctor_warnt_bei_klartext(ablage_ordner):
    config.save_credentials(SCHLUESSEL)
    _, status, text = _zugangsdaten_check()
    assert status == "warn" and "credentials" in text and SCHLUESSEL not in text


def test_doctor_ist_zufrieden_mit_tresor(ablage_ordner, tresor_im_speicher):
    config.save_credentials(SCHLUESSEL)
    save_flugrouten(_routen())
    _, status, text = _zugangsdaten_check()
    assert status == "ok" and tresor.ort() in text

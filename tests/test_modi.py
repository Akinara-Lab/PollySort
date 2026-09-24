"""Die drei Modi mit neuen Namen (2026-09-24): Sparmodus · Lokal · Cloud.

Intern bleiben die Werte ``offline`` / ``ollama`` / ``openrouter`` — sie stehen so in jeder
``hive.toml``. Diese Tests halten fest, dass die neuen Namen überall ankommen UND die alten
weiter funktionieren.
"""

from __future__ import annotations

import pytest

import pollysort.i18n as i18n
from pollysort import config, firstrun
from pollysort.config import HiveSeed
from pollysort.console import BeeConsole


@pytest.mark.parametrize("lang, erwartet", [
    ("de", ("Sparmodus", "Lokal", "Cloud")),
    ("en", ("Low-power", "Local", "Cloud")),
])
def test_sichtbare_namen(lang, erwartet):
    i18n.set_language(lang)
    try:
        assert tuple(i18n.modus_name(p) for p in ("offline", "ollama", "openrouter")) == erwartet
        assert i18n.modus_name("unbekannt") == "unbekannt"
    finally:
        i18n.set_language("de")


@pytest.mark.parametrize("wort, provider", [
    ("spar", "offline"), ("Sparmodus", "offline"), ("low", "offline"), ("heuristik", "offline"),
    ("lokal", "ollama"), ("local", "ollama"),
    ("cloud", "openrouter"), ("api", "openrouter"),
    # die alten Namen bleiben gültig
    ("offline", "offline"), ("ollama", "ollama"), ("online", "openrouter"),
    ("openrouter", "openrouter"),
])
def test_woerter_waehlen_den_internen_wert(wort, provider):
    assert config.provider_aus_wort(wort) == provider


def test_unbekanntes_wort():
    assert config.provider_aus_wort("turbo") is None
    assert config.provider_aus_wort("") is None


@pytest.mark.parametrize("antwort, provider", [
    ("spar", "offline"), ("lokal", "ollama"), ("local", "ollama"), ("1", "offline"),
])
def test_erststart_versteht_die_neuen_namen(antwort, provider):
    got, _ = firstrun.step_ai(BeeConsole(quiet=True), lambda _p: antwort,
                              ollama_probe=lambda: True, has_key=lambda: False,
                              save_key=lambda _k: True)
    assert got == provider


def test_erststart_cloud_ohne_key_faellt_in_den_sparmodus():
    antworten = iter(["cloud", ""])          # Cloud gewählt, Key-Frage übersprungen
    got, gespeichert = firstrun.step_ai(BeeConsole(quiet=True), lambda _p: next(antworten),
                                        ollama_probe=lambda: False, has_key=lambda: False,
                                        save_key=lambda _k: True)
    assert (got, gespeichert) == ("offline", False)


def test_modus_befehl_mit_neuem_namen(tmp_path, monkeypatch):
    from pollysort.repl import BeehiveShell
    hive = tmp_path / "hive"
    hive.mkdir()
    config.write_seed(hive, HiveSeed(provider="offline"))
    sh = BeehiveShell.__new__(BeehiveShell)
    sh.con = BeeConsole(quiet=True)
    sh.hive = hive
    monkeypatch.setattr(sh, "_ollama_ready", lambda refresh=False: True, raising=False)
    sh.do_modus("lokal")
    assert config.load_seed(hive).provider == "ollama"
    sh.do_mode("spar")
    assert config.load_seed(hive).provider == "offline"


def test_hilfe_nennt_die_neuen_namen():
    from pollysort.repl import BeehiveShell
    zeilen = [z for gruppe in BeehiveShell._HELP.values() for z in gruppe if z[2] == "help.d.mode"]
    assert zeilen == [("modus <spar|lokal|cloud>", "mode <low|local|cloud>", "help.d.mode")]

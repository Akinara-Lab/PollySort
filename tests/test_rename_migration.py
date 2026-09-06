"""Paket-Rename `bumble` → `pollysort` und die Übernahme der alten globalen Ablage.

Der Rename ist eine Einbahnstraße: Bestandsnutzer haben ihre Projekte, ihren OpenRouter-Key
und ihre Flugrouten in ``~/.beehive``. Geht dabei etwas verloren, merkt der Nutzer es erst,
wenn er das Tool schon benutzt. Diese Tests halten die Übernahme fest — vor allem, dass sie
**kopiert und nichts löscht**.
"""

from __future__ import annotations

import importlib

import pytest


def _fresh_config(monkeypatch, home):
    """`config` mit einem gefälschten Home-Verzeichnis neu importieren.

    Die Ablage wird beim Import aufgelöst (Modulkonstante), deshalb muss das Modul für
    jeden Fall frisch geladen werden.
    """
    monkeypatch.delenv("POLLYSORT_HOME", raising=False)
    monkeypatch.delenv("BEEHIVE_HOME", raising=False)
    monkeypatch.setattr("pathlib.Path.home", staticmethod(lambda: home))
    import pollysort.config as cfgmod
    return importlib.reload(cfgmod)


def test_new_installation_uses_pollysort_home(monkeypatch, tmp_path):
    cfg = _fresh_config(monkeypatch, tmp_path)
    assert cfg.POLLYSORT_HOME == tmp_path / ".pollysort"
    assert not (tmp_path / ".beehive").exists()


def test_legacy_home_is_copied_not_moved(monkeypatch, tmp_path):
    """Die alte Ablage wird übernommen — und bleibt liegen."""
    old = tmp_path / ".beehive"
    (old / "sub").mkdir(parents=True)
    (old / "config.toml").write_text('hive = "C:/projekt"\n', encoding="utf-8")
    (old / "credentials").write_text("sk-or-geheim", encoding="utf-8")
    (old / "projects.txt").write_text("C:/projekt\n", encoding="utf-8")
    (old / "sub" / "tief.txt").write_text("verschachtelt", encoding="utf-8")

    cfg = _fresh_config(monkeypatch, tmp_path)
    new = tmp_path / ".pollysort"

    assert cfg.POLLYSORT_HOME == new
    # Alles ist angekommen, auch verschachtelt.
    assert (new / "config.toml").read_text(encoding="utf-8") == 'hive = "C:/projekt"\n'
    assert (new / "credentials").read_text(encoding="utf-8") == "sk-or-geheim"
    assert (new / "projects.txt").exists()
    assert (new / "sub" / "tief.txt").read_text(encoding="utf-8") == "verschachtelt"
    # 🛡️ Und die alte Ablage ist UNBERÜHRT — es wird nie gelöscht oder verschoben.
    assert (old / "config.toml").exists()
    assert (old / "credentials").exists()
    # Eine Notiz erklärt dem Nutzer, was passiert ist.
    assert "beehive" in (new / "UEBERNOMMEN.txt").read_text(encoding="utf-8")


def test_existing_new_home_is_never_overwritten(monkeypatch, tmp_path):
    """Wer schon eine neue Ablage hat, darf sie nicht von einer alten überschrieben bekommen."""
    old = tmp_path / ".beehive"
    old.mkdir()
    (old / "config.toml").write_text("alt", encoding="utf-8")
    new = tmp_path / ".pollysort"
    new.mkdir()
    (new / "config.toml").write_text("neu", encoding="utf-8")

    _fresh_config(monkeypatch, tmp_path)
    assert (new / "config.toml").read_text(encoding="utf-8") == "neu"


@pytest.mark.parametrize("var", ["POLLYSORT_HOME", "BEEHIVE_HOME"])
def test_env_override_wins_and_old_name_still_works(monkeypatch, tmp_path, var):
    """`BEEHIVE_HOME` bleibt als Altname gültig — sonst brechen bestehende Skripte."""
    target = tmp_path / "woanders"
    monkeypatch.delenv("POLLYSORT_HOME", raising=False)
    monkeypatch.delenv("BEEHIVE_HOME", raising=False)
    monkeypatch.setenv(var, str(target))
    monkeypatch.setattr("pathlib.Path.home", staticmethod(lambda: tmp_path))
    import pollysort.config as cfgmod
    cfg = importlib.reload(cfgmod)
    assert cfg.POLLYSORT_HOME == target
    assert cfg.CONFIG_PATH == target / "config.toml"


def test_legacy_alias_still_points_at_the_same_place(monkeypatch, tmp_path):
    cfg = _fresh_config(monkeypatch, tmp_path)
    assert cfg.BEEHIVE_HOME == cfg.POLLYSORT_HOME


# --------------------------------------------------------------------------- #
#  Der Rename selbst
# --------------------------------------------------------------------------- #
def test_package_is_importable_under_the_new_name():
    import pollysort
    from pollysort import cli, config, firstrun, repl  # noqa: F401
    assert pollysort.__version__


def test_old_package_name_is_gone():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("bumble")


def test_entry_points_are_renamed():
    """`pollysort` und `pollysort-cli` müssen in den Paket-Metadaten stehen."""
    from importlib.metadata import entry_points
    names = {ep.name for ep in entry_points(group="console_scripts")}
    assert {"pollysort", "pollysort-cli"} <= names, f"gefunden: {sorted(names)}"

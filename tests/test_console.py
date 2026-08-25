"""Konsole: ganzflächiger Dark/Light-Hintergrund (OSC) + statische Ansicht (kein Scrolling)."""

from __future__ import annotations

import datetime
import io

from rich.console import Console

from bumble.config import AppConfig
from bumble.console import PALETTES, BeeConsole, _osc, auto_theme, resolve_theme


def test_palettes_full_background_flip_text_stays_yellow():
    assert set(PALETTES) == {"dark", "light"}
    # Der GANZE Hintergrund kippt schwarz ↔ weiß …
    assert PALETTES["dark"]["term_bg"] == "#000000"
    assert PALETTES["light"]["term_bg"] == "#ffffff"
    # … der Text bleibt in beiden Modi gelb.
    assert PALETTES["dark"]["term_fg"] == PALETTES["light"]["term_fg"]
    assert PALETTES["dark"]["honey"] == PALETTES["light"]["honey"]


def test_theme_switch():
    c = BeeConsole(quiet=True)
    assert c.theme_name == "dark"                 # Default
    assert c.set_theme("light") == "light"
    assert c.theme_name == "light"
    assert c.set_theme("quatsch") == "light"      # ungültig → bleibt beim aktuellen
    assert BeeConsole(theme="light").theme_name == "light"
    assert BeeConsole(theme="unsinn").theme_name == "dark"   # Fallback


def test_osc_colors_paint_whole_terminal():
    assert _osc(11, "#000000") == "\033]11;#000000\a"
    c = BeeConsole(theme="dark")
    buf = io.StringIO()
    c._c = Console(file=buf, force_terminal=True)      # als Terminal behandeln
    c.apply_terminal_colors()
    out = buf.getvalue()
    assert "\033]11;#000000\a" in out                  # Hintergrund schwarz
    assert "\033]10;#ffd700\a" in out                  # Vordergrund gelb
    c.reset_terminal_colors()
    assert "\033]110\a" in buf.getvalue() and "\033]111\a" in buf.getvalue()   # zurückgesetzt


def test_light_mode_paints_white():
    c = BeeConsole(theme="light")
    buf = io.StringIO()
    c._c = Console(file=buf, force_terminal=True)
    c.apply_terminal_colors()
    assert "\033]11;#ffffff\a" in buf.getvalue()       # Hintergrund weiß


def test_clear_and_osc_are_noop_when_not_terminal(capsys):
    # Pipe/CI (kein Terminal): keine Escape-Sequenzen, kein Clear.
    c = BeeConsole(theme="dark")
    c.clear()
    c.apply_terminal_colors()
    assert capsys.readouterr().out == ""


def test_clear_and_header_are_noop_when_quiet(capsys):
    c = BeeConsole(quiet=True)
    c.clear()
    c.header("egal")
    assert capsys.readouterr().out == ""


def test_header_renders_title_and_status(capsys):
    BeeConsole(theme="light").header("Modus offline · 0 lose")
    out = capsys.readouterr().out
    assert "PollySort" in out
    assert "Modus offline" in out


def _at(hour: int) -> datetime.datetime:
    return datetime.datetime(2026, 7, 14, hour, 0)


def test_auto_theme_day_dark_evening_light():
    assert auto_theme(_at(7)) == "dark"      # Tagesbeginn
    assert auto_theme(_at(12)) == "dark"     # Mittag
    assert auto_theme(_at(18)) == "dark"     # Nachmittag
    assert auto_theme(_at(19)) == "light"    # Abend beginnt
    assert auto_theme(_at(23)) == "light"    # Nacht
    assert auto_theme(_at(3)) == "light"     # tiefe Nacht
    assert auto_theme(_at(6)) == "light"     # vor Tagesbeginn


def test_resolve_theme():
    assert resolve_theme("dark") == "dark"
    assert resolve_theme("light") == "light"
    assert resolve_theme("quatsch") == "dark"                 # Fallback
    assert resolve_theme("auto", _at(12)) == "dark"           # tagsüber
    assert resolve_theme("auto", _at(21)) == "light"          # abends


def test_config_view_defaults():
    a = AppConfig()
    assert a.theme == "dark"
    assert a.static_view is True

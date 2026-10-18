"""``pollysort-cli --version`` — so prüft der Release-Workflow das installierte Wheel.

Am 2026-10-18 scheiterte der erste Release-Lauf (v0.4.0b2) auf allen drei Systemen: ``--version``
war eine gewöhnliche Option, und ohne Unterbefehl brach Typer mit „Missing command“ ab, bevor
die Option ausgewertet wurde.
"""

from __future__ import annotations

from typer.testing import CliRunner

from pollysort import __version__
from pollysort.cli import app


def test_version_ohne_befehl():
    r = CliRunner().invoke(app, ["--version"])
    assert r.exit_code == 0, r.output
    assert r.output.strip() == f"pollysort {__version__}"


def test_ohne_alles_bleibt_die_hilfe():
    r = CliRunner().invoke(app, [])
    assert "Usage" in r.output and "--version" in r.output

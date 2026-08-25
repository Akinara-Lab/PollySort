"""Akzeptanz: Schwarm-Architektur v0.3 — Wabenbau/Charter, Kalender, Sammelbienen, Nektar."""

from __future__ import annotations

from pathlib import Path

from bumble.config import NEKTAR_SORTEN, AppConfig, HiveSeed
from bumble.console import BeeConsole
from bumble.journal import Journal
from bumble.llm.client import OfflineClient
from bumble.pipeline import Context, run_cycle
from bumble.swarm import Baubiene, Kalender, Koenigin, Sammelbiene


def _ctx(hive: Path) -> Context:
    seed = HiveSeed(categories=["rechnungen", "vertraege"],
                    responsibility={"rechnungen": [], "vertraege": []})
    hive.mkdir(parents=True, exist_ok=True)
    return Context.build(
        hive=hive, cfg=AppConfig(llm_provider="offline"), seed=seed,
        client=OfflineClient(seed.categories), console=BeeConsole(quiet=True),
        journal=Journal(hive),
    )


def _fill(prompt: str) -> str:
    p = prompt.lower()
    if "zuständig" in p:
        return "max, lena"
    if "ziel" in p:
        return "Rechnungen fristgerecht bezahlen"
    if "deadline" in p:
        return "2099-01-01"
    return ""


# ---- Stufe 2: Wabenbau erzeugt eine vollständige Charter ------------------
def test_wabenbau_builds_charter(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    (hive / "rechnung_1.txt").write_text("Rechnung ACME Betrag 100 EUR zahlbar", encoding="utf-8")
    run_cycle(ctx, mode="move")

    bau = Baubiene(ctx)
    ch = bau.wabenbau("rechnungen", ask=_fill)

    assert ch.stakeholder == ["max", "lena"]
    assert ch.ziel and ch.deadline == "2099-01-01"
    # Stakeholder wurden in die lebende Zuständigkeits-Tabelle gelernt.
    assert ctx.taxonomy.persons_for("rechnungen") == ["max", "lena"]
    # Bienenstock.md liegt sichtbar in der Wabe und nennt die Stakeholder.
    charter_md = hive / "Rechnungen" / "Bienenstock.md"
    assert charter_md.exists()
    text = charter_md.read_text(encoding="utf-8")
    assert "max, lena" in text and "Rechnungen fristgerecht bezahlen" in text
    # Charter-Daten persistiert; Deadline im Kalender.
    assert (hive / ".honig" / "projekte" / "rechnungen.toml").exists()
    assert any(t.faellig == "2099-01-01" for t in Kalender(hive).offen())


def test_wabenbau_reports_open_tasks_when_gaps(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    (hive / "rechnung_1.txt").write_text("Rechnung ACME Betrag 100 EUR zahlbar", encoding="utf-8")
    run_cycle(ctx, mode="move")

    bau = Baubiene(ctx)
    ch = bau.wabenbau("rechnungen")            # ohne Rückfragen → Lücken bleiben offen
    tasks = bau.offene_aufgaben("rechnungen", ch)
    assert "ziel" in ch.luecken()
    assert any("Projektziel" in t for t in tasks)


# ---- Kalender (gemockt) ---------------------------------------------------
def test_kalender_due(tmp_path):
    kal = Kalender(tmp_path / "hive")
    kal.eintragen("Deadline X", "2099-01-01", projekt="p")
    kal.eintragen("Deadline bald", "2000-01-01")          # überfällig
    assert len(kal.offen()) == 2
    due = kal.faellig(innerhalb_tage=7)
    assert any(t.titel == "Deadline bald" for t in due)   # überfällig ist fällig
    assert all(not t.titel == "Deadline X" for t in due)  # ferner Termin nicht


# ---- Sammelbienen: Ablage-Gewohnheiten aus dem Bestand --------------------
def test_sammelbiene_learns_placement(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    (hive / "rechnung_1.txt").write_text("Rechnung ACME Betrag 100 EUR zahlbar", encoding="utf-8")
    run_cycle(ctx, mode="move")

    sammel = Sammelbiene(hive, ctx.store)
    gewohnheiten = sammel.beobachten()
    assert gewohnheiten.get("rechnungen") == "Rechnungen"
    assert sammel.bevorzugter_ort("rechnungen") == "Rechnungen"


# ---- Königin & Schwarm-Status --------------------------------------------
def test_koenigin_schwarm_status(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    (hive / "rechnung_1.txt").write_text("Rechnung ACME Betrag 100 EUR zahlbar", encoding="utf-8")
    run_cycle(ctx, mode="move")
    st = Koenigin(ctx).schwarm_status()
    assert st["dokumente"] >= 1
    assert st["waben"] == 2
    assert "gewohnheiten" in st and "deadlines_faellig" in st


# ---- Nektar-Wechsel (Modell-Kurznamen) -----------------------------------
def test_nektar_sorten_mapping():
    assert NEKTAR_SORTEN["flash"] == "google/gemini-3.5-flash"
    assert NEKTAR_SORTEN["flash-lite"].startswith("google/")
    # Kurzname wird aufgelöst, beliebige ID bleibt unverändert.
    assert NEKTAR_SORTEN.get("flash", "flash") == "google/gemini-3.5-flash"
    assert NEKTAR_SORTEN.get("anthropic/foo", "anthropic/foo") == "anthropic/foo"

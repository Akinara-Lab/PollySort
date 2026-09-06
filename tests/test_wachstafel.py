"""Meta-Learning: „Die lernende Wachstafel" (ACE + RISE, §v0.3).

Sichert zu:
- Reflexion leitet aus Korrekturen Regeln ab und schreibt sie in .honig/wachstafel.md.
- Die Wachstafel wird bei der Klassifizierung berücksichtigt (offline & im Online-Prompt).
- 🔒 Projekt-Isolation: Regeln aus Projekt A wirken NIE in Projekt B.
- 🔒 Kein Code-Harnessing: es entsteht nur die .md-Datei, niemals .py-Code.
"""

from __future__ import annotations

import json
from pathlib import Path

from pollysort.config import AppConfig, HiveSeed, honig
from pollysort.console import BeeConsole
from pollysort.feedback import Feedback
from pollysort.journal import Journal
from pollysort.llm.client import OfflineClient, OpenRouterClient
from pollysort.pipeline import Context, run_cycle
from pollysort.wachstafel import Wachstafel, derive_rules, parse_rules

CATS = ["rechnungen", "internet_2026"]


def _correction(hive: Path, title: str, alt: str, neu: str) -> None:
    Feedback(hive).record(bee_id="x", title=title, funktion="", kategorie_alt=alt,
                          kategorie_neu=neu, quelle="assign")


def _ctx(hive: Path, wachstafel: str = "") -> Context:
    seed = HiveSeed(categories=CATS)
    hive.mkdir(parents=True, exist_ok=True)
    return Context.build(
        hive=hive, cfg=AppConfig(llm_provider="offline"), seed=seed,
        client=OfflineClient(seed.categories, wachstafel=wachstafel),
        console=BeeConsole(quiet=True), journal=Journal(hive))


# ---- RISE: Regeln aus Korrekturen ----------------------------------------
def test_reflektiere_derives_and_writes_rule(tmp_path):
    hive = tmp_path / "hive"
    hive.mkdir()
    _correction(hive, "Rechnung Telekom Festnetz", "rechnungen", "internet_2026")
    wt = Wachstafel(hive)
    rules = wt.reflektiere(Feedback(hive), categories=CATS)

    assert wt.exists()
    assert wt.path.name == "wachstafel.md"
    assert ("telekom", "internet_2026") in wt.regeln()
    assert any(kw == "telekom" and kat == "internet_2026" for kw, kat, *_ in rules)


def test_derive_rules_skips_ambiguous():
    corrections = [
        {"title": "Alpha Telekom", "kategorie_alt": "rechnungen", "kategorie_neu": "internet_2026"},
        {"title": "Beta Telekom", "kategorie_alt": "rechnungen", "kategorie_neu": "rechnungen"},
    ]
    # 'telekom' zeigt 1x auf internet_2026, 1x auf rechnungen → mehrdeutig → keine Regel.
    toks = {kw for kw, *_ in derive_rules(corrections, CATS)}
    assert "telekom" not in toks


# ---- Anwendung offline: Regel schlägt Heuristik --------------------------
def test_offline_client_honors_wachstafel():
    text = "- **telekom** → Wabe **internet_2026**\n"
    off = OfflineClient(CATS, wachstafel=text)
    a = off.analyze(text="Rechnung Telekom Festnetz", file_path="telekom_vertrag.pdf")
    assert a.kategorie == "internet_2026"
    # Ohne Wachstafel würde dieselbe Datei in 'rechnungen' landen (Heuristik).
    a2 = OfflineClient(CATS).analyze(text="Rechnung Telekom Festnetz", file_path="telekom.pdf")
    assert a2.kategorie == "rechnungen"


# ---- Anwendung online: Injektion in den LLM-Prompt -----------------------
def test_wachstafel_injected_into_llm_prompt():
    text = "- **telekom** → Wabe **internet_2026**\n"
    client = OpenRouterClient(api_key="sk-x", model="m", embed_model="e",
                              categories=CATS, wachstafel=text)
    parts = client._build_content(text="Rechnung Telekom", file_path=None)
    blob = json.dumps(parts, ensure_ascii=False)
    assert "Gelernte Projekt-Regeln" in blob
    assert "internet_2026" in blob
    # Ohne Wachstafel kein solcher Block.
    plain = OpenRouterClient(api_key="sk-x", model="m", embed_model="e", categories=CATS)
    assert "Gelernte Projekt-Regeln" not in json.dumps(
        plain._build_content(text="x", file_path=None), ensure_ascii=False)


# ---- 🔒 Projekt-Isolation -------------------------------------------------
def test_project_isolation(tmp_path):
    hive_a = tmp_path / "projekt_a"
    hive_b = tmp_path / "projekt_b"
    hive_a.mkdir()
    hive_b.mkdir()
    _correction(hive_a, "Rechnung Telekom", "rechnungen", "internet_2026")
    Wachstafel(hive_a).reflektiere(Feedback(hive_a), categories=CATS)

    # Getrennte Dateien, jede im eigenen .honig/.
    assert Wachstafel(hive_a).path == honig(hive_a) / "wachstafel.md"
    assert Wachstafel(hive_b).path == honig(hive_b) / "wachstafel.md"
    assert Wachstafel(hive_a).path != Wachstafel(hive_b).path
    assert not Wachstafel(hive_b).exists()

    # A kennt die Regel, B NICHT — dieselbe Datei landet unterschiedlich.
    a = OfflineClient(CATS, wachstafel=Wachstafel(hive_a).text())
    b = OfflineClient(CATS, wachstafel=Wachstafel(hive_b).text())
    assert a.analyze(text="Rechnung Telekom", file_path="t.pdf").kategorie == "internet_2026"
    assert b.analyze(text="Rechnung Telekom", file_path="t.pdf").kategorie == "rechnungen"


# ---- 🔒 Kein Code-Harnessing ---------------------------------------------
def test_reflection_writes_only_markdown_no_code(tmp_path):
    hive = tmp_path / "hive"
    hive.mkdir()
    _correction(hive, "Rechnung Telekom", "rechnungen", "internet_2026")
    Wachstafel(hive).reflektiere(Feedback(hive), categories=CATS)
    # Es entsteht ausschließlich die Wachstafel-Markdown — niemals .py-Code.
    assert (honig(hive) / "wachstafel.md").exists()
    assert list(hive.rglob("*.py")) == []


# ---- Integration: der Sortier-Zyklus nutzt die Wachstafel ----------------
def test_full_cycle_places_by_wachstafel(tmp_path):
    hive = tmp_path / "hive"
    hive.mkdir()
    _correction(hive, "Rechnung Telekom Festnetz", "rechnungen", "internet_2026")
    Wachstafel(hive).reflektiere(Feedback(hive), categories=CATS)

    (hive / "telekom_januar.txt").write_text("Rechnung Telekom Festnetz Januar", encoding="utf-8")
    ctx = _ctx(hive, wachstafel=Wachstafel(hive).text())
    run_cycle(ctx, mode="move")
    # Dank Wachstafel landet die Telekom-Datei in Internet_2026, nicht in Rechnungen.
    assert list((hive / "Internet_2026").glob("telekom_januar.txt"))


def test_leeren_removes_rules(tmp_path):
    hive = tmp_path / "hive"
    hive.mkdir()
    _correction(hive, "Rechnung Telekom", "rechnungen", "internet_2026")
    wt = Wachstafel(hive)
    wt.reflektiere(Feedback(hive), categories=CATS)
    assert wt.exists()
    assert wt.leeren() is True
    assert not wt.exists()
    assert wt.regeln() == []
    assert parse_rules(wt.text()) == []

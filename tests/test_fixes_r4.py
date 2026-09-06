"""Regressionstests für QA-Runde 4 (report.txt, 2026-07-14).

Deckt ab:
- BUG-5:  error-Einträge werden beim nächsten Lauf erneut versucht (kein Dauer-Skip).
- BUG-6:  KI-Totalausfall im Vorschlags-Modus wird gezählt/gemeldet (kein „Sonstiges"-Betrug).
- BUG-7:  Wachstafel lernt keine Stoppwort-/Kategorienwort-Regeln; harte Kappung pro Korrektur.
- BUG-8:  Korrektur-Moves landen im Move-Log (rueckflug trifft den richtigen Move).
- BUG-10: zurueckholen legt die Datei in ihre Wabe zurück (Status assigned), nicht in den Root.
- OPT-5:  Font-/Lizenzblöcke werden vor der Analyse gefiltert.
- OPT-8:  Kaputtes LLM-JSON → ein Versuch mit dem Fallback-Modell.
- OPT-9:  Leere bestehende Ordner zählen als vorhandene Waben.
"""

from __future__ import annotations

from pathlib import Path

from pollysort.config import AppConfig, HiveSeed
from pollysort.console import BeeConsole
from pollysort.guards import IgnoreMatcher
from pollysort.journal import Journal
from pollysort.llm.client import LLMError, OfflineClient, OpenRouterClient, Usage
from pollysort.models import Status
from pollysort.movelog import MoveLog
from pollysort.pipeline import Context, run_cycle
from pollysort.scout import scout, walk


class FailingClient:
    """Simuliert einen toten Provider (Ollama down, Netzfehler)."""

    def __init__(self) -> None:
        self.usage = Usage()

    def analyze(self, *, text=None, file_path=None):
        raise LLMError("Ollama nicht erreichbar: Verbindung verweigert")

    def embed(self, text):
        raise LLMError("Ollama nicht erreichbar: Verbindung verweigert")


def _ctx(hive: Path, client=None, seed: HiveSeed | None = None) -> Context:
    seed = seed or HiveSeed()
    hive.mkdir(parents=True, exist_ok=True)
    return Context.build(
        hive=hive, cfg=AppConfig(llm_provider="offline"), seed=seed,
        client=client or OfflineClient(seed.categories), console=BeeConsole(quiet=True),
        journal=Journal(hive),
    )


def _write_rechnung(hive: Path, name: str = "rechnung_1.txt") -> Path:
    f = hive / name
    f.write_text("Rechnung ACME Betrag 100 EUR UST zahlbar", encoding="utf-8")
    return f


# ---- BUG-5: error-Einträge blockieren die Datei nicht dauerhaft -----------
def test_error_entries_are_retried(tmp_path):
    hive = tmp_path / "hive"
    ctx_broken = _ctx(hive, client=FailingClient())
    f = _write_rechnung(hive)

    s1 = run_cycle(ctx_broken, mode="move")
    assert s1.errors == 1
    row = ctx_broken.store.query()[0]
    assert row["status"] == Status.ERROR.value
    assert f.exists()                                   # Datei blieb liegen

    # Provider „repariert" (Offline-Heuristik) → derselbe Lauf versucht es ERNEUT,
    # statt den error-Eintrag per Hash-Dedupe still zu überspringen.
    ctx_ok = _ctx(hive)
    s2 = run_cycle(ctx_ok, mode="move")
    assert s2.moved == 1 and s2.errors == 0
    row = ctx_ok.store.query()[0]
    assert row["status"] == Status.ASSIGNED.value
    assert (hive / "Rechnungen" / "rechnung_1.txt").exists()


# ---- BUG-6: KI-Ausfall im Vorschlags-Modus wird gezählt -------------------
def test_ai_probe_counts_failures(tmp_path):
    from pollysort.onboarding import propose_structure
    from pollysort.repl import _AiProbe

    hive = tmp_path / "hive"
    hive.mkdir()
    _write_rechnung(hive)
    probe = _AiProbe(FailingClient())

    proposals, _total, used_ai, _existing, _prot = propose_structure(hive, ai_analyze=probe)
    assert probe.errors == 1 and probe.ok == 0          # Ausfall wurde GEZÄHLT
    assert used_ai is False                             # nicht als „KI-Analyse" verkauft
    assert proposals                                    # Heuristik liefert trotzdem etwas


# ---- BUG-7: Wachstafel lernt keine Müll-Regeln ----------------------------
def test_derive_rules_filters_junk():
    from pollysort.wachstafel import _MAX_TOKENS_PER_CORRECTION, derive_rules

    corrections = [{
        "title": "Fira Mono Font Lizenz",
        "funktion": ("Dieses Dokument dient als technische Referenz und Ressourcenpaket "
                     "für die Integration und Darstellung der Schriftart Fira Mono."),
        "kategorie_alt": "technische dokumentation",
        "kategorie_neu": "technologiebericht",
    }]
    cats = ["technische dokumentation", "technologiebericht", "rechnung"]
    rules = derive_rules(corrections, cats)
    keywords = {kw for kw, _kat, _n, _alt in rules}

    assert len(rules) <= _MAX_TOKENS_PER_CORRECTION     # harte Kappung pro Korrektur
    # Funktionswörter und Kategorien-Einzelwörter dürfen NIE Regeln werden:
    assert not keywords & {"dieses", "dient", "technische", "dokumentation",
                           "darstellung", "integration", "referenz"}


# ---- BUG-8: Korrektur-Moves landen im Move-Log ----------------------------
def test_correction_moves_are_logged(tmp_path):
    from pollysort.review import apply_correction

    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    _write_rechnung(hive)
    run_cycle(ctx, mode="move")
    bee_id = ctx.store.query()[0]["id"]

    apply_correction(ctx, bee_id, "vertraege", mode="move")

    rec = MoveLog(hive).last_for(bee_id, action="korrektur")
    assert rec is not None
    assert Path(rec["dst"]).parent.name == "Vertraege"
    # rueckflug (pop_last) trifft jetzt GENAU diese Korrektur, nicht einen alten Move:
    assert MoveLog(hive).pop_last()["action"] == "korrektur"


# ---- BUG-10: zurueckholen legt die Datei in ihre Wabe zurück --------------
def test_resurrect_returns_to_category_folder(tmp_path):
    from pollysort.undertaker import resurrect, undertake

    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    _write_rechnung(hive)
    run_cycle(ctx, mode="move")
    bee_id = ctx.store.query()[0]["id"]

    dest = undertake(hive, ctx.store, bee_id)
    assert dest is not None and dest.parent.name == "papierkorb"

    back = resurrect(hive, ctx.store, bee_id)
    assert back is not None
    assert back.parent.name == "Rechnungen"             # zurück in die Wabe, nicht Root
    row = ctx.store.by_id(bee_id)
    assert row["status"] == Status.ASSIGNED.value       # keine erneute Rückfrage nötig


# ---- OPT-5: Font-/Lizenzblöcke werden gefiltert ---------------------------
def test_font_license_blocks_are_stripped():
    from pollysort.extractor import _strip_font_blocks

    text = ("Projektplan KI-Luftbildanalyse\n\n"
            "Meilensteine und Arbeitspakete für die Segmentierung.\n\n"
            "Fira Mono ist unter der SIL Open Font License verfügbar. "
            "Reserved Font Name Fira Mono.")
    cleaned = _strip_font_blocks(text)
    assert "SIL Open Font License" not in cleaned
    assert "Projektplan" in cleaned and "Meilensteine" in cleaned

    # Besteht der Text NUR aus Lizenzblöcken, bleibt er unangetastet (lieber Müll als nichts).
    only_license = "SIL Open Font License\n\nReserved Font Name Fira Mono."
    assert _strip_font_blocks(only_license) == only_license


# ---- OPT-8: Fallback-Modell bei kaputtem LLM-JSON -------------------------
def test_fallback_model_on_truncated_json(monkeypatch):
    client = OpenRouterClient("key", "primary-model", "embed-model", ["rechnungen"],
                              fallback_model="backup-model")
    used_models: list[str] = []

    def fake_post(path, payload):
        used_models.append(payload["model"])
        if payload["model"] == "primary-model":
            content = '{"title": "abgeschn'           # abgeschnittenes JSON (real beobachtet)
        else:
            content = ('{"title": "Gut", "summary": "s", "keywords": [], '
                       '"funktion_aufgabe": "f", "kategorie": "rechnungen"}')
        return {"choices": [{"message": {"content": content}}], "usage": {}}

    monkeypatch.setattr(client, "_post", fake_post)
    analysis = client.analyze(text="hallo welt")
    assert used_models == ["primary-model", "backup-model"]
    assert analysis.title == "Gut"


# ---- OPT-9: leere bestehende Ordner zählen als Waben ----------------------
def test_existing_structure_includes_empty_folders(tmp_path):
    from pollysort.onboarding import existing_structure

    hive = tmp_path / "hive"
    (hive / "Forschungsbericht").mkdir(parents=True)    # leer, aber bewusst angelegt
    (hive / "Rechnung").mkdir()
    (hive / "Rechnung" / "alt.txt").write_text("x", encoding="utf-8")

    found = existing_structure(hive)
    assert found.get("forschungsbericht") == 0
    assert found.get("rechnung") == 1


# ---- Sicherheitsnetz: Scout liefert Findings, die die Probe versteht ------
def test_probe_success_path(tmp_path):
    from pollysort.repl import _AiProbe

    hive = tmp_path / "hive"
    hive.mkdir()
    _write_rechnung(hive)
    probe = _AiProbe(OfflineClient(["rechnungen"]))
    finding = scout(walk([hive], IgnoreMatcher(hive), recursive=False))[0]
    kategorie, _kws = probe(finding)
    assert probe.ok == 1 and probe.errors == 0
    assert kategorie == "rechnungen"

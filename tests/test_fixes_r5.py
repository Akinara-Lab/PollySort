"""Regressionstests für die PollySort-Roadmap-Arbeit (Phasen 1–6).

- Phase 5 Live-Preview & Apply: der Vorschau→Anwenden-Flow nutzt einen Analyse-Cache,
  sodass „Anwenden" KEINE zweiten KI-Anfragen kostet.
"""

from __future__ import annotations

from pathlib import Path

from bumble import config
from bumble.config import AppConfig, HiveSeed
from bumble.console import BeeConsole
from bumble.journal import Journal
from bumble.llm.client import OfflineClient
from bumble.pipeline import Context, run_cycle


def _ctx(hive: Path, seed: HiveSeed | None = None) -> Context:
    seed = seed or HiveSeed()
    hive.mkdir(parents=True, exist_ok=True)
    return Context.build(
        hive=hive, cfg=AppConfig(llm_provider="offline"), seed=seed,
        client=OfflineClient(seed.categories), console=BeeConsole(quiet=True),
        journal=Journal(hive),
    )


# ---- Phase 5: Vorschau-Cache spart die zweiten KI-Calls beim Anwenden -----
def test_preview_cache_avoids_second_llm_calls(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    (hive / "rechnung_1.txt").write_text("Rechnung ACME Betrag 100 EUR UST", encoding="utf-8")

    cache: dict = {}
    s1 = run_cycle(ctx, mode="move", dry_run=True, cache=cache)
    calls_after_preview = ctx.client.usage.calls
    assert s1.stored >= 1                    # Vorschau würde einsortieren
    assert cache                             # Cache wurde befüllt
    assert ctx.store.query() == []           # Dry-run bleibt nebenwirkungsfrei
    assert (hive / "rechnung_1.txt").exists()

    # Anwenden mit demselben Cache: verschiebt & speichert, aber OHNE neue KI-Anfrage.
    s2 = run_cycle(ctx, mode="move", dry_run=False, cache=cache)
    assert ctx.client.usage.calls == calls_after_preview     # kein zweiter Call
    assert s2.moved >= 1
    assert list((hive / "Rechnungen").glob("rechnung_1.txt"))
    assert len(ctx.store.query()) == 1


def test_apply_without_cache_still_works(tmp_path):
    """Ohne Cache verhält sich der Lauf wie bisher (Regressionsschutz)."""
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    (hive / "rechnung_2.txt").write_text("Rechnung Betrag 50 EUR", encoding="utf-8")
    s = run_cycle(ctx, mode="move", dry_run=False)
    assert s.moved >= 1
    assert list((hive / "Rechnungen").glob("rechnung_2.txt"))


# ---- Phase 4: Mid-Run-Fallback auf Offline-Heuristik ----------------------
def test_midrun_fallback_to_offline(tmp_path):
    """Reißt die KI mitten im Lauf wiederholt ab, sortiert der REST heuristisch weiter."""
    from bumble.llm.client import LLMError, OfflineClient, Usage

    class FlakyClient:
        def __init__(self):
            self.usage = Usage()

        def analyze(self, *, text=None, file_path=None):
            raise LLMError("Provider nicht erreichbar")

        def embed(self, text):
            raise LLMError("Provider nicht erreichbar")

    hive = tmp_path / "hive"
    # Provider != offline, sonst greift der Fallback bewusst nicht.
    seed = HiveSeed()
    hive.mkdir(parents=True, exist_ok=True)
    ctx = Context.build(
        hive=hive, cfg=AppConfig(llm_provider="openrouter"), seed=seed,
        client=FlakyClient(), console=BeeConsole(quiet=True), journal=Journal(hive),
    )
    for i in range(5):
        (hive / f"rechnung_{i}.txt").write_text(f"Rechnung Betrag {i}0 EUR UST", encoding="utf-8")

    s = run_cycle(ctx, mode="move")
    # Erste 3 scheitern (Schwelle), danach Umschaltung → die restlichen 2 werden sortiert.
    assert s.errors == 3
    assert s.moved == 2
    assert isinstance(ctx.client, OfflineClient)     # dauerhaft für den Rest des Laufs
    assert len(list((hive / "Rechnungen").glob("*.txt"))) == 2


# ---- neu auf bereits konfiguriertem Ordner: .honig sichern statt löschen ----
def test_reset_honig_backs_up_without_deleting(tmp_path):
    """`neu` → 'Katalog frisch starten' sichert das alte .honig (löscht nichts)."""
    from bumble.repl import BeehiveShell

    sh = BeehiveShell.__new__(BeehiveShell)     # ohne __init__ (keine globale Config-Kopplung)
    sh.con = BeeConsole(quiet=True)
    proj = tmp_path / "kopie"
    (proj / ".honig").mkdir(parents=True)
    (proj / ".honig" / "hive.toml").write_text("name='x'", encoding="utf-8")
    (proj / ".honig" / "katalog.db").write_text("daten", encoding="utf-8")
    assert config.is_setup(proj)

    sh._reset_honig(proj)

    assert not config.is_setup(proj)            # frisch: kein aktives .honig mehr
    backups = list(proj.glob(".honig.bak-*"))
    assert backups, "altes .honig muss gesichert sein"
    assert (backups[0] / "hive.toml").exists()  # nichts gelöscht
    assert (backups[0] / "katalog.db").exists()


# ---- Abbruch-Wort verlässt eine interaktive Aktion (Kollegin-Wunsch) --------
def test_ask_aborts_on_abort_word(monkeypatch):
    import builtins

    import pytest

    from bumble.repl import AbortAction, BeehiveShell

    sh = BeehiveShell.__new__(BeehiveShell)
    sh.con = BeeConsole(quiet=True)

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "abbruch")
    with pytest.raises(AbortAction):
        sh._ask("Projektname? ")
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "bye")
    with pytest.raises(AbortAction):
        sh._ja("Wirklich? [j/N]: ")
    # Normale Eingabe geht unverändert durch.
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "MeinProjekt")
    assert sh._ask("Projektname? ") == "MeinProjekt"

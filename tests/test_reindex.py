"""F1 — Embedding-Modellwechsel: Erkennung (kostenlos) + Reindex (`gedaechtnis neu`).

Das Embedding-Modell ist nur über die Config-Datei änderbar; es gibt also keinen
interaktiven Wechsel-Moment. Der Fix erkennt den Wechsel stattdessen aus dem Bestand
(gespeichertes Modell != aktuelles, oder gemischte Vektor-Dimensionen) und bietet einen
Reindex mit dem aktuellen Modell an.
"""

from __future__ import annotations

from pathlib import Path

from bumble.config import AppConfig, HiveSeed
from bumble.console import BeeConsole
from bumble.hive_mind.memory import HiveMind
from bumble.journal import Journal
from bumble.llm.client import OfflineClient, embed_model_for
from bumble.pipeline import Context, reindex_memory, run_cycle


def _ctx(hive: Path) -> Context:
    seed = HiveSeed()
    hive.mkdir(parents=True, exist_ok=True)
    return Context.build(
        hive=hive, cfg=AppConfig(llm_provider="offline"), seed=seed,
        client=OfflineClient(seed.categories), console=BeeConsole(quiet=True),
        journal=Journal(hive),
    )


# ---- HiveMind: Modell merken + Wechsel erkennen ---------------------------
def test_remember_records_model_and_detects_name_change(tmp_path):
    mind = HiveMind(tmp_path / "hive")
    assert mind.mismatch("modell-a") is None          # leeres Gedächtnis → keine Warnung
    mind.remember("a1", "rechnung", [0.1, 0.2, 0.3], model="modell-a")
    assert mind.model() == "modell-a"
    assert mind.mismatch("modell-a") is None          # gleiches Modell → alles gut
    assert mind.mismatch("modell-b") == "modell-a"    # Wechsel erkannt (Name)


def test_detects_mixed_dimensions_even_without_model_change(tmp_path):
    mind = HiveMind(tmp_path / "hive")
    mind.remember("a1", "rechnung", [0.1, 0.2, 0.3, 0.4], model="modell-a")
    mind.remember("a2", "vertrag", [0.1, 0.2, 0.3], model="modell-a")   # andere Dimension!
    # Modellname stimmt, aber die gemischten Dimensionen verraten den früheren Wechsel.
    assert mind.mismatch("modell-a") == "gemischte Dimensionen"


def test_reset_clears_vectors(tmp_path):
    mind = HiveMind(tmp_path / "hive")
    mind.remember("a1", "rechnung", [0.1, 0.2], model="m")
    assert mind.count() == 1
    mind.reset()
    assert mind.count() == 0


# ---- Reindex baut das Gedächtnis mit dem aktuellen Modell neu -------------
def test_reindex_rebuilds_with_current_model(tmp_path):
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    (hive / "rechnung_x.txt").write_text("Rechnung ACME Betrag 100 EUR UST", encoding="utf-8")
    run_cycle(ctx, mode="move", dry_run=False)

    assigned = ctx.store.query(status="assigned")
    assert assigned, "Vorbedingung: mindestens ein einsortierter Eintrag"
    eid = assigned[0]["id"]

    # Modellwechsel simulieren: den Vektor durch einen fremd-dimensionalen ersetzen und ein
    # anderes Embedding-Modell eintragen (so, wie es ein Config-Edit hinterlassen würde).
    ctx.mind.remember(eid, assigned[0]["kategorie"], [0.0] * 5, model="perplexity/pplx-embed-v1-4b")
    assert ctx.mind.mismatch("offline:hash-2048") == "perplexity/pplx-embed-v1-4b"

    ok, fail = reindex_memory(ctx)
    assert ok == len(assigned) and fail == 0
    # Nach dem Reindex: aktuelles Modell, einheitliche (Offline-)Dimension 2048, kein Mismatch.
    assert ctx.mind.model() == "offline:hash-2048"
    assert ctx.mind.mismatch("offline:hash-2048") is None
    dim = len(ctx.client.embed("probe"))
    assert dim == 2048
    stored = ctx.mind.neighbors(ctx.client.embed("Rechnung ACME"), k=1)
    assert stored and stored[0].score > 0.0           # matcht wieder (nicht mehr totes Gewicht)


def test_reindex_is_robust_to_embed_errors(tmp_path):
    """Ein KI-Schluckauf bei einzelnen Einträgen bricht den Reindex nicht ab (§16)."""
    hive = tmp_path / "hive"
    ctx = _ctx(hive)
    (hive / "rechnung_y.txt").write_text("Rechnung Betrag 50 EUR", encoding="utf-8")
    run_cycle(ctx, mode="move", dry_run=False)
    assert ctx.store.query(status="assigned")

    class BoomClient(OfflineClient):
        def embed(self, text: str):
            raise RuntimeError("embedding backend down")

    ctx.client = BoomClient(ctx.seed.categories)
    ok, fail = reindex_memory(ctx)
    assert ok == 0 and fail >= 1          # sauber gezählt, kein Absturz


# ---- Helfer: effektives Embedding-Modell je Provider ----------------------
def test_embed_model_for_matches_client_choice():
    assert embed_model_for(AppConfig(llm_provider="offline"), None) == "offline:hash-2048"
    assert embed_model_for(AppConfig(llm_provider="openrouter"), None) == "offline:hash-2048"
    assert embed_model_for(AppConfig(llm_provider="ollama"), None) == "nomic-embed-text-v2-moe"
    got = embed_model_for(AppConfig(llm_provider="openrouter"), "key123")
    assert got == AppConfig().embed_model      # perplexity/pplx-embed-v1-4b (Default)


def test_clients_expose_embed_model():
    assert OfflineClient([]).embed_model == "offline:hash-2048"

"""Doctor-Health-Check + Wächter über den Open-Core-Zustand.

Die zweite Testgruppe hier ist Absicht: PollySort war vor dem Open-Core-Schritt
Fair-Code mit einem Lizenz-Gate (Ultra Swarm, 5-Projekte-Grenze). Unter Apache-2.0 darf
davon nichts zurückkommen — weder versehentlich noch durch einen Merge.
"""

from __future__ import annotations

from pathlib import Path

import pollysort.i18n as i18n
from pollysort import doctor
from pollysort.config import AppConfig
from pollysort.llm import client as client_mod

SRC = Path(__file__).resolve().parent.parent / "src" / "pollysort"


def test_doctor_runs_without_network(monkeypatch):
    # Provider auf offline zwingen → keine echten Netz-Calls im Test.
    monkeypatch.setattr(doctor.config, "load_config", lambda: AppConfig(llm_provider="offline"))
    checks = doctor.run_checks(None)
    assert isinstance(checks, list) and checks
    labels = {c[0] for c in checks}
    assert {"Python", "Modus"} <= labels
    assert "Lizenz" not in labels, "Der Kern ist Apache-2.0 — es gibt keinen Lizenzstatus mehr"
    assert "Modelle" not in labels, "Der Modell-Check gilt nur für Ollama"
    # Jeder Check hat einen gültigen Status.
    assert all(status in ("ok", "warn", "fail") for _, status, _ in checks)


def test_doctor_survives_a_broken_check(monkeypatch):
    """Ein kaputter Einzel-Check darf den Doctor nie stürzen lassen."""
    def boom(*_a, **_k):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(doctor, "_extras_check", boom)
    monkeypatch.setattr(doctor.config, "load_config", lambda: AppConfig(llm_provider="offline"))
    checks = doctor.run_checks(None)
    assert checks, "Der Doctor muss trotzdem ein Ergebnis liefern"


def test_doctor_speaks_english(monkeypatch):
    monkeypatch.setattr(doctor.config, "load_config", lambda: AppConfig(llm_provider="offline"))
    i18n.set_language("en")
    try:
        checks = {c[0]: c for c in doctor.run_checks(None)}
    finally:
        i18n.set_language("de")
    assert {"Mode", "Database", "Memory"} <= set(checks)
    assert checks["Mode"][2] == "low-power (heuristics, free)"
    assert checks["Database"][2] == "no project active"


# --------------------------------------------------------------------------- #
#  Ollama: sind die Modelle wirklich gezogen?
# --------------------------------------------------------------------------- #
def _ollama(monkeypatch, models):
    monkeypatch.setattr(doctor.config, "load_config", lambda: AppConfig(llm_provider="ollama"))
    monkeypatch.setattr(client_mod, "ollama_available", lambda *_a, **_k: models is not None)
    monkeypatch.setattr(client_mod, "ollama_version",
                        lambda *_a, **_k: "0.34.2" if models is not None else None)
    monkeypatch.setattr(client_mod, "ollama_models", lambda *_a, **_k: models)
    monkeypatch.setattr(client_mod, "ollama_geladen", lambda *_a, **_k: None)
    return {c[0]: c for c in doctor.run_checks(None)}


def test_doctor_reports_missing_embedding_model(monkeypatch):
    """Fehlt das Embedding-Modell, lernt das Gedächtnis still nichts dazu — der Doctor
    muss das sagen, mit dem passenden pull-Befehl."""
    checks = _ollama(monkeypatch, ["qwen3.5:9b"])
    _, status, detail = checks["Modelle"]
    assert status == "warn"
    assert "ollama pull nomic-embed-text-v2-moe" in detail
    assert "Gedächtnis" in detail                    # sagt auch, WAS ohne das Modell fehlt


def test_doctor_fails_without_chat_model(monkeypatch):
    checks = _ollama(monkeypatch, ["nomic-embed-text-v2-moe:latest"])
    _, status, detail = checks["Modelle"]
    assert status == "fail"
    assert "ollama pull qwen3.5:9b" in detail


def test_doctor_models_ok_with_latest_tag(monkeypatch):
    checks = _ollama(monkeypatch, ["qwen3.5:9b", "nomic-embed-text-v2-moe:latest"])
    assert checks["Modelle"][1] == "ok"
    assert checks["Modus"][1] == "ok"


def test_doctor_skips_model_check_when_server_is_down(monkeypatch):
    """Server aus → das meldet der Provider-Check; ein zweiter Fehler wäre nur Lärm."""
    checks = _ollama(monkeypatch, None)
    assert "Modelle" not in checks
    assert checks["Modus"][1] == "warn"


def test_ollama_has_model_is_tag_tolerant():
    has = client_mod.ollama_has_model
    assert has("nomic-embed-text-v2-moe", ["nomic-embed-text-v2-moe:latest"])
    assert has("qwen3.5:9b", ["qwen3.5:9b"])
    assert not has("qwen3.5:9b", ["qwen3.5:4b"])
    assert has("qwen3.5", ["qwen3.5:4b"])           # ohne Tag gefragt → jeder Tag passt
    assert not has("qwen3.5:9b", [])


# --------------------------------------------------------------------------- #
#  Open Core — das Lizenz-Gate ist weg und bleibt weg
# --------------------------------------------------------------------------- #
def test_licensing_module_is_gone():
    assert not (SRC / "licensing.py").exists(), \
        "Der Apache-2.0-Kern trägt kein Lizenz-Modul mehr (es gehört ins Cockpit-Paket)"


def test_no_source_file_gates_a_feature():
    """Kein Modul darf noch auf das Gate verweisen — auch nicht als toter Import."""
    offenders = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in ("import pollysort.licensing", "from .licensing", "ultra_swarm_allowed",
                       "free_limit_reached"):
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
    assert not offenders, f"Lizenz-Gate wieder im Kern: {offenders}"


def test_ultra_swarm_is_free():
    """`sortiere turbo` darf nicht mehr auf 1 Biene zurückgestuft werden."""
    import inspect

    from pollysort.repl import BeehiveShell

    src = inspect.getsource(BeehiveShell.do_sortiere)
    assert "workers = 10" in src, "Turbo muss weiterhin parallelisieren"
    assert "licens" not in src.lower(), "Turbo darf an keiner Lizenz mehr hängen"


# --------------------------------------------------------------------------- #
#  GPU-Belegung (2026-09-24): Ein halb auf der CPU geladenes Modell soll auffallen
# --------------------------------------------------------------------------- #
def _lokal(monkeypatch, geladen):
    import pollysort.llm.client as cm
    monkeypatch.setattr(doctor.config, "load_config", lambda: AppConfig(llm_provider="ollama"))
    monkeypatch.setattr(cm, "ollama_geladen", lambda *_a, **_k: geladen)
    monkeypatch.setattr(cm, "ollama_version", lambda *_a, **_k: "0.34.2")
    monkeypatch.setattr(cm, "ollama_models", lambda *_a, **_k: None)
    return {c[0]: c for c in doctor.run_checks(None)}


def test_gpu_check_warnt_bei_teilweise_cpu(monkeypatch):
    checks = _lokal(monkeypatch, [{"name": "qwen3.5:9b", "size": 8_500, "size_vram": 4_930,
                                   "context_length": 65536}])
    assert checks["GPU"][1] == "warn"
    assert "42 %" in checks["GPU"][2] and "65536" in checks["GPU"][2]


def test_gpu_check_ganz_auf_der_grafikkarte(monkeypatch):
    checks = _lokal(monkeypatch, [{"name": "qwen3.5:9b", "size": 5_500, "size_vram": 5_500,
                                   "context_length": 4096}])
    assert checks["GPU"][1] == "ok" and "4096" in checks["GPU"][2]


def test_gpu_check_ohne_grafikkarte_ist_kein_fehler(monkeypatch):
    checks = _lokal(monkeypatch, [{"name": "qwen3.5:9b", "size": 6_100, "size_vram": 0}])
    assert checks["GPU"][1] == "ok"


def test_gpu_check_schweigt_ohne_server_und_in_anderen_modi(monkeypatch):
    assert "GPU" not in _lokal(monkeypatch, None)
    monkeypatch.setattr(doctor.config, "load_config", lambda: AppConfig(llm_provider="offline"))
    assert "GPU" not in {c[0] for c in doctor.run_checks(None)}

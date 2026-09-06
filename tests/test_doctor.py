"""Doctor-Health-Check + Wächter über den Open-Core-Zustand.

Die zweite Testgruppe hier ist Absicht: PollySort war vor dem Open-Core-Schritt
Fair-Code mit einem Lizenz-Gate (Ultra Swarm, 5-Projekte-Grenze). Unter Apache-2.0 darf
davon nichts zurückkommen — weder versehentlich noch durch einen Merge.
"""

from __future__ import annotations

from pathlib import Path

from pollysort import doctor
from pollysort.config import AppConfig

SRC = Path(__file__).resolve().parent.parent / "src" / "pollysort"


def test_doctor_runs_without_network(monkeypatch):
    # Provider auf offline zwingen → keine echten Netz-Calls im Test.
    monkeypatch.setattr(doctor.config, "load_config", lambda: AppConfig(llm_provider="offline"))
    checks = doctor.run_checks(None)
    assert isinstance(checks, list) and checks
    labels = {c[0] for c in checks}
    assert {"Python", "KI-Provider"} <= labels
    assert "Lizenz" not in labels, "Der Kern ist Apache-2.0 — es gibt keinen Lizenzstatus mehr"
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

"""Phase 6: Fair-Code-Lizenzierung + doctor Health-Check."""

from __future__ import annotations

import bumble.licensing as lic
from bumble import doctor
from bumble.config import AppConfig


def test_activate_and_tier(tmp_path, monkeypatch):
    monkeypatch.setattr(lic, "_LICENSE_PATH", tmp_path / "license.json")
    assert lic.tier() == "personal"
    assert not lic.is_licensed()
    assert not lic.ultra_swarm_allowed()

    ok, _msg = lic.activate("F123-ABCD-9999-XYZ0")
    assert ok
    assert lic.is_licensed()
    assert lic.tier() == "freelancer"
    assert lic.ultra_swarm_allowed()

    ok, _ = lic.activate("A123-ABCD-9999-XYZ0")     # 'A'-Präfix → Agency
    assert ok and lic.tier() == "agency"

    bad, msg = lic.activate("nope")                  # ungültiges Format → kein Überschreiben
    assert not bad and "format" in msg.lower()
    assert lic.tier() == "agency"

    assert lic.deactivate()
    assert not lic.is_licensed()
    assert lic.tier() == "personal"


def test_no_master_key_baked_into_code():
    # 🔒 Sicherheits-Garantie: im ausgelieferten Code darf KEIN Master-Schlüssel stehen
    # (ohne gesetzte POLLYSORT_MASTER_KEY-Env ist die Menge leer). Verhindert ein
    # unwiderrufliches Backdoor-Geheimnis im Repo/Wheel.
    import os
    if not os.environ.get("POLLYSORT_MASTER_KEY"):
        assert lic._MASTER_KEYS == set()


def test_master_key_unlocks_developer(tmp_path, monkeypatch):
    monkeypatch.setattr(lic, "_LICENSE_PATH", tmp_path / "license.json")
    # Master-Schlüssel wird ausschließlich über die Umgebung konfiguriert (nie im Code).
    monkeypatch.setattr(lic, "_MASTER_KEYS", {"TEST-MSTR-KEYX-0001"})
    ok, msg = lic.activate("TEST-MSTR-KEYX-0001")
    assert ok and "Master" in msg
    assert lic.tier() == "developer"
    assert lic.is_licensed()
    assert lic.ultra_swarm_allowed()
    # Case-insensitiv.
    lic.deactivate()
    ok2, _ = lic.activate("test-mstr-keyx-0001")
    assert ok2 and lic.tier() == "developer"


def test_dev_env_unlocks_without_file(tmp_path, monkeypatch):
    monkeypatch.setattr(lic, "_LICENSE_PATH", tmp_path / "none.json")   # keine Datei
    assert not lic.is_licensed()
    monkeypatch.setenv("BUMBLENARA_DEV_LICENSE", "1")
    assert lic.is_licensed() and lic.tier() == "developer"
    assert lic.ultra_swarm_allowed()
    monkeypatch.setenv("BUMBLENARA_DEV_LICENSE", "0")                   # 0 = aus
    assert not lic.is_licensed()


def test_free_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(lic, "_LICENSE_PATH", tmp_path / "lic.json")
    monkeypatch.setattr(lic, "project_count", lambda: 5)
    assert lic.free_limit_reached()
    monkeypatch.setattr(lic, "project_count", lambda: 3)
    assert not lic.free_limit_reached()
    # Mit gültiger Lizenz gilt kein Limit.
    lic.activate("F123-ABCD-9999-XYZ0")
    monkeypatch.setattr(lic, "project_count", lambda: 99)
    assert not lic.free_limit_reached()


def test_key_never_stored_plaintext(tmp_path, monkeypatch):
    path = tmp_path / "license.json"
    monkeypatch.setattr(lic, "_LICENSE_PATH", path)
    lic.activate("F123-ABCD-9999-XYZ0")
    blob = path.read_text(encoding="utf-8")
    assert "F123-ABCD-9999-XYZ0" not in blob      # nur maskiert gespeichert (Wachssiegel)
    assert "F123" in blob and "…" in blob


def test_doctor_runs_without_network(monkeypatch):
    # Provider auf offline zwingen → keine echten Netz-Calls im Test.
    monkeypatch.setattr(doctor.config, "load_config", lambda: AppConfig(llm_provider="offline"))
    checks = doctor.run_checks(None)
    assert isinstance(checks, list) and checks
    labels = {c[0] for c in checks}
    assert {"Python", "KI-Provider", "Lizenz"} <= labels
    # Jeder Check hat einen gültigen Status.
    assert all(status in ("ok", "warn", "fail") for _, status, _ in checks)

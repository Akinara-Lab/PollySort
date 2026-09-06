"""``doctor`` — Health-Check der PollySort-Umgebung.

Prüft Interpreter, KI-Provider-Erreichbarkeit, DB-Pfad und optionale Extras — ohne je
Secrets auszugeben. Gibt eine Liste von (label, status, detail) zurück; ``status`` ist
"ok" | "warn" | "fail". Die Ausgabe übernimmt der Aufrufer (REPL/CLI).
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import config


def _py_check() -> tuple[str, str, str]:
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 12)
    return ("Python", "ok" if ok else "fail",
            f"{v.major}.{v.minor}.{v.micro}" + ("" if ok else " (benötigt 3.12+)"))


def _provider_check(hive: Path | None) -> tuple[str, str, str]:
    cfg = config.load_config()
    provider = cfg.llm_provider
    if hive is not None:
        try:
            provider = config.load_seed(hive).provider
        except Exception:
            pass
    if provider == "offline":
        return ("KI-Provider", "ok", "offline (Heuristik, kostenlos)")
    if provider == "ollama":
        from .llm.client import ollama_available
        reachable = ollama_available(cfg.llm_endpoint or "http://localhost:11434")
        return ("KI-Provider", "ok" if reachable else "warn",
                "ollama erreichbar" if reachable else "ollama NICHT erreichbar (Server starten)")
    # openrouter
    key = config.load_credentials()
    if not key:
        return ("KI-Provider", "warn", "openrouter ohne Schlüssel → Offline-Fallback")
    from .llm.client import verify_openrouter_key
    ok, grund = verify_openrouter_key(key)
    return ("KI-Provider", "ok" if ok else "fail", f"openrouter: {grund}")


def _db_check(hive: Path | None) -> tuple[str, str, str]:
    if hive is None:
        return ("Datenbank", "warn", "kein Projekt aktiv")
    try:
        h = config.honig(hive)
        h.mkdir(parents=True, exist_ok=True)
        probe = h / ".doctor_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        db = h / "katalog.db"
        return ("Datenbank", "ok",
                f"{'vorhanden' if db.exists() else 'wird angelegt'} · {h}")
    except OSError as exc:
        return ("Datenbank", "fail", f"nicht schreibbar: {exc}")


def _extras_check() -> tuple[str, str, str]:
    have = []
    for mod, label in (("markitdown", "markitdown"), ("pypdf", "pypdf"), ("magic", "libmagic")):
        try:
            __import__(mod)
            have.append(label)
        except Exception:
            pass
    detail = ", ".join(have) if have else "keine (Kern-Fallback aktiv)"
    return ("Extraktion", "ok", detail)


def _memory_check(hive: Path | None) -> tuple[str, str, str]:
    """F1: Warnt, wenn das Embedding-Modell gewechselt hat (alte Vektoren = totes Gewicht).
    Rein lokal, kein Netz/KI-Call."""
    if hive is None:
        return ("Gedächtnis", "warn", "kein Projekt aktiv")
    from .hive_mind.memory import HiveMind
    from .llm.client import embed_model_for
    mind = HiveMind(hive)
    n = mind.count()
    if n == 0:
        return ("Gedächtnis", "ok", "leer")
    cfg = config.load_config()
    try:
        cfg.llm_provider = config.load_seed(hive).provider
    except Exception:
        pass
    api_key = config.load_credentials() if cfg.llm_provider == "openrouter" else None
    drift = mind.mismatch(embed_model_for(cfg, api_key))
    if drift:
        return ("Gedächtnis", "warn",
                f"{n} Vektoren · Modellwechsel ({drift}) → 'gedaechtnis neu'")
    return ("Gedächtnis", "ok", f"{n} Vektoren · {mind.model() or 'Modell n/a'}")


def run_checks(hive: Path | None) -> list[tuple[str, str, str]]:
    """Alle Health-Checks ausführen. Jeder Check ist isoliert (ein Fehler kippt nie alles)."""
    checks = (_py_check, _provider_check, _db_check, _extras_check, _memory_check)
    hive_checks = (_provider_check, _db_check, _memory_check)
    out: list[tuple[str, str, str]] = []
    for fn in checks:
        try:
            out.append(fn(hive) if fn in hive_checks else fn())
        except Exception as exc:   # ein kaputter Check darf den Doctor nicht stürzen
            out.append((fn.__name__, "warn", f"Check fehlgeschlagen: {exc}"))
    return out

"""``doctor`` — Health-Check der PollySort-Umgebung.

Prüft Interpreter, KI-Provider-Erreichbarkeit, lokale Modelle, DB-Pfad, optionale Extras
und das Gedächtnis — ohne je Secrets auszugeben. Gibt eine Liste von (label, status, detail)
zurück; ``status`` ist "ok" | "warn" | "fail". Die Texte kommen in der aktiven UI-Sprache;
die Ausgabe übernimmt der Aufrufer (REPL/CLI).
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import config, i18n

Check = tuple[str, str, str]


def _provider_for(hive: Path | None) -> tuple[str, config.AppConfig]:
    """Provider des aktiven Projekts (sonst der globale) — der ist für die Checks maßgeblich."""
    cfg = config.load_config()
    provider = cfg.llm_provider
    if hive is not None:
        try:
            provider = config.load_seed(hive).provider
        except Exception:
            pass
    return provider, cfg


def _py_check(_hive: Path | None) -> Check:
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 12)
    return (i18n.t("doctor.python"), "ok" if ok else "fail",
            f"{v.major}.{v.minor}.{v.micro}" + ("" if ok else i18n.t("doctor.py.need")))


def _provider_check(hive: Path | None) -> Check:
    label = i18n.t("doctor.provider")
    provider, cfg = _provider_for(hive)
    if provider == "offline":
        return (label, "ok", i18n.t("doctor.prov.offline"))
    if provider == "ollama":
        from .llm.client import OLLAMA_ENDPOINT, ollama_available
        reachable = ollama_available(cfg.llm_endpoint or OLLAMA_ENDPOINT)
        return (label, "ok" if reachable else "warn",
                i18n.t("doctor.prov.ollama_ok" if reachable else "doctor.prov.ollama_down"))
    # openrouter
    key = config.load_credentials()
    if not key:
        return (label, "warn", i18n.t("doctor.prov.or_nokey"))
    from .llm.client import verify_openrouter_key
    ok, grund = verify_openrouter_key(key)
    return (label, "ok" if ok else "fail", i18n.t("doctor.prov.cloud", reason=grund))


def _models_check(hive: Path | None) -> Check | None:
    """Nur im Ollama-Modus: Sind Analyse- UND Embedding-Modell wirklich gezogen?

    Fehlt das Embedding-Modell, sortiert PollySort zwar — aber das Gedächtnis lernt still
    nichts dazu, und jeder Lauf bleibt ein Kaltstart. Genau solche stillen Ausfälle
    gehören in den Health-Check. ``None`` = trifft nicht zu (anderer Provider, oder der
    Server ist nicht erreichbar — das meldet bereits der Provider-Check).
    """
    provider, cfg = _provider_for(hive)
    if provider != "ollama":
        return None
    from .llm.client import (
        OLLAMA_EMBED_MODEL,
        OLLAMA_ENDPOINT,
        OLLAMA_MODEL,
        ollama_has_model,
        ollama_models,
    )
    models = ollama_models(cfg.llm_endpoint or OLLAMA_ENDPOINT)
    if models is None:
        return None
    label = i18n.t("doctor.models")
    missing = [m for m in (OLLAMA_MODEL, OLLAMA_EMBED_MODEL) if not ollama_has_model(m, models)]
    if not missing:
        return (label, "ok", i18n.t("doctor.models.ok", chat=OLLAMA_MODEL, embed=OLLAMA_EMBED_MODEL))
    hint = " · ".join(f"ollama pull {m}" for m in missing)
    detail = i18n.t("doctor.models.missing", names=", ".join(missing), hint=hint)
    if OLLAMA_MODEL in missing:
        return (label, "fail", detail)          # ohne Analyse-Modell läuft gar nichts
    return (label, "warn", detail + i18n.t("doctor.models.embed_note"))


def _db_check(hive: Path | None) -> Check:
    label = i18n.t("doctor.db")
    if hive is None:
        return (label, "warn", i18n.t("doctor.noproject"))
    try:
        h = config.honig(hive)
        h.mkdir(parents=True, exist_ok=True)
        probe = h / ".doctor_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        db = h / "katalog.db"
        state = i18n.t("doctor.db.exists" if db.exists() else "doctor.db.new")
        return (label, "ok", f"{state} · {h}")
    except OSError as exc:
        return (label, "fail", i18n.t("doctor.db.fail", exc=exc))


def _extras_check(_hive: Path | None) -> Check:
    have = []
    for mod, label in (("markitdown", "markitdown"), ("pypdf", "pypdf"), ("magic", "libmagic")):
        try:
            __import__(mod)
            have.append(label)
        except Exception:
            pass
    detail = ", ".join(have) if have else i18n.t("doctor.extract.none")
    return (i18n.t("doctor.extract"), "ok", detail)


def _memory_check(hive: Path | None) -> Check:
    """F1: Warnt, wenn das Embedding-Modell gewechselt hat (alte Vektoren = totes Gewicht).
    Rein lokal, kein Netz/KI-Call."""
    label = i18n.t("doctor.memory")
    if hive is None:
        return (label, "warn", i18n.t("doctor.noproject"))
    from .hive_mind.memory import HiveMind
    from .llm.client import embed_model_for
    mind = HiveMind(hive)
    n = mind.count()
    if n == 0:
        return (label, "ok", i18n.t("doctor.mem.empty"))
    provider, cfg = _provider_for(hive)
    cfg.llm_provider = provider
    api_key = config.load_credentials() if provider == "openrouter" else None
    drift = mind.mismatch(embed_model_for(cfg, api_key))
    if drift:
        return (label, "warn", i18n.t("doctor.mem.drift", n=n, drift=drift))
    return (label, "ok", i18n.t("doctor.mem.ok", n=n, model=mind.model() or "n/a"))


def run_checks(hive: Path | None) -> list[Check]:
    """Alle Health-Checks ausführen. Jeder Check ist isoliert (ein Fehler kippt nie alles);
    ``None`` heißt „trifft auf diese Umgebung nicht zu" und wird ausgelassen."""
    checks = (_py_check, _provider_check, _models_check, _db_check, _extras_check, _memory_check)
    out: list[Check] = []
    for fn in checks:
        try:
            res = fn(hive)
        except Exception as exc:   # ein kaputter Check darf den Doctor nicht stürzen
            res = (fn.__name__, "warn", i18n.t("doctor.check_failed", exc=exc))
        if res is not None:
            out.append(res)
    return out

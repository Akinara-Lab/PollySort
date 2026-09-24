"""Der Daemon — ``pollysort buzz`` (§10.3). Vereint Flugloch-Autosort + Intervall-Sweep.

Beide Rhythmen sind unabhängig schaltbar; der laufende Daemon liest die Config je Runde
neu, sodass ``pollysort autosort on/off`` / ``pollysort sweep-timer on/off`` ohne Neustart wirken.
Ein echter ``watchdog``-Observer sorgt (wo verfügbar) für sofortige Reaktion; die
Poll-Schleife ist der robuste Fallback für Netz-Volumes (§10.1).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from . import config as cfgmod
from . import i18n
from .lock import QueenLock, QueenLockError
from .pipeline import Context, run_cycle
from .sweeper import sweep

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    _HAVE_WATCHDOG = True
except Exception:  # pragma: no cover
    _HAVE_WATCHDOG = False


class _FluglochHandler:  # pragma: no cover - nur mit watchdog aktiv
    def __init__(self, wake: threading.Event):
        self._wake = wake

    def on_any_event(self, _event):
        self._wake.set()


def _start_observer(flugloch: Path, wake: threading.Event):
    if not _HAVE_WATCHDOG:
        return None
    handler = FileSystemEventHandler()
    handler.on_any_event = lambda _e: wake.set()  # type: ignore[assignment]
    obs = Observer()
    obs.schedule(handler, str(flugloch), recursive=True)
    obs.start()
    return obs


def run_daemon(
    build_ctx,
    hive: Path,
    *,
    mode: str = "move",
    use_autosort: bool = True,
    use_sweep: bool = True,
    max_cycles: int | None = None,
) -> None:
    """Dauerbetrieb. ``build_ctx()`` liefert bei jeder Runde einen frischen Context.

    ``max_cycles`` begrenzt die Schleife (für Tests/Einmalläufe); ``None`` = endlos.
    """
    ctx0 = build_ctx()
    con = ctx0.console
    con.honey(i18n.t("dm.start"), "🟢")
    if _HAVE_WATCHDOG:
        con.info(i18n.t("dm.watchdog"), "🛡️")
    else:
        con.info(i18n.t("dm.poll"), "🛡️")

    wake = threading.Event()
    observer = _start_observer(hive, wake)
    cfg = cfgmod.load_config()
    next_sweep = time.monotonic() + cfg.sweep_interval_minutes * 60
    cycles = 0
    try:
        while max_cycles is None or cycles < max_cycles:
            cfg = cfgmod.load_config()  # Live-Umschaltung ohne Neustart (§10.3)

            if use_autosort and cfg.autosort:
                _guarded(ctx_run_flugloch, build_ctx, mode, con)

            if use_sweep and cfg.sweep_auto and time.monotonic() >= next_sweep:
                _guarded(lambda c: sweep(c, mode=mode), build_ctx, None, con, want_ctx=True)
                next_sweep = time.monotonic() + cfg.sweep_interval_minutes * 60
                con.info(i18n.t("dm.next", m=cfg.sweep_interval_minutes), "⏱️")

            cycles += 1
            wake.wait(timeout=cfg.flugloch_poll_seconds)
            wake.clear()
    except KeyboardInterrupt:  # pragma: no cover
        con.info(i18n.t("dm.stop"), "🐝")
    finally:
        if observer:  # pragma: no cover
            observer.stop()
            observer.join(timeout=2)


def ctx_run_flugloch(ctx: Context, mode: str) -> None:
    run_cycle(ctx, mode=mode)   # verarbeitet die losen Dateien im Arbeitsverzeichnis


def _guarded(fn, build_ctx, mode, con, want_ctx: bool = False) -> None:
    """Einen Schritt unter dem Schreib-Lock ausführen; Fehler nie fatal (§16)."""
    try:
        ctx = build_ctx()
        with QueenLock(ctx.hive):
            if want_ctx:
                fn(ctx)
            else:
                fn(ctx, mode)
    except QueenLockError:
        pass  # anderer Schreiber aktiv → nächste Runde
    except Exception as exc:  # Daemon läuft weiter (§16)
        con.error(i18n.t("dm.failed", err=exc))

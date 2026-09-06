#!/usr/bin/env python3
"""PollySort — Starter für die Konsole (Repo-/Entwickler-Workflow).

Für Endnutzer ist der empfohlene Weg die Installation und dann der Befehl ``pollysort``:

    pipx install .            # oder:  uv tool install .
    pollysort                    # startet die Konsole

Dieses Skript bleibt für den Start direkt aus dem geklonten Repo (``python polly.py``).
Es sorgt dafür, dass ein passender Interpreter läuft, und übergibt dann an ``pollysort.repl``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _bootstrap_interpreter() -> None:
    """Sicherstellen, dass ein passender Python-Interpreter mit den Abhängigkeiten läuft.

    Bumble braucht **Python 3.12+** (u. a. ``tomllib``). Wird das Skript mit einem alten
    oder nackten Python gestartet, wechselt es automatisch in die projekteigene ``.venv``
    (dort liegen der richtige Interpreter UND alle Abhängigkeiten). Existiert keine ``.venv``,
    gibt es eine klare Anleitung statt eines kryptischen Tracebacks.
    """
    venv_py = _HERE / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    already = os.environ.get("POLLYSORT_RELAUNCHED") == "1"
    in_venv = venv_py.exists() and Path(sys.executable).resolve() == venv_py.resolve()

    if not already and venv_py.exists() and not in_venv:
        os.environ["POLLYSORT_RELAUNCHED"] = "1"
        raise SystemExit(subprocess.call([str(venv_py), str(Path(__file__).resolve()),
                                          *sys.argv[1:]]))

    if sys.version_info < (3, 11):  # noqa: UP036 — läuft bewusst auf altem Python (vor Relaunch)
        print(
            "PollySort benötigt Python 3.12+ (gefunden: "
            f"{sys.version_info.major}.{sys.version_info.minor}).\n\n"
            "Empfohlen — einmalig installieren, dann überall 'pollysort' tippen:\n"
            "    pipx install .          # oder:  uv tool install .\n\n"
            "…oder direkt aus dem Repo:\n"
            "    py -3 -m venv .venv\n"
            "    .venv\\Scripts\\pip install -e .\n"
            "    python polly.py"
        )
        raise SystemExit(1)


_bootstrap_interpreter()

# Aus dem Repo (ohne Installation) das Paket unter src/ auffindbar machen.
sys.path.insert(0, str(_HERE / "src"))

try:
    from pollysort.repl import main
except ModuleNotFoundError as _exc:  # fehlende Abhängigkeit → klare Anleitung
    print(f"Fehlende Abhängigkeit: '{_exc.name}'. Bitte installieren:\n"
          '    pip install -e .   (oder: pipx install .)')
    raise SystemExit(1) from _exc


if __name__ == "__main__":
    raise SystemExit(main())

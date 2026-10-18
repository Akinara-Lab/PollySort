"""PollySort — konsolenbasierter, lernender Dokumenten-Archivar im Bienenstock-Stil."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

# Einzige Quelle der Wahrheit ist die Version aus pyproject.toml (Paket-Metadaten). So driftet
# der Banner nie von der ausgelieferten Version weg. Fallback nur, wenn aus einem NICHT
# installierten Quellbaum gestartet wird (z. B. `python polly.py` ohne `pip install`).
try:
    __version__ = _pkg_version("pollysort")
except PackageNotFoundError:      # nicht installiert → aus dem Quellbaum gestartet
    __version__ = "0.4.0b2"

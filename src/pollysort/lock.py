"""Schreib-Lock im Stock (.queen.lock) — weist einen zweiten Schreiber freundlich ab (§16)."""

from __future__ import annotations

import os
from pathlib import Path


class QueenLockError(RuntimeError):
    pass


class QueenLock:
    """Einfaches, plattformübergreifendes Lockfile via O_EXCL."""

    def __init__(self, hive: Path):
        from .config import honig
        honig(hive).mkdir(parents=True, exist_ok=True)
        self.path = honig(hive) / ".lock"
        self._fd: int | None = None

    def __enter__(self) -> QueenLock:
        try:
            self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(self._fd, str(os.getpid()).encode())
        except FileExistsError as exc:
            raise QueenLockError(
                f"Ein anderer Bumble-Prozess arbeitet bereits im Stock (Lock: {self.path}). "
                "Bei Absturz: Datei manuell löschen."
            ) from exc
        return self

    def __exit__(self, *_exc) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.path.unlink()
        except OSError:
            pass

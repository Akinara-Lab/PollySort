"""Gemeinsame Test-Vorkehrungen.

**Kein Test darf ins Netz.** Am 2026-09-24 stellte der LLM-Client auf eine gehaltene
Verbindung (``httpx.Client``) um; drei Tests patchten noch ``httpx.post`` — und schickten
ihre Platzhalter-Schlüssel ungebremst an OpenRouter. Harmlos, aber genau so etwas darf nicht
still passieren. Dieser Wächter sitzt unter jeder httpx-API: Wer den Transport nicht
ersetzt hat, bekommt einen lauten Fehler statt einer echten Anfrage.
"""

from __future__ import annotations

import httpx
import pytest


def _kein_netz(self, request):
    raise RuntimeError(f"Test wollte ins Netz: {request.method} {request.url} — "
                       "Transport im Test ersetzen (z. B. httpx.Client.post patchen)")


@pytest.fixture(autouse=True)
def _netz_sperren(monkeypatch):
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _kein_netz)


@pytest.fixture(autouse=True)
def _eigenes_beenara(monkeypatch, tmp_path):
    """Kein Test sieht ein echtes BeeNara. Liegt das Modell samt Laufzeit auf dem Rechner,
    würde es sonst in jedem Sortier-Test mitentscheiden — und deren Erwartungen kippen.
    BeeNara-Tests legen sich ihr Modell selbst hin (``config.POLLYSORT_HOME``)."""
    from pollysort import beenara, beenara_big, config
    monkeypatch.setattr(config, "POLLYSORT_HOME", tmp_path / "pollysort-home")
    beenara.schliessen()
    beenara_big.schliessen()
    # Auch keine echte Grafikkarte: Ob BeeNara Big laden darf, legt jeder Test selbst fest.
    monkeypatch.setattr(beenara_big, "gpus", lambda: ())
    monkeypatch.delenv(beenara_big.CPU_ERLAUBT, raising=False)

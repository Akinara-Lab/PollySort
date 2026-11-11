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
def _kein_echter_tresor(monkeypatch):
    """Kein Test fasst die Anmeldeinformationsverwaltung des Rechners an.

    Ohne diese Sperre schrieben Tests, die einen Schlüssel oder Flugrouten speichern, echte
    Einträge in den Tresor des Entwicklers. Hier gibt es schlicht keinen Tresor — Zugangsdaten
    landen wie früher in der Datei im Wegwerf-Ordner. Tresor-Tests setzen sich mit der
    Fixture ``tresor_im_speicher`` einen eigenen, der nur im Arbeitsspeicher liegt.
    """
    from pollysort import config, flugrouten, tresor
    monkeypatch.setattr(tresor, "_pruefen", lambda: (None, "kein_speicher"))
    monkeypatch.setattr(tresor, "_gestoert", False)
    monkeypatch.setattr(config, "_UMZUG_VERSUCHT", False)
    monkeypatch.setattr(flugrouten, "_UMZUG_VERSUCHT", set())


class TresorImSpeicher:
    """Steht für das ``keyring``-Modul: gleiche drei Funktionen, Inhalt nur im Arbeitsspeicher."""

    def __init__(self):
        self.inhalt: dict[tuple[str, str], str] = {}
        self.kaputt = False           # True → jeder Zugriff scheitert wie ein gesperrter Tresor
        self.max_zeichen = None       # Zahl → längere Werte lehnt er ab (wie Windows)

    def _pruefe(self):
        if self.kaputt:
            raise RuntimeError("Tresor gesperrt")

    def get_password(self, dienst, name):
        self._pruefe()
        return self.inhalt.get((dienst, name))

    def set_password(self, dienst, name, wert):
        self._pruefe()
        if self.max_zeichen is not None and len(wert) > self.max_zeichen:
            raise OSError("Wert zu lang")
        self.inhalt[(dienst, name)] = wert

    def delete_password(self, dienst, name):
        self._pruefe()
        del self.inhalt[(dienst, name)]


@pytest.fixture
def tresor_im_speicher(monkeypatch, _kein_echter_tresor):
    """Ein Tresor nur für diesen Test — siehe :class:`TresorImSpeicher`."""
    from pollysort import tresor
    speicher = TresorImSpeicher()
    monkeypatch.setattr(tresor, "_pruefen",
                        lambda: (None, "gestoert") if tresor._gestoert else (speicher, ""))
    return speicher


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

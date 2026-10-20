"""Die Ollama-Modelle für den Modus Lokal laden — per Knopfdruck statt im Terminal.

Der Modus Lokal braucht zwei Ollama-Modelle (:data:`ROLLEN`): das **Sprachmodell**
(:data:`~pollysort.llm.client.OLLAMA_MODEL`), das Dokumente liest und einordnet, und das
**Gedächtnis-Modell** (:data:`~pollysort.llm.client.OLLAMA_EMBED_MODEL`, das Embedding für das
Gedächtnis, PollySorts RAG). Fehlt das Sprachmodell, scheitert der Modus Lokal; fehlt das
Gedächtnis-Modell, sortiert PollySort zwar, aber das Gedächtnis lernt still nichts dazu. Bisher hieß
der Rat ``ollama pull …`` im Terminal. Hier holt PollySort die Modelle selbst, über Ollamas eigene
Schnittstelle (``POST /api/pull``), im selben Ablauf wie ``beenara laden``: Meldungen, Fortschritt
in Bytes, Fehler werden gemeldet statt geworfen. So sieht es in der Konsole (``ollama laden``), der
Skript-CLI und der Werkstatt gleich aus.

Ollama legt die Modelle in seinem eigenen Speicher ab; PollySort schreibt dabei nichts auf die
Platte. Einen abgebrochenen Download setzt Ollama beim nächsten Mal fort.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from . import config, i18n
from .llm.client import (
    OLLAMA_EMBED_MODEL,
    OLLAMA_ENDPOINT,
    OLLAMA_MODEL,
    ollama_has_model,
    ollama_models,
)

#: Rolle → Modell. Die Reihenfolge ist die der Werkstatt und von 'ollama'.
ROLLEN = {"sprache": OLLAMA_MODEL, "gedaechtnis": OLLAMA_EMBED_MODEL}
#: Ungefähre Größe in GB, für den Knopf — gemessen am 2026-10-20 (``/api/tags``).
UNGEFAEHR_GB = {"sprache": 6.6, "gedaechtnis": 1.0}
#: Wörter, mit denen man in Konsole und CLI eine Rolle statt eines Modellnamens meint.
ROLLEN_WOERTER = {
    "sprache": "sprache", "sprachmodell": "sprache", "language": "sprache", "chat": "sprache",
    "gedaechtnis": "gedaechtnis", "gedächtnis": "gedaechtnis", "memory": "gedaechtnis",
    "rag": "gedaechtnis", "embedding": "gedaechtnis", "embed": "gedaechtnis",
}

#: Verbinden knapp, Lesen großzügig: Beim Prüfen der Prüfsumme bleibt Ollama zwischen zwei
#: Fortschrittszeilen eine Weile still.
_TIMEOUT = httpx.Timeout(300.0, connect=10.0)


@dataclass
class Stand:
    modell: str
    #: Antwortet ein Ollama-Server? Nur installiert, aber nicht gestartet, zählt als nein.
    erreichbar: bool
    vorhanden: bool
    #: ``sprache`` · ``gedaechtnis`` · ``None`` (ein anderes Modell)
    rolle: str | None = None


def endpunkt() -> str:
    """Ollamas Basisadresse wie im Modus Lokal (``llm_endpoint`` oder Standard), ohne ``/v1``."""
    base = (config.load_config().llm_endpoint or OLLAMA_ENDPOINT).rstrip("/")
    return base[:-3].rstrip("/") if base.endswith("/v1") else base


def rolle_von(modell: str) -> str | None:
    """Welche Rolle hat ``modell`` (tag-tolerant wie ``ollama_has_model``)?"""
    return next((r for r, m in ROLLEN.items() if ollama_has_model(m, [modell])), None)


def staende(endpoint: str | None = None) -> list[Stand]:
    """Stand beider Modelle mit einer Frage an den Server — läuft er nicht, dauert das bis zu
    ``PING_TIMEOUT``."""
    models = ollama_models(endpoint or endpunkt())
    return [Stand(m, models is not None, bool(models) and ollama_has_model(m, models), r)
            for r, m in ROLLEN.items()]


def stand(modell: str = OLLAMA_EMBED_MODEL, endpoint: str | None = None) -> Stand:
    """Ist Ollama erreichbar, und hat es ``modell`` schon?"""
    models = ollama_models(endpoint or endpunkt())
    return Stand(modell, models is not None, bool(models) and ollama_has_model(modell, models),
                 rolle_von(modell))


def bericht(s: Stand) -> list[tuple[str, str, str]]:
    """Statuszeilen ``(art, emoji, text)`` — dieselben in Konsole, Skript-CLI und Werkstatt."""
    if not s.erreichbar:
        return [("ask", "🦙", i18n.t("om.status.offline"))]
    if s.vorhanden:
        return [("honey", "✅", i18n.t("om.status.ready", modell=s.modell))]
    if s.rolle == "sprache":
        return [("ask", "🦙", i18n.t("om.missing.sprache", modell=s.modell))]
    return [("ask", "🧠", i18n.t("om.missing.gedaechtnis", modell=s.modell))]


def bericht_alle(staende_: list[Stand]) -> list[tuple[str, str, str]]:
    """Statuszeilen für beide Modelle, je mit der Rolle davor — für Konsole und Skript-CLI.
    Läuft Ollama nicht, reicht eine Zeile."""
    if not staende_[0].erreichbar:
        return bericht(staende_[0])
    return [(art, emoji, f"{i18n.t(f'om.rolle.{s.rolle}')}: {text}")
            for s in staende_ for art, emoji, text in bericht(s)]


def nach_wunsch(con, wunsch: str = "", *, endpoint: str | None = None) -> bool:
    """``ollama laden [wunsch]``: ohne Wunsch, was fehlt; eine Rolle (``sprache``,
    ``gedaechtnis``, ``rag`` …) lädt deren Modell; sonst ist der Wunsch ein Modellname — so
    klappt auch der Rat von ``doctor`` („ollama pull qwen3.5:9b")."""
    wunsch = wunsch.strip()
    if not wunsch:
        return fehlende_laden(con, endpoint=endpoint)
    rolle = ROLLEN_WOERTER.get(wunsch.lower())
    return laden(con, ROLLEN[rolle] if rolle else wunsch, endpoint=endpoint)


def laden(con, modell: str = OLLAMA_EMBED_MODEL, *, endpoint: str | None = None,
          client: httpx.Client | None = None) -> bool:
    """``modell`` über Ollama holen oder auffrischen. ``True``, wenn Ollama „success" meldet.

    Wie ``beenara laden``: Ein nicht laufendes Ollama, Fehler des Servers und Strg-C werden
    gemeldet, nicht geworfen.
    """
    base = endpoint or endpunkt()
    eigener = client is None
    if client is None:
        client = httpx.Client(timeout=_TIMEOUT)
    try:
        con.bloom(i18n.t("om.checking", modell=modell), "🦙")
        return _ziehen(con, client, base, modell)
    except KeyboardInterrupt:
        con.raw("")
        con.info(i18n.t("om.interrupted"), "⏸️")
        return False
    except (httpx.ConnectError, httpx.ConnectTimeout):
        con.error(i18n.t("om.err.offline", url=base))
        return False
    except (httpx.HTTPError, ValueError) as exc:
        con.error(i18n.t("om.err.pull", err=exc))
        return False
    finally:
        if eigener:
            client.close()


def _ziehen(con, client: httpx.Client, base: str, modell: str) -> bool:
    """Ollamas Antwort ist eine Zeile JSON je Schritt; die großen Schritte sind Schichten
    (``digest``) mit ``total``/``completed`` in Bytes. Der Balken zeigt die Summe aller Schichten,
    die Ollama bis dahin genannt hat."""
    schichten: dict[str, tuple[int, int]] = {}      # digest → (gesamt, erledigt)
    fertig = False
    # „name" für ältere Ollama-Server, die „model" noch nicht kennen.
    with client.stream("POST", f"{base}/api/pull",
                       json={"model": modell, "name": modell, "stream": True}) as r:
        if r.status_code != 200:
            r.read()
            con.error(i18n.t("om.err.pull", err=_fehlertext(r)))
            return False
        con.info(i18n.t("om.start", modell=modell), "⬇️")
        with con.progress(i18n.t("om.progress", modell=modell), transfer=True) as prog:
            task = prog.add_task(i18n.t("om.progress", modell=modell), total=None)
            for zeile in r.iter_lines():
                if not zeile.strip():
                    continue
                schritt = json.loads(zeile)
                if schritt.get("error"):
                    con.error(i18n.t("om.err.pull", err=schritt["error"]))
                    return False
                digest, gesamt = schritt.get("digest"), schritt.get("total")
                if digest and gesamt:
                    schichten[digest] = (int(gesamt), int(schritt.get("completed") or 0))
                    prog.update(task, total=sum(g for g, _ in schichten.values()),
                                completed=sum(e for _, e in schichten.values()))
                if schritt.get("status") == "success":
                    fertig = True
    if not fertig:
        con.error(i18n.t("om.err.incomplete"))
        return False
    rolle = rolle_von(modell)
    con.honey(i18n.t(f"om.done.{rolle}" if rolle else "om.done", modell=modell), "✅")
    return True


def fehlende_laden(con, *, endpoint: str | None = None) -> bool:
    """Was dem Modus Lokal fehlt, nacheinander laden (``ollama laden`` ohne Namen). ``True``,
    wenn danach beide Modelle da sind."""
    s = staende(endpoint)
    if not s[0].erreichbar:
        con.error(i18n.t("om.err.offline", url=endpoint or endpunkt()))
        return False
    fehlt = [x for x in s if not x.vorhanden]
    if not fehlt:
        con.honey(i18n.t("om.all_present"), "✅")
        return True
    ok = True
    for x in fehlt:
        ok = laden(con, x.modell, endpoint=endpoint) and ok
    return ok


def _fehlertext(r: httpx.Response) -> str:
    try:
        return str(r.json().get("error") or f"HTTP {r.status_code}")
    except ValueError:
        return f"HTTP {r.status_code}"

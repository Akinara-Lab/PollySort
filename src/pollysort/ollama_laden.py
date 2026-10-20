"""Das Ollama-Embedding-Modell fürs Gedächtnis laden — per Knopfdruck statt im Terminal.

Im Modus Lokal bettet Ollama jedes Dokument mit :data:`~pollysort.llm.client.OLLAMA_EMBED_MODEL`
ein. Fehlt das Modell, sortiert PollySort zwar, aber das Gedächtnis lernt still nichts dazu;
``doctor`` warnt, und bisher hieß der Rat ``ollama pull …`` im Terminal. Hier holt PollySort das
Modell selbst, über Ollamas eigene Schnittstelle (``POST /api/pull``), im selben Ablauf wie
``beenara laden``: Meldungen, Fortschritt in Bytes, Fehler werden gemeldet statt geworfen. So
sieht es in der Konsole (``ollama laden``), der Skript-CLI und der Werkstatt gleich aus.

Ollama legt das Modell in seinem eigenen Speicher ab; PollySort schreibt dabei nichts auf die
Platte. Einen abgebrochenen Download setzt Ollama beim nächsten Mal fort.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from . import config, i18n
from .llm.client import OLLAMA_EMBED_MODEL, OLLAMA_ENDPOINT, ollama_has_model, ollama_models

#: Verbinden knapp, Lesen großzügig: Beim Prüfen der Prüfsumme bleibt Ollama zwischen zwei
#: Fortschrittszeilen eine Weile still.
_TIMEOUT = httpx.Timeout(300.0, connect=10.0)


@dataclass
class Stand:
    modell: str
    #: Antwortet ein Ollama-Server? Nur installiert, aber nicht gestartet, zählt als nein.
    erreichbar: bool
    vorhanden: bool


def endpunkt() -> str:
    """Ollamas Basisadresse wie im Modus Lokal (``llm_endpoint`` oder Standard), ohne ``/v1``."""
    base = (config.load_config().llm_endpoint or OLLAMA_ENDPOINT).rstrip("/")
    return base[:-3].rstrip("/") if base.endswith("/v1") else base


def stand(modell: str = OLLAMA_EMBED_MODEL, endpoint: str | None = None) -> Stand:
    """Ist Ollama erreichbar, und hat es ``modell`` schon? Fragt den lokalen Server — läuft er
    nicht, dauert das bis zu ``PING_TIMEOUT``."""
    models = ollama_models(endpoint or endpunkt())
    return Stand(modell, models is not None, bool(models) and ollama_has_model(modell, models))


def bericht(s: Stand) -> list[tuple[str, str, str]]:
    """Statuszeilen ``(art, emoji, text)`` — dieselben in Konsole, Skript-CLI und Werkstatt."""
    if not s.erreichbar:
        return [("ask", "🦙", i18n.t("om.status.offline"))]
    if s.vorhanden:
        return [("honey", "✅", i18n.t("om.status.ready", modell=s.modell))]
    return [("ask", "🧠", i18n.t("om.status.missing", modell=s.modell))]


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
    con.honey(i18n.t("om.done", modell=modell), "✅")
    return True


def _fehlertext(r: httpx.Response) -> str:
    try:
        return str(r.json().get("error") or f"HTTP {r.status_code}")
    except ValueError:
        return f"HTTP {r.status_code}"

"""Modelle aktualisieren — BeeNara und BeeNara Big auf die Version, die dieses PollySort braucht.

Jede PollySort-Version ist an genau einen geprüften Commit gebunden (:data:`pollysort.beenara.REVISION`,
:data:`pollysort.beenara_big.REVISION`), denn Laufzeit und Kalibrierung müssen zusammenpassen. Nach einem
PollySort-Update passt ein schon geladenes Modell deshalb nicht mehr und sortiert nicht mit, bis die neue
Version da ist. Die holt :func:`aktualisieren` — die App ruft es beim Start im Hintergrund auf
(Einstellung ``beenara_auto_update``, Standard an):

* nur Modelle, die schon vollständig geladen sind — wer Big nie geladen hat, bekommt es auch jetzt nicht;
* nur die Modelldateien, keine Pakete — fehlt eine Laufzeit, sagt das der Stand wie bisher;
* über denselben Download wie ``beenara laden``: fester Commit, Prüfsummen, Fortsetzen, getauscht wird erst,
  wenn alles geprüft da ist.

Neuere Versionen auf dem Hub, die dieses PollySort nicht kennt, werden nur gemeldet (:func:`neuere_pruefen`,
höchstens einmal am Tag, ohne Dokumentdaten), nie geladen: Ein ungeprüftes Modell sortiert nicht.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from . import __version__, beenara, beenara_big, config, i18n

#: Die Modelle in der Reihenfolge, in der sie aktualisiert werden: das kleine zuerst (es sortiert die
#: meisten Projekte), dann Big.
MODELLE = ("klein", "big")
NAMEN = {"klein": "BeeNara", "big": "BeeNara Big"}
#: So oft fragt PollySort den Hub höchstens nach neueren Versionen.
ABSTAND = timedelta(days=1)
STAND_DATEI = "aktualisierung.json"

_SPERRE = threading.Lock()
_LAEUFT = threading.Event()
_TAG = re.compile(r"^v(\d+)\.(\d+)$")


def _modul(name: str):
    return beenara if name == "klein" else beenara_big


def veraltet() -> list[str]:
    """Welche Modelle vollständig daliegen, aber nicht auf dem Commit, den dieses PollySort braucht."""
    return [name for name in MODELLE
            if (s := _modul(name).stand()).vollstaendig and not s.passend]


def geladen() -> list[str]:
    """Welche Modelle vollständig daliegen, in welcher Version auch immer."""
    return [name for name in MODELLE if _modul(name).stand().vollstaendig]


def laeuft() -> bool:
    """Läuft gerade ein automatisches Update (für Stand und Oberfläche)?"""
    return _LAEUFT.is_set()


def aktualisieren(con, *, client: httpx.Client | None = None) -> dict[str, bool]:
    """Die veralteten Modelle auf den Commit dieses PollySort bringen — ``{modell: geklappt}``.

    Läuft schon ein Update, kommt ``{}`` zurück. Fehler werden gemeldet, nicht geworfen; was halb
    geladen ist, bleibt für das nächste Mal liegen (wie bei ``beenara laden``)."""
    if not _SPERRE.acquire(blocking=False):
        return {}
    _LAEUFT.set()
    try:
        ergebnis: dict[str, bool] = {}
        for name in veraltet():
            mod = _modul(name)
            con.info(i18n.t("mu.start", modell=NAMEN[name], alt=mod.stand().version,
                            neu=mod.REVISION[:7]), "🔄")
            try:
                ergebnis[name] = mod.laden(con, client=client)
            except Exception as exc:          # ein Update darf die App nie abreißen
                con.error(i18n.t("mu.err", modell=NAMEN[name], err=exc))
                ergebnis[name] = False
        return ergebnis
    finally:
        _LAEUFT.clear()
        _SPERRE.release()


# --------------------------------------------------------------------------- #
#  Neuere Versionen auf dem Hub — nur melden
# --------------------------------------------------------------------------- #
def _tag_zahl(tag: str) -> tuple[int, int] | None:
    m = _TAG.match(tag or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _datei() -> Path:
    return config.POLLYSORT_HOME / "modelle" / STAND_DATEI


def _lesen() -> dict:
    try:
        data = json.loads(_datei().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _schreiben(data: dict) -> None:
    d = _datei()
    d.parent.mkdir(parents=True, exist_ok=True)
    tmp = d.with_name(d.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, d)


def neuere() -> dict[str, str]:
    """Was die letzte Prüfung gefunden hat — ``{modell: tag}``, nur Modelle, die geladen sind. Ohne Netz."""
    da = set(geladen())
    neu = _lesen().get("neuer") or {}
    return {name: tag for name, tag in neu.items()
            if name in da and isinstance(tag, str) and _ist_neuer(tag, _modul(name).VERSION)}


def _ist_neuer(tag: str, version: str) -> bool:
    a, b = _tag_zahl(tag), _tag_zahl(version)
    return a is not None and b is not None and a > b


def neuere_pruefen(*, client: httpx.Client | None = None, jetzt: datetime | None = None) -> dict[str, str]:
    """Den Hub fragen, ob es für die geladenen Modelle einen neueren Versions-Tag gibt als den, den
    dieses PollySort kennt — höchstens einmal je :data:`ABSTAND`. Netzfehler bleiben still: Dann gilt
    das letzte Ergebnis. Gibt :func:`neuere` zurück."""
    jetzt = jetzt or datetime.now(UTC)
    da = geladen()
    if not da:
        return {}
    stand = _lesen()
    try:
        zuletzt = datetime.fromisoformat(stand["geprueft"])
    except (KeyError, TypeError, ValueError):
        zuletzt = None
    if zuletzt is not None and jetzt - zuletzt < ABSTAND:
        return neuere()
    eigener = client is None
    if client is None:
        client = httpx.Client(follow_redirects=True, timeout=httpx.Timeout(15.0, connect=10.0),
                              headers={"User-Agent": f"pollysort/{__version__}"})
    neu = dict(stand.get("neuer") or {})
    try:
        for name in da:
            mod = _modul(name)
            try:
                r = client.get(f"{beenara._endpoint()}/api/models/{mod.REPO}/refs")
                r.raise_for_status()
                tags = [t.get("name", "") for t in r.json().get("tags") or []]
            except (httpx.HTTPError, ValueError, AttributeError, TypeError):
                return neuere()
            hoechster = max((t for t in tags if _tag_zahl(t)), key=_tag_zahl, default=None)
            if hoechster and _ist_neuer(hoechster, mod.VERSION):
                neu[name] = hoechster
            else:
                neu.pop(name, None)
    finally:
        if eigener:
            client.close()
    _schreiben({"geprueft": jetzt.replace(microsecond=0).isoformat(), "neuer": neu})
    return neuere()

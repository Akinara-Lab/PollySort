"""BeeNara — das lokale Entscheider-Modell von Hugging Face holen.

BeeNara (https://huggingface.co/Kwokou/BeeNara) liest ein Dokument zusammen mit den
Ordnernamen und wählt einen davon — oder sagt „keiner passt". Es ist eine ONNX-Datei, die
offline auf der CPU läuft. Dieses Modul lädt das Modell nur herunter, prüft es und meldet den
Stand; in den Sortierlauf ist es noch nicht eingebunden.

Ablage: ``~/.pollysort/modelle/BeeNara/`` — global, nie im Projektordner (der bleibt sauber).

Der Download braucht kein ``huggingface_hub``: httpx ist ohnehin Kern-Abhängigkeit, und die
Hub-API liefert Größe und Prüfsumme jeder Datei mit. Alle Dateien kommen aus **demselben
Commit** (``main`` wird einmal aufgelöst), damit nie Modell und Kalibrierung aus zwei
Versionen zusammenkommen. Jede Datei landet erst als ``.part`` und wird gegen ihre
Prüfsumme verifiziert; erst wenn alle geprüft sind, bekommen sie gemeinsam ihre Namen. Ein
abgebrochener Download setzt beim nächsten ``beenara laden`` an derselben Stelle fort.
``HF_ENDPOINT`` lenkt auf einen Spiegel um.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from . import __version__, config, i18n

REPO = "Kwokou/BeeNara"
REVISION = "main"

#: Was PollySort zum Ausführen braucht. ``beenara.py`` aus dem Repo wird bewusst NICHT
#: geladen — fremder Code aus dem Netz wird hier nie ausgeführt.
PFLICHT = ("onnx/beenara.onnx", "onnx/calibration.json",
           "tokenizer/tokenizer.json", "tokenizer/tokenizer_config.json")
#: Lizenz und Herkunftsvermerk (Apache-2.0, Gewichte aus mmBERT) — kommen mit, wenn vorhanden.
BEILAGEN = ("LICENSE", "NOTICE")

#: Für Texte, die vor jeder Netzanfrage stehen (Erststart-Frage).
UNGEFAEHR_MB = 370

HERKUNFT = "herkunft.json"
_PUFFER_MB = 50                    # Luft auf der Platte über die reine Downloadgröße hinaus
_BLOCK = 1 << 20


class DownloadFehler(Exception):
    """Ein Download-Schritt ist gescheitert; die Meldung ist schon übersetzt."""


def ordner() -> Path:
    """Wo BeeNara liegt. Zur Aufrufzeit berechnet, damit ``POLLYSORT_HOME`` greift."""
    return config.POLLYSORT_HOME / "modelle" / "BeeNara"


def _mb(n: int) -> int:
    return round(n / 1_000_000)


def _endpoint() -> str:
    return (os.environ.get("HF_ENDPOINT") or "https://huggingface.co").rstrip("/")


# --------------------------------------------------------------------------- #
#  Lokaler Stand (ohne Netz)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Stand:
    pfad: Path
    vollstaendig: bool
    revision: str | None
    belegt: int                 # Bytes im Ordner, auch Halbfertiges
    angefangen: bool            # Teile da, aber nicht vollständig → 'beenara laden' setzt fort

    @property
    def version(self) -> str:
        return (self.revision or "?")[:7]

    @property
    def mb(self) -> int:
        return _mb(self.belegt)


def _herkunft_lesen(d: Path) -> dict | None:
    try:
        data = json.loads((d / HERKUNFT).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def stand() -> Stand:
    """Liegt BeeNara vollständig da? Liest nur ``herkunft.json`` und die Dateigrößen —
    die Prüfsummen wurden beim Download geprüft, ein Neu-Hashen von 330 MB wäre hier zu teuer."""
    d = ordner()
    try:
        belegt = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) if d.is_dir() else 0
    except OSError:
        belegt = 0
    man = _herkunft_lesen(d) or {}
    dateien = man.get("dateien") or {}
    try:
        vollstaendig = all(p in dateien for p in PFLICHT) and all(
            (d / p).is_file() and (d / p).stat().st_size == info.get("size")
            for p, info in dateien.items())
    except (OSError, AttributeError):
        vollstaendig = False
    return Stand(pfad=d, vollstaendig=vollstaendig, revision=man.get("revision"),
                 belegt=belegt, angefangen=belegt > 0 and not vollstaendig)


def entfernen() -> None:
    """Den BeeNara-Ordner löschen — nur die eigenen Downloads, nichts vom Nutzer."""
    d = ordner()
    if d.exists():
        shutil.rmtree(d)


# --------------------------------------------------------------------------- #
#  Download
# --------------------------------------------------------------------------- #
def _kurz(exc: Exception) -> str:
    """Fehlertext ohne lange CDN-Adressen."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    text = str(exc).strip() or type(exc).__name__
    return text if len(text) <= 160 else text[:157] + "…"


def _dateiliste(client: httpx.Client) -> tuple[str, dict[str, dict]]:
    """``main`` auf einen Commit auflösen und Größe + Prüfsumme der gebrauchten Dateien holen."""
    r = client.get(f"{_endpoint()}/api/models/{REPO}/revision/{REVISION}",
                   params={"blobs": "true"})
    r.raise_for_status()
    data = r.json()
    sha = str(data["sha"])
    hub = {s["rfilename"]: s for s in data.get("siblings") or []}
    fehlt = [p for p in PFLICHT if p not in hub]
    if fehlt:
        raise DownloadFehler(i18n.t("bn.err.layout", repo=REPO, names=", ".join(fehlt)))
    dateien: dict[str, dict] = {}
    for p in (*PFLICHT, *(b for b in BEILAGEN if b in hub)):
        s = hub[p]
        lfs = s.get("lfs") or {}
        # Große Dateien (LFS/Xet) tragen SHA-256, kleine nur die Git-Blob-ID (SHA-1).
        dateien[p] = ({"size": int(lfs["size"]), "sha256": str(lfs["sha256"])} if lfs.get("sha256")
                      else {"size": int(s["size"]), "git": str(s["blobId"])})
    return sha, dateien


def _pruefen(pfad: Path, info: dict) -> bool:
    if not pfad.is_file() or pfad.stat().st_size != info["size"]:
        return False
    if "sha256" in info:
        h, soll = hashlib.sha256(), info["sha256"]
    else:
        h, soll = hashlib.sha1(), info["git"]
        h.update(b"blob %d\0" % info["size"])
    with pfad.open("rb") as fh:
        for block in iter(lambda: fh.read(_BLOCK), b""):
            h.update(block)
    return h.hexdigest() == soll


def _aktuell(pfad: Path, info: dict, alt: dict | None) -> bool:
    """Ist die Datei schon die gewünschte? Gleicher Eintrag wie beim letzten Download und
    gleiche Größe reicht — sonst entscheidet die Prüfsumme (z. B. nach einem halben Update)."""
    if not pfad.is_file():
        return False
    if alt == info:
        return pfad.stat().st_size == info["size"]
    return _pruefen(pfad, info)


def _part(ziel: Path) -> Path:
    return ziel.with_name(ziel.name + ".part")


def _part_groesse(ziel: Path) -> int:
    part = _part(ziel)
    return part.stat().st_size if part.exists() else 0


def _datei_laden(client: httpx.Client, url: str, ziel: Path, info: dict,
                 weiter: Callable[[int], None]) -> None:
    """Eine Datei nach ``<ziel>.part`` laden (mit Fortsetzen) und prüfen. Umbenannt wird
    erst, wenn alle Teile geprüft da sind (``_offene_laden``)."""
    ziel.parent.mkdir(parents=True, exist_ok=True)
    part = _part(ziel)
    da = _part_groesse(ziel)
    if da > info["size"]:
        part.unlink()
        da = 0
    if da < info["size"]:
        headers = {"Range": f"bytes={da}-"} if da else {}
        with client.stream("GET", url, headers=headers) as r:
            r.raise_for_status()
            if da and r.status_code != 206:      # Server ignoriert Range → von vorn
                da = 0
            weiter(da)
            with part.open("ab" if da else "wb") as fh:
                for chunk in r.iter_bytes(_BLOCK):
                    fh.write(chunk)
                    weiter(len(chunk))
    if not _pruefen(part, info):
        part.unlink(missing_ok=True)
        raise DownloadFehler(i18n.t("bn.err.hash", name=ziel.name))


def _herkunft_schreiben(d: Path, sha: str, dateien: dict[str, dict]) -> None:
    data = {"repo": REPO, "revision": sha,
            "geladen": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "dateien": dateien}
    tmp = d / (HERKUNFT + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, d / HERKUNFT)


def _offene_laden(con, client: httpx.Client, sha: str, dateien: dict[str, dict],
                  offen: list[str]) -> bool:
    """Die fehlenden Dateien laden — mit Platz-Check und Fortschrittsbalken."""
    d = ordner()
    gesamt = sum(dateien[p]["size"] for p in offen)
    # Was von einem früheren Versuch schon als .part daliegt, muss nicht mehr übers Netz.
    noch = gesamt - sum(min(_part_groesse(d / p), dateien[p]["size"]) for p in offen)
    frei = shutil.disk_usage(d).free
    if frei < noch + _PUFFER_MB * 1_000_000:
        con.error(i18n.t("bn.err.space", need=_mb(noch) + _PUFFER_MB, free=_mb(frei), path=d))
        return False
    con.info(i18n.t("bn.start", n=len(offen), mb=_mb(noch), version=sha[:7], path=d), "⬇️")
    try:
        with con.progress(i18n.t("bn.progress"), transfer=True) as prog:
            task = prog.add_task(i18n.t("bn.progress"), total=gesamt)
            for p in offen:
                _datei_laden(client, f"{_endpoint()}/{REPO}/resolve/{sha}/{p}", d / p,
                             dateien[p], lambda n: prog.advance(task, n))
        # Erst jetzt tauschen, alles in einem Zug — sonst läge nach einem abgebrochenen
        # Update ein neues Modell neben der alten Kalibrierung. Ohne herkunft.json gilt der
        # Ordner während des Tauschs als unvollständig; 'beenara laden' räumt das dann auf.
        (d / HERKUNFT).unlink(missing_ok=True)
        for p in offen:
            os.replace(_part(d / p), d / p)
    except KeyboardInterrupt:
        con.raw("")
        con.info(i18n.t("bn.interrupted"), "⏸️")
        return False
    except DownloadFehler as exc:
        con.error(str(exc))
        return False
    except (httpx.HTTPError, OSError) as exc:
        con.error(i18n.t("bn.err.download", err=_kurz(exc)))
        return False
    return True


def laden(con, *, client: httpx.Client | None = None) -> bool:
    """BeeNara herunterladen, fortsetzen oder aktualisieren.

    Gibt ``True`` zurück, wenn das Modell danach vollständig und geprüft da ist. Fehler,
    fehlender Platz und Strg-C werden gemeldet statt geworfen — der Erststart darf an einem
    Download nie scheitern. Halbfertige Dateien bleiben für das nächste Mal liegen.
    """
    eigener = client is None
    if client is None:
        client = httpx.Client(follow_redirects=True,
                              timeout=httpx.Timeout(30.0, connect=10.0),
                              headers={"User-Agent": f"pollysort/{__version__}"})
    d = ordner()
    try:
        con.bloom(i18n.t("bn.checking", repo=REPO), "🔎")
        try:
            sha, dateien = _dateiliste(client)
        except DownloadFehler as exc:
            con.error(str(exc))
            return False
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            con.error(i18n.t("bn.err.hub", err=_kurz(exc)))
            return False

        alt = _herkunft_lesen(d) or {}
        alt_dateien = alt.get("dateien") or {}
        if alt.get("revision") == sha and stand().vollstaendig:
            con.honey(i18n.t("bn.current", version=sha[:7], path=d), "✅")
            return True

        offen = [p for p, info in dateien.items()
                 if not _aktuell(d / p, info, alt_dateien.get(p))]
        d.mkdir(parents=True, exist_ok=True)
        if offen and not _offene_laden(con, client, sha, dateien, offen):
            return False
        _herkunft_schreiben(d, sha, dateien)
        con.honey(i18n.t("bn.done", version=sha[:7], mb=_mb(stand().belegt), path=d), "✅")
        return True
    finally:
        if eigener:
            client.close()

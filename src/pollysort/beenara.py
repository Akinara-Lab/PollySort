"""BeeNara — das lokale Entscheider-Modell: von Hugging Face holen, prüfen, bereitstellen.

BeeNara (https://huggingface.co/Kwokou/BeeNara) liest ein Dokument zusammen mit den
Ordnernamen und wählt einen davon — oder sagt „keiner passt". Es ist eine ONNX-Datei, die
offline auf der CPU läuft. Dieses Modul lädt Modell und Laufzeit-Pakete, meldet den Stand und
öffnet das Modell für den Sortierlauf (:func:`oeffnen`); wie dort entschieden wird, steht in
:mod:`pollysort.entscheidung`.

Ablage: ``~/.pollysort/modelle/BeeNara/`` — global, nie im Projektordner (der bleibt sauber).

Der Download braucht kein ``huggingface_hub``: httpx ist ohnehin Kern-Abhängigkeit, und die
Hub-API liefert Größe und Prüfsumme jeder Datei mit. Alle Dateien kommen aus **einem festen
Commit** (:data:`REVISION`), auf den die Laufzeit in :mod:`pollysort.beenara_laufzeit`
abgestimmt ist — ein neues BeeNara kommt mit einem PollySort-Update, nie still über ``main``.
Jede Datei landet erst als ``.part`` und wird gegen ihre Prüfsumme verifiziert; erst wenn
alle geprüft sind, bekommen sie gemeinsam ihre Namen. Ein abgebrochener Download setzt beim
nächsten ``beenara laden`` an derselben Stelle fort. ``HF_ENDPOINT`` lenkt auf einen Spiegel um.

Die Laufzeit (``onnxruntime``, ``tokenizers``, ``numpy``) ist das Extra ``pollysort[beenara]``.
Fehlt sie, installiert ``beenara laden`` sie in die Umgebung, in der PollySort läuft.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from . import __version__, config, i18n

REPO = "Kwokou/BeeNara"
#: BeeNara v0.3 (Hub-Stand vom 2026-10-08, Tag ``v0.3``; v0.2 war e7497f1). Wer diesen Wert
#: anhebt, prüft vorher die Laufzeit gegen das neue Modell (Stufe-0, Paritätstest) — sonst
#: entscheidet PollySort mit einer Kalibrierung, für die seine Laufzeit nicht gebaut ist.
REVISION = "8597874e56a0522e09d9f2f65174aacffc05e319"

#: Die Laufzeit-Pakete — genau das Extra ``[beenara]`` aus pyproject.toml.
PAKETE = ("onnxruntime>=1.30", "tokenizers>=0.20", "numpy>=1.26")
_MODULE = ("onnxruntime", "tokenizers", "numpy")

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


@dataclass(frozen=True)
class Quelle:
    """Ein Hub-Repo auf einem festen Commit: welche Dateien gebraucht werden und welche nur
    mitkommen. Dieselbe Download-Logik lädt BeeNara und die Teile von BeeNara Big."""

    repo: str
    revision: str
    pflicht: tuple[str, ...]
    beilagen: tuple[str, ...] = ()
    #: Präfix der Meldungen: ``bn`` (BeeNara) oder ``bb`` (BeeNara Big); fehlt ein ``bb.…``-
    #: Text, gilt der ``bn.…``-Text.
    texte: str = "bn"


def quelle() -> Quelle:
    """BeeNara selbst — zur Aufrufzeit gebaut, damit ein angehobenes :data:`REVISION` greift."""
    return Quelle(REPO, REVISION, PFLICHT, BEILAGEN)


def _t(q: Quelle, key: str, **kw) -> str:
    eigen = f"{q.texte}.{key}"
    return i18n.t(eigen if i18n.vorhanden(eigen) else f"bn.{key}", **kw)


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
    soll: str | None = None     # der Commit, auf den die Laufzeit abgestimmt ist (Standard: REVISION)

    @property
    def version(self) -> str:
        return (self.revision or "?")[:7]

    @property
    def mb(self) -> int:
        return _mb(self.belegt)

    @property
    def passend(self) -> bool:
        """Vollständig UND genau der Commit, auf den die Laufzeit abgestimmt ist."""
        return self.vollstaendig and self.revision == (self.soll or REVISION)


def _herkunft_lesen(d: Path) -> dict | None:
    try:
        data = json.loads((d / HERKUNFT).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def stand() -> Stand:
    """Liegt BeeNara vollständig da? Liest nur ``herkunft.json`` und die Dateigrößen —
    die Prüfsummen wurden beim Download geprüft, ein Neu-Hashen von 330 MB wäre hier zu teuer."""
    return stand_in(ordner(), quelle())


def stand_in(d: Path, q: Quelle) -> Stand:
    """Der Stand eines Download-Ordners für die Quelle ``q`` (siehe :func:`stand`)."""
    try:
        belegt = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) if d.is_dir() else 0
    except OSError:
        belegt = 0
    man = _herkunft_lesen(d) or {}
    dateien = man.get("dateien") or {}
    try:
        vollstaendig = all(p in dateien for p in q.pflicht) and all(
            (d / p).is_file() and (d / p).stat().st_size == info.get("size")
            for p, info in dateien.items())
    except (OSError, AttributeError):
        vollstaendig = False
    return Stand(pfad=d, vollstaendig=vollstaendig, revision=man.get("revision"),
                 belegt=belegt, angefangen=belegt > 0 and not vollstaendig, soll=q.revision)


def entfernen() -> None:
    """Den BeeNara-Ordner löschen — nur die eigenen Downloads, nichts vom Nutzer."""
    schliessen()                    # eine offene Sitzung hält unter Windows die Datei fest
    d = ordner()
    if d.exists():
        shutil.rmtree(d)


# --------------------------------------------------------------------------- #
#  Laufzeit: Pakete prüfen, installieren, Modell öffnen
# --------------------------------------------------------------------------- #
def _version(v: str) -> tuple[int, ...]:
    """``"1.30.0"`` → ``(1, 30, 0)``; ``"2.14.1+cu130"`` → ``(2, 14, 1)``. Nur die Zahlen vorn."""
    teile: list[int] = []
    for t in v.split("+")[0].split("."):
        ziffern = t[:len(t) - len(t.lstrip("0123456789"))]
        if not ziffern:
            break
        teile.append(int(ziffern))
    return tuple(teile)


def zu_alt(pakete: tuple[str, ...]) -> list[str]:
    """Die Angaben aus ``pakete`` (``name>=x.y``), deren installierte Fassung älter ist.

    Fehlt ein Paket ganz, meldet das :func:`laufzeit_fehlt` über den Import-Namen. Am 2026-10-08
    gefunden: ``markitdown`` zog unter Windows magika 0.6.3 und damit ``onnxruntime<=1.20.1`` —
    BeeNara v0.3 (8-Bit) lässt sich damit nicht öffnen, galt aber als „bereit“."""
    alt = []
    for spez in pakete:
        name, _, mindest = spez.partition(">=")
        if not mindest:
            continue
        try:
            ist = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        if _version(ist) < _version(mindest):
            alt.append(spez)
    return alt


def laufzeit_fehlt() -> list[str]:
    """Welche Laufzeit-Pakete fehlen oder sind zu alt? Leer = BeeNara kann rechnen."""
    return [m for m in _MODULE if importlib.util.find_spec(m) is None] + zu_alt(PAKETE)


def warum_nicht(cfg) -> str | None:
    """Warum BeeNara gerade nicht mitsortiert — ``None`` heißt: bereit.

    ``aus`` (abgeschaltet) · ``modell`` (nicht geladen) · ``version`` (anderer Commit als
    :data:`REVISION`) · ``laufzeit`` (Pakete fehlen). Modus und Ordnerzahl sind Sache des
    Projekts und stehen in :mod:`pollysort.entscheidung`.
    """
    if not getattr(cfg, "beenara", True):
        return "aus"
    s = stand()
    if not s.vollstaendig:
        return "modell"
    if not s.passend:
        return "version"
    if laufzeit_fehlt():
        return "laufzeit"
    return None


def _installationsbefehl() -> list[str] | None:
    """Wie sich Pakete in genau die Umgebung bringen lassen, in der PollySort läuft.

    pip, wenn vorhanden (venv, pipx); sonst ``uv pip --python`` (uv-Tool-Umgebungen haben
    kein pip). Außerhalb einer venv mit ``--user``, wie der Installer.
    """
    if importlib.util.find_spec("pip") is not None:
        befehl = [sys.executable, "-m", "pip", "install", "--quiet"]
        if sys.prefix == sys.base_prefix:
            befehl.append("--user")
        return [*befehl, *PAKETE]
    uv = shutil.which("uv")
    if uv:
        return [uv, "pip", "install", "--quiet", "--python", sys.executable, *PAKETE]
    return None


def laufzeit_installieren(con) -> bool:
    """Fehlende Laufzeit-Pakete installieren. ``True`` = danach alles da."""
    fehlt = laufzeit_fehlt()
    if not fehlt:
        return True
    befehl = _installationsbefehl()
    if befehl is None:
        con.error(i18n.t("bn.rt.manual", pakete=" ".join(PAKETE)))
        return False
    con.bloom(i18n.t("bn.rt.installing", pakete=", ".join(fehlt)), "📦")
    # Ein schon geladenes, zu altes onnxruntime rechnet bis zum Neustart weiter.
    neu_starten = any(s.partition(">=")[0] in sys.modules for s in zu_alt(PAKETE))
    try:
        r = subprocess.run(befehl, capture_output=True, text=True, timeout=1800)
    except KeyboardInterrupt:
        con.raw("")
        con.info(i18n.t("bn.interrupted"), "⏸️")
        return False
    except (OSError, subprocess.TimeoutExpired) as exc:
        con.error(i18n.t("bn.rt.failed", err=_kurz(exc), cmd=" ".join(befehl)))
        return False
    importlib.invalidate_caches()
    if r.returncode != 0:
        letzte = ((r.stderr or "") + (r.stdout or "")).strip().splitlines()
        con.error(i18n.t("bn.rt.failed", err=letzte[-1] if letzte else f"Code {r.returncode}",
                         cmd=" ".join(befehl)))
        return False
    if laufzeit_fehlt() or neu_starten:
        # Installiert, aber in einem Pfad, den dieser Prozess beim Start nicht kannte
        # (z. B. ein frisch angelegtes Benutzer-site-packages) — oder die alte Fassung ist geladen.
        con.info(i18n.t("bn.rt.restart"), "🔁")
        return False
    con.honey(i18n.t("bn.rt.done"), "✅")
    return True


_SITZUNGEN: dict[str, object] = {}
_SPERRE = threading.Lock()


def threads() -> int:
    """Wie viele CPU-Threads eine Entscheidung nutzt.

    Gemessen am 2026-10-02 auf einem Core Ultra 7 255H (6 P-, 8 E-, 2 LP-Kerne, Akku), Median
    über 40 Dokumente mit 8 Ordnern: 2 → 810 ms · 4 → 481 ms · **6 → 368 ms** · 8 → 380 ms
    (streut stärker) · 16 → 861 ms · ONNX-Standard (alle Kerne) → 493 ms. Mehr Threads ziehen
    die Effizienzkerne mit hinein und bremsen. ``POLLYSORT_BEENARA_THREADS`` überschreibt das.
    """
    try:
        gewuenscht = int(os.environ.get("POLLYSORT_BEENARA_THREADS", "0"))
    except ValueError:
        gewuenscht = 0
    if gewuenscht > 0:
        return gewuenscht
    return max(1, min(6, os.cpu_count() or 1))


def oeffnen():
    """Das Modell zum Rechnen öffnen — einmal je Prozess, denn Laden dauert ~3 s.

    Wirft, wenn Laufzeit oder Modell kaputt sind; der Sortierlauf meldet das und macht ohne
    BeeNara weiter. Thread-sicher: der Ultra Swarm ruft ``decide`` parallel auf, und ONNX
    Runtime erlaubt das auf einer Sitzung.
    """
    with _SPERRE:
        schluessel = str(ordner())
        if schluessel not in _SITZUNGEN:
            from .beenara_laufzeit import BeeNara
            _SITZUNGEN[schluessel] = BeeNara(ordner(), threads=threads())
        return _SITZUNGEN[schluessel]


def schliessen() -> None:
    """Offene Sitzungen verwerfen (vor dem Entfernen oder nach einem Update)."""
    with _SPERRE:
        _SITZUNGEN.clear()


def ist_offen() -> bool:
    """Ist das Modell in diesem Prozess schon geladen? (Dann kostet der nächste Lauf nichts.)"""
    with _SPERRE:
        return str(ordner()) in _SITZUNGEN


def bericht(cfg, hive: Path | None = None) -> list[tuple[str, str, str]]:
    """Der Stand als Zeilen ``(art, emoji, text)`` — dieselben in Konsole, CLI und Flugbrett.

    ``art`` ist eine Methode der Konsole (``honey`` · ``ask`` · ``info``). Mit ``hive`` sagt die
    letzte Zeile, ob BeeNara in genau diesem Projekt mitentscheidet (Modus, Ordnerzahl).
    """
    from . import entscheidung
    s = stand()
    zeilen: list[tuple[str, str, str]] = []
    if s.vollstaendig:
        zeilen.append(("honey", "✅", i18n.t("bn.status.ok", version=s.version, mb=s.mb,
                                             path=s.pfad)))
    elif s.angefangen:
        zeilen.append(("ask", "❓", i18n.t("bn.status.partial")))
    else:
        zeilen.append(("info", "⬇️", i18n.t("bn.status.none", repo=REPO, mb=UNGEFAEHR_MB)))
    grund = warum_nicht(cfg)
    if grund is None:
        zeilen.append(("honey", "⚡", i18n.t("bn.active.ja")))
        if hive is not None and config.is_setup(hive):
            from .hive_mind import Taxonomy
            seed = config.load_seed(hive)
            name = seed.name or hive.name
            # Wie der Sortierlauf: die lebende Taxonomie, vor dem ersten Lauf der Seed.
            kats = Taxonomy(hive).categories or seed.categories
            if seed.provider == "openrouter":
                zeilen.append(("info", "☁️", i18n.t("bn.project.cloud", name=name)))
            elif not entscheidung.beenara_passt(kats):
                zeilen.append(("info", "🗂️", i18n.t("bn.project.count", name=name,
                                                    n=len(entscheidung.ordner_namen(kats)))))
            else:
                zeilen.append(("info", "📂", i18n.t("bn.project.ok", name=name)))
    elif grund == "version":
        zeilen.append(("ask", "❓", i18n.t("bn.active.version", have=s.version,
                                           need=REVISION[:7])))
    elif grund == "laufzeit":
        zeilen.append(("ask", "❓", i18n.t("bn.active.laufzeit",
                                           pakete=", ".join(laufzeit_fehlt()))))
    elif grund == "aus":
        zeilen.append(("info", "💤", i18n.t("bn.active.aus")))
    elif s.vollstaendig or s.angefangen:
        zeilen.append(("info", "⬇️", i18n.t("bn.active.modell")))
    return zeilen


# --------------------------------------------------------------------------- #
#  Download
# --------------------------------------------------------------------------- #
def _kurz(exc: Exception) -> str:
    """Fehlertext ohne lange CDN-Adressen."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    text = str(exc).strip() or type(exc).__name__
    return text if len(text) <= 160 else text[:157] + "…"


def _dateiliste(client: httpx.Client, q: Quelle) -> tuple[str, dict[str, dict]]:
    """Den festen Commit auflösen und Größe + Prüfsumme der gebrauchten Dateien holen."""
    r = client.get(f"{_endpoint()}/api/models/{q.repo}/revision/{q.revision}",
                   params={"blobs": "true"})
    r.raise_for_status()
    data = r.json()
    sha = str(data["sha"])
    hub = {s["rfilename"]: s for s in data.get("siblings") or []}
    fehlt = [p for p in q.pflicht if p not in hub]
    if fehlt:
        raise DownloadFehler(i18n.t("bn.err.layout", repo=q.repo, names=", ".join(fehlt)))
    dateien: dict[str, dict] = {}
    for p in (*q.pflicht, *(b for b in q.beilagen if b in hub)):
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


def _herkunft_schreiben(d: Path, q: Quelle, sha: str, dateien: dict[str, dict]) -> None:
    data = {"repo": q.repo, "revision": sha,
            "geladen": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "dateien": dateien}
    tmp = d / (HERKUNFT + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, d / HERKUNFT)


def _offene_laden(con, client: httpx.Client, q: Quelle, d: Path, sha: str,
                  dateien: dict[str, dict], offen: list[str]) -> bool:
    """Die fehlenden Dateien laden — mit Platz-Check und Fortschrittsbalken."""
    gesamt = sum(dateien[p]["size"] for p in offen)
    # Was von einem früheren Versuch schon als .part daliegt, muss nicht mehr übers Netz.
    noch = gesamt - sum(min(_part_groesse(d / p), dateien[p]["size"]) for p in offen)
    frei = shutil.disk_usage(d).free
    if frei < noch + _PUFFER_MB * 1_000_000:
        con.error(i18n.t("bn.err.space", need=_mb(noch) + _PUFFER_MB, free=_mb(frei), path=d))
        return False
    con.info(_t(q, "start", n=len(offen), mb=_mb(noch), version=sha[:7], path=d), "⬇️")
    try:
        with con.progress(_t(q, "progress"), transfer=True) as prog:
            task = prog.add_task(_t(q, "progress"), total=gesamt)
            for p in offen:
                _datei_laden(client, f"{_endpoint()}/{q.repo}/resolve/{sha}/{p}", d / p,
                             dateien[p], lambda n: prog.advance(task, n))
        # Erst jetzt tauschen, alles in einem Zug — sonst läge nach einem abgebrochenen
        # Update ein neues Modell neben der alten Kalibrierung. Ohne herkunft.json gilt der
        # Ordner während des Tauschs als unvollständig; 'beenara laden' räumt das dann auf.
        (d / HERKUNFT).unlink(missing_ok=True)
        for p in offen:
            os.replace(_part(d / p), d / p)
    except KeyboardInterrupt:
        con.raw("")
        con.info(_t(q, "interrupted"), "⏸️")
        return False
    except DownloadFehler as exc:
        con.error(str(exc))
        return False
    except (httpx.HTTPError, OSError) as exc:
        con.error(_t(q, "err.download", err=_kurz(exc)))
        return False
    return True


def laden(con, *, client: httpx.Client | None = None) -> bool:
    """BeeNara herunterladen, fortsetzen oder aktualisieren.

    Gibt ``True`` zurück, wenn das Modell danach vollständig und geprüft da ist. Fehler,
    fehlender Platz und Strg-C werden gemeldet statt geworfen — der Erststart darf an einem
    Download nie scheitern. Halbfertige Dateien bleiben für das nächste Mal liegen.
    """
    ok = laden_quelle(con, quelle(), ordner(), client=client)
    if ok:
        schliessen()                    # eine Sitzung auf dem alten Stand nicht weiterbenutzen
    return ok


def laden_quelle(con, q: Quelle, d: Path, *, client: httpx.Client | None = None) -> bool:
    """Die Dateien der Quelle ``q`` nach ``d`` laden, fortsetzen oder aktualisieren — siehe
    :func:`laden`. Gemeldet wird mit den Texten der Quelle (``q.texte``)."""
    if stand_in(d, q).passend:
        # Der Commit ist fest — liegt er vollständig da, gibt es nichts nachzufragen (auch offline).
        con.honey(_t(q, "current", version=q.revision[:7], path=d), "✅")
        return True
    eigener = client is None
    if client is None:
        client = httpx.Client(follow_redirects=True,
                              timeout=httpx.Timeout(30.0, connect=10.0),
                              headers={"User-Agent": f"pollysort/{__version__}"})
    try:
        con.bloom(_t(q, "checking", repo=q.repo), "🔎")
        try:
            sha, dateien = _dateiliste(client, q)
        except DownloadFehler as exc:
            con.error(str(exc))
            return False
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            con.error(i18n.t("bn.err.hub", err=_kurz(exc)))
            return False

        alt = _herkunft_lesen(d) or {}
        alt_dateien = alt.get("dateien") or {}
        if alt.get("revision") == sha and stand_in(d, q).vollstaendig:
            con.honey(_t(q, "current", version=sha[:7], path=d), "✅")
            return True

        offen = [p for p, info in dateien.items()
                 if not _aktuell(d / p, info, alt_dateien.get(p))]
        d.mkdir(parents=True, exist_ok=True)
        if offen and not _offene_laden(con, client, q, d, sha, dateien, offen):
            return False
        _herkunft_schreiben(d, q, sha, dateien)
        con.honey(_t(q, "done", version=sha[:7], mb=_mb(stand_in(d, q).belegt), path=d), "✅")
        return True
    finally:
        if eigener:
            client.close()


def einrichten(con, *, client: httpx.Client | None = None) -> bool:
    """Alles, was BeeNara zum Sortieren braucht: das Modell, dann fehlende Laufzeit-Pakete.
    Das ist ``beenara laden`` und die Zusage im Erststart."""
    return laden(con, client=client) and laufzeit_installieren(con)

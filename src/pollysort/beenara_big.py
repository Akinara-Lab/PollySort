"""BeeNara Big — das große Entscheider-Modell für ganze Ordnerbäume: holen, prüfen, öffnen.

BeeNara Big (https://huggingface.co/Kwokou/BeeNara-Big, v0.3, Vorschau) liest den ganzen
Ordnerbaum — 3 bis etwa 300 Ordner, trainiert bis 500 — und schlägt den passenden Ordner vor.
Es ist Qwen3.5-2B-Base mit LoRA und einem kleinen Entscheidungskopf und braucht eine NVIDIA-GPU
mit mindestens 8 GB. In v0.3 ist es nur für Vorschläge kalibriert: Was Big entscheidet, wird
immer eine Rückfrage mit seinem Favoriten.

Zwei Teile, beide auf festem Commit und mit Prüfsumme geladen — dieselbe Logik wie BeeNara
(:func:`pollysort.beenara.laden_quelle`):

* der Big-Teil (LoRA, Kopf, Kalibrierung, Tokenizer, ~164 MB) aus :func:`quelle_big`,
* das Basismodell Qwen3.5-2B-Base (~4,6 GB) aus :func:`quelle_basis` nach ``basis/``.

Ablage: ``~/.pollysort/modelle/BeeNara-Big/``. Die Laufzeit (torch mit CUDA, transformers,
peft, …) ist das Extra ``pollysort[beenara-big]``; ``beenara big laden`` installiert sie, torch
aus dem PyTorch-Index passend zum Grafiktreiber. Welches Modell sortiert, entscheidet die
Einstellung ``beenara_modell`` (siehe :func:`pollysort.entscheidung.beenara_modell_fuer`).
"""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from . import beenara, config, i18n
from .beenara import Quelle, Stand, stand_in

REPO = "Kwokou/BeeNara-Big"
#: BeeNara Big v0.3 (Hub-Commit vom 2026-10-08, mit Lader und Quickstart). Die Modelldateien sind
#: dieselben wie in 91e082d und in d453bef (Tag ``v0.3``, dort nur der Lader für die GPU
#: korrigiert — PollySort lädt keinen Code vom Hub). Wer diesen Wert anhebt, prüft vorher die
#: Laufzeit gegen das neue Modell (Paritätstest) — wie bei BeeNara.
REVISION = "64266f0783557431f6e2d5bcf06e00bd8631f4d6"
BASIS_REPO = "Qwen/Qwen3.5-2B-Base"
#: Genau die Basis, auf der Big trainiert wurde (steht auch in ``big_config.json``).
BASIS_REVISION = "b1485b2fa6dfa1287294f269f5fb618e03d52d7c"

PFLICHT = ("big_config.json", "kopf.safetensors", "lora.safetensors", "kalibrierung.json",
           "tokenizer/tokenizer.json", "tokenizer/tokenizer_config.json",
           "bildprozessor/preprocessor_config.json")
BEILAGEN = ("LICENSE", "NOTICE", "tokenizer/chat_template.jinja", "kalibrierung_8bit.json")
BASIS_PFLICHT = ("config.json", "model.safetensors-00001-of-00001.safetensors",
                 "model.safetensors.index.json")
BASIS_BEILAGEN = ("LICENSE",)

#: Die Laufzeit — genau das Extra ``[beenara-big]`` aus pyproject.toml. torch kommt mit CUDA aus
#: dem PyTorch-Index (:func:`torch_index`), der Rest von PyPI.
PAKETE = ("torch>=2.14", "transformers>=5.17", "peft>=0.21", "safetensors>=0.8", "tokenizers>=0.20",
          "pillow>=10")
_MODULE = ("torch", "transformers", "peft", "safetensors", "tokenizers", "PIL")

#: Für Texte vor jeder Netzanfrage: Big-Teil + Basismodell.
UNGEFAEHR_MB = 4_720
#: So viel Grafikspeicher braucht Big in bf16 bei großen Bäumen (Gewichte 4,6 GB + Aktivierungen).
MIN_VRAM_MB = 8_000
#: Ohne passende GPU trotzdem laden (rechnet dann auf der CPU — Sekunden bis Minuten je Dokument).
CPU_ERLAUBT = "POLLYSORT_BEENARA_BIG_CPU"


def quelle_big() -> Quelle:
    return Quelle(REPO, REVISION, PFLICHT, BEILAGEN, texte="bb")


def quelle_basis() -> Quelle:
    return Quelle(BASIS_REPO, BASIS_REVISION, BASIS_PFLICHT, BASIS_BEILAGEN, texte="bb")


def ordner() -> Path:
    """Wo Big liegt. Zur Aufrufzeit berechnet, damit ``POLLYSORT_HOME`` greift."""
    return config.POLLYSORT_HOME / "modelle" / "BeeNara-Big"


def basis_ordner() -> Path:
    return ordner() / "basis"


# --------------------------------------------------------------------------- #
#  Lokaler Stand (ohne Netz)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class StandBig:
    big: Stand
    basis: Stand

    @property
    def pfad(self) -> Path:
        return self.big.pfad

    @property
    def vollstaendig(self) -> bool:
        return self.big.vollstaendig and self.basis.vollstaendig

    @property
    def passend(self) -> bool:
        return self.big.passend and self.basis.passend

    @property
    def angefangen(self) -> bool:
        return (self.big.belegt + self.basis.belegt) > 0 and not self.vollstaendig

    @property
    def version(self) -> str:
        return self.big.version

    @property
    def mb(self) -> int:
        return self.big.mb                # big.belegt zählt den Unterordner basis/ schon mit


def stand() -> StandBig:
    return StandBig(big=stand_in(ordner(), quelle_big()), basis=stand_in(basis_ordner(), quelle_basis()))


def entfernen() -> None:
    """Den Big-Ordner löschen — nur die eigenen Downloads, nichts vom Nutzer."""
    schliessen()
    d = ordner()
    if d.exists():
        shutil.rmtree(d)


# --------------------------------------------------------------------------- #
#  GPU
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def gpus() -> tuple[dict, ...]:
    """NVIDIA-Karten laut ``nvidia-smi``: ``({name, mb, treiber}, …)`` — leer ohne Karte/Treiber.
    Einmal je Prozess gefragt; die Werkstatt zeichnet oft neu."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return ()
    try:
        r = subprocess.run([smi, "--query-gpu=name,memory.total,driver_version",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return ()
    out = []
    for zeile in (r.stdout or "").strip().splitlines() if r.returncode == 0 else []:
        teile = [t.strip() for t in zeile.split(",")]
        if len(teile) >= 3:
            try:
                out.append({"name": teile[0], "mb": int(float(teile[1])), "treiber": teile[2]})
            except ValueError:
                continue
    return tuple(out)


def gpu_grund() -> str | None:
    """Warum diese Maschine Big nicht tragen kann — ``None`` heißt: passt.
    ``keine`` (keine NVIDIA-GPU) · ``klein`` (weniger als :data:`MIN_VRAM_MB`)."""
    if os.environ.get(CPU_ERLAUBT) == "1":
        return None
    karten = gpus()
    if not karten:
        return "keine"
    if max(k["mb"] for k in karten) < MIN_VRAM_MB:
        return "klein"
    return None


def gpu_reicht() -> bool:
    """Steckt eine NVIDIA-Karte mit mindestens :data:`MIN_VRAM_MB`? (Ohne Rücksicht auf die
    CPU-Erlaubnis — die entscheidet nur, ob geladen werden darf.)"""
    return any(k["mb"] >= MIN_VRAM_MB for k in gpus())


def torch_index(treiber: str | None) -> str:
    """CUDA-Build von torch passend zum Treiber: cu130 braucht Treiber ≥ 580, cu126 ≥ 560
    (wie im Trainingspaket); darunter oder ohne Karte die CPU-Fassung."""
    try:
        v = float(".".join(treiber.split(".")[:2])) if treiber else 0.0
    except ValueError:
        v = 0.0
    if v >= 580:
        return "cu130"
    if v >= 560:
        return "cu126"
    return "cpu"


def cuda_index() -> str:
    """Der PyTorch-Index für diese Maschine: ``cu130`` · ``cu126`` · ``cpu``."""
    karten = gpus()
    return torch_index(karten[0]["treiber"] if karten and gpu_reicht() else None)


def torch_ohne_cuda() -> bool:
    """Liegt torch nur als CPU-Fassung da, obwohl eine passende NVIDIA-Karte steckt? Dann würde
    Big auf der CPU rechnen; ``beenara big laden`` tauscht torch gegen die CUDA-Fassung.

    Gelesen wird nur die Versionsangabe — torch zu importieren dauert Sekunden. ``+cpu`` und die
    Windows-Räder von PyPI (ohne ``+cu…``) sind reine CPU-Fassungen; unter Linux bringt das Rad
    von PyPI CUDA schon mit."""
    if cuda_index() == "cpu":
        return False
    try:
        v = importlib.metadata.version("torch")
    except importlib.metadata.PackageNotFoundError:
        return False
    return v.endswith("+cpu") or (sys.platform == "win32" and "+cu" not in v)


def auf_gpu() -> bool:
    """Wird Big auf der Grafikkarte rechnen? (Passende Karte, CUDA-Fassung von torch.)"""
    return cuda_index() != "cpu" and not torch_ohne_cuda()


# --------------------------------------------------------------------------- #
#  Laufzeit
# --------------------------------------------------------------------------- #
def laufzeit_fehlt() -> list[str]:
    """Welche Laufzeit-Pakete fehlen oder sind zu alt? Leer = Big kann rechnen. ``torch (CUDA)``:
    torch ist da, aber ohne CUDA, obwohl die Grafikkarte reicht."""
    fehlt = [m for m in _MODULE if importlib.util.find_spec(m) is None] + beenara.zu_alt(PAKETE)
    if "torch" not in fehlt and torch_ohne_cuda():
        fehlt.append("torch (CUDA)")
    return fehlt


def warum_nicht(cfg) -> str | None:
    """Warum Big gerade nicht mitsortiert — ``None`` heißt: bereit.
    ``aus`` · ``modell`` · ``version`` · ``laufzeit`` wie bei :func:`pollysort.beenara.warum_nicht`."""
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


def installationsbefehle() -> list[list[str]] | None:
    """Wie die Laufzeit in genau die Umgebung kommt, in der PollySort läuft: erst torch, allein aus
    dem PyTorch-Index (CUDA passend zum Treiber; eine CPU-Fassung wird dabei ersetzt), dann der
    Rest von PyPI — der lässt das passende torch stehen. ``None``: weder pip noch uv.

    pip, wenn vorhanden (venv, pipx); sonst ``uv pip --python`` (uv-Tool-Umgebungen haben kein pip)."""
    url = f"https://download.pytorch.org/whl/{cuda_index()}"
    torch_spez, rest = PAKETE[0], list(PAKETE[1:])
    tauschen = importlib.util.find_spec("torch") is not None and torch_ohne_cuda()
    noetig = importlib.util.find_spec("torch") is None or tauschen or bool(beenara.zu_alt(PAKETE[:1]))
    if importlib.util.find_spec("pip") is not None:
        basis = [sys.executable, "-m", "pip", "install", "--quiet"]
        if sys.prefix == sys.base_prefix:
            basis.append("--user")
        tausch = ["--force-reinstall", "--no-deps"] if tauschen else []
    elif uv := shutil.which("uv"):
        basis = [uv, "pip", "install", "--quiet", "--python", sys.executable]
        tausch = ["--reinstall-package", "torch"] if tauschen else []
    else:
        return None
    befehle = [[*basis, *tausch, "--index-url", url, torch_spez]] if noetig else []
    return [*befehle, [*basis, *rest]]


def laufzeit_installieren(con) -> bool:
    """Fehlende Laufzeit-Pakete installieren. ``True`` = danach alles da."""
    fehlt = laufzeit_fehlt()
    if not fehlt:
        return True
    befehle = installationsbefehle()
    if befehle is None:
        con.error(i18n.t("bn.rt.manual", pakete=" ".join(PAKETE)))
        return False
    # Ist torch schon in diesem Prozess geladen, rechnet er bis zum Neustart mit der alten Fassung.
    neu_starten = "torch" in sys.modules and torch_ohne_cuda()
    con.bloom(i18n.t("bb.rt.installing", pakete=", ".join(fehlt)), "📦")
    for befehl in befehle:
        try:
            r = subprocess.run(befehl, capture_output=True, text=True, timeout=3600)
        except KeyboardInterrupt:
            con.raw("")
            con.info(i18n.t("bb.interrupted"), "⏸️")
            return False
        except (OSError, subprocess.TimeoutExpired) as exc:
            con.error(i18n.t("bn.rt.failed", err=beenara._kurz(exc), cmd=" ".join(befehl)))
            return False
        if r.returncode != 0:
            letzte = ((r.stderr or "") + (r.stdout or "")).strip().splitlines()
            con.error(i18n.t("bn.rt.failed", err=letzte[-1] if letzte else f"Code {r.returncode}",
                             cmd=" ".join(befehl)))
            return False
    importlib.invalidate_caches()
    if laufzeit_fehlt() or neu_starten:
        con.info(i18n.t("bn.rt.restart"), "🔁")
        return False
    con.honey(i18n.t("bb.rt.done"), "✅")
    return True


# --------------------------------------------------------------------------- #
#  Laden, öffnen
# --------------------------------------------------------------------------- #
def laden(con, *, client=None) -> bool:
    """Big herunterladen, fortsetzen oder aktualisieren — erst prüfen, ob die GPU reicht.
    Fehler und Strg-C werden gemeldet statt geworfen, Halbfertiges bleibt für das nächste Mal."""
    grund = gpu_grund()
    if grund is not None:
        karten = gpus()
        con.error(i18n.t(f"bb.gpu.{grund}", mb=max((k["mb"] for k in karten), default=0),
                         need=MIN_VRAM_MB, env=CPU_ERLAUBT))
        return False
    ok = (beenara.laden_quelle(con, quelle_big(), ordner(), client=client)
          and beenara.laden_quelle(con, quelle_basis(), basis_ordner(), client=client))
    if ok:
        schliessen()
    return ok


def einrichten(con, *, client=None) -> bool:
    """Alles, was Big zum Sortieren braucht: Big-Teil und Basismodell, dann die Laufzeit.
    Das ist ``beenara big laden`` und der Knopf in der Werkstatt."""
    return laden(con, client=client) and laufzeit_installieren(con)


_SITZUNGEN: dict[str, object] = {}
_SPERRE = threading.Lock()


def oeffnen():
    """Das Modell öffnen — einmal je Prozess, denn Laden dauert je nach Platte bis zu einer
    Minute. Wirft, wenn Laufzeit oder Modell kaputt sind; der Sortierlauf meldet das und macht
    ohne Big weiter."""
    with _SPERRE:
        schluessel = str(ordner())
        if schluessel not in _SITZUNGEN:
            from .beenara_big_laufzeit import BeeNaraBig
            # Auf der Grafikkarte nur, wenn sie reicht — mit der CPU-Erlaubnis und einer zu
            # kleinen Karte lieber langsam als ein Abbruch mitten im Lauf (Speicher voll).
            _SITZUNGEN[schluessel] = BeeNaraBig(ordner(), base=str(basis_ordner()),
                                                device=None if gpu_reicht() else "cpu",
                                                threads=beenara.threads())
        return _SITZUNGEN[schluessel]


def schliessen() -> None:
    with _SPERRE:
        _SITZUNGEN.clear()


def ist_offen() -> bool:
    with _SPERRE:
        return str(ordner()) in _SITZUNGEN


def bericht(cfg) -> list[tuple[str, str, str]]:
    """Der Stand als Zeilen ``(art, emoji, text)`` — wie :func:`pollysort.beenara.bericht`."""
    s = stand()
    zeilen: list[tuple[str, str, str]] = []
    if s.vollstaendig:
        zeilen.append(("honey", "✅", i18n.t("bb.status.ok", version=s.version, mb=s.mb, path=s.pfad)))
    elif s.angefangen:
        zeilen.append(("ask", "❓", i18n.t("bb.status.partial")))
    else:
        zeilen.append(("info", "⬇️", i18n.t("bb.status.none", repo=REPO, mb=UNGEFAEHR_MB)))
    karten = gpus()
    if karten:
        k = max(karten, key=lambda x: x["mb"])
        zeilen.append(("info", "🖥️", i18n.t("bb.gpu.ok", name=k["name"], mb=k["mb"])))
    gpu = gpu_grund()
    if gpu is not None and not s.vollstaendig:
        zeilen.append(("ask", "❓", i18n.t(f"bb.gpu.{gpu}", mb=max((k["mb"] for k in karten), default=0),
                                           need=MIN_VRAM_MB, env=CPU_ERLAUBT)))
    grund = warum_nicht(cfg)
    if grund is None:
        zeilen.append(("honey", "⚡", i18n.t("bb.active.ja")))
        zeilen.append(("info", "⚙️", i18n.t("bb.geraet.gpu" if auf_gpu() else "bb.geraet.cpu")))
    elif grund == "version":
        zeilen.append(("ask", "❓", i18n.t("bb.active.version", have=s.version, need=REVISION[:7])))
    elif grund == "laufzeit":
        zeilen.append(("ask", "❓", i18n.t("bb.active.laufzeit", pakete=", ".join(laufzeit_fehlt()))))
    elif grund == "aus":
        zeilen.append(("info", "💤", i18n.t("bn.active.aus")))
    modus = getattr(cfg, "beenara_modell", "auto")
    zeilen.append(("info", "🔀", i18n.t(f"bb.modus.{modus}")))
    return zeilen

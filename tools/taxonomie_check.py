#!/usr/bin/env python3
"""Prüft, ob PollySort für die Testprojekte eine *saubere* Ordnerstruktur vorschlägt.

Der Fehler, um den es geht: Weil jedes Dokument einzeln analysiert wird, entstehen
überlappende Kategorien — „Rechnungen" **und** „Finanzen", obwohl es nur Rechnungen gibt.
Umgekehrt sollen echte Untergruppen (Rechnungen · Reisekosten · Kontoauszüge) sehr wohl
getrennt bleiben. Genau diese beiden Seiten misst dieses Skript.

    python tools/taxonomie_check.py                      # offline (schnell, kostenlos)
    python tools/taxonomie_check.py --modus ollama       # lokal mit qwen3.5:9b
    python tools/taxonomie_check.py --modus ollama --szenario 01-nur-rechnungen

Exit-Code 0 = alle Szenarien bestanden, 1 = mindestens eines nicht.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Windows-Pipes laufen als cp1252 — Haken und Kreuze würden dort die Ausgabe
# sprengen. Wie in der REPL: auf UTF-8 stellen, sonst auf ASCII ausweichen.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pollysort import config  # noqa: E402
from pollysort.llm import build_client  # noqa: E402
from pollysort.onboarding import propose_structure  # noqa: E402


# --------------------------------------------------------------------------- #
#  Bewertung
# --------------------------------------------------------------------------- #
def _trifft(label: str, begriffe: list[str]) -> bool:
    """Meint dieses Kategorie-Label eines der Begriffe? (Wortstamm-Vergleich)"""
    lab = label.strip().lower()
    return any(b in lab or lab in b for b in begriffe)


def bewerte(kategorien: list[str], erwartung: dict) -> list[tuple[bool, str]]:
    """Alle Regeln gegen die vorgeschlagenen Kategorien prüfen. [(bestanden, Text)]"""
    ergebnis: list[tuple[bool, str]] = []
    n = len(kategorien)

    lo, hi = erwartung["min_kategorien"], erwartung["max_kategorien"]
    ergebnis.append((lo <= n <= hi, f"Anzahl Kategorien {n} (erwartet {lo}–{hi})"))

    for gruppe in erwartung.get("muss_abdecken", []):
        getroffen = [k for k in kategorien if _trifft(k, gruppe)]
        ergebnis.append((bool(getroffen),
                         f"abgedeckt: {'/'.join(gruppe[:2])} → "
                         f"{', '.join(getroffen) if getroffen else 'FEHLT'}"))

    for links, rechts in erwartung.get("verboten_zusammen", []):
        a = [k for k in kategorien if _trifft(k, links)]
        b = [k for k in kategorien if _trifft(k, rechts)]
        doppelt = bool(a) and bool(b) and set(a) != set(b)
        ergebnis.append((not doppelt,
                         f"keine Dopplung {'/'.join(links[:2])} × {'/'.join(rechts[:2])}"
                         + (f" → BEIDE da: {', '.join(a)} | {', '.join(b)}" if doppelt else "")))
    return ergebnis


# --------------------------------------------------------------------------- #
#  Ein Szenario laufen lassen
# --------------------------------------------------------------------------- #
class _Analyse:
    """Zählende Analyse-Funktion (Datei → (kategorie, keywords)) wie im echten Setup."""

    def __init__(self, client):
        self._client = client
        self.ok = 0
        self.errors = 0
        self.last_reason = ""

    def __call__(self, finding):
        from pollysort.extractor import extract
        from pollysort.models import Status
        a, status, reason = extract(finding, self._client, max_file_mb=100)
        if status != Status.INDEXED:
            self.errors += 1
            self.last_reason = str(reason or "Analyse fehlgeschlagen")
            raise RuntimeError(self.last_reason)
        self.ok += 1
        return a.kategorie, list(a.keywords)


def pruefe(ordner: Path, erwartung: dict, *, modus: str, stichprobe: int) -> tuple[bool, dict]:

    cfg = config.load_config()
    cfg.llm_provider = modus
    api_key = config.load_credentials() if modus == "openrouter" else None
    analyse = None
    if modus != "offline":
        analyse = _Analyse(build_client(cfg, api_key, [], []))

    start = time.time()
    vorschlaege, gescannt, ki, _vorhanden, protokoll = propose_structure(
        ordner, ai_analyze=analyse, ai_sample=stichprobe)
    dauer = time.time() - start

    kategorien = [k for k, _ in vorschlaege]
    checks = bewerte(kategorien, erwartung)
    bestanden = all(ok for ok, _ in checks)

    return bestanden, {
        "kategorien": vorschlaege, "checks": checks, "dauer": dauer,
        "gescannt": gescannt, "ki": ki, "beschreibung": erwartung["beschreibung"],
        "protokoll": protokoll,
        "fehler": getattr(analyse, "errors", 0), "ok": getattr(analyse, "ok", 0),
    }


# --------------------------------------------------------------------------- #
#  Ausgabe
# --------------------------------------------------------------------------- #
GRUEN, ROT, GELB, GRAU, AUS = "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[0m"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ziel", default="test projekte")
    ap.add_argument("--modus", default="offline", choices=["offline", "ollama", "openrouter"])
    ap.add_argument("--szenario", default=None, help="nur dieses Szenario prüfen")
    ap.add_argument("--stichprobe", type=int, default=15,
                    help="wie viele Dokumente die KI ansieht (Default 15)")
    args = ap.parse_args()

    wurzel = Path(args.ziel).expanduser().resolve()
    if not wurzel.is_dir():
        print(f"{ROT}Ordner nicht gefunden: {wurzel}{AUS}")
        print("Erst erzeugen:  python tools/testprojekte.py")
        return 2

    erwartungen_datei = wurzel / "erwartungen.json"
    if not erwartungen_datei.exists():
        print(f"{ROT}erwartungen.json fehlt in {wurzel}{AUS}")
        print("Erst erzeugen:  python tools/testprojekte.py")
        return 2
    erwartungen = json.loads(erwartungen_datei.read_text(encoding="utf-8"))

    ordner = sorted(p for p in wurzel.iterdir() if p.is_dir() and p.name in erwartungen)
    if args.szenario:
        ordner = [p for p in ordner if p.name == args.szenario]
    if not ordner:
        print(f"{ROT}Keine Szenarien gefunden.{AUS}")
        return 2

    print(f"\n  Taxonomie-Prüfung · Modus {GELB}{args.modus}{AUS} · "
          f"{len(ordner)} Szenario(en)\n")
    if args.modus == "ollama":
        from pollysort.llm.client import OLLAMA_MODEL, ollama_available
        if not ollama_available():
            print(f"{ROT}  Kein lokaler Ollama-Server erreichbar (ollama serve).{AUS}\n")
            return 2
        print(f"{GRAU}  Modell: {OLLAMA_MODEL}{AUS}\n")

    gesamt_ok = True
    for p in ordner:
        ok, r = pruefe(p, erwartungen[p.name], modus=args.modus,
                       stichprobe=args.stichprobe)
        gesamt_ok &= ok
        kopf = f"{GRUEN}BESTANDEN{AUS}" if ok else f"{ROT}DURCHGEFALLEN{AUS}"
        print(f"  {p.name}  [{kopf}]   {GRAU}{r['dauer']:.1f}s{AUS}")
        print(f"  {GRAU}{r['beschreibung']}{AUS}")
        labels = ", ".join(f"{k} ({n})" for k, n in r["kategorien"])
        print(f"    Vorschlag: {labels}")
        for zeile in r["protokoll"]:
            print(f"    {GRAU}zusammengelegt: {zeile}{AUS}")
        if r["fehler"]:
            print(f"    {GELB}{r['fehler']} KI-Analyse(n) fehlgeschlagen, "
                  f"{r['ok']} erfolgreich{AUS}")
        for c_ok, text in r["checks"]:
            zeichen = f"{GRUEN}✓{AUS}" if c_ok else f"{ROT}✗{AUS}"
            print(f"    {zeichen} {text}")
        print()

    if gesamt_ok:
        print(f"  {GRUEN}Alle Szenarien bestanden.{AUS}\n")
        return 0
    print(f"  {ROT}Mindestens ein Szenario ist durchgefallen.{AUS}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

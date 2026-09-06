"""Der wachsende Bienenstock — Fortschritt sichtbar machen.

Aufräumen ist undankbar: Man sieht erst etwas, wenn man fertig ist, und dann sieht man
nichts mehr. Dieses Modul macht den Weg dorthin sichtbar — Stufen, Abzeichen, Serien.

**Was hier bewusst NICHT passiert:** Es gibt keine Punkte fürs Starten des Programms,
keine täglichen Anmelde-Belohnungen, keine Erinnerungen mit schlechtem Gewissen und
nichts, was künstlich verknappt wird. Jeder Punkt steht für ein Dokument, das wirklich
einsortiert wurde, oder für eine Regel, die das Werkzeug wirklich gelernt hat. Eine
Fortschrittsanzeige, die lügt, ist schlimmer als gar keine.

Der Stand liegt pro Projekt in ``.honig/spiel.json`` — wie alles Generierte.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from . import i18n

# --------------------------------------------------------------------------- #
#  Stufen
# --------------------------------------------------------------------------- #
#: (ab wie vielen sortierten Dokumenten, Schlüssel). Die Schwellen wachsen bewusst
#: langsam an: Die ersten Stufen sollen an einem Nachmittag erreichbar sein, die
#: letzte darf Monate dauern.
STUFEN: list[tuple[int, str]] = [
    (0, "schwarm"),
    (10, "jung"),
    (50, "summend"),
    (150, "stark"),
    (400, "golden"),
    (1000, "legendaer"),
]


def stufe_fuer(dokumente: int) -> tuple[int, str]:
    """(Index, Schlüssel) der erreichten Stufe."""
    erreicht = 0
    for i, (schwelle, _) in enumerate(STUFEN):
        if dokumente >= schwelle:
            erreicht = i
    return erreicht, STUFEN[erreicht][1]


def naechste_stufe(dokumente: int) -> tuple[int, int] | None:
    """(noch nötige Dokumente, Schwelle der nächsten Stufe) — oder None bei Maximum."""
    for schwelle, _ in STUFEN:
        if dokumente < schwelle:
            return schwelle - dokumente, schwelle
    return None


# --------------------------------------------------------------------------- #
#  Abzeichen
# --------------------------------------------------------------------------- #
#: Schlüssel → Bedingung. Jede Bedingung prüft NUR echte Arbeit.
ABZEICHEN: dict[str, str] = {
    "erste_wabe": "erstes Dokument einsortiert",
    "zehn": "10 Dokumente einsortiert",
    "hundert": "100 Dokumente einsortiert",
    "lehrmeister": "erste Korrektur beigebracht",
    "weise": "5 gelernte Regeln auf der Wachstafel",
    "blitzblank": "Posteingang komplett leer geräumt",
    "serie": "7 Tage in Folge aufgeräumt",
    "vielfalt": "6 verschiedene Waben gefüllt",
}


@dataclass
class Stand:
    """Der Fortschritt eines Bienenstocks. Reine Zählwerte, keine Dokumentinhalte."""

    dokumente: int = 0
    korrekturen: int = 0
    regeln: int = 0
    waben: int = 0
    serie: int = 0
    letzter_tag: str = ""
    abzeichen: list[str] = field(default_factory=list)

    @property
    def stufe(self) -> str:
        return stufe_fuer(self.dokumente)[1]


# --------------------------------------------------------------------------- #
#  Laden & Speichern
# --------------------------------------------------------------------------- #
def _pfad(hive: Path) -> Path:
    from .config import honig
    return honig(hive) / "spiel.json"


def laden(hive: Path) -> Stand:
    """Den Stand lesen. Eine kaputte Datei kostet nie mehr als den Fortschritt."""
    p = _pfad(hive)
    try:
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                bekannt = {f for f in Stand().__dict__}
                return Stand(**{k: v for k, v in d.items() if k in bekannt})
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return Stand()


def speichern(hive: Path, stand: Stand) -> None:
    p = _pfad(hive)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(stand), ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass          # Fortschritt ist nett, aber nie wichtiger als der Sortierlauf


# --------------------------------------------------------------------------- #
#  Fortschreiben
# --------------------------------------------------------------------------- #
def _serie_fortschreiben(stand: Stand, heute: date) -> None:
    """Tagesserie pflegen: gestern → +1, heute → unverändert, älter → zurück auf 1."""
    heute_iso = heute.isoformat()
    if stand.letzter_tag == heute_iso:
        return
    try:
        vorher = date.fromisoformat(stand.letzter_tag) if stand.letzter_tag else None
    except ValueError:
        vorher = None
    stand.serie = stand.serie + 1 if vorher and (heute - vorher).days == 1 else 1
    stand.letzter_tag = heute_iso


def nach_lauf(hive: Path, *, sortiert: int = 0, korrekturen: int = 0, regeln: int | None = None,
              waben: int | None = None, eingang_leer: bool = False,
              heute: date | None = None) -> tuple[Stand, list[str], bool]:
    """Den Stand nach einem Sortierlauf fortschreiben.

    Gibt ``(stand, neue_abzeichen, stufe_aufgestiegen)`` zurück — der Aufrufer feiert.
    Ohne echte Arbeit (``sortiert`` und ``korrekturen`` beide 0) ändert sich **nichts**:
    Wer nur zuschaut, sammelt nichts ein.
    """
    stand = laden(hive)
    vorher_stufe = stufe_fuer(stand.dokumente)[0]

    if sortiert <= 0 and korrekturen <= 0:
        return stand, [], False

    stand.dokumente += max(0, sortiert)
    stand.korrekturen += max(0, korrekturen)
    if regeln is not None:
        stand.regeln = max(stand.regeln, regeln)
    if waben is not None:
        stand.waben = max(stand.waben, waben)
    _serie_fortschreiben(stand, heute or datetime.now(UTC).date())

    verdient = {
        "erste_wabe": stand.dokumente >= 1,
        "zehn": stand.dokumente >= 10,
        "hundert": stand.dokumente >= 100,
        "lehrmeister": stand.korrekturen >= 1,
        "weise": stand.regeln >= 5,
        "blitzblank": eingang_leer and sortiert > 0,
        "serie": stand.serie >= 7,
        "vielfalt": stand.waben >= 6,
    }
    neu = [k for k, ok in verdient.items() if ok and k not in stand.abzeichen]
    stand.abzeichen.extend(neu)

    speichern(hive, stand)
    return stand, neu, stufe_fuer(stand.dokumente)[0] > vorher_stufe


# --------------------------------------------------------------------------- #
#  Anzeige
# --------------------------------------------------------------------------- #
def balken(anteil: float, breite: int = 18) -> str:
    """Ein Fortschrittsbalken aus Wabenzeichen."""
    anteil = max(0.0, min(1.0, anteil))
    voll = round(anteil * breite)
    return "▓" * voll + "░" * (breite - voll)


def uebersicht(stand: Stand) -> list[str]:
    """Mehrzeilige Fortschritts-Anzeige (fertig formatiert, ohne Emoji-Präfix)."""
    idx, schluessel = stufe_fuer(stand.dokumente)
    zeilen = [i18n.t(f"spiel.stufe.{schluessel}") + f"  ({i18n.t('spiel.stufe')} {idx + 1}/{len(STUFEN)})"]

    weiter = naechste_stufe(stand.dokumente)
    if weiter:
        fehlt, schwelle = weiter
        von = STUFEN[idx][0]
        anteil = (stand.dokumente - von) / max(1, schwelle - von)
        zeilen.append(f"{balken(anteil)}  {stand.dokumente}/{schwelle}  "
                      + i18n.t("spiel.bis_naechste", n=fehlt))
    else:
        zeilen.append(f"{balken(1.0)}  {stand.dokumente}  " + i18n.t("spiel.maximum"))

    zeilen.append(i18n.t("spiel.zahlen", dokumente=stand.dokumente, waben=stand.waben,
                         regeln=stand.regeln, serie=stand.serie))
    if stand.abzeichen:
        namen = " · ".join(i18n.t(f"spiel.abzeichen.{a}") for a in stand.abzeichen)
        zeilen.append(i18n.t("spiel.abzeichen_titel", n=len(stand.abzeichen),
                             gesamt=len(ABZEICHEN)) + "  " + namen)
    return zeilen

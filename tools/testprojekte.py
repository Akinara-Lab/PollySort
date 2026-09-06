#!/usr/bin/env python3
"""Erzeugt reproduzierbare Testprojekte für die Taxonomie-Prüfung.

Warum generiert statt eingecheckt: Die Dokumente sollen jederzeit identisch neu entstehen
können, ohne dass ein paar hundert Textschnipsel im Repository liegen. Der Generator und
die Erwartungen sind getrackt, die erzeugten Ordner nicht (`.gitignore`).

    python tools/testprojekte.py                 # nach "test projekte/" schreiben
    python tools/testprojekte.py --ziel <pfad>   # woanders hin
    python tools/testprojekte.py --neu           # vorhandene Projekte vorher wegräumen

Die Dokumente tragen **bewusst keine verräterischen Präfixe**: Die Zuordnung muss allein
über den Inhalt gelingen, sonst misst der Test die Dateinamen statt das Modell.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

# --------------------------------------------------------------------------- #
#  Bausteine
# --------------------------------------------------------------------------- #
FIRMEN = ["Telekom Deutschland GmbH", "Stadtwerke Musterstadt AG", "Bürobedarf Krämer e.K.",
          "CloudHost Systems GmbH", "Reinigung Sauber & Söhne", "Fahrzeugservice Nord GmbH",
          "Druckerei Lindqvist", "IT-Systemhaus Waldmann", "Catering Rosenthal",
          "Versicherungskammer Sued", "Möbelwerk Hansen", "Energieversorgung Ost AG",
          "Papierwaren Bittner", "Logistik Sandmann GmbH"]

MITARBEITER = ["Anna Petrov", "Jonas Bergmann", "Leyla Demir", "Mark Osei",
               "Sofia Ricci", "Tobias Kellner"]


def rechnung(i: int) -> tuple[str, str]:
    firma = FIRMEN[i % len(FIRMEN)]
    nr = 40000 + i * 137
    betrag = 89.9 + i * 47.35
    monat = (i % 12) + 1
    return (f"dok_{i:03d}.txt", f"""{firma}
Musterstraße {10 + i}, 12345 Musterstadt

RECHNUNG Nr. R-{nr}
Rechnungsdatum: 2026-{monat:02d}-{(i % 27) + 1:02d}
Leistungszeitraum: 2026-{monat:02d}

Position 1: Leistung laut Vertrag           {betrag:.2f} EUR
Umsatzsteuer 19 %                            {betrag * 0.19:.2f} EUR
------------------------------------------------
Rechnungsbetrag                              {betrag * 1.19:.2f} EUR

Zahlbar ohne Abzug bis zum 2026-{monat:02d}-{min((i % 27) + 15, 28):02d}.
Bitte geben Sie bei der Überweisung die Rechnungsnummer an.
USt-IdNr. DE{200000000 + i}
""")


def spesenabrechnung(i: int) -> tuple[str, str]:
    person = MITARBEITER[i % len(MITARBEITER)]
    tage = 2 + (i % 4)
    km = 120 + i * 33
    return (f"dok_{i:03d}.txt", f"""REISEKOSTENABRECHNUNG

Mitarbeiterin/Mitarbeiter: {person}
Personalnummer: {5000 + i}
Kostenstelle: {300 + (i % 5)}
Reisezweck: Kundentermin und Projektabstimmung
Reisezeitraum: {tage} Tage

Verpflegungsmehraufwand ({tage} Tage x 28,00 EUR)   {tage * 28:.2f} EUR
Fahrtkosten eigener PKW ({km} km x 0,30 EUR)        {km * 0.30:.2f} EUR
Übernachtung laut Beleg                             {tage * 89:.2f} EUR

Erstattungsbetrag zur Auszahlung mit der nächsten Gehaltsabrechnung.
Genehmigt durch die Abteilungsleitung.
""")


def kontoauszug(i: int) -> tuple[str, str]:
    monat = (i % 12) + 1
    return (f"dok_{i:03d}.txt", f"""Sparkasse Musterstadt
KONTOAUSZUG Nr. {monat}/2026

Kontoinhaber: Muster Handels GmbH
IBAN: DE89 3704 0044 0532 0130 {i:02d}
Auszugsdatum: 2026-{monat:02d}-28

Alter Kontostand                        {12000 + i * 310:.2f} EUR
Summe Gutschriften                       {4300 + i * 95:.2f} EUR
Summe Lastschriften                      {3100 + i * 77:.2f} EUR
Neuer Kontostand                        {13200 + i * 328:.2f} EUR

Einzelumsätze siehe Anlage. Bitte prüfen Sie die Buchungen innerhalb von sechs Wochen.
""")


def arbeitsvertrag(i: int) -> tuple[str, str]:
    person = MITARBEITER[i % len(MITARBEITER)]
    return (f"dok_{i:03d}.txt", f"""ARBEITSVERTRAG

zwischen der Muster Handels GmbH, vertreten durch die Geschäftsführung,
und {person}, wohnhaft in Musterstadt.

§ 1 Tätigkeit
Die Mitarbeiterin/der Mitarbeiter wird als Fachkraft im Bereich Vertrieb eingestellt.

§ 2 Beginn und Probezeit
Das Arbeitsverhältnis beginnt am 2026-{(i % 12) + 1:02d}-01. Die Probezeit beträgt sechs Monate.

§ 3 Vergütung
Das monatliche Bruttogehalt beträgt {3800 + i * 210} EUR, zahlbar zum Monatsende.

§ 4 Kündigungsfrist
Die Kündigungsfrist beträgt drei Monate zum Quartalsende.

§ 5 Urlaub
Der Urlaubsanspruch beträgt 30 Arbeitstage pro Kalenderjahr.
""")


def mietvertrag(i: int) -> tuple[str, str]:
    return (f"dok_{i:03d}.txt", f"""GEWERBEMIETVERTRAG

Vermieter: Immobilien Hartmann KG
Mieter: Muster Handels GmbH

§ 1 Mietgegenstand
Büroflächen im Objekt Musterstraße {20 + i}, insgesamt {180 + i * 25} qm.

§ 2 Mietzeit
Das Mietverhältnis beginnt am 2026-01-01 und läuft auf unbestimmte Zeit.

§ 3 Miete
Die monatliche Nettokaltmiete beträgt {2400 + i * 190} EUR zuzüglich Nebenkosten.

§ 4 Kündigung
Die Kündigungsfrist beträgt sechs Monate zum Quartalsende.
Eine Kündigung bedarf der Schriftform.
""")


def protokoll(i: int) -> tuple[str, str]:
    monat = (i % 12) + 1
    return (f"dok_{i:03d}.txt", f"""PROTOKOLL DER TEAMSITZUNG

Datum: 2026-{monat:02d}-{(i % 27) + 1:02d}
Ort: Besprechungsraum 2
Teilnehmende: {", ".join(MITARBEITER[: 3 + (i % 3)])}

TOP 1 — Rückblick
Der Projektstand wurde vorgestellt. Die Meilensteine des Vorquartals sind erreicht.

TOP 2 — Offene Punkte
Die Abstimmung mit dem Dienstleister steht noch aus.
Verantwortlich: {MITARBEITER[i % len(MITARBEITER)]}, Frist: Ende des Monats.

TOP 3 — Beschlüsse
Das Team beschließt, den wöchentlichen Termin auf Dienstag zu verlegen.

Nächste Sitzung: {(monat % 12) + 1:02d}/2026.
""")


def schriftverkehr(i: int) -> tuple[str, str]:
    firma = FIRMEN[i % len(FIRMEN)]
    return (f"dok_{i:03d}.txt", f"""Muster Handels GmbH
An: {firma}

Betreff: Ihre Anfrage vom vergangenen Monat

Sehr geehrte Damen und Herren,

vielen Dank für Ihr Schreiben. Wir bestätigen den Eingang Ihrer Unterlagen und
haben die Angelegenheit an die zuständige Abteilung weitergeleitet.

Für Rückfragen stehen wir Ihnen gern zur Verfügung. Eine abschließende Antwort
erhalten Sie innerhalb der nächsten zwei Wochen.

Mit freundlichen Grüßen
Muster Handels GmbH
""")


def versicherung(i: int) -> tuple[str, str]:
    return (f"dok_{i:03d}.txt", f"""Versicherungskammer Sued
VERSICHERUNGSSCHEIN

Versicherungsnummer: VS-{700000 + i * 31}
Versicherungsnehmer: Muster Handels GmbH
Sparte: Betriebshaftpflichtversicherung

Versicherungsbeginn: 2026-01-01
Versicherungssumme: {2000000 + i * 100000} EUR pauschal
Jahresbeitrag: {840 + i * 65:.2f} EUR

Der Vertrag verlängert sich jeweils um ein Jahr, sofern er nicht drei Monate
vor Ablauf schriftlich gekündigt wird.
""")


def steuerbescheid(i: int) -> tuple[str, str]:
    return (f"dok_{i:03d}.txt", f"""FINANZAMT MUSTERSTADT
Steuernummer: 123/456/{7890 + i}

BESCHEID über Körperschaftsteuer {2024 + (i % 3)}

Festgesetzte Körperschaftsteuer            {8400 + i * 320:.2f} EUR
Bereits geleistete Vorauszahlungen         {7900 + i * 300:.2f} EUR
------------------------------------------------
Nachzahlung                                 {500 + i * 20:.2f} EUR

Der Betrag ist innerhalb eines Monats nach Bekanntgabe fällig.
Rechtsbehelfsbelehrung: Gegen diesen Bescheid kann innerhalb eines Monats
Einspruch eingelegt werden.
""")


# --------------------------------------------------------------------------- #
#  Szenarien
# --------------------------------------------------------------------------- #
#: Jedes Szenario: Dokumente + was eine gute Taxonomie leisten muss.
#:
#: `verboten_zusammen` ist der Kern der Prüfung: Diese Begriffsfelder dürfen NICHT
#: gleichzeitig als eigene Kategorien auftauchen, weil sie hier dieselben Dokumente
#: meinen würden — genau der Doppelordner-Fehler ("Rechnungen" UND "Finanzen",
#: obwohl es nur Rechnungen gibt).
SZENARIEN: dict[str, dict] = {
    "01-nur-rechnungen": {
        "beschreibung": "Ausschließlich Eingangsrechnungen. Eine einzige Kategorie ist richtig.",
        "dokumente": [(rechnung, 14)],
        "erwartung": {
            "min_kategorien": 1,
            "max_kategorien": 2,
            "muss_abdecken": [["rechnung", "eingangsrechnung", "beleg"]],
            "verboten_zusammen": [
                [["rechnung", "eingangsrechnung"], ["finanz", "buchhaltung", "buchführung"]],
                [["rechnung", "eingangsrechnung"], ["beleg", "belege"]],
            ],
        },
    },
    "02-finanzen-gemischt": {
        "beschreibung": ("Rechnungen, Reisekostenabrechnungen und Kontoauszüge. Drei klar "
                         "unterscheidbare Gruppen — hier sind mehrere Kategorien richtig."),
        "dokumente": [(rechnung, 6), (spesenabrechnung, 5), (kontoauszug, 5)],
        "erwartung": {
            "min_kategorien": 2,
            "max_kategorien": 4,
            "muss_abdecken": [
                ["rechnung", "eingangsrechnung"],
                ["reisekosten", "spesen", "abrechnung", "personal"],
                ["kontoauszug", "kontoauszuege", "bank", "konto"],
            ],
            "verboten_zusammen": [
                [["rechnung"], ["eingangsrechnung"]],
            ],
        },
    },
    "03-kanzlei": {
        "beschreibung": "Verträge, Protokolle, Schriftverkehr und ein paar Rechnungen.",
        "dokumente": [(arbeitsvertrag, 4), (mietvertrag, 3), (protokoll, 4),
                      (schriftverkehr, 4), (rechnung, 3)],
        "erwartung": {
            "min_kategorien": 3,
            "max_kategorien": 6,
            "muss_abdecken": [
                ["vertrag", "vertraege", "verträge"],
                ["protokoll", "sitzung", "besprechung"],
                ["schriftverkehr", "korrespondenz", "brief", "post"],
            ],
            "verboten_zusammen": [
                [["vertrag", "vertraege"], ["arbeitsvertrag"]],
                [["vertrag", "vertraege"], ["mietvertrag"]],
            ],
        },
    },
    "04-gemischtes-buero": {
        "beschreibung": ("Breite Mischung: Rechnungen, Verträge, Versicherungen, Steuer, "
                         "Protokolle. Der Härtefall für saubere Abgrenzung."),
        "dokumente": [(rechnung, 5), (mietvertrag, 3), (versicherung, 4),
                      (steuerbescheid, 4), (protokoll, 3), (schriftverkehr, 3)],
        "erwartung": {
            "min_kategorien": 4,
            "max_kategorien": 7,
            "muss_abdecken": [
                ["rechnung", "eingangsrechnung"],
                ["versicherung", "police"],
                ["steuer", "finanzamt", "bescheid"],
                # Gewerbemietverträge dürfen auch unter "Immobilien" landen — das ist
                # keine Fehlablage, sondern eine zweite vertretbare Sicht. Deutsche
                # Komposita stellen den Dokumenttyp ohnehin ans Ende
                # ("Gewerbemiet-VERTRAG"), das Thema an den Anfang.
                ["vertrag", "vertraege", "verträge", "immobilien", "miete"],
            ],
            "verboten_zusammen": [
                [["steuer", "finanzamt"], ["finanz", "buchhaltung"]],
                [["rechnung"], ["beleg", "belege"]],
            ],
        },
    },
}


def erzeuge(ziel: Path, *, neu: bool = False) -> list[Path]:
    ziel.mkdir(parents=True, exist_ok=True)
    angelegt: list[Path] = []
    # Die Erwartungen liegen bewusst NEBEN den Szenario-Ordnern, nicht darin: alles in
    # einem Projektordner ist für PollySort ein zu sortierendes Dokument — eine
    # erwartung.json darin würde sich selbst mitzählen und das Ergebnis verfälschen.
    erwartungen: dict[str, dict] = {}
    for name, szenario in SZENARIEN.items():
        ordner = ziel / name
        if neu and ordner.exists():
            shutil.rmtree(ordner)
        ordner.mkdir(parents=True, exist_ok=True)

        i = 0
        for macher, anzahl in szenario["dokumente"]:
            for _ in range(anzahl):
                dateiname, inhalt = macher(i)
                (ordner / dateiname).write_text(inhalt, encoding="utf-8")
                i += 1

        erwartungen[name] = {"beschreibung": szenario["beschreibung"],
                             "dokumente": i, **szenario["erwartung"]}
        angelegt.append(ordner)
        print(f"  {name:<24} {i:>3} Dokument(e)  ·  {szenario['beschreibung'][:52]}…")
    (ziel / "erwartungen.json").write_text(
        json.dumps(erwartungen, ensure_ascii=False, indent=2), encoding="utf-8")
    return angelegt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ziel", default="test projekte", help="Zielordner (Default: 'test projekte')")
    ap.add_argument("--neu", action="store_true", help="vorhandene Szenario-Ordner vorher löschen")
    args = ap.parse_args()

    ziel = Path(args.ziel).expanduser().resolve()
    print(f"\nTestprojekte -> {ziel}\n")
    ordner = erzeuge(ziel, neu=args.neu)
    print(f"\n{len(ordner)} Szenario(en) bereit.")
    print("Prüfen mit:  python tools/taxonomie_check.py --modus ollama\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Gemeinsame Klassifikations-Heuristik (offline, kostenlos).

Wird sowohl vom Offline-LLM-Client (Sortieren ohne Cloud) als auch vom Onboarding-Scanner
(Ordnerstruktur-Vorschlag) genutzt — so greifen vorgeschlagene Kategorien später auch
wirklich beim Sortieren.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

# Schlüsselwörter je Kategorie (deutsch + gängige englische Begriffe).
RULES: dict[str, list[str]] = {
    "rechnungen": ["rechnung", "invoice", "betrag", "zahlung", "ust", "mwst", "quittung",
                   "beleg", "mahnung", "zahlbar", "receipt", "payment", "amount", "skonto",
                   "lieferschein", "gutschrift", "faktura", "billing", "teilzahlung",
                   "ratenzahlung", "kassenbon", "faellig", "fällig"],
    "vertraege": ["vertrag", "vereinbarung", "kündigung", "kuendigung", "agreement",
                  "mietvertrag", "arbeitsvertrag", "contract", "lease", "terms", "klausel",
                  "laufzeit", "unterschrift", "unterzeichnet", "widerruf", "geheimhaltung",
                  "verpflichtung", "konditionen", "signatur", "signature", "kaufvertrag",
                  "dienstvertrag", "nutzungsbedingungen"],
    "protokolle": ["protokoll", "sitzung", "meeting", "beschluss", "tagesordnung", "besprechung",
                   "minutes", "agenda", "teilnehmer", "anwesend", "abstimmung", "votum",
                   "vorstand", "gremium", "niederschrift", "aktennotiz", "gesprächsnotiz",
                   "gespraechsnotiz", "moderator", "wortmeldung"],
    "korrespondenz": ["brief", "schreiben", "anschreiben", "korrespondenz", "letter", "email",
                      "nachricht", "mitteilung", "betreff", "gruesse", "grüße", "antwort",
                      "rückantwort", "rueckantwort", "absender", "empfänger", "empfaenger",
                      "postkarte", "umschlag", "memo"],
    # 'finanzen' war lange ein Sammeltopf: Kontoauszüge, Steuerbescheide und Gehalt
    # landeten alle darin und verschwanden dann als Oberbegriff in der Konsolidierung.
    # Die beiden häufigsten Sorten haben jetzt eigene Kategorien.
    "kontoauszuege": ["kontoauszug", "kontoauszüge", "kontostand", "iban", "saldo",
                      "lastschrift", "lastschriften", "gutschriften", "sparkasse",
                      "kontoinhaber", "buchungen", "einzelumsaetze", "einzelumsätze",
                      "bankleitzahl", "girokonto", "auszugsdatum"],
    "steuer": ["steuer", "steuern", "finanzamt", "steuernummer", "steuerbescheid",
               "koerperschaftsteuer", "körperschaftsteuer", "umsatzsteuervoranmeldung",
               "einkommensteuer", "gewerbesteuer", "vorauszahlungen", "rechtsbehelfsbelehrung",
               "einspruch", "nachzahlung", "veranlagung", "elster"],
    # 'finanzen' behält die spezifischen Begriffe BEWUSST mit: Wer nur eine Kategorie
    # "Finanzen" führt, muss weiterhin einen Steuerbescheid oder Kontoauszug dorthin
    # einsortiert bekommen (snap_category). Welche Kategorie beim freien Klassifizieren
    # gewinnt, entscheidet die Bewertung — die spezifische trägt ihren Namen im Text und
    # bekommt dafür den Namensbonus.
    "finanzen": ["gehalt", "lohn", "bilanz", "buchhaltung", "überweisung", "ueberweisung",
                 "kredit", "darlehen", "zinsen", "sparbuch", "dividende", "aktien", "depot",
                 "budget", "guthaben", "einkommen", "ausgaben", "einnahmen",
                 "kontoauszug", "kontostand", "iban", "saldo",
                 "steuer", "finanzamt", "steuerbescheid"],
    "versicherung": ["versicherung", "police", "schaden", "tarif", "haftpflicht", "rechtsschutz",
                     "deckung", "beitrag", "prämie", "praemie", "selbstbeteiligung", "hausrat",
                     "risiko", "insurance", "policy", "coverage", "claim", "premium", "liability"],
    "bewerbung": ["bewerbung", "lebenslauf", "zeugnis", "motivationsschreiben", "resume",
                  "qualifikation", "berufserfahrung", "arbeitszeugnis", "praktikum", "ausbildung",
                  "bewerber", "personaler", "vorstellungsgespräch", "vorstellungsgespraech",
                  "stellenanzeige", "jobangebot", "application", "applicant", "arbeitgeber"],
    "recherche": ["studie", "analyse", "recherche", "research", "paper", "quelle", "untersuchung",
                  "methodik", "ergebnisse", "auswertung", "literatur", "bibliografie",
                  "bibliographie", "fussnote", "zitat", "abstract", "dissertation", "experiment",
                  "umfrage", "befragung", "statistik", "publikation", "hypothese"],
    "reisen": ["reise", "travel", "flug", "flight", "hotel", "ticket", "boarding", "gepäck",
               "gepaeck", "reservierung", "unterkunft", "urlaub", "itinerary", "abflug",
               "ankunft", "mietwagen", "kreuzfahrt", "visum", "ferienwohnung", "pauschalreise",
               "hostel"],
    "gesundheit": ["medical", "medizin", "arzt", "diagnose", "befund", "rezept", "medikament",
                   "therapie", "behandlung", "patient", "krankenhaus", "klinik", "praxis",
                   "labor", "impfung", "attest", "krankschreibung", "symptom", "prescription",
                   "treatment", "diagnosis"],
    "immobilien": ["immobilie", "grundstück", "grundstueck", "wohnung", "miete", "vermieter",
                   "makler", "exposé", "expose", "quadratmeter", "wohnfläche", "wohnflaeche",
                   "grundbuch", "hypothek", "eigentum", "eigentümer", "eigentuemer",
                   "nebenkosten", "kaution", "grundriss", "bauplan", "property", "mortgage"],
    "spesen": ["spesen", "reisekosten", "reisekostenabrechnung", "verpflegungsmehraufwand",
               "kilometerpauschale", "fahrtkosten", "dienstreise", "kostenstelle",
               "personalnummer", "erstattungsbetrag", "auswaertstaetigkeit", "tagegeld",
               "uebernachtungspauschale", "reisezweck", "expense", "mileage"],
    "kfz": ["fahrzeug", "automobil", "kennzeichen", "zulassung", "hauptuntersuchung",
            "führerschein", "fuehrerschein", "werkstatt", "reparatur", "reifen", "kilometerstand",
            "bußgeld", "bussgeld", "diesel", "benzin", "motorrad", "verkehr", "inspektion"],
}

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic"}
TABLE_EXT = {".csv", ".xlsx", ".xls", ".tsv"}
SLIDE_EXT = {".ppt", ".pptx", ".key", ".odp"}
TYPE_CATEGORY = {"bilder": IMAGE_EXT, "tabellen": TABLE_EXT, "praesentationen": SLIDE_EXT}

_TEXT_SUFFIXES = {".txt", ".md", ".csv", ".log", ".json", ".html", ".htm", ".xml", ".yaml", ".yml"}


def _hit(blob: str, needle: str) -> bool:
    # Treffer nur am Wortanfang (erlaubt Plural/Suffix wie "rechnungen", verhindert aber
    # Mid-Word-Fehltreffer wie "reisekostenabRECHNUNG").
    return re.search(r"\b" + re.escape(needle), blob) is not None


def _stem_match(a: str, b: str) -> bool:
    """Zwei Kategorienamen teilen sich einen Wortstamm (Singular/Plural, gleiche Wurzel).

    Gemeinsamer Präfix von >= 5 Zeichen: ``rechnung`` ↔ ``rechnungen``,
    ``vertrag`` ↔ ``vertraege``, ``protokoll`` ↔ ``protokolle`` — aber
    ``recherche`` ↮ ``rechnung`` (nur 4 gemeinsame Zeichen).
    """
    if a == b:
        return True
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i >= 5


def _needles_for(cat: str, *, use_rules: bool) -> list[str]:
    """Stichwörter für eine ZIELkategorie zusammenstellen.

    So erbt eine frei benannte Projekt-Kategorie die reichen RULES-Regeln über den
    Wortstamm (``rechnung`` → invoice/betrag/beleg …) und Mehrwort-Kategorien greifen
    über ihre Einzelwörter (``technische dokumentation`` → "technische"/"dokumentation").
    Früher waren die RULES starr an die kanonischen Plural-Schlüssel gebunden und
    liefen bei abweichenden Kategorienamen ins Leere.
    """
    needles = {cat}
    for w in re.split(r"[\s_\-/]+", cat):
        if len(w) >= 4:
            needles.add(w)
    if use_rules:
        for key, values in RULES.items():
            if _stem_match(cat, key):
                needles.add(key)
                needles.update(values)
    return list(needles)


#: Zusatzgewicht, wenn der Kategoriename selbst im Text steht ("KONTOAUSZUG Nr. 3/2026").
#: Das ist das mit Abstand stärkste Signal und soll nicht von vielen schwachen
#: Allerweltstreffern überstimmt werden.
_NAME_BONUS = 12


def _score(blob: str, cat: str) -> int:
    """Wie gut passt diese Kategorie auf den Text?

    Jeder Treffer zählt mit seiner Länge: Längere Begriffe sind spezifischer.
    „kontoauszug" (11) wiegt damit deutlich schwerer als „beleg" (5) — und genau
    darauf kam es an.
    """
    punkte = 0
    for needle in _needles_for(cat, use_rules=True):
        if _hit(blob, needle):
            punkte += len(needle)
            if needle == cat:
                punkte += _NAME_BONUS
    return punkte


def classify_scored(stem: str, text: str, ext: str, *,
                    allowed: list[str] | None = None) -> tuple[str, int]:
    """Wie :func:`classify`, liefert aber auch die Punktzahl des Gewinners mit.

    0 Punkte heißt: Die Kategorie kam nur über den Dateityp (``TYPE_CATEGORY``) oder gar
    nicht zustande. Der Assigner braucht die Punkte, um eine heuristische Zweitmeinung nur
    dann gelten zu lassen, wenn sie auf einem spezifischen Begriff fußt — ein einzelnes
    „beleg" (5 Punkte) soll kein Dokument einsortieren.
    """
    blob = f"{stem} {text}".lower()
    cats = list(RULES.keys()) if allowed is None else allowed
    bewertet = [(_score(blob, c), c) for c in cats if c and c != "_unassigned"]
    bewertet = [(s, c) for s, c in bewertet if s > 0]
    if bewertet:
        # Bei Gleichstand entscheidet der Name alphabetisch — reproduzierbar statt zufällig.
        punkte, kat = max(bewertet, key=lambda sc: (sc[0], -ord(sc[1][0])))
        return kat, punkte
    for cat, exts in TYPE_CATEGORY.items():
        if ext in exts and (allowed is None or cat in allowed):
            return cat, 0
    return "_unassigned", 0


def classify(stem: str, text: str, ext: str, *, allowed: list[str] | None = None) -> str:
    """Die am BESTEN passende Kategorie raten (``allowed`` = nur Projekt-Kategorien).

    Früher gewann schlicht die Kategorie, die in ``RULES`` zufällig zuerst stand: Weil
    ``rechnungen`` der erste Schlüssel ist und dort Allerweltswörter wie „betrag", „beleg"
    oder „gutschrift" stehen, landete jedes Geschäftsdokument dort — ein Kontoauszug
    wegen „Gutschriften", eine Reisekostenabrechnung wegen „laut Beleg". Jetzt wird
    bewertet und die stärkste Übereinstimmung gewinnt.
    """
    return classify_scored(stem, text, ext, allowed=allowed)[0]


def snap_category(label: str, known: list[str]) -> str | None:
    """Ein (LLM-)Kategorielabel auf die bekannte Projekt-Menge „einrasten".

    Verhindert, dass beim Sortieren Ordner AUSSERHALB der vorgeschlagenen Kategorien
    entstehen (das LLM liefert z. B. „steuerbescheid" statt „finanzen" oder „invoice"
    statt „rechnungen"). Reihenfolge der Treffer: exakt → Wortstamm → gemeinsames
    aussagekräftiges Wort → Synonym/Stichwort (RULES). Rückgabe: passende bekannte
    Kategorie oder ``None`` (kein sicherer Treffer → der Aufrufer fragt lieber nach).
    """
    label = (label or "").strip().lower()
    known_l = [k.strip().lower() for k in known if k and k.strip().lower() != "_unassigned"]
    if not label or label == "_unassigned" or not known_l:
        return None
    # 1) exakt (nach Normalisierung)
    if label in known_l:
        return label
    # 2) Wortstamm (Singular/Plural, gleiche Wurzel)
    for k in known_l:
        if _stem_match(label, k):
            return k
    # 3) gemeinsames aussagekräftiges Wort (für Mehrwort-Kategorien)
    label_words = {w for w in re.split(r"[\s_\-/]+", label) if len(w) >= 4}
    for k in known_l:
        if label_words & {w for w in re.split(r"[\s_\-/]+", k) if len(w) >= 4}:
            return k
    # 4) Synonym/Stichwort: das Label trifft die Regeln einer bekannten Kategorie
    for k in known_l:
        needles = [n for n in _needles_for(k, use_rules=True) if len(n) >= 4]
        if label in needles or any(_hit(label, n) for n in needles):
            return k
    return None


# Kategorien, die typischerweise von Datum-Unterordnern profitieren (Jahr/Monat).
def datums_muster() -> str:
    """Das vorgeschlagene Unterordner-Muster in der aktiven Sprache.

    ``mover.resolve_subpath`` versteht beide Schreibweisen ({jahr}/{monat} und
    {year}/{month}) und löst sie identisch auf — ein englischer Nutzer soll aber
    keinen deutschen Platzhalter vorgeschlagen bekommen. Bereits gespeicherte Muster
    funktionieren dadurch unverändert weiter.
    """
    from . import i18n
    return "{year}/{month}" if i18n.get_language() == "en" else "{jahr}/{monat}"


_DATE_ORIENTED = {
    "rechnung", "rechnungen", "invoice", "beleg", "belege", "quittung", "receipt",
    "kontoauszug", "auszug", "finanzen", "finanz", "steuer", "gehalt", "lohn", "mahnung",
    "buchung", "zahlung", "abrechnung", "gehaltsabrechnung", "bill", "statement",
}


def suggest_subrouting(categories: list[str]) -> dict[str, str]:
    """Pre-Screening-Vorschlag: welche Kategorien nach ``{jahr}/{monat}`` gegliedert werden.

    Heuristik über den Kategorienamen und seine RULES-Synonyme — datumslastige Ablagen
    (Rechnungen, Kontoauszüge, Finanzen …) bekommen einen Jahr/Monat-Vorschlag.
    """
    out: dict[str, str] = {}
    for cat in categories:
        c = (cat or "").strip().lower()
        if not c or c == "_unassigned":
            continue
        words = set(re.split(r"[\s_\-/]+", c))
        needles = set(_needles_for(c, use_rules=True))
        if (words & _DATE_ORIENTED) or (needles & _DATE_ORIENTED):
            out[c] = datums_muster()
    return out


def read_snippet(path: Path, *, limit: int = 800) -> str:
    """Anfang einer Textdatei lesen (für Heuristik/Vorschlag); Binärdateien → leer."""
    if path.suffix.lower() in _TEXT_SUFFIXES:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")[:limit]
        except OSError:
            return ""
    return ""


_MONATE = {
    "januar": 1, "jan": 1, "january": 1, "februar": 2, "feb": 2, "february": 2, "märz": 3,
    "maerz": 3, "mär": 3, "march": 3, "mar": 3, "april": 4, "apr": 4, "mai": 5, "may": 5,
    "juni": 6, "jun": 6, "june": 6, "juli": 7, "jul": 7, "july": 7, "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9, "oktober": 10, "okt": 10, "october": 10, "oct": 10,
    "november": 11, "nov": 11, "dezember": 12, "dez": 12, "december": 12, "dec": 12,
}
_MONATSNAME = "|".join(sorted(_MONATE, key=len, reverse=True))
_DATUMSFORMEN = [
    re.compile(r"(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})"),                 # 2026-07-14
    re.compile(r"(?P<d>\d{1,2})\.\s?(?P<m>\d{1,2})\.\s?(?P<y>\d{4})"),          # 14.07.2026
    re.compile(r"(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{4})"),                   # 14/07/2026
    re.compile(rf"(?P<d>\d{{1,2}})\.?\s+(?P<mn>{_MONATSNAME})\.?\s+(?P<y>\d{{4}})",
               re.I),                                                            # 14. Juli 2026
    re.compile(rf"(?P<mn>{_MONATSNAME})\.?\s+(?P<d>\d{{1,2}}),?\s+(?P<y>\d{{4}})",
               re.I),                                                            # July 14, 2026
]
#: Beschriftungen, die das Datum DES Dokuments einleiten.
_DATUM_LABEL = re.compile(
    r"(rechnungsdatum|belegdatum|ausstellungsdatum|ausgestellt am|datum|invoice date|"
    r"date of issue|issue date|\bdate\b|dated|\bvom\b|stand)\s*[:.]?\s*$", re.I)
#: … und solche, die eine FRIST oder einen ZEITRAUM einleiten — das ist nie das Belegdatum.
_KEIN_BELEGDATUM = re.compile(
    r"(bis|fällig|faellig|frist|zahlbar|spätestens|spaetestens|gültig|gueltig|laufzeit|"
    r"zeitraum|beginn|ende|due|until|valid|period|deadline)\b[^\n]{0,25}$", re.I)


def _datum_aus(m) -> date | None:
    try:
        monat = _MONATE[m.group("mn").lower()] if "mn" in m.groupdict() and m.group("mn") \
            else int(m.group("m"))
        d = date(int(m.group("y")), monat, int(m.group("d")))
    except (ValueError, KeyError):
        return None
    return d if 1990 <= d.year <= 2100 else None


def dokument_datum(text: str, *, kopf: int = 3000) -> date | None:
    """Das Datum, an dem das Dokument ausgestellt wurde — ohne KI.

    Früher entschied das erste Datum irgendwo in Dateiname, Titel oder Zusammenfassung. Bei
    Rechnungen steht davor aber oft „zahlbar bis" oder der Leistungszeitraum — und die
    Rechnung landete im falschen Monat. Jetzt gilt:

    1. ein beschriftetes Datum („Rechnungsdatum:", „Datum:", „Kontoauszug vom …");
    2. sonst das erste Datum, vor dem keine Frist/kein Zeitraum steht („bis", „fällig" …).
    """
    kopf_text = (text or "")[:kopf]
    treffer = []
    for rx in _DATUMSFORMEN:
        for m in rx.finditer(kopf_text):
            d = _datum_aus(m)
            if d is not None:
                treffer.append((m.start(), d))
    treffer.sort()
    for start, d in treffer:
        davor = kopf_text[max(0, start - 40):start]
        if _DATUM_LABEL.search(davor):
            return d
    for start, d in treffer:
        davor = kopf_text[max(0, start - 40):start]
        if not _KEIN_BELEGDATUM.search(davor):
            return d
    return None


def kurz_titel(stem: str, text: str) -> str:
    """Ein Titel ohne KI: die erste Zeile mit echtem Wort (≥ 3 Buchstaben), sonst der
    Dateiname. Versalien werden lesbar gemacht („REISEKOSTENABRECHNUNG" → „Reisekostenabrechnung")."""
    for zeile in (text or "").splitlines():
        z = " ".join(zeile.split()).strip(" -—:•*#|=_")
        if sum(ch.isalpha() for ch in z) >= 3:
            if z.isupper():
                z = z.title()
            return z[:80]
    return stem.replace("_", " ").replace("-", " ").strip().title() or "Dokument"


def keywords(text: str, limit: int = 6) -> list[str]:
    """Ein paar aussagekräftige Stichwörter (>=5 Buchstaben) aus dem Text ziehen."""
    seen: list[str] = []
    for w in re.findall(r"[a-zäöüß]{5,}", text.lower()):
        if w not in seen:
            seen.append(w)
        if len(seen) >= limit:
            break
    return seen

"""Taxonomie-Regeln — wie aus vielen Einzel-Labels **eine saubere** Ordnerstruktur wird.

Das Problem, das dieses Modul löst: Beim Struktur-Vorschlag wird jedes Dokument **einzeln**
analysiert. Ein Modell, das eine Rechnung isoliert sieht, antwortet mal „rechnungen", mal
„finanzen", mal „buchhaltung" — alles vertretbar, aber zusammen ergibt es drei Ordner für
denselben Stapel Papier. Niemand hat je auf die Gesamtmenge geschaut.

Hier schaut jemand darauf. Zwei Ebenen, absichtlich in dieser Reihenfolge:

1. **Die Regeln als System-Message** (:data:`SYSTEM_REGELN`) — das Modell bekommt sie beim
   Konsolidierungs-Aufruf und beim Einzel-Label.
2. **Deterministische Nachkontrolle** (:func:`konsolidieren`) — die Regeln werden im Code
   noch einmal erzwungen. Ein Sprachmodell hält sich nicht zuverlässig an Vorgaben; die
   Ordnerstruktur des Nutzers ist aber kein Ort für „meistens".

Die Leitregel in einem Satz: **Zwei Ordner dürfen nie dieselbe Frage beantworten.**
"""

from __future__ import annotations

from .heuristics import RULES, _stem_match

# --------------------------------------------------------------------------- #
#  Die Regeln — Text für das Modell
# --------------------------------------------------------------------------- #
#: Wird dem LLM als verbindliche Vorgabe mitgegeben. Bewusst knapp und in Beispielen
#: gedacht, nicht in Abstraktionen — kleine Modelle (9B) folgen Beispielen deutlich
#: zuverlässiger als Prinzipien.
SYSTEM_REGELN = """Regeln für eine gute Ablage-Struktur (verbindlich):

1. ÜBERSCHNEIDUNGSFREI. Zwei Kategorien duerfen nie dieselben Dokumente meinen.
   Falsch: "Rechnungen" UND "Finanzen", wenn es nur Rechnungen gibt.
   Richtig: nur "Rechnungen".

2. OBERBEGRIFF NUR BEI MEHREREN GRUPPEN. Ein weiter Begriff (Finanzen, Verwaltung,
   Allgemein, Sonstiges) ist nur erlaubt, wenn er mehrere unterschiedliche Gruppen
   zusammenfasst, die einzeln zu klein waeren.
   Falsch: nur Rechnungen -> "Finanzen".
   Richtig: Rechnungen + Reisekostenabrechnungen + Kontoauszuege -> drei eigene
   Kategorien, ODER "Finanzen" nur dann, wenn von jeder Gruppe nur ein, zwei
   Dokumente da sind.

3. NIE OBERBEGRIFF UND UNTERBEGRIFF NEBENEINANDER. Wenn "Rechnungen" existiert,
   darf daneben kein "Finanzen" und kein "Belege" stehen.

4. SPEZIFISCH SCHLAEGT ALLGEMEIN. Beschreibt eine engere Kategorie alle Dokumente,
   nimm die engere.

5. NACH DOKUMENTTYP BENENNEN, nicht nach Abteilung, Absender oder Projekt.
   Richtig: "Vertraege", "Protokolle", "Kontoauszuege".
   Falsch: "Buchhaltung", "Herr Meier", "Projekt Nord".

6. MINDESTGROESSE. Eine Kategorie lohnt sich ab etwa drei Dokumenten. Weniger ->
   in die naechstpassende Kategorie einsortieren.

7. KEINE SYNONYME. "Rechnung" und "Rechnungen" und "Eingangsrechnungen" sind EINE
   Kategorie. Entscheide dich fuer einen Namen (Plural, kleingeschrieben, ein Wort).
"""

#: Oberbegriffe und die Kategorien, die sie verschlucken würden.
#:
#: Steht ein Oberbegriff **neben** einem seiner Unterbegriffe, ist das immer der
#: Doppelordner-Fehler — dann verschwindet der Oberbegriff (Regel 3). Steht er allein,
#: darf er bleiben: dann ist er die einzige sinnvolle Klammer über einen gemischten Rest.
OBERBEGRIFFE: dict[str, set[str]] = {
    "finanzen": {"rechnungen", "belege", "steuer", "steuern", "kontoauszuege", "kontoauszug",
                 "buchhaltung", "gehalt", "gehaelter", "lohn", "zahlungen", "reisekosten",
                 "spesen", "abrechnungen", "mahnungen", "bank"},
    "buchhaltung": {"rechnungen", "belege", "kontoauszuege", "steuer", "steuern", "mahnungen"},
    "kosten": {"rechnungen", "spesen", "reisekosten", "belege"},
    "verwaltung": {"vertraege", "korrespondenz", "protokolle", "versicherung", "behoerden",
                   "bescheide", "schriftverkehr"},
    "personal": {"bewerbung", "bewerbungen", "arbeitsvertraege", "gehalt", "gehaelter",
                 "reisekosten", "spesen", "zeugnisse"},
    "dokumente": set(),
    "allgemein": set(),
    "unterlagen": set(),
    "sonstiges": set(),
}

#: Wie viele Dokumente eine eigene Kategorie mindestens rechtfertigen (Regel 6).
MINDEST_DOKUMENTE = 3

#: Obergrenze — mehr Ordner als das überblickt niemand mehr.
MAX_KATEGORIEN = 8


# --------------------------------------------------------------------------- #
#  Hilfen
# --------------------------------------------------------------------------- #
def _familie(label: str) -> str | None:
    """Zu welcher RULES-Familie gehört das Label (über seine Synonyme)?

    Es gewinnt die Familie mit dem **längsten** passenden Begriff, nicht die erste in
    der Reihenfolge des Regelwerks. Sonst landet „reisekostenabrechnungen" bei „reisen",
    nur weil „reise" ein Präfix davon ist und weiter oben steht — und die viel genauere
    Übereinstimmung mit „reisekostenabrechnung" unter „spesen" bliebe ungenutzt.
    """
    lab = label.strip().lower()
    if lab in RULES:
        return lab
    bester, beste_laenge = None, 0
    for kat, begriffe in RULES.items():
        laenge = 0
        if _stem_match(lab, kat):
            laenge = len(kat)
        for b in begriffe:
            if _stem_match(lab, b):
                laenge = max(laenge, len(b))
        if laenge > beste_laenge:
            bester, beste_laenge = kat, laenge
    return bester


#: Fugenlaute deutscher Komposita. Steht einer davon direkt vor dem Kopf-Nomen, ist das
#: lange Wort eine Zusammensetzung MIT diesem Kopf ("Eingang-s-rechnungen" = Rechnungen).
#: Steht dort etwas anderes, ist es ein eigenes Wort ("reisekosten-ab-rechnung" ist eben
#: KEINE Rechnung) — genau deshalb reicht ein simpler Teilstring-Vergleich hier nicht.
_FUGENLAUTE = set("sner")


def _kompositum_mit_kopf(lang: str, kopf: str) -> bool:
    """Ist ``lang`` ein Kompositum, dessen Kopf-Nomen ``kopf`` ist?"""
    if len(kopf) < 8 or len(lang) <= len(kopf) or not lang.endswith(kopf):
        return False
    return lang[-len(kopf) - 1] in _FUGENLAUTE


def _gleichbedeutend(a: str, b: str) -> bool:
    """Meinen zwei Labels dasselbe? (Wortstamm, Kompositum oder gemeinsame RULES-Familie)"""
    if a == b:
        return True
    if _stem_match(a, b):
        return True
    # Deutsche Komposita hängen den Kopf hinten an: "eingangsrechnungen" ist dasselbe
    # wie "rechnungen". _stem_match vergleicht nur Präfixe und sieht das nicht.
    if _kompositum_mit_kopf(a, b) or _kompositum_mit_kopf(b, a):
        return True
    fa, fb = _familie(a), _familie(b)
    return fa is not None and fa == fb


def _deckt(a: str, b: str) -> bool:
    """Beschreibt der Name ``a`` auch alle Dokumente, die ``b`` hießen?

    Ja, wenn ``a`` der Kopf des Kompositums ist („vertraege" deckt „arbeitsvertraege"), sein
    Präfix („steuer" deckt „steuerbescheide") oder seine RULES-Familie („spesen" deckt
    „reisekostenabrechnungen"). Umgekehrt nie: „arbeitsvertraege" beschreibt keinen Mietvertrag.
    """
    return (a == b or _kompositum_mit_kopf(b, a) or (len(a) >= 5 and b.startswith(a))
            or _familie(b) == a)


def _gruppenname(mitglieder: list[str], anzahl: dict[str, int]) -> str:
    """Der Name für eine Gruppe gleichbedeutender Labels (Regel 4 konsequent angewandt).

    Bis 2026-09-24 gewann schlicht das häufigste Label. Im Ollama-Lauf hießen 4 Verträge
    „arbeitsvertraege" und 3 „vertraege" — alle 7, darunter 3 Mietverträge, landeten in
    einem Ordner „Arbeitsvertraege". Jetzt gewinnt der Name, der ALLE deckt; unter mehreren
    der häufigste. Deckt keiner alle, die gemeinsame Familie — und erst dann der häufigste.
    """
    reihenfolge = sorted(mitglieder, key=lambda k: (-anzahl[k], k))
    for kandidat in reihenfolge:
        if all(_deckt(kandidat, m) for m in mitglieder):
            return kandidat
    familien = {_familie(m) for m in mitglieder}
    if len(familien) == 1 and None not in familien:
        return familien.pop()
    return reihenfolge[0]


def _ist_oberbegriff_von(ober: str, unter: str) -> bool:
    kinder = OBERBEGRIFFE.get(ober.strip().lower())
    if kinder is None:
        return False
    u = unter.strip().lower()
    return any(_stem_match(u, k) for k in kinder)


# --------------------------------------------------------------------------- #
#  Die Konsolidierung
# --------------------------------------------------------------------------- #
def konsolidieren(labels: dict[str, int], *,
                  mindest: int = MINDEST_DOKUMENTE,
                  maximum: int = MAX_KATEGORIEN) -> tuple[dict[str, int], list[str]]:
    """Aus rohen Einzel-Labels eine überschneidungsfreie Struktur machen.

    Gibt ``(kategorien_mit_anzahl, protokoll)`` zurück. Das Protokoll nennt jede
    Zusammenlegung im Klartext — der Nutzer soll sehen, *warum* aus fünf Vorschlägen
    drei Ordner wurden, statt es hinnehmen zu müssen.

    Die Reihenfolge der Schritte ist wesentlich: erst Synonyme (sonst zählt derselbe
    Stapel doppelt und wirkt größer), dann Oberbegriffe (braucht die bereinigten
    Zahlen), dann die Mindestgröße (braucht beides).
    """
    protokoll: list[str] = []
    rein = {k.strip().lower(): v for k, v in labels.items() if k and k.strip()}
    rein.pop("_unassigned", None)
    if not rein:
        return {}, protokoll

    # Die Mindestgröße muss zur Menge passen. Bei sechs Dokumenten in drei sauber
    # getrennten Gruppen wären drei Ordner völlig richtig — eine starre Untergrenze
    # von drei faltet sie alle zu einem einzigen zusammen (real beobachtet in einem
    # Ollama-Lauf: 2 Rechnungen + 2 Reisekosten + 2 Kontoauszüge wurden eine Wabe).
    # Also: nie mehr als ein Viertel des Bestands verlangen, nie weniger als zwei.
    gesamt = sum(rein.values())
    mindest = max(2, min(mindest, gesamt // 4))

    # -- Regel 7: Synonyme und Wortstämme zusammenlegen ----------------------
    # Erst die Gruppen bilden (verglichen wird mit dem häufigsten Label der Gruppe), dann
    # den Namen wählen, der ALLE Mitglieder deckt (_gruppenname, Regel 4).
    gruppen: dict[str, list[str]] = {}
    for label in sorted(rein, key=lambda k: (-rein[k], k)):
        for kopf in gruppen:
            if _gleichbedeutend(label, kopf):
                gruppen[kopf].append(label)
                break
        else:
            gruppen[label] = [label]
    zusammen: dict[str, int] = {}
    for mitglieder in gruppen.values():
        name = _gruppenname(mitglieder, rein)
        zusammen[name] = zusammen.get(name, 0) + sum(rein[m] for m in mitglieder)
        for m in mitglieder:
            if m != name:
                protokoll.append(f"'{m}' → '{name}' (dasselbe gemeint)")

    # -- Regel 3: kein Oberbegriff neben seinem Unterbegriff ------------------
    for ober in sorted(zusammen, key=lambda k: -zusammen[k]):
        if ober not in zusammen:
            continue
        kinder = [u for u in zusammen if u != ober and _ist_oberbegriff_von(ober, u)]
        if not kinder:
            continue
        ziel = max(kinder, key=lambda k: zusammen[k])
        zusammen[ziel] += zusammen.pop(ober)
        protokoll.append(f"'{ober}' → '{ziel}' (Oberbegriff neben Unterbegriff)")

    # -- Regel 6: zu kleine Kategorien einsortieren ---------------------------
    # Nur solange mehr als eine Kategorie übrig bleibt — der letzte Ordner bleibt
    # immer stehen, auch wenn er klein ist.
    for klein in sorted([k for k, v in zusammen.items() if v < mindest], key=lambda k: zusammen[k]):
        if len(zusammen) <= 1 or klein not in zusammen:
            continue
        rest = [k for k in zusammen if k != klein]
        fam = _familie(klein)
        passend = [k for k in rest if fam and _familie(k) == fam]
        ziel = max(passend or rest, key=lambda k: zusammen[k])
        zusammen[ziel] += zusammen.pop(klein)
        protokoll.append(f"'{klein}' → '{ziel}' (zu wenige Dokumente)")

    # -- Deckelung ------------------------------------------------------------
    if len(zusammen) > maximum:
        geordnet = sorted(zusammen.items(), key=lambda kv: -kv[1])
        behalten = dict(geordnet[:maximum])
        ziel = geordnet[0][0]
        for name, n in geordnet[maximum:]:
            behalten[ziel] += n
            protokoll.append(f"'{name}' → '{ziel}' (mehr als {maximum} Kategorien)")
        zusammen = behalten

    return dict(sorted(zusammen.items(), key=lambda kv: -kv[1])), protokoll


def pruefe(kategorien: list[str]) -> list[str]:
    """Eine fertige Kategorienliste auf Regelverstöße prüfen. Gibt Klartext-Beanstandungen.

    Für Tests und für den ``doctor`` — und um eine LLM-Antwort zu bewerten, bevor man
    sie übernimmt.
    """
    k = [c.strip().lower() for c in kategorien if c and c.strip()]
    probleme: list[str] = []
    for i, a in enumerate(k):
        for b in k[i + 1:]:
            if _gleichbedeutend(a, b):
                probleme.append(f"'{a}' und '{b}' meinen dasselbe")
            elif _ist_oberbegriff_von(a, b):
                probleme.append(f"'{a}' ist ein Oberbegriff von '{b}'")
            elif _ist_oberbegriff_von(b, a):
                probleme.append(f"'{b}' ist ein Oberbegriff von '{a}'")
    if len(k) > MAX_KATEGORIEN:
        probleme.append(f"{len(k)} Kategorien — mehr als {MAX_KATEGORIEN} überblickt niemand")
    return probleme

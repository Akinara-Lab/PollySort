"""Dreistufige Entscheidung — Gedächtnis → Nummer → Rückfrage (Plan §8.3, gemessen §8.13).

Bis 2026-09-24 schrieb das Modell für **jede** Datei Titel, Zusammenfassung und Stichworte,
bevor die Kategorie feststand — 22 s je Dokument mit dem 9B. Die Kategorie selbst sind davon
eine Handvoll Tokens. Seitdem wird im Ollama-Modus in dieser Reihenfolge entschieden:

A. **Gedächtnis.** Der Dokument-Auszug wird eingebettet (0,03 s GPU, 0,2 s CPU) und mit den
   schon einsortierten Dokumenten verglichen. Ist das ähnlichste bekannte Dokument sehr nah
   *und* klar näher als jede andere Kategorie, entscheidet das Gedächtnis allein — ohne
   KI-Aufruf. Die Schwellen sind gemessen: Fehlt eine Kategorie ganz im Gedächtnis, kam kein
   fremdes Dokument über 0,67 Ähnlichkeit; ab 0,75 entschied das Gedächtnis im fortlaufenden
   Lauf 40 von 54 Dokumenten, keines davon falsch.
B. **Nummer.** Sonst wählt das Sprachmodell die Kategorie mit einem einzigen Token; die
   Konfidenz kommt aus den Logprobs (``OllamaClient.decide``). 9B: 99 % in 0,5 s.
C. **Rückfrage**, wenn das Modell „keine passt" sagt oder unsicher ist — wie bisher über die
   Schwelle des Projekts.

Titel und Zusammenfassung entstehen dabei zunächst heuristisch (:func:`kurz_analyse`); die
KI verfeinert sie danach (:mod:`pollysort.nacherfassung`) — die Datei liegt dann schon im
richtigen Ordner.

Heuristik- und OpenRouter-Modus sind nicht betroffen: Nur ein Client mit Textbasis „auszug"
und einer ``decide``-Methode nimmt diesen Weg (:func:`unterstuetzt`).

**BeeNara** (seit 2026-10-02, :mod:`pollysort.beenara`). Ist das lokale Entscheider-Modell
geladen, wählt es in Stufe B statt des Sprachmodells — im Modus Lokal nach dem Gedächtnis, im
Sparmodus statt der Heuristik. Gemessen auf den 70 Dokumenten der Testprojekte erkennt es
„keiner passt" in 94 % der Fälle, das 9B in 44 %, und rechnet auf der CPU in 0,3 s. Es sortiert
nur, wenn seine konforme Vorhersagemenge genau einen Ordner enthält (kalibriert ≥ 0,97); sonst
Rückfrage mit seinem Favoriten als Vorschlag. Danach rät kein zweites Modell nach: „keiner
passt" wird nie automatisch übergangen. Eine gelernte Wachstafel-Regel und ein widersprechendes
Gedächtnis haben Vorrang. Außerhalb von 3–9 Ordnern (so trainiert und kalibriert) und ohne
lokalen Text gilt der bisherige Weg; im Modus Cloud entscheidet BeeNara nicht mit.

**BeeNara Big** (seit 2026-10-08, :mod:`pollysort.beenara_big`) nimmt denselben Platz ein, für
3–500 Ordner und nur mit Vorschlägen: Sein Favorit wird immer eine Rückfrage. Welches der beiden
entscheidet, sagt :func:`beenara_modell_fuer` (Einstellung ``beenara_modell``).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

from .models import BeeAnalysis, Status

#: Ähnlichkeit zum nächsten bekannten Dokument, ab der das Gedächtnis allein entscheidet.
AEHNLICH = 0.75
#: So viel näher als die nächstbeste andere Kategorie muss es sein.
ABSTAND = 0.05
#: So viele Dokumente der Kategorie müssen schon im Gedächtnis liegen.
MINDEST = 2

#: BeeNara ist auf 3 bis 9 Ordner trainiert und kalibriert (v0.3: Risiko-Schwelle nur dort).
#: Darüber trug die Shortlist in v0.3 nicht (~53 % auf großen Bäumen) — das wird BeeNara Big;
#: darunter trägt die Kalibrierung nicht — dann der bisherige Weg.
BEENARA_MIN, BEENARA_MAX = 3, 9
#: So viel Text bekommt BeeNara höchstens; es kürzt selbst auf seine ~300 Dokument-Tokens.
BEENARA_ZEICHEN = 3000
#: Anteil des Dokumentendes, wenn gekürzt wird — wie im Training von v0.3 (Anfang 70 %, Ende 30 %).
BEENARA_ENDE = 0.3
#: Wann BeeNara selbst einsortiert. ``risk`` (v0.3): nur wenn die kalibrierte Konfidenz die
#: Risiko-Schwelle der Ordnerzahl erreicht — höchstens 1 % der automatischen Entscheidungen falsch
#: (δ = 0,1). Stufe-0 am 2026-10-08: fehlt der richtige Ordner, 0 statt 4 von 70 falsch
#: einsortiert (``conformal``, wie v0.2), dafür 7–15 Punkte öfter eine Rückfrage.
BEENARA_REGEL = "risk"
#: BeeNara Big (:mod:`pollysort.beenara_big`) ist auf 3–300 Ordner trainiert, in 5 % der
#: Aufgaben bis 500. In v0.3 macht es nur Vorschläge (keine Risiko-Schwelle zertifizierbar).
BIG_MIN, BIG_MAX = 3, 500
#: Werte der Einstellung ``beenara_modell``: welches Modell sortiert, wenn beide da sind.
MODELLE = ("auto", "klein", "big")


def beenara_text(text: str, zeichen: int = BEENARA_ZEICHEN) -> str:
    """Anfang und Ende eines langen Dokuments. v0.3 liest das Ende mit — dort stehen Summe,
    Unterschrift und Grußformel; ein reiner Anfangsausschnitt würde es abschneiden."""
    if len(text) <= zeichen:
        return text
    ende = int(zeichen * BEENARA_ENDE)
    return text[:zeichen - ende - 1] + "\n" + text[-ende:]


def beenara_modell_fuer(modus: str, n: int, *, klein_bereit: bool, big_bereit: bool) -> str | None:
    """Welches BeeNara bei ``n`` Ordnern entscheidet: ``klein`` · ``big`` · ``None`` (keins).

    ``auto`` (Standard): das kleine BeeNara für 3–9 Ordner — dort sortiert es selbst; sonst
    Big bis 500 Ordner, das nur vorschlägt. ``klein`` und ``big`` erzwingen ein Modell; außerhalb
    seines Bereichs entscheidet dann der bisherige Weg. Ist Big nicht geladen, ist ``auto``
    genau das Verhalten vor Big."""
    klein = klein_bereit and BEENARA_MIN <= n <= BEENARA_MAX
    big = big_bereit and BIG_MIN <= n <= BIG_MAX
    if modus == "klein":
        return "klein" if klein else None
    if modus == "big":
        return "big" if big else None
    return "klein" if klein else ("big" if big else None)


@dataclass
class Vorab:
    """Ergebnis der Analyse, bevor gespeichert wird — auch der Inhalt des Vorschau-Caches."""

    analysis: BeeAnalysis
    ext_status: Status
    reason: str | None
    vec: list[float] | None
    #: Fest entschiedene Kategorie (Stufe A/B). ``None`` → der Assigner entscheidet wie bisher.
    kategorie: str | None = None
    confidence: float | None = None
    #: ``gedaechtnis`` · ``nummer`` · ``analyse`` — erscheint in der Lauf-Zusammenfassung.
    quelle: str = "analyse"
    #: Titel/Zusammenfassung nur heuristisch → zur Nacherfassung vormerken.
    kurz: bool = False

    def als_cache(self) -> dict:
        return {"analysis": self.analysis, "ext_status": self.ext_status,
                "reason": self.reason, "vec": self.vec, "kategorie": self.kategorie,
                "confidence": self.confidence, "quelle": self.quelle, "kurz": self.kurz}

    @classmethod
    def aus_cache(cls, c: dict) -> Vorab:
        return cls(c["analysis"], c["ext_status"], c["reason"], c.get("vec"),
                   c.get("kategorie"), c.get("confidence"), c.get("quelle", "analyse"),
                   c.get("kurz", False))

    def mit_vec(self, vec: list[float] | None) -> Vorab:
        return replace(self, vec=vec)


def unterstuetzt(client) -> bool:
    """Nimmt dieser Client den dreistufigen Weg? (Heute: nur der Ollama-Client.)"""
    return (getattr(client, "memory_basis", None) == "auszug"
            and callable(getattr(client, "decide", None)))


def beenara_weg(client) -> str | None:
    """Wo BeeNara mitentscheidet: ``lokal`` (Ollama, nach dem Gedächtnis) oder ``spar``
    (statt der Heuristik). ``None`` im Modus Cloud — dort schreibt die Cloud-Analyse ohnehin
    Titel und Zusammenfassung, BeeNara würde nichts sparen."""
    if unterstuetzt(client):
        return "lokal"
    from .llm.client import OfflineClient
    return "spar" if isinstance(client, OfflineClient) else None


def beenara_passt(kategorien: list[str], bereich: tuple[int, int] = (BEENARA_MIN, BEENARA_MAX)) -> bool:
    """Liegt die Ordnerzahl im Bereich, auf den das Modell trainiert ist (Standard: BeeNara)?"""
    return bereich[0] <= len(ordner_namen(kategorien)) <= bereich[1]


def ordner_namen(kategorien: list[str]) -> list[str]:
    """Die Kategorien, die als Ordner zur Wahl stehen (ohne ``_unassigned``)."""
    return [c for c in kategorien if c and c.strip().lower() != "_unassigned"]


def beenara_waehlen(bee, text: str, kategorien: list[str], beste: dict[str, float], *,
                    sprache: str = "de") -> tuple[str, float] | None:
    """Stufe B mit BeeNara: ``(kategorie, konfidenz)`` oder ``None`` (trägt hier nicht).

    * sicher (Regel :data:`BEENARA_REGEL`: Konfidenz über der Risiko-Schwelle) → dieser Ordner
      mit seiner kalibrierten Wahrscheinlichkeit; widerspricht das Gedächtnis deutlich,
      gedeckelt wie im Assigner.
    * „keiner passt" vorn → ``_unassigned`` mit 0 → Rückfrage.
    * unsicher zwischen Ordnern → Favorit als Vorschlag, gedeckelt → Rückfrage.

    ``bee.decide`` darf ``None`` liefern (ausgefallen, siehe pipeline); dann ``None``.
    Ordnerbereich und Textlänge bringt das Modell mit (``ordner_bereich``, ``text_zeichen`` —
    BeeNara Big liest 3–500 Ordner und mehr Text); ohne sie gelten die Werte von BeeNara.
    """
    from .assigner import CONFLICT
    from .beenara_laufzeit import NONE

    namen = ordner_namen(kategorien)
    bereich = getattr(bee, "ordner_bereich", (BEENARA_MIN, BEENARA_MAX))
    if not beenara_passt(namen, bereich) or not (text or "").strip():
        return None
    d = bee.decide(beenara_text(text, getattr(bee, "text_zeichen", BEENARA_ZEICHEN)), namen,
                   language=sprache, rule=BEENARA_REGEL)
    if d is None:
        return None
    if d.category is not None:
        kat = d.category.strip().lower()
        eigene = beste.get(kat, 0.0)
        gegen = max((v for k, v in beste.items() if k != kat), default=0.0)
        conf = min(d.confidence, CONFLICT) if gegen >= AEHNLICH and gegen > eigene else d.confidence
        return kat, round(conf, 4)
    favorit = max(d.distribution, key=d.distribution.get)
    if favorit == NONE:
        return "_unassigned", 0.0
    return favorit.strip().lower(), round(min(d.confidence, CONFLICT), 4)


# --------------------------------------------------------------------------- #
#  Stufe A — das Gedächtnis
# --------------------------------------------------------------------------- #
def beste_je_kategorie(vec: list[float], eintraege) -> dict[str, float]:
    """Für jede Kategorie die Ähnlichkeit ihres nächsten Dokuments (ein Durchlauf)."""
    from .hive_mind.memory import _cosine
    beste: dict[str, float] = {}
    for _bid, kat, v in eintraege:
        if kat == "_unassigned":
            continue
        s = _cosine(vec, v)
        if s > beste.get(kat, -1.0):
            beste[kat] = s
    return beste


def _numpy():
    """numpy, falls installiert (kommt mit dem Extra [beenara]) — sonst ``None``."""
    try:
        import numpy
    except ImportError:
        return None
    return numpy


class Schnappschuss:
    """Kopie des Gedächtnisses für einen Sortierlauf.

    SQLite-Verbindungen dürfen nicht zwischen Threads wandern; die parallelen Worker des Ultra
    Swarm lesen deshalb aus dieser Kopie. Im einthreadigen Teil wächst sie mit (``merken``) —
    so muss nicht jede Datei das ganze Gedächtnis neu aus der Datenbank laden (vorher ~50 ms je
    Datei bei 57 Einträgen, wachsend mit dem Archiv).

    Mit numpy rechnet ``beste_je_kategorie`` alle Ähnlichkeiten als eine Matrix-Multiplikation
    (float32, Abweichung zur reinen Python-Rechnung < 1e-6); ohne numpy wie bisher.
    """

    def __init__(self, eintraege):
        self._eintraege = list(eintraege)
        self._anzahl = Counter(kat for _b, kat, _v in self._eintraege)
        # Normierte Vektoren als Matrix mit Reserve-Zeilen (erst bei Bedarf gebaut): Neu
        # Gelerntes wird hineingeschrieben, statt die Matrix je Datei neu aufzubauen.
        self._matrix = None
        self._zeilen = 0

    @staticmethod
    def _normiert(np, vec):
        v = np.asarray(vec, dtype=np.float32)
        n = float(np.linalg.norm(v))
        return v / n if n else v                  # Nullvektor: Ähnlichkeit 0 wie bei _cosine

    def _matrix_bauen(self, np) -> bool:
        if len({len(v) for _b, _k, v in self._eintraege}) != 1:
            return False                          # gemischte Dimensionen: wie bisher rechnen
        dim = len(self._eintraege[0][2])
        m = np.zeros((len(self._eintraege) + 64, dim), dtype=np.float32)
        for i, (_b, _k, v) in enumerate(self._eintraege):
            m[i] = self._normiert(np, v)
        # Erst die Zeilenzahl, dann die Matrix — ein paralleler Leser (Ultra Swarm) sieht
        # entweder keine Matrix (und baut selbst) oder eine vollständige.
        self._zeilen = len(self._eintraege)
        self._matrix = m
        return True

    def beste_je_kategorie(self, vec: list[float]) -> dict[str, float]:
        np = _numpy()
        if np is None or not self._eintraege:
            return beste_je_kategorie(vec, self._eintraege)
        if self._matrix is None and not self._matrix_bauen(np):
            return beste_je_kategorie(vec, self._eintraege)
        q = np.asarray(vec, dtype=np.float32)
        nq = float(np.linalg.norm(q))
        if q.shape[0] != self._matrix.shape[1] or nq == 0:
            return beste_je_kategorie(vec, self._eintraege)
        aehnlich = (self._matrix[:self._zeilen] @ (q / nq)).tolist()
        beste: dict[str, float] = {}
        for (_bid, kat, _v), s in zip(self._eintraege, aehnlich):
            if kat != "_unassigned" and s > beste.get(kat, -1.0):
                beste[kat] = s
        return beste

    def merken(self, bee_id: str, kategorie: str, vec: list[float]) -> None:
        """Was der Lauf gerade gelernt hat, auch hier nachtragen (wie ``HiveMind.remember``:
        ein Eintrag je Datei, ein zweites Mal ersetzt den ersten)."""
        for i, (bid, kat, _v) in enumerate(self._eintraege):
            if bid == bee_id:                     # selten (Wiederholung nach Fehler): neu bauen
                self._anzahl[kat] -= 1
                del self._eintraege[i]
                self._matrix = None
                break
        self._eintraege.append((bee_id, kategorie, vec))
        self._anzahl[kategorie] += 1
        m = self._matrix
        if m is None:
            return
        if len(vec) != m.shape[1]:
            self._matrix = None
            return
        np = _numpy()
        if self._zeilen == m.shape[0]:            # Reserve aufgebraucht: verdoppeln
            groesser = np.zeros((2 * m.shape[0], m.shape[1]), dtype=np.float32)
            groesser[:self._zeilen] = m[:self._zeilen]
            self._matrix = m = groesser
        m[self._zeilen] = self._normiert(np, vec)
        self._zeilen += 1

    def count(self, kategorie: str) -> int:
        return self._anzahl.get(kategorie, 0)


def aus_gedaechtnis(beste: dict[str, float], zaehle, kategorien: list[str]) -> tuple[str, float] | None:
    """Stufe A: ``(kategorie, ähnlichkeit)``, wenn das Gedächtnis allein entscheiden darf."""
    if not beste:
        return None
    erlaubt = {k.strip().lower() for k in kategorien if k}
    kat = max(beste, key=beste.get)
    s = beste[kat]
    fremd = max((v for k, v in beste.items() if k != kat), default=0.0)
    if kat in erlaubt and s >= AEHNLICH and s - fremd >= ABSTAND and zaehle(kat) >= MINDEST:
        return kat, round(s, 4)
    return None


# --------------------------------------------------------------------------- #
#  Kurz-Erfassung (ohne KI)
# --------------------------------------------------------------------------- #
def kurz_analyse(path: Path, text: str, kategorie: str) -> BeeAnalysis:
    """Titel, Zusammenfassung und Stichworte heuristisch — die KI verfeinert sie später."""
    from .heuristics import keywords, kurz_titel
    return BeeAnalysis(
        title=kurz_titel(path.stem, text),
        summary=" ".join(text.split())[:280],
        keywords=keywords(text, limit=5),
        funktion_aufgabe="",
        kategorie=kategorie,
    )


# --------------------------------------------------------------------------- #
#  Der Weg durch A → B → C
# --------------------------------------------------------------------------- #
def analysieren(client, f, *, max_file_mb: int, kategorien: list[str], gedaechtnis,
                memory_ok: bool, beenara=None, sprache: str = "de") -> Vorab | None:
    """Eine Datei dreistufig analysieren.

    ``gedaechtnis`` braucht ``beste_je_kategorie(vec)`` und ``count(kategorie)`` — ein
    :class:`Schnappschuss` mit den Vektoren des aktuellen Modells (``HiveMind.eintraege``).
    ``memory_ok=False`` schaltet Stufe A ganz ab. ``beenara``: das geöffnete Modell, dann
    entscheidet es Stufe B statt des Sprachmodells (wo es trägt).

    ``None`` heißt: Dieser Weg trägt hier nicht (kein lokaler Text, etwa bei Bildern; zu
    groß) — der Aufrufer analysiert wie bisher vollständig.
    """
    from .extractor import AUSZUG_ZEICHEN, extract, volltext
    from .llm import LLMError, LLMRequestError
    from .llm.client import _apply_wachstafel
    from .wachstafel import parse_rules

    if not unterstuetzt(client) or f.size_bytes > max_file_mb * 1024 * 1024:
        return None
    try:
        voll = volltext(f.path, f.mime_type)
    except Exception:
        voll = None
    text = voll.strip()[:AUSZUG_ZEICHEN] if voll else None
    if not text:
        return None

    def fehler(exc: Exception) -> Vorab:
        # Wie der Extractor: Netz-/Provider-Fehler bleiben ERROR und werden beim nächsten
        # Lauf automatisch erneut versucht (BUG-5).
        return Vorab(BeeAnalysis(title=f.path.stem, kategorie="_unassigned"), Status.ERROR,
                     f"LLM-Extraktion fehlgeschlagen: {exc}", None)

    try:
        vec = client.embed(text)
    except LLMError as exc:
        return fehler(exc)
    beste = gedaechtnis.beste_je_kategorie(vec) if memory_ok else {}

    # Stufe A — außer, eine gelernte Wachstafel-Regel trifft: Dann soll das Modell sie
    # sehen (sie steht in seinem Prompt), statt dass das Gedächtnis an ihr vorbeientscheidet.
    # Dasselbe gilt für BeeNara: Es kennt die Regeln nicht.
    regeln = parse_rules(getattr(client, "_wachstafel", "") or "")
    if not (regeln and _apply_wachstafel(text.lower(), regeln) is not None):
        treffer = aus_gedaechtnis(beste, gedaechtnis.count, kategorien)
        if treffer:
            kat, s = treffer
            return Vorab(kurz_analyse(f.path, text, kat), Status.INDEXED, None, vec,
                         kategorie=kat, confidence=s, quelle="gedaechtnis", kurz=True)
        # Stufe B mit BeeNara — wo es nicht trägt (Ordnerzahl), wählt das Sprachmodell.
        wahl = (beenara_waehlen(beenara, voll.strip(), kategorien, beste, sprache=sprache)
                if beenara is not None else None)
        if wahl is not None:
            kat, conf = wahl
            return Vorab(kurz_analyse(f.path, text, kat), Status.INDEXED, None, vec,
                         kategorie=kat, confidence=conf, quelle="beenara", kurz=True)

    # Stufe B — das Sprachmodell
    try:
        wahl = client.decide(text, kategorien)
    except LLMRequestError:
        wahl = None                    # Server kennt den Weg nicht → volle Analyse
    except LLMError as exc:
        return fehler(exc)
    if wahl is None:
        analysis, status, reason = extract(f, client, max_file_mb=max_file_mb)
        return Vorab(analysis, status, reason, vec if status == Status.INDEXED else None)

    kat, p = wahl
    if kat == "_unassigned":
        conf = 0.0                     # „keine passt" → Stufe C, die Rückfrage
    else:
        # Sieht das Gedächtnis eine ANDERE Kategorie deutlich näher, ist der Fall
        # mehrdeutig — wie im Assigner lieber nachfragen.
        from .assigner import CONFLICT
        eigene = beste.get(kat, 0.0)
        gegen = max((v for k, v in beste.items() if k != kat), default=0.0)
        conf = min(p, CONFLICT) if gegen >= AEHNLICH and gegen > eigene else p
    return Vorab(kurz_analyse(f.path, text, kat), Status.INDEXED, None, vec,
                 kategorie=kat, confidence=round(conf, 4), quelle="nummer", kurz=True)


# --------------------------------------------------------------------------- #
#  Sparmodus: BeeNara statt der Heuristik
# --------------------------------------------------------------------------- #
def spar_mit_beenara(bee, client, f, vorab: Vorab, *, kategorien: list[str], gedaechtnis,
                     sprache: str = "de") -> Vorab:
    """Im Sparmodus entscheidet BeeNara die Kategorie der heuristischen Analyse neu.

    Titel, Zusammenfassung und Stichworte bleiben die der Heuristik (Sparmodus heißt: keine
    KI-Texte). Unverändert zurück kommt ``vorab``, wenn eine gelernte Wachstafel-Regel trifft
    (sie schlägt hier wie bisher alles), wenn es keinen lokalen Text gibt oder wenn BeeNara
    nicht trägt. Das Gedächtnis darf widersprechen — so wirken Korrekturen des Nutzers weiter.
    """
    from .extractor import gedaechtnis_text, volltext
    from .llm.client import _apply_wachstafel
    from .models import embedding_text_for

    try:
        text = volltext(f.path, f.mime_type)
    except Exception:
        text = None
    if not text:
        return vorab
    regeln = getattr(client, "_rules", None) or []
    # Wie der OfflineClient: Dateiname und Text zusammen gegen die Regeln.
    if regeln and _apply_wachstafel(f"{f.path.stem} {text}".lower(), regeln) is not None:
        return vorab
    vec = client.embed(gedaechtnis_text(client, f.path, embedding_text_for(vorab.analysis)))
    wahl = beenara_waehlen(bee, text.strip(), kategorien, gedaechtnis.beste_je_kategorie(vec),
                           sprache=sprache)
    if wahl is None:
        return vorab
    kat, conf = wahl
    analysis = vorab.analysis.model_copy(
        update={"kategorie": kat, "funktion_aufgabe": "" if kat == "_unassigned" else kat})
    # vec=None: Der Eintragstext enthält die Aufgabe, und die ist jetzt eine andere —
    # ingest bettet ihn deshalb neu ein (offline kostet das nichts).
    return replace(vorab, analysis=analysis, kategorie=kat, confidence=conf, quelle="beenara",
                   vec=None)

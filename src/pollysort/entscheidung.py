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

#: BeeNara v0.2 ist auf 3 bis 9 Ordner trainiert und kalibriert. Darüber braucht es die
#: Shortlist aus v0.3, darunter trägt die Kalibrierung nicht — dann der bisherige Weg.
BEENARA_MIN, BEENARA_MAX = 3, 9
#: So viel Text bekommt BeeNara; es kürzt selbst auf seine ~300 Dokument-Tokens.
BEENARA_ZEICHEN = 3000


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


def beenara_passt(kategorien: list[str]) -> bool:
    """Liegt die Ordnerzahl im Bereich, auf den BeeNara trainiert und kalibriert ist?"""
    return BEENARA_MIN <= len(ordner_namen(kategorien)) <= BEENARA_MAX


def ordner_namen(kategorien: list[str]) -> list[str]:
    """Die Kategorien, die als Ordner zur Wahl stehen (ohne ``_unassigned``)."""
    return [c for c in kategorien if c and c.strip().lower() != "_unassigned"]


def beenara_waehlen(bee, text: str, kategorien: list[str], beste: dict[str, float], *,
                    sprache: str = "de") -> tuple[str, float] | None:
    """Stufe B mit BeeNara: ``(kategorie, konfidenz)`` oder ``None`` (trägt hier nicht).

    * sicher (Vorhersagemenge = genau ein Ordner) → dieser Ordner mit seiner kalibrierten
      Wahrscheinlichkeit; widerspricht das Gedächtnis deutlich, gedeckelt wie im Assigner.
    * „keiner passt" vorn → ``_unassigned`` mit 0 → Rückfrage.
    * unsicher zwischen Ordnern → Favorit als Vorschlag, gedeckelt → Rückfrage.

    ``bee.decide`` darf ``None`` liefern (ausgefallen, siehe pipeline); dann ``None``.
    """
    from .assigner import CONFLICT
    from .beenara_laufzeit import NONE

    namen = ordner_namen(kategorien)
    if not beenara_passt(namen) or not (text or "").strip():
        return None
    d = bee.decide(text[:BEENARA_ZEICHEN], namen, language=sprache)
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


class Schnappschuss:
    """Feste Kopie des Gedächtnisses für die parallelen Worker des Ultra Swarm.

    SQLite-Verbindungen dürfen nicht zwischen Threads wandern; die Worker lesen deshalb
    aus dieser Kopie. Was während des Laufs neu gelernt wird, sehen sie nicht — das kostet
    höchstens einen KI-Aufruf mehr, nie eine falsche Zuordnung.
    """

    def __init__(self, eintraege):
        self._eintraege = list(eintraege)
        self._anzahl = Counter(kat for _b, kat, _v in self._eintraege)

    def beste_je_kategorie(self, vec: list[float]) -> dict[str, float]:
        return beste_je_kategorie(vec, self._eintraege)

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

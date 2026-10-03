"""Die Browser-Konsole — derselbe Ausgabe-Layer wie im Terminal, nur als Ereignisstrom.

Der Kern (Pipeline, Schwarm, Sweep …) spricht ausschließlich über ``BeeConsole`` mit dem
Menschen. Diese Unterklasse druckt nichts: Jede Meldung wird ein kleines Ereignis
(Art, Emoji, Text), das an die Abonnenten des ``Ereignisbus`` geht. Die Oberfläche zeigt
daraus das Bienen-Protokoll, den Fortschritt und die Hinweise. So braucht der Kern für
das Flugbrett keine einzige Sonderzeile.

Die Farb-Semantik bleibt dieselbe (§12): ``honey`` = Erfolg, ``bloom`` = in Arbeit,
``ask`` = Rückfrage, ``error`` = Fehler, ``info`` = leise Notiz.
"""

from __future__ import annotations

import io
import itertools
import queue
import threading
from collections import deque
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime

from rich.console import Console
from rich.errors import MarkupError
from rich.markup import render as render_markup
from rich.text import Text

from ..console import BeeConsole


def klartext(nachricht) -> str:
    """Rich-Markup (``[honey]s[/honey]``) und Renderables zu reinem Text machen."""
    if isinstance(nachricht, str):
        try:
            return render_markup(nachricht).plain
        except MarkupError:
            return nachricht
    if isinstance(nachricht, Text):
        return nachricht.plain
    puffer = io.StringIO()
    Console(file=puffer, width=100, color_system=None, highlight=False).print(nachricht)
    return puffer.getvalue().rstrip()


class Ereignisbus:
    """Verteilt Ereignisse an alle offenen Browser-Tabs und merkt sich die letzten.

    Jeder Tab bekommt eine eigene Warteschlange. Läuft eine voll (Tab eingeschlafen),
    wird das Ereignis für diesen Tab verworfen — ein hängender Tab darf nie einen
    Sortierlauf ausbremsen.
    """

    def __init__(self, *, gedaechtnis: int = 200):
        self._abos: list[queue.Queue] = []
        self._letzte: deque[dict] = deque(maxlen=gedaechtnis)
        self._zaehler = itertools.count(1)
        self._lock = threading.Lock()

    def senden(self, ereignis: dict) -> dict:
        ereignis = {"nr": next(self._zaehler),
                    "zeit": datetime.now().strftime("%H:%M:%S"), **ereignis}
        with self._lock:
            self._letzte.append(ereignis)
            abos = list(self._abos)
        for q in abos:
            try:
                q.put_nowait(ereignis)
            except queue.Full:
                pass
        return ereignis

    def abonnieren(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=500)
        with self._lock:
            self._abos.append(q)
        return q

    def abbestellen(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._abos:
                self._abos.remove(q)

    def letzte(self) -> list[dict]:
        with self._lock:
            return list(self._letzte)

    def abonnenten(self) -> int:
        """Wie viele Fenster/Tabs hören gerade zu? (Die App beendet sich, wenn keins mehr da ist.)"""
        with self._lock:
            return len(self._abos)


class WebKonsole(BeeConsole):
    """``BeeConsole`` ohne Terminal: Jede Ausgabe wird ein Ereignis statt einer Zeile."""

    def __init__(self, senke: Callable[[dict], object] | None = None):
        # quiet → die Basisklasse schreibt keine Terminal-Farbsequenzen (OSC) ins Fenster,
        # aus dem der Server gestartet wurde. Alle Ausgabe-Methoden sind unten ersetzt.
        super().__init__(quiet=True, plain=True)
        self._senke = senke
        self._lokal = threading.local()

    # -- Sammeln: was hat eine Aktion gemeldet? -----------------------------
    @contextmanager
    def sammeln(self):
        """Alle Meldungen dieses Threads mitschreiben (für die Antwort einer Aktion)."""
        vorher = getattr(self._lokal, "liste", None)
        liste: list[dict] = []
        self._lokal.liste = liste
        try:
            yield liste
        finally:
            self._lokal.liste = vorher

    def _melden(self, art: str, text: str, emoji: str = "") -> None:
        ereignis = {"art": art, "emoji": emoji, "text": text}
        liste = getattr(self._lokal, "liste", None)
        if liste is not None:
            liste.append(ereignis)
        if self._senke is not None:
            try:
                self._senke(ereignis)
            except Exception:
                pass      # eine Anzeige darf nie einen Lauf abbrechen (§16)

    # -- Ersetzte Ausgabe-Methoden -----------------------------------------
    def say(self, emoji: str, msg: str, style: str = "") -> None:
        self._melden(style or "info", klartext(msg), emoji)

    def honey(self, msg: str, emoji: str = "🍯") -> None:
        self._melden("honey", klartext(msg), emoji)

    def bloom(self, msg: str, emoji: str = "🌸") -> None:
        self._melden("bloom", klartext(msg), emoji)

    def ask(self, msg: str, emoji: str = "❓") -> None:
        self._melden("ask", klartext(msg), emoji)

    def error(self, msg: str, emoji: str = "⚠️") -> None:
        self._melden("error", klartext(msg), emoji)

    def info(self, msg: str, emoji: str = "🐝") -> None:
        self._melden("info", klartext(msg), emoji)

    def rule(self, title: str = "") -> None:
        if title:
            self._melden("rule", klartext(title))

    def raw(self, *args, **_kwargs) -> None:
        text = " ".join(klartext(a) for a in args).strip()
        if text:
            self._melden("raw", text)

    def celebrate(self, msg: str) -> None:
        self._melden("feier", klartext(msg), "🎉")

    def header(self, status: str, title: str = "🐝 PollySort") -> None:
        pass

    def clear(self) -> None:
        pass

    def apply_terminal_colors(self) -> None:
        pass

    def reset_terminal_colors(self) -> None:
        pass

    @contextmanager
    def progress(self, description: str = "🐝 verarbeite …", *, transfer: bool = False):
        # transfer=True: Bytes statt Schritte (BeeNara-Download) — die Seite zeigt dann MB.
        yield _WebFortschritt(self, einheit="bytes" if transfer else None)


class _WebFortschritt:
    """Fortschritt als Ereignisse: dieselbe Schnittstelle wie ``rich.progress.Progress``."""

    def __init__(self, konsole: WebKonsole, *, einheit: str | None = None):
        self._k = konsole
        self._einheit = einheit
        self._aufgaben: dict[int, dict] = {}
        self._nr = itertools.count(1)

    def _senden(self, tid: int) -> None:
        a = self._aufgaben[tid]
        if self._einheit == "bytes":
            # Ein Download kommt in 1-MB-Stücken — ein Ereignis je Prozent reicht, sonst
            # verdrängen ein paar hundert Fortschritte das Protokoll (der Bus merkt sich 200).
            prozent = int(100 * a["erledigt"] / a["gesamt"]) if a["gesamt"] else 0
            if prozent == a.get("gemeldet") and a["erledigt"] < a["gesamt"]:
                return
            a["gemeldet"] = prozent
        if self._k._senke is not None:
            ereignis = {"art": "fortschritt", "erledigt": a["erledigt"],
                        "gesamt": a["gesamt"], "text": a["text"]}
            if self._einheit:
                ereignis["einheit"] = self._einheit
            try:
                self._k._senke(ereignis)
            except Exception:
                pass

    def add_task(self, description: str = "", total: float | None = None, **_k) -> int:
        tid = next(self._nr)
        self._aufgaben[tid] = {"erledigt": 0, "gesamt": int(total or 0),
                               "text": klartext(description)}
        self._senden(tid)
        return tid

    def advance(self, tid: int, advance: float = 1, **_k) -> None:
        if tid in self._aufgaben:
            self._aufgaben[tid]["erledigt"] += int(advance)
            self._senden(tid)

    def update(self, tid: int, *, description: str | None = None, total: float | None = None,
               advance: float | None = None, completed: float | None = None, **_k) -> None:
        a = self._aufgaben.get(tid)
        if a is None:
            return
        if description is not None:
            a["text"] = klartext(description)
        if total is not None:
            a["gesamt"] = int(total)
        if completed is not None:
            a["erledigt"] = int(completed)
        if advance:
            a["erledigt"] += int(advance)
        self._senden(tid)

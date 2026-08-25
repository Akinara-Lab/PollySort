"""Bienen-Konsole: Emoji-Statusmeldungen & rich-Grundausstattung (§12, §20).

Zentraler Ausgabe-Layer. Alle Animationen/Emojis sind über die Flags
``--quiet``/``--plain``/``--no-emoji`` abschaltbar, damit Logs und CI sauber bleiben.
"""

from __future__ import annotations

import datetime
from contextlib import contextmanager

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text
from rich.theme import Theme

# Farb-Semantik (§12): Honiggelb=Erfolg, Blütenrosa=in Arbeit, Orange=Rückfrage, Rot=Fehler.
# Zwei Paletten — je eine für dunklen und hellen Terminal-Hintergrund. Der Nutzer wählt die
# passende via 'thema dunkel|hell'; die Vordergrundfarben sind jeweils auf Lesbarkeit getrimmt,
# und die Kopfzeile (Frame) bekommt einen sichtbar unterschiedlichen Hintergrund-Ton.
# Zwei Modi: der GANZE Terminal-Hintergrund wird schwarz (dark) bzw. weiß (light);
# der Text bleibt in beiden gelb (nur die Helligkeit des Golds ist auf Lesbarkeit getrimmt),
# die Emojis bleiben unverändert. ``term_bg``/``term_fg`` werden per OSC-Sequenz an das
# Terminal geschickt und färben so das komplette Fenster (nicht nur die Fläche hinter dem Text).
PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "honey": "gold1", "bloom": "hot_pink", "ask": "dark_orange",
        "err": "red", "muted": "grey58", "base_fg": "gold1",
        "term_bg": "#000000", "term_fg": "#ffd700",
    },
    "light": {
        "honey": "gold1", "bloom": "hot_pink", "ask": "dark_orange",
        "err": "red", "muted": "grey35", "base_fg": "gold1",
        "term_bg": "#ffffff", "term_fg": "#ffd700",
    },
}


def _make_theme(p: dict[str, str]) -> Theme:
    return Theme({k: p[k] for k in ("honey", "bloom", "ask", "err", "muted")})


def _osc(code: int, color: str) -> str:
    """OSC-Sequenz zum Setzen der Terminal-Standardfarbe (10=Vordergrund, 11=Hintergrund)."""
    return f"\033]{code};{color}\a"


# Automatik-Thema: tagsüber dunkel, abends/nachts hell (wie gewünscht).
AUTO_DAY_START = 7        # ab 07:00 gilt „tagsüber" → dark
AUTO_DAY_END = 19         # ab 19:00 gilt „abends"   → light


def auto_theme(now: datetime.datetime | None = None) -> str:
    """Konkretes Thema nach Tageszeit: 07–19 Uhr dunkel, sonst hell."""
    hour = (now or datetime.datetime.now()).hour
    return "dark" if AUTO_DAY_START <= hour < AUTO_DAY_END else "light"


def resolve_theme(pref: str, now: datetime.datetime | None = None) -> str:
    """Nutzer-Voreinstellung (dark|light|auto) → konkretes Thema (dark|light)."""
    if pref == "auto":
        return auto_theme(now)
    return pref if pref in PALETTES else "dark"


class BeeConsole:
    """Gekapselte rich-Konsole mit abschaltbaren Bienen-Verzierungen + Dark/Light-Thema."""

    def __init__(self, *, quiet: bool = False, plain: bool = False, no_emoji: bool = False,
                 theme: str = "dark"):
        self.quiet = quiet
        self.plain = plain
        self.no_emoji = no_emoji or plain
        self.theme_name = theme if theme in PALETTES else "dark"
        self._palette = PALETTES[self.theme_name]
        self._c = self._build_console()
        self.apply_terminal_colors()

    def _build_console(self) -> Console:
        # base_fg → aller Fließtext ist gelb (Emojis behalten ihre eigenen Farben).
        return Console(theme=_make_theme(self._palette), highlight=False, soft_wrap=False,
                       style=self._palette["base_fg"])

    # -- Dark/Light: den GANZEN Terminal-Hintergrund einfärben --------------
    def apply_terminal_colors(self) -> None:
        """Terminal-Vorder-/Hintergrund per OSC setzen — färbt das komplette Fenster."""
        if self.quiet or not self._c.is_terminal:
            return
        p = self._palette
        self._c.file.write(_osc(11, p["term_bg"]) + _osc(10, p["term_fg"]))
        self._c.file.flush()

    def reset_terminal_colors(self) -> None:
        """Beim Verlassen die Standardfarben des Terminals wiederherstellen."""
        if not self._c.is_terminal:
            return
        self._c.file.write("\033]110\a\033]111\a")   # 110=Vordergrund, 111=Hintergrund zurück
        self._c.file.flush()

    def set_theme(self, name: str) -> str:
        """Dark/Light live umschalten. Gibt den effektiv gesetzten Namen zurück."""
        self.theme_name = name if name in PALETTES else self.theme_name
        self._palette = PALETTES[self.theme_name]
        self._c = self._build_console()
        self.apply_terminal_colors()
        return self.theme_name

    # -- Statische Ansicht (kein Log-Scrolling) -----------------------------
    def clear(self) -> None:
        if self.quiet or not self._c.is_terminal:
            return
        # 3J löscht den Scrollback, 2J den Schirm, H setzt den Cursor nach oben →
        # wirklich statisch, kein Zurückscrollen. Danach den Hintergrund neu absichern.
        self._c.file.write("\033[3J\033[2J\033[H")
        self._c.file.flush()
        self.apply_terminal_colors()

    def header(self, status: str, title: str = "🐝 PollySort") -> None:
        """Persistente Kopfzeile der statischen Ansicht (gelber Titel + Trennlinie)."""
        if self.quiet:
            return
        head = Text(title, style="bold honey")
        if status:
            head.append(f"   {status}", style="muted")
        self._c.print(head)
        self._c.rule(style="honey")

    # -- Basis --------------------------------------------------------------
    def _fmt(self, emoji: str, msg: str) -> str:
        return msg if self.no_emoji else f"{emoji}  {msg}"

    def _safe_print(self, *args, **kwargs) -> None:
        """Eine Konsolen-Ausgabe darf NIE einen Lauf abbrechen (§16).

        Auf Windows-Pipes/cp1252-Streams können Emojis einen UnicodeEncodeError
        auslösen — der riss vorher den ganzen Sortier-Zyklus mit (QA-Befund R4b).
        Degradiert dann zu ASCII; schlägt auch das fehl, wird die Ausgabe verworfen.
        """
        try:
            self._c.print(*args, **kwargs)
        except UnicodeEncodeError:
            try:
                cleaned = [a.encode("ascii", "replace").decode() if isinstance(a, str) else a
                           for a in args]
                self._c.print(*cleaned, **kwargs)
            except Exception:
                pass
        except Exception:
            pass

    def say(self, emoji: str, msg: str, style: str = "") -> None:
        if self.quiet:
            return
        text = self._fmt(emoji, msg)
        self._safe_print(text, style=style or None)

    # -- semantische Kurzformen --------------------------------------------
    def honey(self, msg: str, emoji: str = "🍯") -> None:
        self.say(emoji, msg, "honey")

    def bloom(self, msg: str, emoji: str = "🌸") -> None:
        self.say(emoji, msg, "bloom")

    def ask(self, msg: str, emoji: str = "❓") -> None:
        self.say(emoji, msg, "ask")

    def error(self, msg: str, emoji: str = "⚠️") -> None:
        # Fehler immer zeigen, auch im quiet-Modus.
        self._safe_print(self._fmt(emoji, msg), style="err")

    def info(self, msg: str, emoji: str = "🐝") -> None:
        self.say(emoji, msg, "muted")

    def rule(self, title: str = "") -> None:
        if not self.quiet:
            self._c.rule(title, style="muted")

    def raw(self, *args, **kwargs) -> None:
        self._safe_print(*args, **kwargs)

    def celebrate(self, msg: str) -> None:
        """Konfetti-Moment nach sauberem Zyklus (§12) — abschaltbar via quiet/plain/no-emoji."""
        if self.quiet:
            return
        if self.no_emoji:
            self._c.print(msg, style="honey")
            return
        self._c.print("   ✨ 🍯 🐝  ✨   🐝 🍯 ✨", style="honey")
        self._c.print(f"🎉  {msg}", style="honey")

    @property
    def rich(self) -> Console:
        return self._c

    # -- Fortschritt (§12) --------------------------------------------------
    @contextmanager
    def progress(self, description: str = "🐝 verarbeite …"):
        """Fortschrittsbalken mit Bienen-Skin; im quiet/plain-Modus ein No-Op."""
        if self.quiet or self.plain:
            yield _NullProgress()
            return
        cols = [
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[bloom]{task.description}"),
            BarColumn(complete_style="honey", finished_style="honey"),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
        ]
        with Progress(*cols, console=self._c, transient=False) as p:
            yield p


class _NullProgress:
    """Stiller Ersatz für den Fortschrittsbalken (quiet/plain/CI)."""

    def add_task(self, *_a, **_k) -> int:
        return 0

    def advance(self, *_a, **_k) -> None:
        pass

    def update(self, *_a, **_k) -> None:
        pass

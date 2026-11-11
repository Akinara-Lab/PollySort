"""Wächterbienen (Communication Agents, §v0.3) — überwachen Eingang UND Deadlines und melden.

Erweitert die bisherige „Wache" um Termin-Wachdienst mit **echten** Benachrichtigungen:
Bei fälligen Deadlines fliegen die Wächterbienen über die konfigurierten Flugrouten aus
(Discord/E-Mail). Ohne konfigurierte Flugrouten melden sie nur hier (Journal + Konsole).

``gemeldet`` heißt: **wirklich verschickt**. Ansehen oder ein Lauf ohne Flugrouten setzt den
Merker nicht — sonst bliebe ein Termin stumm, sobald später Flugrouten eingerichtet werden.

🔒 Wachssiegel: Der Melde-Weg ist vollständig von der LLM-Generierung getrennt. Ins Journal
(``log.jsonl``) gehen nur Metadaten (Kanal-Name, Erfolg, Termin-ID) — nie Credentials.
"""

from __future__ import annotations

import json
import time

from .. import i18n
from .kalender import Kalender, Termin

#: Die Wache prüft alle paar Sekunden. Was sie dabei schon hier angezeigt hat, merkt sich der
#: Prozess — sonst stünde dieselbe Deadline bei jedem Takt neu in Konsole und Protokoll.
_LOKAL_GEZEIGT: set[tuple[str, str]] = set()
#: Wann die Wache zuletzt einen Versand versucht hat. Scheitert er (Netz weg, Token falsch),
#: probiert sie es erst nach ``VERSUCH_PAUSE`` wieder statt bei jedem Takt.
_LETZTER_VERSUCH: dict[tuple[str, str], float] = {}
VERSUCH_PAUSE = 15 * 60

#: Marke in ``.honig/``: der einmalige Abgleich alter ``gemeldet``-Merker ist gelaufen.
ABGLEICH_MARKE = "kalender.gemeldet-v2"


class Waechterbiene:
    def __init__(self, ctx, *, flugrouten=None, kanaele=None):
        self.ctx = ctx
        self.kalender = Kalender(ctx.hive)
        if flugrouten is None:
            from ..flugrouten import load_flugrouten
            flugrouten = load_flugrouten()
        self.flugrouten = flugrouten
        if kanaele is None:
            from .kanaele import build_kanaele
            kanaele = build_kanaele(flugrouten)
        self.kanaele = kanaele
        self.send_real = bool(kanaele)

    # -- Deadlines -----------------------------------------------------------
    def deadlines_pruefen(self, *, innerhalb_tage: int = 7, senden: bool | None = None,
                          nur_neue: bool = True) -> list[Termin]:
        """Fällige/überfällige Deadlines finden und melden.

        ``senden=None`` → automatisch (die Wache): verschickt, wenn Flugrouten da sind, sonst
        zeigt sie jede Deadline einmal je Programmlauf hier an. ``senden=True`` → ausdrücklich
        verschicken (``kalender melden``). ``senden=False`` → nur anzeigen. ``nur_neue``
        verhindert Doppel-Versand über das ``gemeldet``-Flag.
        """
        automatisch = senden is None
        senden = self.send_real if automatisch else senden
        self._altlast_abgleichen()
        due = self.kalender.faellig(innerhalb_tage=innerhalb_tage)
        for t in due:
            schluessel = (str(self.kalender.path), t.id)
            if senden and self.kanaele:
                if nur_neue and t.gemeldet:
                    continue
                if automatisch and self._kuerzlich_versucht(schluessel):
                    continue
                _LETZTER_VERSUCH[schluessel] = time.monotonic()
                self._melden(t, senden=True)
            else:
                if automatisch:
                    if schluessel in _LOKAL_GEZEIGT:
                        continue
                    _LOKAL_GEZEIGT.add(schluessel)
                self._melden(t, senden=False)
        return due

    @staticmethod
    def _kuerzlich_versucht(schluessel: tuple[str, str]) -> bool:
        zuletzt = _LETZTER_VERSUCH.get(schluessel)
        return zuletzt is not None and time.monotonic() - zuletzt < VERSUCH_PAUSE

    def _altlast_abgleichen(self) -> None:
        """Einmal je Projekt: ``gemeldet`` nur behalten, wo das Journal einen Versand belegt.

        Ältere Versionen setzten den Merker schon beim bloßen Ansehen (``kalender``) und in der
        Wache ohne Flugrouten. Solche Termine wären nach dem Einrichten der Flugrouten für immer
        stumm geblieben. Jeder echte Versand steht als ``waechter_versand`` im Journal — was dort
        fehlt, wurde nie verschickt und darf wieder gemeldet werden.
        """
        marke = self.kalender.path.with_name(ABGLEICH_MARKE)
        if marke.exists():
            return
        try:
            belegt: set[str] = set()
            log = getattr(getattr(self.ctx, "journal", None), "log", None)
            if log is not None and log.exists():
                with log.open(encoding="utf-8") as fh:
                    for zeile in fh:
                        if '"waechter_versand"' not in zeile:
                            continue
                        try:
                            rec = json.loads(zeile)
                        except json.JSONDecodeError:
                            continue
                        if rec.get("event") == "waechter_versand" and rec.get("erfolg") is True:
                            belegt.add(str(rec.get("termin")))
            self.kalender.gemeldet_abgleichen(belegt)
            marke.write_text("gemeldet = wirklich verschickt (Abgleich mit log.jsonl erledigt)\n",
                             encoding="utf-8")
        except OSError:
            pass          # der Abgleich darf die Wache nie stören; beim nächsten Mal erneut

    def _melden(self, t: Termin, *, senden: bool) -> None:
        tage = t.tage_bis()
        con = getattr(self.ctx, "console", None)
        if con is not None:
            # Früher: „'Miete' ist 3 Tag(e) überfällig fällig" — zwei Sätze, zwei Schlüssel.
            key = "wb.due" if tage >= 0 else "wb.overdue"
            con.ask(i18n.t(key, title=t.titel, n=abs(tage), date=t.faellig), "🔔")
        # Journal: NUR Metadaten (keine Credentials).
        self.ctx.journal.event("waechter_reminder", termin=t.id, projekt=t.projekt,
                               faellig=t.faellig, tage=tage,
                               kanaele=[k.name for k in self.kanaele])
        if senden and self.kanaele:
            self._ausfliegen(t)

    def _ausfliegen(self, t: Termin) -> None:
        """Über alle Flugrouten echt versenden — mit bienenthematischer Quittung."""
        con = getattr(self.ctx, "console", None)
        tage = t.tage_bis()
        wann = i18n.t("wb.when_overdue") if tage < 0 else i18n.t("wb.when_in", n=tage)
        titel = f"Deadline: {t.titel}"
        text = i18n.t("wb.mail", date=t.faellig, when=wann)
        from .kanaele import KanalAbgelehnt

        # Je Flugroute merken, wer die Deadline schon hat: Scheitert eine (Mailserver weg),
        # bekommt beim nächsten Versuch nur sie die Nachricht — nicht alle anderen noch einmal.
        an, abgelehnt = self.kalender.zustellung(t.id)
        alle = set()
        for nr, k in enumerate(self.kanaele):
            kennung = getattr(k, "schluessel", None) or f"{k.name}#{nr}"
            alle.add(kennung)
            if kennung in an:
                continue
            try:
                k.senden(titel, text)
                an.add(kennung)
                abgelehnt.discard(kennung)
                if con is not None:
                    stock = getattr(k, "STOCK", f"{k.name}-Wabe")
                    con.honey(i18n.t("r.routes.test_ok", target=stock), "🐝")
                self.ctx.journal.event("waechter_versand", kanal=k.name, termin=t.id, erfolg=True)
            except Exception as exc:      # KanalError o. ä. — Text enthält bewusst kein Secret
                if isinstance(exc, KanalAbgelehnt):
                    abgelehnt.add(kennung)
                if con is not None:
                    con.error(i18n.t("wb.back", name=k.name, err=exc))
                self.ctx.journal.event("waechter_versand", kanal=k.name, termin=t.id, erfolg=False)
        try:
            self.kalender.zustellung_merken(t.id, an, abgelehnt)
        except OSError:
            pass
        # Gemeldet ist die Deadline, wenn jede Flugroute sie hat oder dauerhaft ablehnt — und
        # mindestens eine sie wirklich bekommen hat. Bis dahin probiert die Wache es weiter.
        if alle <= an | abgelehnt and alle & an:
            self.kalender.markiere_gemeldet(t.id)

    # -- Testflug ------------------------------------------------------------
    def flugtest(self) -> list[str]:
        """Testnachricht über alle aktiven Flugrouten schicken. Gibt die erfolgreichen zurück."""
        con = getattr(self.ctx, "console", None)
        ok: list[str] = []
        for k in self.kanaele:
            try:
                k.senden(i18n.t("wb.test_title"), i18n.t("wb.test_text"))
                ok.append(k.name)
                if con is not None:
                    stock = getattr(k, "STOCK", f"{k.name}-Wabe")
                    con.honey(i18n.t("r.routes.test_ok", target=stock), "🐝")
            except Exception as exc:
                if con is not None:
                    con.error(i18n.t("r.routes.blocked", name=k.name, err=exc))
        return ok

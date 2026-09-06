"""Wächterbienen (Communication Agents, §v0.3) — überwachen Eingang UND Deadlines und melden.

Erweitert die bisherige „Wache" um Termin-Wachdienst mit **echten** Benachrichtigungen:
Bei fälligen Deadlines fliegen die Wächterbienen über die konfigurierten Flugrouten aus
(Discord/E-Mail). Ohne konfigurierte Flugrouten bleibt es beim gemockten Melden (Journal +
Konsole).

🔒 Wachssiegel: Der Melde-Weg ist vollständig von der LLM-Generierung getrennt. Ins Journal
(``log.jsonl``) gehen nur Metadaten (Kanal-Name, Erfolg, Termin-ID) — nie Credentials.
"""

from __future__ import annotations

from .kalender import Kalender, Termin


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

        ``senden=None`` → automatisch (echte Kanäle, wenn konfiguriert). ``nur_neue``
        verhindert Doppel-Versand über das ``gemeldet``-Flag.
        """
        senden = self.send_real if senden is None else senden
        due = self.kalender.faellig(innerhalb_tage=innerhalb_tage)
        for t in due:
            if nur_neue and senden and t.gemeldet:
                continue
            self._melden(t, senden=senden)
        return due

    def _melden(self, t: Termin, *, senden: bool) -> None:
        tage = t.tage_bis()
        wann = f"in {tage} Tag(en)" if tage >= 0 else f"{-tage} Tag(e) überfällig"
        con = getattr(self.ctx, "console", None)
        if con is not None:
            con.ask(f"Wächterbienen summen: '{t.titel}' ist {wann} fällig ({t.faellig}).", "🔔")
        # Journal: NUR Metadaten (keine Credentials).
        self.ctx.journal.event("waechter_reminder", termin=t.id, projekt=t.projekt,
                               faellig=t.faellig, tage=tage,
                               kanaele=[k.name for k in self.kanaele])
        if senden and self.kanaele:
            self._ausfliegen(t)
        else:
            self.kalender.markiere_gemeldet(t.id)   # gemockt: als gemeldet vermerken

    def _ausfliegen(self, t: Termin) -> None:
        """Über alle Flugrouten echt versenden — mit bienenthematischer Quittung."""
        con = getattr(self.ctx, "console", None)
        tage = t.tage_bis()
        wann = "überfällig" if tage < 0 else f"in {tage} Tagen"
        titel = f"Deadline: {t.titel}"
        text = f"Fällig am {t.faellig} ({wann})."
        erfolg_gesamt = True
        for k in self.kanaele:
            try:
                k.senden(titel, text)
                if con is not None:
                    stock = getattr(k, "STOCK", f"{k.name}-Wabe")
                    con.honey(f"Wächterbienen haben die {stock} erfolgreich informiert!", "🐝")
                self.ctx.journal.event("waechter_versand", kanal=k.name, termin=t.id, erfolg=True)
            except Exception as exc:      # KanalError o. ä. — Text enthält bewusst kein Secret
                erfolg_gesamt = False
                if con is not None:
                    con.error(f"Wächterbiene kehrt vom {k.name}-Flug zurück: {exc}")
                self.ctx.journal.event("waechter_versand", kanal=k.name, termin=t.id, erfolg=False)
        if erfolg_gesamt:
            self.kalender.markiere_gemeldet(t.id)   # erst nach Erfolg → kein Doppel-Versand

    # -- Testflug ------------------------------------------------------------
    def flugtest(self) -> list[str]:
        """Testnachricht über alle aktiven Flugrouten schicken. Gibt die erfolgreichen zurück."""
        con = getattr(self.ctx, "console", None)
        ok: list[str] = []
        for k in self.kanaele:
            try:
                k.senden("Bienentanz-Testflug",
                         "🐝 Hallo vom Bienenstock! Diese Flugroute steht bereit.")
                ok.append(k.name)
                if con is not None:
                    stock = getattr(k, "STOCK", f"{k.name}-Wabe")
                    con.honey(f"Wächterbienen haben die {stock} erfolgreich informiert!", "🐝")
            except Exception as exc:
                if con is not None:
                    con.error(f"Flugroute {k.name} blockiert: {exc}")
        return ok

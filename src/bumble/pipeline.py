"""Flugzyklus — Pollenflug → Einlagerung → Zuordnung (§9).

Ein einheitlicher Zyklus für beide Modi (index/move):
  Scout → Guard → Extractor → Embed → Assigner → Inspector → Store → (Move) → Hive Mind.
Jede Larve ist isoliert: ein Fehler pro Datei bricht den Lauf nie ab (§16).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import mover
from .assigner import assign
from .config import AppConfig, HiveSeed
from .console import BeeConsole
from .extractor import extract
from .feedback import Feedback
from .guards import IgnoreMatcher, has_landed, within_size_limit
from .hive_mind import HiveMind, Taxonomy
from .inspector import decide
from .journal import Journal
from .models import BeeEntry, Status
from .movelog import MoveLog
from .scout import scout, walk
from .store import Store


@dataclass
class CycleSummary:
    stored: int = 0
    assigned: int = 0
    duplicates: int = 0
    needs_review: int = 0
    errors: int = 0
    skipped: int = 0
    moved: int = 0
    recovered: int = 0
    llm_calls: int = 0
    est_cost_eur: float = 0.0
    new_ids: list[str] = field(default_factory=list)
    by_category: dict[str, int] = field(default_factory=dict)

    def exit_code(self) -> int:
        # §19: 0 ok · 2 offene Rückfragen · 3 Fehler-Einträge
        if self.errors:
            return 3
        if self.needs_review:
            return 2
        return 0


def bee_id(content_hash: str) -> str:
    return content_hash.split(":")[-1][:8]


@dataclass
class Context:
    """Alles, was ein Zyklus zum Arbeiten braucht — einmal aufgebaut, wiederverwendbar."""

    hive: Path
    cfg: AppConfig
    seed: HiveSeed
    client: object
    console: BeeConsole
    journal: Journal
    store: Store
    mind: HiveMind
    taxonomy: Taxonomy
    feedback: Feedback
    movelog: MoveLog

    @classmethod
    def build(cls, *, hive, cfg, seed, client, console, journal) -> Context:
        return cls(
            hive=hive, cfg=cfg, seed=seed, client=client, console=console, journal=journal,
            store=Store(hive), mind=HiveMind(hive),
            taxonomy=Taxonomy.bootstrap(hive, seed), feedback=Feedback(hive),
            movelog=MoveLog(hive),
        )


def run_cycle(
    ctx: Context,
    *,
    mode: str = "move",
    roots: list[Path] | None = None,
    recursive: bool | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    cache: dict | None = None,
    workers: int = 1,
) -> CycleSummary:
    """Ein Lauf über den Posteingang (Default: lose Dateien im Arbeitsverzeichnis).

    Ohne ``roots`` werden die losen Dateien direkt im Stock-Root verarbeitet (nicht rekursiv);
    schon einsortierte Kategorie-Ordner bleiben unangetastet. Zeigt ``roots`` auf einen
    fremden Ordner (Import), wird dieser rekursiv eingelesen.

    ``cache`` (optional, dict): Analyse-Zwischenspeicher für den Vorschau→Anwenden-Flow.
    Ein Dry-run FÜLLT ihn (Analyse + Embedding je content_hash); ein anschließender echter
    Lauf mit demselben dict NUTZT ihn wieder → keine zweiten KI-Calls beim „Anwenden".

    ``workers`` > 1 aktiviert den **Ultra Swarm**: die teuren KI-Analysen (extract+embed)
    laufen parallel in einem Worker-Pool und WÄRMEN den Cache vor; das eigentliche
    Einlagern (DB, Move, Gedächtnis) bleibt danach **einthreadig** — so gibt es keine
    SQLite-/Ordner-/MoveLog-Races. Effekt: viele Dateien deutlich schneller, gleiches Ergebnis.
    """
    con = ctx.console
    matcher = IgnoreMatcher(ctx.hive, extra=ctx.seed.exclude)
    if roots is None:
        roots = [ctx.hive]
        recursive = False if recursive is None else recursive
    else:
        recursive = True if recursive is None else recursive

    findings = scout(walk(roots, matcher, recursive=recursive))
    if limit:
        findings = findings[:limit]

    if not findings:
        con.info("Keine neuen Dateien zu sortieren. Alles aufgeräumt. ✨", "🐝")
        return CycleSummary()

    con.info(f"{len(findings)} Datei(en) gefunden — verarbeite …", "🔍")
    # F1: Hat sich das Embedding-Modell geändert (nur per Config-Datei möglich), matchen die
    # alten Vektoren nicht mehr — einmal je Lauf freundlich darauf hinweisen (kein KI-Call).
    if not dry_run:
        drift = ctx.mind.mismatch(getattr(ctx.client, "embed_model", None))
        if drift:
            con.info(f"Das Embedding-Modell hat sich geändert (Gedächtnis: {drift}). Alte "
                     "Vektoren matchen nicht mehr zuverlässig — 'gedaechtnis neu' baut das "
                     "Gedächtnis mit dem aktuellen Modell neu auf.", "⚠️")
    # Ultra Swarm: KI-Analysen parallel vorbereiten (füllt den Cache), Rest bleibt sequenziell.
    if workers and workers > 1 and not dry_run:
        cache = cache if cache is not None else {}
        n = _prewarm_parallel(ctx, findings, workers, cache)
        if n:
            con.honey(f"Ultra Swarm: {n} Dokument(e) parallel mit {workers} Bienen "
                      "vorbereitet — lagere jetzt ein …", "⚡")
    summary = CycleSummary()
    prior_calls = 0            # KI-Calls vor einem etwaigen Offline-Wechsel (Kostenanzeige)
    fail_streak = 0            # aufeinanderfolgende Fehl-Dateien (KI wohl nicht erreichbar)
    switched = False
    with con.progress("sortiere") as prog:
        task = prog.add_task("sortiere", total=len(findings))
        for f in findings:
            prog.update(task, description=f"🌸 {f.path.name}")
            errs_before = summary.errors
            try:
                _process_one(ctx, f, mode=mode, dry_run=dry_run, summary=summary, cache=cache)
            except Exception as exc:  # letzte Sicherheitsnetz-Isolation (§16)
                summary.errors += 1
                con.error(f"{f.path.name}: unerwarteter Fehler — {exc}")
            fail_streak = fail_streak + 1 if summary.errors > errs_before else 0
            # Reißt die KI mitten im Lauf wiederholt ab, den REST heuristisch sortieren,
            # statt reihenweise Fehler-Einträge zu produzieren (Offline-Fallback, §16).
            if not switched and fail_streak >= _LLM_FAIL_THRESHOLD and not dry_run:
                prior_calls, switched = _fallback_offline(ctx)
            prog.advance(task)

    summary.llm_calls = prior_calls + ctx.client.usage.calls
    summary.est_cost_eur = ctx.client.usage.est_cost_eur()
    _finish(ctx, summary, mode, dry_run=dry_run)
    return summary


def reindex_memory(ctx: Context) -> tuple[int, int]:
    """Das Gedächtnis mit dem AKTUELLEN Embedding-Modell neu aufbauen (F1-Remedy).

    Bettet alle einsortierten Einträge aus ihrem GESPEICHERTEN Text neu ein (keine
    Neu-Analyse, nur Embedding-Calls), verwirft vorher die alten (fremd-dimensionalen)
    Vektoren. Robust: ein Fehler pro Eintrag bricht den Lauf nie ab. Gibt ``(ok, fehler)``.
    """
    from .store import row_to_entry

    model = getattr(ctx.client, "embed_model", None)
    rows = ctx.store.query(status=Status.ASSIGNED.value)
    ctx.mind.reset()                       # Alt-Vektoren verwerfen — sonst bleibt totes Gewicht
    ok = fail = 0
    con = ctx.console
    with con.progress("gedaechtnis neu") as prog:
        task = prog.add_task("reindex", total=len(rows))
        for row in rows:
            entry = row_to_entry(row)
            prog.update(task, description=f"🧠 {entry.id}")
            try:
                vec = ctx.client.embed(entry.embedding_text())
                ctx.mind.remember(entry.id, entry.kategorie, vec, model)
                ok += 1
            except Exception as exc:       # KI-Schluckauf → überspringen, nicht abbrechen (§16)
                fail += 1
                con.error(f"Reindex übersprungen ({entry.id}): {exc}")
            prog.advance(task)
    return ok, fail


_LLM_FAIL_THRESHOLD = 3    # so viele Fehler in Folge → auf Offline-Heuristik umschalten
_SWARM_CAP = 20            # Obergrenze für parallele Worker (schont Provider/Rate-Limits)


def _prewarm_parallel(ctx: Context, findings, workers: int, cache: dict) -> int:
    """Ultra Swarm: die teuren KI-Analysen parallel berechnen und in den Cache legen.

    Nur genuin NEUE Dateien werden vorbereitet (Dedup-/Landing-Check als DB-Read vorab,
    einthreadig). Pro Datei: extract + (bei Erfolg) embed — beides über den LLM-Client,
    der je Aufruf einen eigenen HTTP-Request macht. DB, Move und Gedächtnis fasst DIESE
    Funktion NICHT an; das passiert danach sequenziell → keine Nebenläufigkeits-Races.
    """
    from concurrent.futures import ThreadPoolExecutor

    todo = []
    for f in findings:
        if not has_landed(f.path, quick=True):
            continue
        existing = ctx.store.by_hash(f.content_hash)
        if existing and existing.get("status") != Status.ERROR.value:
            continue                      # Dublette/bekannt → kein KI-Call nötig
        if f.content_hash in cache:
            continue                      # schon vorgewärmt (z. B. aus einer Vorschau)
        todo.append(f)
    if not todo:
        return 0

    def prepare(f):
        try:
            analysis, ext_status, reason = extract(f, ctx.client, max_file_mb=ctx.seed.max_file_mb)
            vec = None
            if ext_status == Status.INDEXED:
                entry = BeeEntry.from_analysis(
                    id=bee_id(f.content_hash), path=str(f.path), original_path=str(f.path),
                    filename=f.path.name, mime_type=f.mime_type, size_bytes=f.size_bytes,
                    content_hash=f.content_hash, analysis=analysis)
                vec = ctx.client.embed(entry.embedding_text())
            return f.content_hash, {"analysis": analysis, "ext_status": ext_status,
                                    "reason": reason, "vec": vec}
        except Exception:
            return None                   # Cache-Miss → sequenzieller Pfad rechnet/meldet normal

    n = max(1, min(int(workers), _SWARM_CAP, len(todo)))
    done = 0
    with ThreadPoolExecutor(max_workers=n) as pool:
        for res in pool.map(prepare, todo):
            if res is not None:
                cache[res[0]] = res[1]
                done += 1
    return done


def _fallback_offline(ctx: Context) -> tuple[int, bool]:
    """Den Rest des Laufs mit der Offline-Heuristik sortieren. Gibt (bisherige_calls, True).

    Kein Umschalten, wenn ohnehin schon offline gearbeitet wird (dann bleibt es beim
    heutigen Verhalten: Fehler zählen, nächster Lauf versucht es erneut — BUG-5).
    """
    from .llm.client import OfflineClient
    if isinstance(ctx.client, OfflineClient):
        return 0, True
    from .wachstafel import Wachstafel
    prior = ctx.client.usage.calls
    ctx.client = OfflineClient(ctx.seed.categories, wachstafel=Wachstafel(ctx.hive).text())
    ctx.console.info("KI wiederholt nicht erreichbar — der Rest des Laufs läuft über die "
                     "Offline-Heuristik (kostenlos, kein Absturz).", "🛟")
    return prior, True


def _process_one(ctx: Context, f, *, mode: str, dry_run: bool, summary: CycleSummary,
                 cache: dict | None = None) -> None:
    con = ctx.console
    store = ctx.store
    if not has_landed(f.path, quick=True):
        summary.skipped += 1
        return

    # Dedupe / Recovery gegen die DB (§9/§16)
    existing = store.by_hash(f.content_hash)
    if existing:
        # Fehler-Einträge (z. B. KI-Ausfall) blockieren die Datei NICHT dauerhaft:
        # beim nächsten Lauf wird die Analyse erneut versucht statt still übersprungen.
        if existing.get("status") == Status.ERROR.value:
            con.info(f"Neuer Anlauf (war Fehler): {f.path.name}", "🔁")
            ingest(ctx, f, mode=mode, dry_run=dry_run, summary=summary, cache=cache)
            return
        known_paths = {existing["path"], existing.get("original_path")}
        if str(f.path) in known_paths:
            # Bekannter Pfad → nichts zu tun.
            if not Path(existing["path"]).exists() and Path(f.path).exists():
                store.update_path(existing["id"], str(f.path))  # Recovery
                summary.recovered += 1
            else:
                summary.skipped += 1
        elif not Path(existing["path"]).exists():
            # Gleicher Inhalt, alter Pfad weg → verschoben/umbenannt: nur Pfad nachziehen.
            store.update_path(existing["id"], str(f.path))
            summary.recovered += 1
            con.info(f"Pfad repariert: {f.path.name} (kein LLM-Call)", "🔀")
        else:
            store.add_duplicate_path(existing["id"], str(f.path))
            summary.duplicates += 1
            con.info(f"Dublette: {f.path.name} (kein neuer Eintrag, kein LLM-Call)", "🛡️")
        return

    if not within_size_limit(f.path, ctx.seed.max_file_mb):
        con.ask(f"{f.path.name} > {ctx.seed.max_file_mb} MB → Metadaten-Eintrag")

    ingest(ctx, f, mode=mode, dry_run=dry_run, summary=summary, cache=cache)


def ingest(ctx: Context, f, *, mode: str, dry_run: bool, summary: CycleSummary,
           supersedes: str | None = None, cache: dict | None = None) -> BeeEntry:
    """Eine genuin neue (oder geänderte) Datei voll verarbeiten (§9). Von Zyklus & Sweep genutzt."""
    con, store = ctx.console, ctx.store
    # Analyse + Embedding aus dem Vorschau-Cache wiederverwenden (kein zweiter KI-Call
    # beim „Anwenden"). Sonst frisch berechnen und — falls ein Cache mitläuft — ablegen.
    cached = cache.get(f.content_hash) if cache is not None else None
    if cached is not None:
        analysis, ext_status, reason, vec = (
            cached["analysis"], cached["ext_status"], cached["reason"], cached["vec"])
    else:
        analysis, ext_status, reason = extract(f, ctx.client, max_file_mb=ctx.seed.max_file_mb)
        vec = None
    entry = BeeEntry.from_analysis(
        id=bee_id(f.content_hash), path=str(f.path), original_path=str(f.path),
        filename=f.path.name, mime_type=f.mime_type, size_bytes=f.size_bytes,
        content_hash=f.content_hash, analysis=analysis,
    )
    entry.error_reason = reason
    entry.supersedes = supersedes

    if ext_status == Status.INDEXED:
        if vec is None:
            vec = ctx.client.embed(entry.embedding_text())
        a = assign(embedding=vec, llm_kategorie=analysis.kategorie,
                   hive=ctx.mind, taxonomy=ctx.taxonomy)
        entry.funktion.kategorie = a.kategorie
        entry.confidence = a.confidence
        entry.zustaendigkeit = a.zustaendigkeit
        entry.status = decide(confidence=a.confidence, threshold=ctx.seed.threshold_assign,
                              mode=mode, extractor_status=ext_status)
    else:
        entry.status = ext_status
        entry.zustaendigkeit = ctx.taxonomy.persons_for(entry.funktion.kategorie)

    # Frisch berechnete Analyse für einen späteren „Anwenden"-Lauf zwischenspeichern
    # (nur wenn ein Cache mitläuft und der Wert noch nicht daher kam).
    if cache is not None and cached is None:
        cache[f.content_hash] = {"analysis": analysis, "ext_status": ext_status,
                                 "reason": reason, "vec": vec}

    # Dry-run (vorschau) ist bewusst NEBENWIRKUNGSFREI: kein DB-Eintrag, kein Move, kein
    # Gedächtnis. Sonst würde die Vorschau die Datei als 'assigned' registrieren und ein
    # späterer echter Lauf sie über die Hash-Dedupe stillschweigend überspringen.
    if not dry_run:
        store.save(entry)  # persist ZUERST (Crash-Recovery, §9)

    # -- Move: NUR sicher zugeordnete Dateien wandern in ihren Kategorie-Ordner.
    # Unsichere (needs_review) und Fehlerfälle bleiben liegen — so sind die einzigen
    # losen Dateien im Root genau die, die noch deine Aufmerksamkeit brauchen.
    if mode == "move" and entry.status == Status.ASSIGNED:
        dest = mover.move(ctx.hive, entry, dry_run=dry_run,
                          subrouting=getattr(ctx.seed, "subrouting", None))
        if dry_run:
            con.info(f"[dry-run] {f.path.name} → {dest.relative_to(ctx.hive)}", "🧪")
        else:
            src_before = f.path
            store.update_path(entry.id, str(dest))
            entry.path = str(dest)
            store.save(entry)  # Pfad-Update + Re-Export (§9)
            ctx.movelog.record(bee_id=entry.id, src=str(src_before), dst=str(dest))
            summary.moved += 1

    # -- Gedächtnis (§14): jedes erfolgreich analysierte Dokument mit eindeutigem Label
    # merken — auch wenn die Confidence noch unter der Schwelle liegt. So bootstrappt der
    # Stock aus dem Kaltstart heraus; falsche Frühlabels korrigiert 'bumble assign' (§24).
    if not dry_run and vec is not None and entry.funktion.kategorie != "_unassigned":
        ctx.mind.remember(entry.id, entry.funktion.kategorie, vec,
                          getattr(ctx.client, "embed_model", None))

    _tally(con, entry, reason, summary)
    return entry


def _tally(con: BeeConsole, entry: BeeEntry, reason, summary: CycleSummary) -> None:
    from .config import pretty_category
    if entry.status in (Status.ASSIGNED, Status.INDEXED):
        summary.stored += 1
        summary.assigned += 1 if entry.status == Status.ASSIGNED else 0
        summary.new_ids.append(entry.id)
        folder = pretty_category(entry.funktion.kategorie)
        summary.by_category[folder] = summary.by_category.get(folder, 0) + 1
    elif entry.status == Status.NEEDS_REVIEW:
        summary.needs_review += 1
    else:
        summary.errors += 1
        con.error(f"{entry.filename}: {reason}")


def _finish(ctx: Context, s: CycleSummary, mode: str, *, dry_run: bool = False) -> None:
    con = ctx.console
    con.rule("Vorschau" if dry_run else "Fertig")
    # Aufschlüsselung nach Kategorie — das Herzstück des Feedbacks.
    if s.by_category:
        parts = ", ".join(f"{n} → {cat}" for cat, n in sorted(s.by_category.items(),
                                                              key=lambda x: -x[1]))
        if dry_run:
            con.honey(f"[Vorschau] {s.stored} Datei(en) würden einsortiert: {parts}", "🧪")
        else:
            con.honey(f"{s.stored} Datei(en) sortiert: {parts}", "🍯")
    if s.duplicates:
        con.info(f"{s.duplicates} Dublette(n) erkannt (nicht doppelt abgelegt) — "
                 f"'dubletten aufraeumen' legt sie in die Quarantäne", "🛡️")
    if s.recovered:
        con.info(f"{s.recovered} Pfad(e) nachgezogen", "🔀")
    if s.errors:
        con.error(f"{s.errors} Datei(en) mit Fehler — 'liste error' zeigt sie")
    if s.needs_review:
        con.ask(f"{s.needs_review} Datei(en) unsicher — liegen noch hier. "
                f"Mit 'rueckfragen' schnell zuordnen.")
    if s.llm_calls:
        con.info(f"{s.llm_calls} KI-Anfragen · ~{s.est_cost_eur:.4f} €", "🧠")
    if dry_run:
        # Vorschau ist nebenwirkungsfrei: keine Konfetti-Meldung, kein Journal-Eintrag.
        con.info("Vorschau — es wurde nichts verschoben oder gespeichert.", "🧪")
        return
    if not s.needs_review and not s.errors and s.stored:
        con.celebrate("Sauber sortiert — nichts bleibt liegen!")
    ctx.journal.entry(f"{mode}-Lauf", [
        f"eingelagert: {s.stored}", f"verschoben: {s.moved}", f"dubletten: {s.duplicates}",
        f"needs_review: {s.needs_review}", f"fehler: {s.errors}",
        f"llm_calls: {s.llm_calls}", f"kosten_eur: ~{s.est_cost_eur:.4f}",
    ])
    ctx.journal.event(f"{mode}_cycle", stored=s.stored, moved=s.moved,
                      duplicates=s.duplicates, needs_review=s.needs_review,
                      errors=s.errors, llm_calls=s.llm_calls, est_cost_eur=s.est_cost_eur)

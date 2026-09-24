"""Flugzyklus — Pollenflug → Einlagerung → Zuordnung (§9).

Ein einheitlicher Zyklus für beide Modi (index/move):
  Scout → Guard → Extractor → Embed → Assigner → Inspector → Store → (Move) → Hive Mind.
Jede Larve ist isoliert: ein Fehler pro Datei bricht den Lauf nie ab (§16).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import entscheidung, i18n, mover, nacherfassung
from .assigner import assign
from .config import AppConfig, HiveSeed
from .console import BeeConsole
from .extractor import extract, gedaechtnis_text
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
    #: Wer entschieden hat: gedaechtnis · nummer · analyse (Plan §8.3).
    quellen: dict[str, int] = field(default_factory=dict)

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
    #: Passt das Gedächtnis zum aktuellen Embedding-Modell und seiner Textbasis? ``None`` =
    #: noch nicht geprüft (siehe :func:`_memory_ok`).
    memory_ok: bool | None = None

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
        con.info(i18n.t("pl.nothing"), "🐝")
        return CycleSummary()

    con.info(i18n.t("pl.found", n=len(findings)), "🔍")
    # F1: Hat sich das Embedding-Modell geändert (nur per Config-Datei möglich), matchen die
    # alten Vektoren nicht mehr — einmal je Lauf freundlich darauf hinweisen (kein KI-Call).
    if not dry_run:
        current = getattr(ctx.client, "embed_model", None)
        drift = ctx.mind.mismatch(current)
        if drift and current and drift.split("#")[0] == current.split("#")[0]:
            # Gleiches Modell, neue Textbasis (Update vom 2026-09-24) — anders erklären.
            con.info(i18n.t("pl.drift_basis"), "⚠️")
        elif drift:
            con.info(i18n.t("pl.drift", drift=drift), "⚠️")
    # Ultra Swarm: KI-Analysen parallel vorbereiten (füllt den Cache), Rest bleibt sequenziell.
    if workers and workers > 1 and not dry_run:
        cache = cache if cache is not None else {}
        n = _prewarm_parallel(ctx, findings, workers, cache)
        if n:
            con.honey(i18n.t("pl.turbo", n=n, workers=workers), "⚡")
    summary = CycleSummary()
    prior_calls = 0            # KI-Calls vor einem etwaigen Offline-Wechsel (Kostenanzeige)
    fail_streak = 0            # aufeinanderfolgende Fehl-Dateien (KI wohl nicht erreichbar)
    switched = False
    with con.progress(i18n.t("pl.progress.sort")) as prog:
        task = prog.add_task(i18n.t("pl.progress.sort"), total=len(findings))
        for f in findings:
            prog.update(task, description=f"🌸 {f.path.name}")
            errs_before = summary.errors
            try:
                _process_one(ctx, f, mode=mode, dry_run=dry_run, summary=summary, cache=cache)
            except Exception as exc:  # letzte Sicherheitsnetz-Isolation (§16)
                summary.errors += 1
                con.error(i18n.t("pl.unexpected", name=f.path.name, err=exc))
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
    with con.progress(i18n.t("pl.progress.reindex")) as prog:
        task = prog.add_task("reindex", total=len(rows))
        for row in rows:
            entry = row_to_entry(row)
            prog.update(task, description=f"🧠 {entry.id}")
            try:
                vec = ctx.client.embed(gedaechtnis_text(ctx.client, entry.path,
                                                        entry.embedding_text()))
                ctx.mind.remember(entry.id, entry.kategorie, vec, model)
                ok += 1
            except Exception as exc:       # KI-Schluckauf → überspringen, nicht abbrechen (§16)
                fail += 1
                con.error(i18n.t("pl.reindex_skip", id=entry.id, err=exc))
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

    # Die Worker lesen das Gedächtnis aus einer festen Kopie: SQLite-Verbindungen dürfen
    # nicht zwischen Threads wandern.
    schnappschuss = _gedaechtnis_sicht(ctx) if entscheidung.unterstuetzt(ctx.client) else None

    def prepare(f):
        try:
            return f.content_hash, _analysieren(ctx, f, gedaechtnis=schnappschuss).als_cache()
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
    ctx.memory_ok = None                  # anderes Embedding → Gedächtnis neu bewerten
    ctx.console.info(i18n.t("pl.fallback"), "🛟")
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
            con.info(i18n.t("pl.retry", name=f.path.name), "🔁")
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
            con.info(i18n.t("pl.path_fixed", name=f.path.name), "🔀")
        else:
            store.add_duplicate_path(existing["id"], str(f.path))
            summary.duplicates += 1
            con.info(i18n.t("pl.duplicate", name=f.path.name), "🛡️")
        return

    if not within_size_limit(f.path, ctx.seed.max_file_mb):
        con.ask(i18n.t("pl.too_big", name=f.path.name, mb=ctx.seed.max_file_mb))

    ingest(ctx, f, mode=mode, dry_run=dry_run, summary=summary, cache=cache)


def ingest(ctx: Context, f, *, mode: str, dry_run: bool, summary: CycleSummary,
           supersedes: str | None = None, cache: dict | None = None) -> BeeEntry:
    """Eine genuin neue (oder geänderte) Datei voll verarbeiten (§9). Von Zyklus & Sweep genutzt."""
    con, store = ctx.console, ctx.store
    # Analyse + Embedding aus dem Vorschau-Cache wiederverwenden (kein zweiter KI-Call
    # beim „Anwenden"). Sonst frisch berechnen und — falls ein Cache mitläuft — ablegen.
    cached = cache.get(f.content_hash) if cache is not None else None
    if cached is not None:
        vorab = entscheidung.Vorab.aus_cache(cached)
    else:
        vorab = _analysieren(ctx, f)
    analysis, ext_status, reason, vec = vorab.analysis, vorab.ext_status, vorab.reason, vorab.vec
    entry = BeeEntry.from_analysis(
        id=bee_id(f.content_hash), path=str(f.path), original_path=str(f.path),
        filename=f.path.name, mime_type=f.mime_type, size_bytes=f.size_bytes,
        content_hash=f.content_hash, analysis=analysis,
    )
    entry.error_reason = reason
    entry.supersedes = supersedes

    if ext_status == Status.INDEXED and vorab.kategorie is not None:
        # Stufe A oder B hat entschieden (Plan §8.3) — kein Assigner, keine volle Analyse.
        if vec is None:
            vec = ctx.client.embed(gedaechtnis_text(ctx.client, f.path, entry.embedding_text()))
        entry.funktion.kategorie = vorab.kategorie
        entry.confidence = vorab.confidence or 0.0
        entry.zustaendigkeit = ctx.taxonomy.persons_for(vorab.kategorie)
        entry.status = decide(confidence=entry.confidence, threshold=ctx.seed.threshold_assign,
                              mode=mode, extractor_status=ext_status)
        summary.quellen[vorab.quelle] = summary.quellen.get(vorab.quelle, 0) + 1
    elif ext_status == Status.INDEXED:
        if vec is None:
            vec = ctx.client.embed(gedaechtnis_text(ctx.client, f.path, entry.embedding_text()))
        a = assign(embedding=vec, llm_kategorie=analysis.kategorie,
                   hive=ctx.mind, taxonomy=ctx.taxonomy,
                   analysis_text=entry.embedding_text(), use_memory=_memory_ok(ctx))
        summary.quellen["analyse"] = summary.quellen.get("analyse", 0) + 1
        if a.quelle == "zweitmeinung":
            # Sichtbar machen, dass hier nicht das Modell entschieden hat, sondern die
            # Heuristik auf dessen eigener Zusammenfassung — Vertrauen braucht
            # Nachvollziehbarkeit, auch im Journal.
            from .config import pretty_category
            con.info(i18n.t("pl.second_opinion", name=f.path.name,
                            label=analysis.kategorie or "—",
                            cat=pretty_category(a.kategorie)), "🔎")
            if not dry_run:
                ctx.journal.event("zweitmeinung", file=f.path.name,
                                  label=analysis.kategorie, kategorie=a.kategorie)
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
        cache[f.content_hash] = vorab.mit_vec(vec).als_cache()

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
            con.info(i18n.t("pl.dry_move", name=f.path.name,
                              dest=dest.relative_to(ctx.hive)), "🧪")
        else:
            src_before = f.path
            store.update_path(entry.id, str(dest))
            entry.path = str(dest)
            store.save(entry)  # Pfad-Update + Re-Export (§9)
            ctx.movelog.record(bee_id=entry.id, src=str(src_before), dst=str(dest))
            summary.moved += 1

    # -- Gedächtnis (§14): jedes erfolgreich analysierte Dokument mit eindeutigem Label
    # merken — auch wenn die Confidence noch unter der Schwelle liegt. So bootstrappt der
    # Stock aus dem Kaltstart heraus; falsche Frühlabels korrigiert 'pollysort assign' (§24).
    if not dry_run and vec is not None and entry.funktion.kategorie != "_unassigned":
        ctx.mind.remember(entry.id, entry.funktion.kategorie, vec,
                          getattr(ctx.client, "embed_model", None))
        ctx.memory_ok = None              # erster Eintrag kann den Zustand ändern

    # Nur heuristisch erfasst → die KI verfeinert Titel/Zusammenfassung später.
    if not dry_run and vorab.kurz and entry.status.value in nacherfassung.ZUSTAENDE:
        nacherfassung.vormerken(ctx.hive, [entry.id])

    _tally(con, entry, reason, summary)
    return entry


def _memory_ok(ctx: Context) -> bool:
    """Darf das Gedächtnis mitentscheiden? Nein, wenn es aus einem anderen Embedding-Modell
    oder einer anderen Textbasis stammt (F1) — einmal geprüft, dann gemerkt."""
    if ctx.memory_ok is None:
        ctx.memory_ok = not ctx.mind.mismatch(getattr(ctx.client, "embed_model", None))
    return ctx.memory_ok


def _gedaechtnis_sicht(ctx: Context) -> entscheidung.Schnappschuss:
    """Das Gedächtnis, wie Stufe A es sehen darf: nur Vektoren des aktuellen Modells samt
    Textbasis. Ein Altbestand aus einem anderen Modell (vor 'gedaechtnis neu') bleibt so
    außen vor, statt Ähnlichkeiten zwischen zwei Vektorräumen vorzutäuschen."""
    return entscheidung.Schnappschuss(
        ctx.mind.eintraege(getattr(ctx.client, "embed_model", None)))


def _analysieren(ctx: Context, f, *, gedaechtnis=None) -> entscheidung.Vorab:
    """Dreistufig, wo der Client es kann (Ollama); sonst die volle Analyse wie bisher."""
    vorab = None
    if entscheidung.unterstuetzt(ctx.client):
        vorab = entscheidung.analysieren(
            ctx.client, f, max_file_mb=ctx.seed.max_file_mb, kategorien=ctx.taxonomy.categories,
            gedaechtnis=gedaechtnis or _gedaechtnis_sicht(ctx), memory_ok=True)
    if vorab is None:
        analysis, ext_status, reason = extract(f, ctx.client, max_file_mb=ctx.seed.max_file_mb)
        vorab = entscheidung.Vorab(analysis, ext_status, reason, None)
    return vorab


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
        con.error(i18n.t("pl.entry_error", name=entry.filename, reason=reason))


def _finish(ctx: Context, s: CycleSummary, mode: str, *, dry_run: bool = False) -> None:
    con = ctx.console
    con.rule(i18n.t("pl.rule.preview") if dry_run else i18n.t("pl.rule.done"))
    # Aufschlüsselung nach Kategorie — das Herzstück des Feedbacks.
    if s.by_category:
        parts = ", ".join(f"{n} → {cat}" for cat, n in sorted(s.by_category.items(),
                                                              key=lambda x: -x[1]))
        if dry_run:
            con.honey(i18n.t("pl.preview_sorted", n=s.stored, parts=parts), "🧪")
        else:
            con.honey(i18n.t("pl.sorted", n=s.stored, parts=parts), "🍯")
    if s.duplicates:
        con.info(i18n.t("pl.duplicates", n=s.duplicates), "🛡️")
    if s.recovered:
        con.info(i18n.t("pl.recovered", n=s.recovered), "🔀")
    if s.errors:
        con.error(i18n.t("pl.errors", n=s.errors))
    if s.needs_review:
        con.ask(i18n.t("pl.review", n=s.needs_review))
    if s.quellen.get("gedaechtnis") or s.quellen.get("nummer"):
        con.info(i18n.t("pl.quellen", mem=s.quellen.get("gedaechtnis", 0),
                        num=s.quellen.get("nummer", 0), voll=s.quellen.get("analyse", 0)), "⚡")
    if s.llm_calls:
        # Ehrlich bleiben: Offline gibt es gar keine KI-Anfragen, und lokale Inferenz
        # (Ollama) kostet nichts. Ein „~0.0006 €" für einen Lauf auf dem eigenen
        # Rechner ist schlicht erfunden — und Vertrauen ist hier die ganze Währung.
        provider = getattr(ctx.cfg, "llm_provider", "")
        if provider == "offline":
            con.info(i18n.t("pl.calls_offline", n=s.llm_calls), "🧠")
        elif provider == "ollama":
            con.info(i18n.t("pl.calls_local", n=s.llm_calls), "🧠")
        else:
            con.info(i18n.t("pl.calls_online", n=s.llm_calls,
                            cost=f"{s.est_cost_eur:.4f}"), "🧠")
    if dry_run:
        # Vorschau ist nebenwirkungsfrei: keine Konfetti-Meldung, kein Journal-Eintrag.
        con.info(i18n.t("pl.preview_note"), "🧪")
        return
    if not s.needs_review and not s.errors and s.stored:
        con.celebrate(i18n.t("pl.celebrate"))
    ctx.journal.entry(f"{mode}-Lauf", [
        f"eingelagert: {s.stored}", f"verschoben: {s.moved}", f"dubletten: {s.duplicates}",
        f"needs_review: {s.needs_review}", f"fehler: {s.errors}",
        f"llm_calls: {s.llm_calls}", f"kosten_eur: ~{s.est_cost_eur:.4f}",
    ])
    ctx.journal.event(f"{mode}_cycle", stored=s.stored, moved=s.moved,
                      duplicates=s.duplicates, needs_review=s.needs_review,
                      errors=s.errors, llm_calls=s.llm_calls, est_cost_eur=s.est_cost_eur)
